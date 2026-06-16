# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Full pipeline: fetch → dedup → DeepSeek summary → render HTML
python3 run.py

# Fetch only: fetch and cache articles, skip LLM processing
python3 run.py --fetch-only

# Dry run: validate config and sources, no LLM call
python3 run.py --dry-run

python3 run.py --date 2026-06-15        # Generate report for a specific date
python3 run.py --config custom.yaml     # Use a different config file
```

Requires `DEEPSEEK_API_KEY` env var, either via `.env` file or shell export. No tests or linting configured.

## Architecture

**Data flow**: `config.yaml` → `Fetcher` (concurrent plugin fetch) → `CacheManager` (SQLite dedup) → `NewsProcessor` (DeepSeek batch classify/summarize) → `Renderer` (Jinja2 → self-contained HTML)

**Plugin system** (`src/sources/`): Any `.py` file with a non-abstract `SourcePlugin` subclass is auto-registered via `__init_subclass__`. The plugin contract:
- `name` property — human-readable source name
- `async fetch() -> list[Article]` — return articles or empty list on failure
- `async validate() -> bool` (optional) — called at startup; return `False` to disable the plugin

Plugins receive their config section from `config.yaml` via `configure(dict)`. `Fetcher` runs all enabled plugins concurrently with `asyncio.gather`, isolating failures per plugin.

**RSS source** (`src/sources/rss_feed.py`): Uses wewe-rss self-built aggregation service. Each entry's `<author><name>` (微信公众号名称) becomes the `source_name`, so per-article sources show the actual account name (e.g., 36氪, 雷峰网) rather than a generic feed label.

**Deduplication**: Two-stage — exact URL match in SQLite (`fetch_history` table, TTL 72h), then LLM-based semantic dedup during processing.

**LLM processing** (`src/processor.py`): Articles batched (default 10/batch), sent to DeepSeek V4 Pro. Prompt asks for `category`, `chinese_summary` (3-5 sentences), `importance_score` (1-10), and `is_duplicate_of`. No `key_points` — only a concise summary. Parser handles markdown code fences and partial JSON. Batch failures fall back to unprocessed articles.

**Output**: Single-column, self-contained HTML via Jinja2 (`templates/report.html` + `templates/macros.html`). Header is compact: title + date on left, inline stat pills on right. Summaries rendered with a left border accent. Reports named `report-YYYY-MM-DD.html` — same-date runs overwrite.

## Config

`sources` maps directly to plugin class names. Currently two sources enabled:
- `GitHubTrending` — GitHub trending repos
- `RSSFeed` — single feed from `http://rss.charleslee.cn/feeds/all.atom` (wewe-rss)

`${ENV_VAR}` interpolation supported. See `src/config.py` for all properties.

## Key files

- Add a news source → create a file in `src/sources/` with a `SourcePlugin` subclass, then add its config in `config.yaml`
- Modify LLM prompt or categories → `src/processor.py` (`CATEGORIES`, `SYSTEM_PROMPT`)
- Change HTML layout/styling → `templates/report.html`
- Change article card structure → `templates/macros.html`
