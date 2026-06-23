import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)

BASE_URL = "http://www.semi-insights.com"


def _parse_semi_date(text: str) -> datetime | None:
    """Parse dates like '2024.06.22' or '2024-06-22'."""
    text = text.strip()
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%m.%d.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


class SemiInsightsSource(SourcePlugin):
    """Scrape news from semi-insights.com (半导体行业观察)."""

    @property
    def name(self) -> str:
        return "半导体行业观察"

    async def fetch(self) -> list[Article]:
        max_articles = self._config.get("max_articles", 20)
        articles: list[Article] = []

        try:
            async with httpx.AsyncClient(timeout=30, verify=False, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                resp.raise_for_status()
        except Exception as e:
            raise SourceError(f"SemiInsights fetch failed: {e}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("ul.info-news-c > li")

        for item in items[:max_articles]:
            try:
                # Title and URL from h5 > a
                title_el = item.select_one("h5 a") or item.select_one("a[href]")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                article_url = urljoin(BASE_URL, title_el.get("href", ""))
                if not title or not article_url:
                    continue

                # Description from p.p
                desc_el = item.select_one("p.p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Author from span.a-author
                author_el = item.select_one("span.a-author")
                author = author_el.get_text(strip=True) if author_el else None

                # Category from span.a-name > a
                cat_el = item.select_one("span.a-name a")
                category = cat_el.get_text(strip=True) if cat_el else None

                # Date from span.date
                date_el = item.select_one("span.date")
                published_at = _parse_semi_date(date_el.get_text(strip=True)) if date_el else None

                tags = []
                if category:
                    tags.append(f"category:{category}")

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
                logger.warning(f"Failed to parse SemiInsights article: {e}")
                continue

        logger.info(f"SemiInsights: fetched {len(articles)} articles")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
