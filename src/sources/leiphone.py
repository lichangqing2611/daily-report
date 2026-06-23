import logging
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.leiphone.com"


def _parse_relative_date(text: str) -> datetime | None:
    """Parse Chinese relative dates like '昨天 18:03', '2小时前', '06月18日', '2026-06-18'."""
    text = text.strip()
    now = datetime.now()

    # ISO format
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    # "昨天 HH:MM"
    m = re.match(r"昨天\s*(\d{1,2}):(\d{2})", text)
    if m:
        d = now - timedelta(days=1)
        return d.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # "前天 HH:MM"
    m = re.match(r"前天\s*(\d{1,2}):(\d{2})", text)
    if m:
        d = now - timedelta(days=2)
        return d.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # "X小时前"
    m = re.match(r"(\d+)\s*小时前", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    # "X分钟前"
    m = re.match(r"(\d+)\s*分钟前", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    # "MM月DD日" or "MM月DD日 HH:MM"
    m = re.match(r"(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        hour = int(m.group(3)) if m.group(3) else 0
        minute = int(m.group(4)) if m.group(4) else 0
        return datetime(now.year, month, day, hour, minute)

    return None


class LeiphoneSource(SourcePlugin):
    """Scrape news from leiphone.com (雷峰网)."""

    @property
    def name(self) -> str:
        return "雷峰网"

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
            raise SourceError(f"Leiphone fetch failed: {e}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".article-list .item, .list-item, .index-pageList .list > ul > li")

        for item in items[:max_articles]:
            try:
                # Title and URL from h3 > a
                title_el = item.select_one("h3 a") or item.select_one("h2 a") or item.select_one("a.headTit")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                article_url = urljoin(BASE_URL, title_el.get("href", ""))
                if not title or not article_url:
                    continue

                # Description
                desc_el = item.select_one("p.des, div.des, p.intro, p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Author
                author_el = item.select_one("a[href*='/author/']")
                author = author_el.get_text(strip=True) if author_el else None

                # Category
                cat_el = item.select_one("a[href*='/category/']")
                category = cat_el.get_text(strip=True) if cat_el else None

                # Date
                date_el = item.select_one("span.time, div.time, .date")
                published_at = None
                if date_el:
                    published_at = _parse_relative_date(date_el.get_text(strip=True))

                # Tags
                tag_els = item.select("a[href*='/tag/']")
                tags = [t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)]

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
                logger.warning(f"Failed to parse Leiphone article: {e}")
                continue

        logger.info(f"Leiphone: fetched {len(articles)} articles")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
