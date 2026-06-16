import asyncio
import logging
from datetime import datetime

from src.cache import CacheManager, compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)


class Fetcher:
    """Orchestrates plugin loading, concurrent fetching, and deduplication."""

    def __init__(self, sources_config: dict, cache: CacheManager):
        self.sources_config = sources_config
        self.cache = cache
        self.plugins: list[SourcePlugin] = []
        self.failed_plugins: list[dict] = []

    async def load_plugins(self) -> None:
        plugins = SourcePlugin.create_all(self.sources_config)

        for plugin in plugins:
            try:
                is_valid = await plugin.validate()
                if is_valid:
                    self.plugins.append(plugin)
                    logger.info(f"Plugin loaded: {plugin.name}")
                else:
                    logger.warning(f"Plugin disabled (validate returned False): {plugin.name}")
                    self.failed_plugins.append({
                        "name": plugin.name,
                        "error": "Validation failed",
                    })
            except Exception as e:
                logger.error(f"Plugin validation error: {plugin.name}: {e}")
                self.failed_plugins.append({
                    "name": plugin.name,
                    "error": str(e),
                })

    async def fetch_all(self) -> list[Article]:
        """Run all enabled plugins concurrently. Returns flat list of all articles."""
        if not self.plugins:
            logger.warning("No plugins loaded, nothing to fetch")
            return []

        tasks = []
        for plugin in self.plugins:
            tasks.append(self._fetch_one(plugin))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for i, result in enumerate(results):
            plugin = self.plugins[i]
            if isinstance(result, Exception):
                logger.error(f"Plugin {plugin.name} failed: {result}")
                self.failed_plugins.append({
                    "name": plugin.name,
                    "error": str(result),
                })
            elif isinstance(result, list):
                all_articles.extend(result)
                logger.info(f"Plugin {plugin.name}: {len(result)} articles")

        # Compute content hash for any articles that don't have one
        for article in all_articles:
            if not article.content_hash:
                article.content_hash = compute_content_hash(article.title, article.description)

        return all_articles

    async def _fetch_one(self, plugin: SourcePlugin) -> list[Article]:
        try:
            articles = await plugin.fetch()
            if not isinstance(articles, list):
                return []
            # Apply max_articles cap
            max_arts = plugin.max_articles
            if max_arts and max_arts > 0 and len(articles) > max_arts:
                articles = articles[:max_arts]
            return articles
        except SourceError as e:
            logger.error(f"Plugin {plugin.name} source error: {e}")
            raise
        except Exception as e:
            logger.error(f"Plugin {plugin.name} unexpected error: {e}")
            raise

    async def deduplicate(self, articles: list[Article]) -> tuple[list[Article], int]:
        """Apply cache-based deduplication. Returns (new_articles, deduped_count)."""
        return self.cache.deduplicate(articles)

    def get_stats(self) -> dict:
        """Return summary of fetch results."""
        return {
            "total_plugins": len(self.plugins),
            "failed_plugins": len(self.failed_plugins),
            "failed_plugin_details": self.failed_plugins,
        }
