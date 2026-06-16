import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)


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
                    # h2 text has "owner / repo" format with whitespace
                    full_name = " ".join(h2.stripped_strings).replace(" ", "").replace("\n", "")
                    repo_url = "https://github.com" + h2["href"]

                    description_el = repo.select_one("p")
                    description_text = description_el.get_text(strip=True) if description_el else ""

                    language_el = repo.select_one('[itemprop="programmingLanguage"]')
                    language = language_el.get_text(strip=True) if language_el else ""

                    stars_el = repo.select("a[href*='/stargazers']")
                    stars_text = stars_el[-1].get_text(strip=True) if stars_el else ""

                    forks_el = repo.select("a[href*='/forks']")
                    forks_text = forks_el[-1].get_text(strip=True) if forks_el else ""

                    # Build richer description
                    meta_parts = []
                    if language:
                        meta_parts.append(language)
                    if stars_text:
                        meta_parts.append(f"Stars: {stars_text}")
                    if forks_text:
                        meta_parts.append(f"Forks: {forks_text}")
                    meta = " | ".join(meta_parts)
                    description = f"[{meta}] {description_text}" if meta else description_text

                    content_hash = compute_content_hash(full_name, description)
                    articles.append(Article(
                        title=full_name,
                        url=repo_url,
                        source_name=self.name,
                        source_type="github_trending",
                        description=description,
                        tags=[language] if language else [],
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

        logger.info(f"GitHub Trending: fetched {len(articles)} repos")
        return articles

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://github.com/trending", follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
