"""Smoke-test the YouTube Data API key used by GitHub Actions.

This script deliberately performs one tiny long-video search matching the
planned humanoid-interview source. It prints only non-sensitive result metadata;
the API key is never logged. Keep this check in the workflow when the YouTube
source is enabled so expired, deleted, or incorrectly restricted keys fail fast.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.googleapis.com/youtube/v3/search"


def main() -> int:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY is missing from the workflow environment.", file=sys.stderr)
        return 1

    params = {
        "part": "snippet",
        "q": '"humanoid robot" interview',
        "type": "video",
        "videoDuration": "long",
        "order": "viewCount",
        "publishedAfter": (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat().replace("+00:00", "Z"),
        "maxResults": 1,
    }
    request = Request(
        f"{API_URL}?{urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Horizon/1.0",
            "X-Goog-Api-Key": api_key,
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        # Parse Google's JSON error without printing the request URL, which
        # contains the secret API key as a query parameter.
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            message = error_payload.get("error", {}).get("message", "unknown API error")
        except Exception:
            message = "unknown API error"
        print(f"YouTube Data API check failed (HTTP {exc.code}): {message}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", str(exc))
        print(f"YouTube Data API network check failed: {reason}", file=sys.stderr)
        return 1

    items = payload.get("items", [])
    if not items:
        print("YouTube Data API key works; the smoke-test query returned no videos.")
        return 0

    snippet = items[0].get("snippet", {})
    print("YouTube Data API key works.")
    print(f"Sample title: {snippet.get('title', 'unknown')}")
    print(f"Sample channel: {snippet.get('channelTitle', 'unknown')}")
    print(f"Sample published: {snippet.get('publishedAt', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
