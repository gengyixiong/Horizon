"""YouTube Data API scraper for popular long-form robotics interviews."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

import httpx

from .base import BaseScraper
from ..models import ContentItem, SourceType, YouTubeConfig

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:  # Graceful local fallback; package is a project dependency.
    YouTubeTranscriptApi = None


logger = logging.getLogger(__name__)


class YouTubeScraper(BaseScraper):
    """Discover long videos, rank by view velocity, and sample captions.

    Search and statistics use the official YouTube Data API. Public captions
    are best-effort because YouTube may block transcript requests from cloud
    runner IPs. When captions are unavailable, Horizon explicitly summarizes
    only the video description instead of pretending it heard the interview.
    """

    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
    _DURATION_RE = re.compile(
        r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
    )

    def __init__(self, config: YouTubeConfig, http_client: httpx.AsyncClient):
        super().__init__({"youtube": config}, http_client)
        self.cfg = config
        self.api_key = os.getenv(config.api_key_env)

    def _headers(self) -> dict[str, str]:
        # Sending the key in a header keeps it out of exception URLs and logs.
        return {
            "Accept": "application/json",
            "User-Agent": "Horizon/1.0",
            "X-Goog-Api-Key": self.api_key or "",
        }

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.api_key:
            raise ValueError(
                f"Missing YouTube API key environment variable: {self.cfg.api_key_env}"
            )
        if not self.cfg.queries:
            return []

        # Long interviews are less frequent than news, so they use their own
        # lookback window even when the daily news window is only 48 hours.
        configured_since = datetime.now(timezone.utc) - timedelta(
            days=self.cfg.lookback_days
        )
        effective_since = min(since, configured_since)

        search_results = await asyncio.gather(
            *(self._search(query, effective_since) for query in self.cfg.queries)
        )

        matched_queries: Dict[str, Set[str]] = {}
        for query, video_ids in zip(self.cfg.queries, search_results):
            for video_id in video_ids:
                matched_queries.setdefault(video_id, set()).add(query)

        if not matched_queries:
            return []

        details = await self._fetch_video_details(list(matched_queries))
        candidates: List[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for video in details:
            parsed = self._parse_video(video, now)
            if not parsed or parsed["published_at"] < effective_since:
                continue
            if not (
                self.cfg.min_duration_minutes
                <= parsed["duration_minutes"]
                <= self.cfg.max_duration_minutes
            ):
                continue
            if (
                parsed["views"] < self.cfg.min_views
                and parsed["views_per_day"] < self.cfg.min_views_per_day
            ):
                continue
            parsed["matched_queries"] = sorted(
                matched_queries.get(parsed["video_id"], set())
            )
            candidates.append(parsed)

        # View velocity finds newly popular niche interviews; total views break
        # ties in favor of established high-signal conversations.
        candidates.sort(
            key=lambda item: (item["views_per_day"], item["views"]),
            reverse=True,
        )
        candidates = candidates[: self.cfg.max_candidates]

        transcript_semaphore = asyncio.Semaphore(3)

        async def fetch_transcript_bounded(video_id: str) -> Optional[str]:
            async with transcript_semaphore:
                return await self._fetch_transcript(video_id)

        transcript_tasks = [
            fetch_transcript_bounded(item["video_id"]) for item in candidates
        ]
        transcripts = await asyncio.gather(*transcript_tasks)

        items: List[ContentItem] = []
        for candidate, transcript in zip(candidates, transcripts):
            description = candidate["description"].strip()
            if transcript:
                content = (
                    "Transcript samples across the interview:\n"
                    f"{transcript}\n\n"
                    "Video description:\n"
                    f"{description[:1500]}"
                )
                summary_basis = "transcript"
            else:
                content = (
                    "Public transcript unavailable; summarize only the supplied "
                    "video description and do not invent claims from the interview.\n\n"
                    f"Video description:\n{description[:3500]}"
                )
                summary_basis = "description"

            items.append(
                ContentItem(
                    id=self._generate_id(
                        "youtube", "video", candidate["video_id"]
                    ),
                    source_type=SourceType.YOUTUBE,
                    title=candidate["title"],
                    url=f"https://www.youtube.com/watch?v={candidate['video_id']}",
                    content=content,
                    author=candidate["channel_title"],
                    published_at=candidate["published_at"],
                    metadata={
                        "category": self.cfg.category,
                        "video_id": candidate["video_id"],
                        "channel": candidate["channel_title"],
                        "channel_id": candidate["channel_id"],
                        "duration_minutes": candidate["duration_minutes"],
                        "views": candidate["views"],
                        "views_per_day": round(candidate["views_per_day"], 1),
                        "likes": candidate["likes"],
                        "comments": candidate["comments"],
                        "matched_queries": candidate["matched_queries"],
                        "transcript_available": bool(transcript),
                        "summary_basis": summary_basis,
                    },
                )
            )

        return items

    async def _search(self, query: str, since: datetime) -> List[str]:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "videoDuration": "long",
            "publishedAfter": self._format_rfc3339(since),
            "maxResults": self.cfg.max_results_per_query,
        }
        response = await self.client.get(
            self.SEARCH_URL,
            params=params,
            headers=self._headers(),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            item.get("id", {}).get("videoId")
            for item in payload.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

    async def _fetch_video_details(self, video_ids: List[str]) -> List[dict]:
        videos: List[dict] = []
        for start in range(0, len(video_ids), 50):
            batch = video_ids[start : start + 50]
            response = await self.client.get(
                self.VIDEOS_URL,
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(batch),
                },
                headers=self._headers(),
                follow_redirects=True,
            )
            response.raise_for_status()
            videos.extend(response.json().get("items", []))
        return videos

    def _parse_video(
        self, video: dict, now: datetime
    ) -> Optional[dict[str, Any]]:
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        details = video.get("contentDetails", {})
        try:
            published_at = datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            )
            duration_minutes = self.parse_duration_minutes(details["duration"])
        except (KeyError, TypeError, ValueError):
            return None

        views = self._safe_int(statistics.get("viewCount"))
        age_days = max((now - published_at).total_seconds() / 86400, 1 / 24)
        return {
            "video_id": video.get("id", ""),
            "title": snippet.get("title", "Untitled YouTube video"),
            "description": snippet.get("description", ""),
            "channel_title": snippet.get("channelTitle", "unknown"),
            "channel_id": snippet.get("channelId", ""),
            "published_at": published_at,
            "duration_minutes": duration_minutes,
            "views": views,
            "views_per_day": views / age_days,
            "likes": self._safe_int(statistics.get("likeCount")),
            "comments": self._safe_int(statistics.get("commentCount")),
        }

    async def _fetch_transcript(self, video_id: str) -> Optional[str]:
        if YouTubeTranscriptApi is None:
            return None
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_transcript_sync, video_id),
                timeout=20,
            )
            return self.sample_transcript(raw)
        except Exception as exc:
            # Cloud runner IPs are frequently blocked by YouTube's transcript
            # endpoint. This is expected and must not fail the whole digest.
            logger.info("Transcript unavailable for YouTube video %s: %s", video_id, exc)
            return None

    def _fetch_transcript_sync(self, video_id: str) -> List[dict]:
        transcript = YouTubeTranscriptApi().fetch(
            video_id,
            languages=self.cfg.transcript_languages,
        )
        return transcript.to_raw_data()

    @classmethod
    def sample_transcript(
        cls, snippets: Iterable[dict], max_chars: int = 3800, windows: int = 12
    ) -> Optional[str]:
        """Sample caption windows across the full runtime, not just the intro."""
        rows = [row for row in snippets if str(row.get("text", "")).strip()]
        if not rows:
            return None

        full = " ".join(str(row["text"]).strip() for row in rows)
        if len(full) <= max_chars:
            return full

        sample_parts: List[str] = []
        used_indices: Set[int] = set()
        # Reserve space for timestamps/newlines and truncate an individual
        # oversized caption row so the final time window is never cut off.
        per_window = max(80, max_chars // windows - 20)
        for position in range(windows):
            index = round(position * (len(rows) - 1) / max(windows - 1, 1))
            if index in used_indices:
                continue
            used_indices.add(index)
            start = float(rows[index].get("start", 0) or 0)
            chunk: List[str] = []
            size = 0
            for row in rows[index:]:
                text = str(row.get("text", "")).strip()
                if not text:
                    continue
                if not chunk and len(text) > per_window:
                    text = text[:per_window]
                if chunk and size + len(text) + 1 > per_window:
                    break
                chunk.append(text)
                size += len(text) + 1
            if chunk:
                sample_parts.append(
                    f"[{cls._format_timestamp(start)}] {' '.join(chunk)}"
                )
        return "\n".join(sample_parts)[:max_chars]

    @classmethod
    def parse_duration_minutes(cls, value: str) -> int:
        match = cls._DURATION_RE.fullmatch(value or "")
        if not match:
            raise ValueError(f"Invalid YouTube duration: {value}")
        seconds = (
            int(match.group("hours") or 0) * 3600
            + int(match.group("minutes") or 0) * 60
            + int(match.group("seconds") or 0)
        )
        return max(1, math.ceil(seconds / 60))

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _format_rfc3339(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
