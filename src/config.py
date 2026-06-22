import os
import re
from pathlib import Path

import yaml


_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _interpolate_env(value):
    """Recursively replace ${VAR} patterns with environment variable values."""
    if isinstance(value, str):
        def replace(match):
            env_var = match.group(1)
            return os.environ.get(env_var, "")
        return _ENV_VAR_RE.sub(replace, value)
    elif isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            raw = yaml.safe_load(f)

        self.data = _interpolate_env(raw)
        self._validate()

    def _validate(self):
        if not self.llm_api_key:
            raise ValueError("llm.api_key is required (set DEEPSEEK_API_KEY env var)")

    def get_section(self, path: str) -> dict:
        keys = path.split(".")
        value = self.data
        for key in keys:
            value = value.get(key, {})
        return value

    @property
    def llm_provider(self) -> str:
        return self.data.get("llm", {}).get("provider", "deepseek")

    @property
    def llm_api_key(self) -> str:
        return self.data.get("llm", {}).get("api_key", "")

    @property
    def llm_api_base(self) -> str:
        return self.data.get("llm", {}).get("api_base", "https://api.deepseek.com/v1")

    @property
    def llm_model(self) -> str:
        return self.data.get("llm", {}).get("model", "deepseek-v4-pro")

    @property
    def llm_max_tokens(self) -> int:
        return self.data.get("llm", {}).get("max_tokens", 16384)

    @property
    def llm_temperature(self) -> float:
        return self.data.get("llm", {}).get("temperature", 0.3)

    @property
    def source_urls(self) -> dict[str, str]:
        return self.data.get("source_urls", {})

    @property
    def output_dir(self) -> str:
        return self.data.get("output", {}).get("dir", "./output")

    @property
    def output_keep_days(self) -> int:
        return self.data.get("output", {}).get("keep_days", 30)

    @property
    def cache_db_path(self) -> str:
        return self.data.get("cache", {}).get("db_path", "./cache/articles.db")

    @property
    def cache_ttl_hours(self) -> int:
        return self.data.get("cache", {}).get("ttl_hours", 72)

    @property
    def processing_batch_size(self) -> int:
        return self.data.get("processing", {}).get("batch_size", 10)

    @property
    def processing_max_total(self) -> int:
        return self.data.get("processing", {}).get("max_total_articles", 80)

    @property
    def logging_level(self) -> str:
        return self.data.get("logging", {}).get("level", "INFO")

    @property
    def logging_file(self) -> str:
        return self.data.get("logging", {}).get("file", "")

    @property
    def sources_config(self) -> dict:
        return self.data.get("sources", {})

    @property
    def enabled_source_names(self) -> list[str]:
        sources = self.sources_config
        return [name for name, cfg in sources.items() if cfg.get("enabled", True)]
