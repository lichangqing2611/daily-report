import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse various RSS date formats."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    # feedparser may have already parsed it
    return None


class RSSFeed(SourcePlugin):
    @property
    def name(self) -> str:
        return "RSS Feeds"

    async def fetch(self) -> list[Article]:
        feeds = self._config.get("feeds", [])
        if not feeds:
            logger.warning("No RSS feeds configured")
            return []

        all_articles = []

        for feed_config in feeds:
            feed_name = feed_config.get("name", "Unknown")
            feed_url = feed_config.get("url", "")
            max_articles = feed_config.get("max_articles", 10)

            if not feed_url:
                logger.warning(f"RSS feed '{feed_name}' has no URL, skipping")
                continue

            try:
                feed = await self._parse_feed(feed_url)
                entries = feed.entries[:max_articles] if feed.entries else []

                for entry in entries:
                    title = entry.get("title", "No Title").strip()
                    link = entry.get("link", "")
                    description = entry.get("summary", entry.get("description", ""))
                    # Strip HTML tags from description
                    if description:
                        from html import unescape
                        import re
                        description = re.sub(r"<[^>]+>", "", description)
                        description = unescape(description).strip()
                    author = entry.get("author", "")
                    published = entry.get("published_parsed")
                    if published:
                        try:
                            published_at = datetime(*published[:6], tzinfo=timezone.utc)
                        except Exception:
                            published_at = None
                    else:
                        published_at = None

                    tags = []
                    if hasattr(entry, "tags") and entry.tags:
                        tags = [t.get("term", "") for t in entry.tags if t.get("term")]

                    content_hash = compute_content_hash(title, description)
                    all_articles.append(Article(
                        title=title,
                        url=link,
                        source_name=f"{self.name} - {feed_name}",
                        source_type="rss",
                        description=description[:500],
                        author=author or None,
                        published_at=published_at,
                        tags=tags,
                        content_hash=content_hash,
                        fetch_timestamp=datetime.now(),
                    ))

                logger.info(f"RSS '{feed_name}': fetched {len(entries)} articles")

            except Exception as e:
                logger.error(f"RSS feed '{feed_name}' ({feed_url}) failed: {e}")
                continue

        return all_articles

    async def _parse_feed(self, url: str) -> feedparser.FeedParserDict:
        """Fetch and parse an RSS/Atom feed."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            raise SourceError(f"Feed parse error: {feed.bozo_exception}")
        return feed

    async def validate(self) -> bool:
        feeds = self._config.get("feeds", [])
        if not feeds:
            return False
        first_url = feeds[0].get("url", "")
        if not first_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(first_url, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
