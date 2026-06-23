import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)

BASE_URL = "https://developer.volcengine.com"
API_URL = f"{BASE_URL}/api/fe/v1/articles"


class VolcengineSource(SourcePlugin):
    """Fetch articles from developer.volcengine.com (火山引擎) via their JSON API.

    The site is a Modern.js SPA whose SSR HTML does not include article URLs.
    We use the internal `/api/fe/v1/articles` endpoint which returns structured
    data with item IDs, author names, tags, and categories.
    """

    @property
    def name(self) -> str:
        return "火山引擎"

    async def fetch(self) -> list[Article]:
        max_articles = self._config.get("max_articles", 10)
        articles: list[Article] = []

        try:
            async with httpx.AsyncClient(timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": f"{BASE_URL}/articles",
            }) as client:
                cursor = ""
                while len(articles) < max_articles:
                    resp = await client.get(f"{API_URL}?cursor={cursor}")
                    resp.raise_for_status()
                    body = resp.json()
                    items = body.get("data", [])
                    if not items:
                        break

                    for item in items:
                        if len(articles) >= max_articles:
                            break

                        content = item.get("content", {})
                        user = item.get("user", {})

                        title = content.get("name", "").strip()
                        item_id = content.get("item_id", "")
                        if not title or not item_id:
                            continue

                        article_url = f"{BASE_URL}/articles/{item_id}"
                        description = (content.get("abstract") or "").strip()
                        author = user.get("name", "").strip() or None

                        # Parse publish_time (Unix timestamp)
                        ts = content.get("publish_time")
                        published_at = None
                        if ts:
                            try:
                                published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                            except (ValueError, OSError):
                                pass

                        # Collect tags and categories
                        tags: list[str] = []
                        for cat in item.get("categories", []) or []:
                            name = cat.get("name", "").strip()
                            if name:
                                tags.append(f"category:{name}")
                        for tag in item.get("tags", []) or []:
                            name = tag.get("name", "").strip()
                            if name:
                                tags.append(name)

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

                    # Paginate
                    cursor = body.get("cursor", "")
                    if not cursor:
                        break

        except Exception as e:
            raise SourceError(f"Volcengine fetch failed: {e}") from e

        logger.info(f"Volcengine: fetched {len(articles)} articles")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": f"{BASE_URL}/articles",
            }) as client:
                resp = await client.get(f"{API_URL}?cursor=")
                return resp.status_code == 200
        except Exception:
            return False
