import json
import logging
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI

from src.config import Config
from src.models import Article, ProcessedArticle, Report
from src.cache import compute_content_hash

logger = logging.getLogger(__name__)

CATEGORIES = [
    "大模型与AI",
    "半导体与芯片",
    "开源工具与框架",
    "AI应用与产品",
    "政策与监管",
    "研究论文",
    "商业与投融资",
    "其他",
]

SYSTEM_PROMPT = """你是一个中文AI科技新闻编辑。给定一批文章，对每篇文章返回一个JSON对象，包含以下字段：
- category: 分类，必须是以下之一：{categories}
- chinese_summary: 3-5句中文摘要，简洁精炼、信息密度高。如果原文是英文，请翻译关键信息。
- importance_score: 重要性评分 1.0-10.0（浮点数），评分标准：
  * 9-10: 重大突破、行业里程碑事件
  * 7-8: 重要产品发布、关键技术进展
  * 5-6: 值得关注的行业动态
  * 3-4: 一般性新闻
  * 1-2: 边角信息
- is_duplicate_of: 如果这篇文章与列表中的另一篇本质上重复，填入那篇文章的url，否则为null

输入是一批文章，每篇有title、description、url、source_name、published_at字段。
严格返回JSON数组，不要有任何其他文字。"""


class NewsProcessor:
    def __init__(self, config: Config):
        self.client = AsyncOpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_api_base,
        )
        self.model = config.llm_model
        self.max_tokens = config.llm_max_tokens
        self.temperature = config.llm_temperature
        self.batch_size = config.processing_batch_size
        self.max_total = config.processing_max_total

    async def process(self, articles: list[Article]) -> list[ProcessedArticle]:
        if not articles:
            return []

        # Truncate to max_total
        if len(articles) > self.max_total:
            articles = articles[:self.max_total]

        # Split into batches
        batches = [
            articles[i:i + self.batch_size]
            for i in range(0, len(articles), self.batch_size)
        ]

        all_processed = []
        for batch in batches:
            try:
                processed = await self._process_batch(batch)
                all_processed.extend(processed)
                logger.info(f"Processed batch: {len(processed)} articles")
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                # Fall back to unprocessed articles
                for a in batch:
                    all_processed.append(ProcessedArticle(
                        title=a.title,
                        url=a.url,
                        source_name=a.source_name,
                        source_type=a.source_type,
                        description=a.description,
                        author=a.author,
                        published_at=a.published_at,
                        tags=a.tags,
                        content_hash=a.content_hash,
                        fetch_timestamp=a.fetch_timestamp,
                        processing_timestamp=datetime.now(),
                    ))

        # Drop semantic duplicates
        deduped = self._drop_duplicates(all_processed)
        logger.info(f"Semantic dedup: {len(all_processed)} -> {len(deduped)}")

        return deduped

    async def _process_batch(self, articles: list[Article]) -> list[ProcessedArticle]:
        # Build input JSON
        input_data = []
        for a in articles:
            input_data.append({
                "title": a.title,
                "description": a.description[:300],
                "url": a.url,
                "source_name": a.source_name,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            })

        prompt = SYSTEM_PROMPT.format(categories=", ".join(CATEGORIES))

        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)},
            ],
        )

        text = resp.choices[0].message.content or ""
        parsed = self._parse_response(text)

        results = []
        for i, a in enumerate(articles):
            data = parsed[i] if i < len(parsed) else {}
            results.append(ProcessedArticle(
                title=a.title,
                url=a.url,
                source_name=a.source_name,
                source_type=a.source_type,
                description=a.description,
                author=a.author,
                published_at=a.published_at,
                tags=a.tags,
                content_hash=a.content_hash,
                fetch_timestamp=a.fetch_timestamp,
                category=data.get("category", "其他"),
                chinese_summary=data.get("chinese_summary", a.description[:200]),
                importance_score=float(data.get("importance_score", 5.0)),
                processing_timestamp=datetime.now(),
            ))
        return results

    def _parse_response(self, text: str) -> list[dict]:
        """Parse JSON from LLM response, handling markdown code fences."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extract from markdown code fence
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove opening and closing fences
            inner = "\n".join(lines[1:-1])
            if inner.startswith("json"):
                inner = inner[4:]
            try:
                return json.loads(inner.strip())
            except json.JSONDecodeError:
                pass
        # Try find JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning(f"Failed to parse LLM response as JSON: {text[:200]}...")
        return []

    @staticmethod
    def _extract_stars_today(article: ProcessedArticle) -> int:
        for tag in article.tags:
            if tag.startswith("stars_today_raw:"):
                try:
                    return int(tag.split(":", 1)[1])
                except (ValueError, IndexError):
                    pass
        return 0

    def _drop_duplicates(self, articles: list[ProcessedArticle]) -> list[ProcessedArticle]:
        """Drop articles with lower importance that are near-duplicates."""
        seen_urls = set()
        result = []
        # Sort by importance desc so we keep the higher-scored duplicate
        sorted_articles = sorted(articles, key=lambda a: a.importance_score, reverse=True)
        for a in sorted_articles:
            if a.url not in seen_urls:
                seen_urls.add(a.url)
                result.append(a)
        return result

    async def build_report(
        self,
        articles: list[ProcessedArticle],
        report_date,
        total_fetched: int = 0,
        total_deduped: int = 0,
        failed_sources: Optional[list[dict]] = None,
    ) -> Report:
        # Sort by importance desc
        sorted_articles = sorted(articles, key=lambda a: a.importance_score, reverse=True)

        # Separate GitHub Trending repos (re-sort by stars_today_raw desc)
        github_repos = [a for a in sorted_articles if a.source_type == "github_trending"]
        github_repos.sort(key=lambda a: self._extract_stars_today(a), reverse=True)
        non_github = [a for a in sorted_articles if a.source_type != "github_trending"]

        # Top stories (from non-GitHub articles only)
        top_stories = non_github[:5]

        # Group by category (non-GitHub only)
        categories: dict[str, list[ProcessedArticle]] = {}
        for a in non_github:
            categories.setdefault(a.category, []).append(a)

        # Stats
        source_stats: dict[str, int] = {}
        for a in sorted_articles:
            source_stats[a.source_name] = source_stats.get(a.source_name, 0) + 1

        category_stats: dict[str, int] = {}
        for a in sorted_articles:
            category_stats[a.category] = category_stats.get(a.category, 0) + 1

        return Report(
            report_date=report_date,
            generated_at=datetime.now(),
            articles=sorted_articles,
            categories=categories,
            top_stories=top_stories,
            github_repos=github_repos,
            source_stats=source_stats,
            category_stats=category_stats,
            total_fetched=total_fetched,
            total_deduped=total_deduped,
            total_published=len(sorted_articles),
            failed_sources=failed_sources or [],
        )
