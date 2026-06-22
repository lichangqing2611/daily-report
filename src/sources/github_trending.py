import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)


def _parse_count(text: str) -> str:
    """Normalize a count string like '1,234' or '1.2k' to a display-friendly form."""
    if not text:
        return "0"
    text = text.strip().lower()
    # Already has a k/m suffix, return as-is
    if text.endswith(("k", "m")):
        return text
    # Remove commas and try to convert
    try:
        n = int(text.replace(",", ""))
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)
    except (ValueError, AttributeError):
        return text


class GitHubTrending(SourcePlugin):
    @property
    def name(self) -> str:
        return "GitHub Trending"

    async def fetch(self) -> list[Article]:
        since = self._config.get("since", "daily")
        language = self._config.get("language", "")
        max_repos = self._config.get("max_repos", 15)

        url = f"https://github.com/trending/{language}"
        params = {"since": since}

        articles = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            repos = soup.select("article.Box-row")[:max_repos]

            for repo in repos:
                try:
                    h2 = repo.select_one("h2 a")
                    if not h2:
                        continue
                    full_name = " ".join(h2.stripped_strings).replace(" ", "").replace("\n", "")
                    repo_url = "https://github.com" + h2["href"]

                    description_el = repo.select_one("p")
                    description_text = description_el.get_text(strip=True) if description_el else ""

                    language_el = repo.select_one('[itemprop="programmingLanguage"]')
                    lang = language_el.get_text(strip=True) if language_el else ""

                    stars_el = repo.select("a[href*='/stargazers']")
                    stars_total_text = stars_el[-1].get_text(strip=True) if stars_el else ""

                    forks_el = repo.select("a[href*='/forks']")
                    forks_text = forks_el[-1].get_text(strip=True) if forks_el else ""

                    # Parse stars today (text like "1,834 stars today")
                    stars_today_text = "0"
                    stars_today_el = repo.find(string=re.compile(r"stars?\s+today"))
                    if stars_today_el:
                        m = re.search(r"([\d,]+)\s*stars?\s*today", stars_today_el.get_text())
                        if m:
                            stars_today_text = m.group(1)

                    # Store structured stats in tags for template rendering
                    tags = []
                    if lang:
                        tags.append(lang)
                    stars_total_display = _parse_count(stars_total_text)
                    stars_today_display = _parse_count(stars_today_text) if stars_today_text != "0" else ""
                    forks_display = _parse_count(forks_text) if forks_text else ""
                    tags.append(f"stars_total:{stars_total_display}")
                    if stars_today_display:
                        tags.append(f"stars_today:{stars_today_display}")
                        # Raw numeric value for sorting
                        try:
                            tags.append(f"stars_today_raw:{int(stars_today_text.replace(',', ''))}")
                        except (ValueError, AttributeError):
                            pass
                    if forks_display:
                        tags.append(f"forks:{forks_display}")

                    content_hash = compute_content_hash(full_name, description_text)
                    articles.append(Article(
                        title=full_name,
                        url=repo_url,
                        source_name=self.name,
                        source_type="github_trending",
                        description=description_text,
                        tags=tags,
                        content_hash=content_hash,
                        fetch_timestamp=datetime.now(),
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse GitHub trending repo: {e}")
                    continue

        except httpx.HTTPError as e:
            logger.error(f"GitHub Trending fetch failed: {e}")
            raise SourceError(f"GitHub Trending HTTP error: {e}") from e
        except Exception as e:
            logger.error(f"GitHub Trending unexpected error: {e}")
            raise SourceError(f"GitHub Trending error: {e}") from e

        # Sort by stars_today descending
        def _stars_today_sort_key(a: Article) -> int:
            for tag in a.tags:
                if tag.startswith("stars_today_raw:"):
                    try:
                        return int(tag.split(":", 1)[1])
                    except ValueError:
                        pass
            return 0

        articles.sort(key=_stars_today_sort_key, reverse=True)

        logger.info(f"GitHub Trending: fetched {len(articles)} repos")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://github.com/trending", follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
