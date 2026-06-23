from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source_name: str
    source_type: str
    description: str = ""
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""
    fetch_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessedArticle:
    title: str
    url: str
    source_name: str
    source_type: str
    description: str = ""
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""
    fetch_timestamp: Optional[datetime] = None
    category: str = "其他"
    chinese_summary: str = ""
    importance_score: float = 5.0
    processing_timestamp: Optional[datetime] = None


@dataclass
class Report:
    report_date: date
    generated_at: datetime = field(default_factory=datetime.now)
    articles: list[ProcessedArticle] = field(default_factory=list)
    categories: dict[str, list[ProcessedArticle]] = field(default_factory=dict)
    top_stories: list[ProcessedArticle] = field(default_factory=list)
    github_repos: list[ProcessedArticle] = field(default_factory=list)
    paper_rankings: list[ProcessedArticle] = field(default_factory=list)
    source_stats: dict[str, int] = field(default_factory=dict)
    category_stats: dict[str, int] = field(default_factory=dict)
    total_fetched: int = 0
    total_deduped: int = 0
    total_published: int = 0
    failed_sources: list[dict] = field(default_factory=list)
