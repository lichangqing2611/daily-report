from abc import ABC, abstractmethod
from typing import Optional

from src.models import Article


class SourceError(Exception):
    """Raised when a source fails critically."""
    pass


class SourcePlugin(ABC):
    """Abstract base for all news sources. Subclasses are auto-registered."""

    _registry: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not ABC in cls.__bases__:
            SourcePlugin._registry[cls.__name__] = cls

    def configure(self, config: dict):
        """Apply source-specific configuration."""
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name shown in the report."""

    @abstractmethod
    async def fetch(self) -> list[Article]:
        """Fetch articles from this source. Return empty list on soft failure."""

    async def validate(self) -> bool:
        """Optional. Called at startup. Return False to disable without crashing."""
        return True

    @property
    def max_articles(self) -> int:
        """Override to cap articles per run. 0 means no cap."""
        return self._config.get("max_articles", 0)

    @classmethod
    def get_all_plugins(cls) -> dict[str, type]:
        return dict(cls._registry)

    @classmethod
    def create_all(cls, sources_config: dict) -> list["SourcePlugin"]:
        instances = []
        for class_name, plugin_cls in cls._registry.items():
            plugin_config = sources_config.get(class_name, {})
            if not plugin_config.get("enabled", True):
                continue
            instance = plugin_cls()
            instance.configure(plugin_config)
            instances.append(instance)
        return instances
