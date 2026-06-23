import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.qbitai.com"


def _parse_qbitai_date(text: str) -> datetime | None:
    """Parse Chinese relative dates like '52分钟前', '17小时前', '昨天', '2天前'."""
    text = text.strip()
    now = datetime.now()

    m = re.match(r"(\d+)\s*分钟前", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    m = re.match(r"(\d+)\s*小时前", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    m = re.match(r"(\d+)\s*天前", text)
    if m:
        return now - timedelta(days=int(m.group(1)))

    if text == "昨天":
        return now - timedelta(days=1)

    if text == "前天":
        return now - timedelta(days=2)

    # "YYYY-MM-DD"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    return None


class QbitaiSource(SourcePlugin):
    """Scrape news from qbitai.com (量子位)."""

    @property
    def name(self) -> str:
        return "量子位"

    async def fetch(self) -> list[Article]:
        max_articles = self._config.get("max_articles", 20)
        articles: list[Article] = []

        try:
            async with httpx.AsyncClient(timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                resp.raise_for_status()
        except Exception as e:
            raise SourceError(f"Qbitai fetch failed: {e}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".article_list .picture_text")

        for item in items[:max_articles]:
            try:
                # Title and URL from h4 > a
                title_el = item.select_one("h4 a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                article_url = urljoin(BASE_URL, title_el.get("href", ""))
                if not title or not article_url:
                    continue

                # Description: text node between h4 and author link
                # We extract all text content and find description between title and author
                description = ""
                author_el = item.select_one("a[href*='?author=']")
                if author_el:
                    # Get the raw text of the container
                    full_text = item.get_text(" ", strip=True)
                    # Try to extract description between title and author
                    title_idx = full_text.find(title)
                    author_text = author_el.get_text(strip=True)
                    author_idx = full_text.find(author_text, title_idx + len(title)) if title_idx >= 0 else -1
                    if title_idx >= 0 and author_idx > title_idx:
                        between = full_text[title_idx + len(title):author_idx].strip()
                        # Clean up: remove tag texts that appear between title and author
                        tag_els = item.select("a[href*='/tag/']")
                        for t in tag_els:
                            between = between.replace(t.get_text(strip=True), "")
                        between = between.strip()
                        if between and len(between) > 2:
                            description = between

                # Author
                author = author_el.get_text(strip=True) if author_el else None

                # Date
                date_el = item.select_one("span.time")
                published_at = _parse_qbitai_date(date_el.get_text(strip=True)) if date_el else None

                # Tags
                tag_els = item.select("a[href*='/tag/']")
                tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

                content_hash = compute_content_hash(title, article_url)
                articles.append(Article(
                    title=title,
                    url=article_url,
                    source_name=self.name,
                    source_type="web",
                    description=description[:500],
                    author=author,
                    published_at=published_at,
                    tags=tags,
                    content_hash=content_hash,
                    fetch_timestamp=datetime.now(),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse Qbitai article: {e}")
                continue

        logger.info(f"Qbitai: fetched {len(articles)} articles")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
