# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Full pipeline (new articles only): fetch → dedup → DeepSeek summary → render HTML
python3 run.py

# Process ALL articles, skip cache dedup
python3 run.py --date 2026-06-15 --all

# Fetch only: fetch and cache articles, skip LLM processing
python3 run.py --fetch-only

# Dry run: validate config and sources, no LLM call
python3 run.py --dry-run

python3 run.py --date 2026-06-15        # Generate report for a specific date
python3 run.py --config custom.yaml     # Use a different config file
```

API key via `.env` file (`DEEPSEEK_API_KEY=xxx`) loaded by `python-dotenv`. No tests or linting configured.

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

**Output**: Self-contained HTML via Jinja2 (`templates/report.html` + `templates/macros.html`). Reports named `report-YYYY-MM-DD.html` — same-date runs overwrite.

**Layout**: Two-tab UI under the header:
- **科技新闻** tab — Top Stories + category-grouped articles. Summaries rendered with left border accent.
- **GitHub Trending** tab — Dedicated section for GitHub repos, sorted by daily new stars descending. Each card shows repo name (linked to GitHub) + inline stats (language, ⭐ total stars, 📈 daily stars, 🍴 forks) in one row, with LLM-generated Chinese introduction below. GitHub Trending articles are separated in `build_report()` into `Report.github_repos` and excluded from the news categories/top-stories.

**GitHub Trending data flow**:
1. `github_trending.py` scrapes the trending page — parses repo name, description, language, total stars, daily stars ("stars today"), forks. Daily stars parsed via `repo.find(string=re.compile(r"stars?\s+today"))` (BeautifulSoup text-node search).
2. Stats stored in `Article.tags` as structured strings: `lang`, `stars_total:1.5k`, `stars_today:86`, `stars_today_raw:86` (raw integer for sorting), `forks:234`.
3. `fetch()` sorts articles by `stars_today_raw` descending before returning.
4. `processor.py` `build_report()` re-sorts `github_repos` by `stars_today_raw` via `_extract_stars_today()` (since the global sort is by `importance_score`).
5. `macros.html` `github_repo_card` parses tags with Jinja2 `select("contains", ...)` filter to extract display values.

**Jinja2 extensions**: The renderer registers a custom `contains` test (`self.env.tests["contains"] = lambda value, substr: substr in value`) used by `github_repo_card` to parse structured `tags` entries.

**Footer**: Source names are hyperlinked when a URL is configured in `source_urls` (config.yaml → `Config.source_urls` → passed to template via `renderer.render()`).

## Config

`sources` maps directly to plugin class names. Currently two sources enabled:
- `GitHubTrending` — GitHub trending repos (fetches repo name, description, language, total stars, daily stars "stars today", forks; stores in `tags` as structured key:value strings)
- `RSSFeed` — single feed from `http://rss.charleslee.cn/feeds/all.atom` (wewe-rss)

`source_urls` maps display names to website URLs for footer hyperlinks. `${ENV_VAR}` interpolation supported. See `src/config.py` for all properties.

## Key files

- Add a news source → create a file in `src/sources/` with a `SourcePlugin` subclass, then add its config in `config.yaml`
- Modify LLM prompt or categories → `src/processor.py` (`CATEGORIES`, `SYSTEM_PROMPT`)
- Change HTML layout/styling → `templates/report.html`
- Change article card structure → `templates/macros.html`
- Change GitHub repo card → `templates/macros.html` (`github_repo_card` macro, driven by `tags` list)
- Change GitHub trending sort order → `src/sources/github_trending.py` (`fetch()` sort) and `src/processor.py` (`_extract_stars_today()` + `build_report()` sort)
- Add source homepage link → `config.yaml` (`source_urls` section)
- Register Jinja2 custom test/filter → `src/renderer.py`
