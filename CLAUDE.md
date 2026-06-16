# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Dry run: fetch sources only, no LLM call, no output
python3 run.py --dry-run

# Fetch only: fetch and cache articles, skip LLM processing
python3 run.py --fetch-only

# Full pipeline: fetch → dedup → DeepSeek summary → render HTML
python3 run.py

python3 run.py --date 2026-06-15        # Generate report for a specific date
python3 run.py --config custom.yaml     # Use a different config file
```

The entry point requires `DEEPSEEK_API_KEY` environment variable set, either via `.env` file or shell export.

There are no tests or linting configured.

## Architecture

**Data flow**: `config.yaml` → `Fetcher` (concurrent plugin fetch) → `CacheManager` (SQLite dedup) → `NewsProcessor` (DeepSeek batch classify/summarize) → `Renderer` (Jinja2 → self-contained HTML)

**Plugin system** (`src/sources/`): Any `.py` file with a non-abstract `SourcePlugin` subclass is auto-registered via `__init_subclass__`. The plugin contract requires:
- `name` property — human-readable source name
- `async fetch() -> list[Article]` — return articles or empty list on failure
- `async validate() -> bool` (optional) — called at startup; return `False` to disable the plugin gracefully

Plugins receive their config section from `config.yaml` via `configure(dict)`. The `Fetcher` runs all enabled plugins concurrently with `asyncio.gather` and isolates failures per plugin.

**Deduplication**: Two-stage — exact URL match in SQLite (`fetch_history` table, TTL 72h) before processing, then LLM-based semantic dedup during processing.

**LLM processing** (`src/processor.py`): Articles are batched (default 10/batch), sent to DeepSeek V4 Pro with a structured prompt asking for JSON output containing `category`, `chinese_summary`, `key_points`, `importance_score` (1-10), and `is_duplicate_of`. The response parser handles markdown code fences and partial JSON. Batch failures fall back to unprocessed articles without crashing the pipeline.

**Output**: Self-contained HTML via Jinja2 (`templates/report.html` + `templates/macros.html`). Reports are named `report-YYYY-MM-DD.html` — same-date runs overwrite. History is preserved indefinitely (no auto-cleanup).

## Config

`config.yaml` uses `${ENV_VAR}` interpolation. The `sources` section maps directly to plugin class names — enabling/disabling or adding a source means updating this section. See `src/config.py` for all properties.

## Key files for modifications

- Add a news source → create a file in `src/sources/` with a `SourcePlugin` subclass, then add its config in `config.yaml`
- Modify LLM prompt or categories → `src/processor.py` (`CATEGORIES`, `SYSTEM_PROMPT`)
- Change HTML output → `templates/report.html`
