#!/usr/bin/env python3
"""AI 科技日报 - CLI entry point."""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from src.config import Config
from src.cache import CacheManager
from src.fetcher import Fetcher
from src.processor import NewsProcessor
from src.renderer import Renderer


def setup_logging(config: Config):
    handlers = [logging.StreamHandler()]
    log_file = config.logging_file
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, config.logging_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


async def run_full(config: Config, report_date: date, include_all: bool = False):
    logger = logging.getLogger("daily-report")

    logger.info(f"=== Daily Report: {report_date.isoformat()} ===")

    # 1. Cache
    cache = CacheManager(config.cache_db_path, config.cache_ttl_hours)
    cache.prune_expired()

    # 2. Fetch
    fetcher = Fetcher(config.sources_config, cache)
    await fetcher.load_plugins()

    if not fetcher.plugins:
        logger.error("No plugins loaded. Check your config.yaml sources.")
        return None

    all_articles = await fetcher.fetch_all()
    logger.info(f"Fetched {len(all_articles)} articles total")

    if include_all:
        articles_for_processing = all_articles
        deduped_count = 0
        logger.info("--all: processing all fetched articles (skipping dedup)")
    else:
        articles_for_processing, deduped_count = await fetcher.deduplicate(all_articles)
        logger.info(f"After dedup: {len(articles_for_processing)} new (deduped {deduped_count})")

    if not articles_for_processing:
        logger.warning("No articles to process")
        return None

    # 3. Process with LLM
    processor = NewsProcessor(config)
    processed = await processor.process(articles_for_processing)
    logger.info(f"Processed {len(processed)} articles")

    # 4. Build report
    report = await processor.build_report(
        articles=processed,
        report_date=report_date,
        total_fetched=len(all_articles),
        total_deduped=deduped_count,
        failed_sources=fetcher.failed_plugins,
    )

    # 5. Render
    renderer = Renderer(template_dir="./templates", output_dir=config.output_dir)
    output_path = renderer.render(report, source_urls=config.source_urls)

    # 6. Record
    cache.record_report(report_date, str(output_path), report.total_published)

    # 7. Report index
    recent = cache.get_recent_reports(days=config.output_keep_days)
    if recent:
        renderer.render_index(recent)

    logger.info(f"Report generated: {output_path}")
    return output_path


async def run_fetch_only(config: Config):
    logger = logging.getLogger("daily-report")
    cache = CacheManager(config.cache_db_path, config.cache_ttl_hours)
    fetcher = Fetcher(config.sources_config, cache)
    await fetcher.load_plugins()
    articles = await fetcher.fetch_all()
    logger.info(f"Fetched {len(articles)} articles")
    for a in articles[:10]:
        logger.info(f"  [{a.source_name}] {a.title}")
    return articles


async def run_dry(config: Config):
    logger = logging.getLogger("daily-report")
    cache = CacheManager(":memory:")
    fetcher = Fetcher(config.sources_config, cache)
    await fetcher.load_plugins()
    articles = await fetcher.fetch_all()
    logger.info(f"Dry run: fetched {len(articles)} articles (no LLM, no output)")
    for a in articles[:20]:
        logger.info(f"  [{a.source_name}] {a.title}")
    return articles


def main():
    parser = argparse.ArgumentParser(description="AI 科技日报生成器")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--date", help="Report date (YYYY-MM-DD, default today)")
    parser.add_argument("--all", action="store_true", dest="include_all", help="Process all fetched articles, skip dedup")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch and cache, skip processing")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but skip LLM and output")
    args = parser.parse_args()

    config = Config(args.config)
    setup_logging(config)

    report_date = date.fromisoformat(args.date) if args.date else date.today()

    if args.dry_run:
        asyncio.run(run_dry(config))
    elif args.fetch_only:
        asyncio.run(run_fetch_only(config))
    else:
        result = asyncio.run(run_full(config, report_date, include_all=args.include_all))
        if result:
            print(f"\n✅ Report: {result}")
            print(f"   Open: open {result}")


if __name__ == "__main__":
    main()
