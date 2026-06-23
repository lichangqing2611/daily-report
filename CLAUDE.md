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

**Web scraping sources** — four individual website scrapers replace the unstable RSSFeed:

- `LeiphoneSource` (`src/sources/leiphone.py`): Scrapes leiphone.com (雷峰网) — SSR HTML with `.article-list .item` containers. Parses Chinese relative dates (昨天 HH:MM, X小时前, MM月DD日).
- `SemiInsightsSource` (`src/sources/semi_insights.py`): Scrapes semi-insights.com (半导体行业观察) — PHPCMS SSR, `ul.info-news-c > li` containers. Disables SSL verification (self-signed cert). Date format: YYYY.MM.DD.
- `QbitaiSource` (`src/sources/qbitai.py`): Scrapes qbitai.com (量子位) — WordPress SSR, `.article_list .picture_text` containers. Needs real User-Agent header to avoid Cloudflare 403. Parses relative dates (X分钟前, X小时前).
- `VolcengineSource` (`src/sources/volcengine.py`): Uses `/api/fe/v1/articles` JSON API directly (Modern.js SPA — SSR HTML lacks article URLs). Returns structured data with author names, categories, tags, and Unix timestamps.

**RSS source** (`src/sources/rss_feed.py`): Disabled by default. Uses wewe-rss self-built aggregation service. Kept as a fallback option.

**BAAI Hub** (`src/sources/baai_hub.py`): Uses Playwright headless Chromium to scroll-load up to 30 papers from BAAI Hub hotness ranking. Falls back to static HTTP scrape (10 papers) if Playwright unavailable. Paper titles are batch-translated to Chinese via DeepSeek in `run.py:_translate_paper_titles()`.

**Deduplication**: Two-stage — exact URL match in SQLite (`fetch_history` table, TTL 72h), then LLM-based semantic dedup during processing.

**LLM processing** (`src/processor.py`): Articles batched (default 10/batch), sent to DeepSeek V4 Pro. Prompt asks for `category`, `chinese_summary` (3-5 sentences), `importance_score` (1-10), and `is_duplicate_of`. No `key_points` — only a concise summary. Parser handles markdown code fences and partial JSON. Batch failures fall back to unprocessed articles.

**Output**: Self-contained HTML via Jinja2 (`templates/report.html` + `templates/macros.html`). Reports named `report-YYYY-MM-DD.html` — same-date runs overwrite.

**Layout**: Three-tab UI under the header:
- **科技新闻** tab — Top Stories + category-grouped articles. Summaries rendered with left border accent.
- **GitHub Trending** tab — Dedicated section for GitHub repos, sorted by daily new stars descending. Each card shows repo name (linked to GitHub) + inline stats (language, total stars, daily stars, forks) in one row, with LLM-generated Chinese introduction below. GitHub Trending articles are separated in `build_report()` into `Report.github_repos` and excluded from the news categories/top-stories.
- **热门论文** tab — BAAI Hub paper rankings (top 30). Each paper card shows rank badge (top 3 gold), English title (linked), Chinese translation subtitle, and full Chinese summary.

**GitHub Trending data flow**:
1. `github_trending.py` scrapes the trending page — parses repo name, description, language, total stars, daily stars ("stars today"), forks. Daily stars parsed via `repo.find(string=re.compile(r"stars?\s+today"))` (BeautifulSoup text-node search).
2. Stats stored in `Article.tags` as structured strings: `lang`, `stars_total:1.5k`, `stars_today:86`, `stars_today_raw:86` (raw integer for sorting), `forks:234`.
3. `fetch()` sorts articles by `stars_today_raw` descending before returning.
4. `processor.py` `build_report()` re-sorts `github_repos` by `stars_today_raw` via `_extract_stars_today()` (since the global sort is by `importance_score`).
5. `macros.html` `github_repo_card` parses tags with Jinja2 `select("contains", ...)` filter to extract display values.

**Jinja2 extensions**: The renderer registers a custom `contains` test (`self.env.tests["contains"] = lambda value, substr: substr in value`) used by `github_repo_card` to parse structured `tags` entries.

**Footer**: Source names are hyperlinked when a URL is configured in `source_urls` (config.yaml → `Config.source_urls` → passed to template via `renderer.render()`).

## Config

`sources` maps directly to plugin class names. Currently enabled sources:
- `GitHubTrending` — GitHub trending repos
- `BAAIHub` — BAAI Hub paper rankings (hotness, weekly)
- `LeiphoneSource` — 雷峰网 tech news (scraped)
- `SemiInsightsSource` — 半导体行业观察 (scraped)
- `QbitaiSource` — 量子位 AI news (scraped)
- `VolcengineSource` — 火山引擎 developer articles (API)

`RSSFeed` is kept but disabled (`enabled: false`).

`source_urls` maps display names to website URLs for footer hyperlinks. `${ENV_VAR}` interpolation supported. See `src/config.py` for all properties.

## Key files

- Add a news source → create a file in `src/sources/` with a `SourcePlugin` subclass, then add its config in `config.yaml`
- Modify LLM prompt or categories → `src/processor.py` (`CATEGORIES`, `SYSTEM_PROMPT`)
- Change HTML layout/styling → `templates/report.html`
- Change article card structure → `templates/macros.html` (`article_card`, `github_repo_card`, `paper_card` macros)
- Change GitHub trending sort order → `src/sources/github_trending.py` (`fetch()` sort) and `src/processor.py` (`_extract_stars_today()` + `build_report()` sort)
- Change paper title translation → `run.py` (`_translate_paper_titles()`)
- Change BAAI Hub scroll/load behavior → `src/sources/baai_hub.py` (`fetch()` scroll loop)
- Add source homepage link → `config.yaml` (`source_urls` section)
- Register Jinja2 custom test/filter → `src/renderer.py`
