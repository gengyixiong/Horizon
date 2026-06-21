from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from src.models import RSSSourceConfig
from src.scrapers.rss import RSSScraper


def test_rss_ids_are_deterministic() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-1</guid>
        <title>Item 1</title>
        <link>https://example.com/item-1</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description>Hello</description>
      </item>
    </channel></rss>
    """
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    first = asyncio.run(scraper.fetch(since))[0].id
    second = asyncio.run(scraper.fetch(since))[0].id

    assert first == second
    assert first == "rss:example.com_feed.xml:5e2d5d1e58e94d76"


def test_rss_keyword_filter_and_podcast_duration() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
      <channel><title>Podcast</title>
        <item>
          <guid>robot-episode</guid>
          <title>Humanoid robotics interview</title>
          <link>https://example.com/robot</link>
          <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
          <description>Whole-body control and locomotion.</description>
          <itunes:duration>01:15:30</itunes:duration>
        </item>
        <item>
          <guid>unrelated-episode</guid>
          <title>Cooking interview</title>
          <link>https://example.com/cooking</link>
          <pubDate>Fri, 24 Apr 2026 13:00:00 GMT</pubDate>
          <description>Recipes and kitchens.</description>
          <itunes:duration>45:00</itunes:duration>
        </item>
      </channel>
    </rss>
    """
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    source = RSSSourceConfig(
        name="Podcast",
        url="https://example.com/feed.xml",
        category="long-form",
        keywords=["humanoid", "robotics"],
    )
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    assert items[0].metadata["duration_minutes"] == 76
    assert items[0].metadata["summary_basis"] == "description"


def test_rss_episode_url_falls_back_to_audio_enclosure() -> None:
    entry = {
        "links": [
            {
                "rel": "enclosure",
                "href": "https://cdn.example.com/episode.mp3",
            }
        ]
    }

    assert RSSScraper._extract_entry_url(entry, "https://example.com/feed.xml") == (
        "https://cdn.example.com/episode.mp3"
    )
