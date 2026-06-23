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


async def _translate_paper_titles(papers: list, config: Config, logger) -> None:
    """Batch-translate paper titles to Chinese and store in tags as title_cn."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.llm_api_key, base_url=config.llm_api_base)
    titles = [p.title for p in papers]

    resp = await client.chat.completions.create(
        model=config.llm_model,
        temperature=0.3,
        max_tokens=4096,
        messages=[{
            "role": "system",
            "content": "你是一个学术论文标题翻译助手。将以下英文论文标题翻译为简洁准确的中文。保留专有名词（模型名、方法名等）的英文原文。严格返回JSON数组，每个元素是一个字符串，对应每篇论文的中文译名。不要有任何其他文字。",
        }, {
            "role": "user",
            "content": f"翻译以下{len(titles)}篇论文标题为中文，返回JSON字符串数组：\n" +
                       "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles)),
        }],
    )

    text = resp.choices[0].message.content or ""
    # Parse JSON array from response
    import json, re
    try:
        cn_titles = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        cn_titles = json.loads(m.group()) if m else []

    for i, paper in enumerate(papers):
        if i < len(cn_titles) and cn_titles[i]:
            paper.tags.append(f"title_cn:{cn_titles[i]}")

    logger.info(f"Translated {min(len(cn_titles), len(papers))} paper titles")


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

    # Separate paper rankings (no LLM needed, already have Chinese abstracts)
    paper_articles = [a for a in articles_for_processing if a.source_type == "paper_ranking"]
    news_articles = [a for a in articles_for_processing if a.source_type != "paper_ranking"]

    if not articles_for_processing:
        logger.warning("No articles to process")
        return None

    # 3. Process news with LLM
    processor = NewsProcessor(config)
    processed_news = await processor.process(news_articles) if news_articles else []
    logger.info(f"Processed {len(processed_news)} news articles")

    # Convert paper articles to ProcessedArticle (skip LLM)
    paper_processed = []
    for a in paper_articles:
        from src.models import ProcessedArticle
        paper_processed.append(ProcessedArticle(
            title=a.title,
            url=a.url,
            source_name=a.source_name,
            source_type=a.source_type,
            description=a.description,
            author=a.author,
            published_at=a.published_at,
            tags=list(a.tags),
            content_hash=a.content_hash,
            fetch_timestamp=a.fetch_timestamp,
            category="热门论文",
            chinese_summary=a.description,  # BAAI abstracts are already in Chinese
            importance_score=5.0,
        ))

    # Batch-translate paper titles to Chinese via LLM
    if paper_processed:
        await _translate_paper_titles(paper_processed, config, logger)

    # 4. Build report
    report = await processor.build_report(
        articles=processed_news + paper_processed,
        report_date=report_date,
        total_fetched=len(all_articles),
        total_deduped=deduped_count,
        failed_sources=fetcher.failed_plugins,
        paper_rankings=paper_processed,
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
