from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import SourceType, YouTubeConfig
from src.scrapers.youtube import YouTubeScraper


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_youtube_fetch_filters_and_emits_popularity_metadata() -> None:
    published = datetime.now(timezone.utc) - timedelta(days=1)
    search_response = _response(
        {"items": [{"id": {"videoId": "video-1"}}]}
    )
    details_response = _response(
        {
            "items": [
                {
                    "id": "video-1",
                    "snippet": {
                        "title": "Humanoid Robotics Interview",
                        "description": "A deep discussion about bipedal locomotion.",
                        "channelTitle": "Robotics Lab",
                        "channelId": "channel-1",
                        "publishedAt": published.isoformat().replace("+00:00", "Z"),
                    },
                    "statistics": {
                        "viewCount": "12000",
                        "likeCount": "900",
                        "commentCount": "80",
                    },
                    "contentDetails": {"duration": "PT1H5M10S"},
                }
            ]
        }
    )
    client = AsyncMock()
    client.get.side_effect = [search_response, details_response]
    config = YouTubeConfig(
        enabled=True,
        queries=['"humanoid robot" interview'],
        min_views=1000,
        min_views_per_day=0,
    )

    with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"}):
        scraper = YouTubeScraper(config, client)
        scraper._fetch_transcript = AsyncMock(
            return_value="[0:00] A transcript sample about humanoid control."
        )
        items = asyncio.run(
            scraper.fetch(datetime.now(timezone.utc) - timedelta(hours=48))
        )

    assert len(items) == 1
    item = items[0]
    assert item.source_type == SourceType.YOUTUBE
    assert item.metadata["duration_minutes"] == 66
    assert item.metadata["views"] == 12000
    assert item.metadata["views_per_day"] > 0
    assert item.metadata["summary_basis"] == "transcript"
    assert "Transcript samples" in (item.content or "")
    for call in client.get.call_args_list:
        assert "key" not in call.kwargs["params"]


def test_youtube_duration_and_transcript_sampling() -> None:
    assert YouTubeScraper.parse_duration_minutes("PT45M1S") == 46
    assert YouTubeScraper.parse_duration_minutes("PT2H") == 120

    snippets = [
        {"text": f"segment {index} " * 25, "start": index * 60}
        for index in range(40)
    ]
    sample = YouTubeScraper.sample_transcript(snippets, max_chars=1200, windows=6)
    assert sample is not None
    assert "[0:00]" in sample
    assert "[39:00]" in sample
    assert len(sample) <= 1200
