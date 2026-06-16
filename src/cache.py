import hashlib
import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path

from src.models import Article


class CacheManager:
    def __init__(self, db_path: str = "./cache/articles.db", ttl_hours: int = 72):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self.ttl_hours = ttl_hours
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_history (
                url TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                source_name TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                published_at TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS report_index (
                report_date DATE PRIMARY KEY,
                file_path TEXT NOT NULL,
                article_count INTEGER,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    def is_duplicate(self, url: str) -> bool:
        cutoff = datetime.now() - timedelta(hours=self.ttl_hours)
        row = self._conn.execute(
            "SELECT 1 FROM fetch_history WHERE url = ? AND fetched_at > ?",
            (url, cutoff.isoformat()),
        ).fetchone()
        return row is not None

    def is_hash_duplicate(self, content_hash: str) -> bool:
        cutoff = datetime.now() - timedelta(hours=self.ttl_hours)
        row = self._conn.execute(
            "SELECT 1 FROM fetch_history WHERE content_hash = ? AND fetched_at > ?",
            (content_hash, cutoff.isoformat()),
        ).fetchone()
        return row is not None

    def mark_fetched(self, article: Article):
        self._conn.execute(
            """INSERT OR REPLACE INTO fetch_history
               (url, content_hash, source_name, fetched_at, title, published_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                article.url,
                article.content_hash,
                article.source_name,
                article.fetch_timestamp.isoformat() if article.fetch_timestamp else datetime.now().isoformat(),
                article.title,
                article.published_at.isoformat() if article.published_at else None,
            ),
        )
        self._conn.commit()

    def deduplicate(self, articles: list[Article]) -> tuple[list[Article], int]:
        new_articles = []
        deduped_count = 0
        for article in articles:
            if self.is_duplicate(article.url) or self.is_hash_duplicate(article.content_hash):
                deduped_count += 1
            else:
                new_articles.append(article)
                self.mark_fetched(article)
        return new_articles, deduped_count

    def prune_expired(self) -> int:
        cutoff = datetime.now() - timedelta(hours=self.ttl_hours)
        cursor = self._conn.execute(
            "DELETE FROM fetch_history WHERE fetched_at < ?",
            (cutoff.isoformat(),),
        )
        self._conn.commit()
        return cursor.rowcount

    def record_report(self, report_date: date, file_path: str, article_count: int):
        self._conn.execute(
            """INSERT OR REPLACE INTO report_index
               (report_date, file_path, article_count, generated_at)
               VALUES (?, ?, ?, ?)""",
            (report_date.isoformat(), file_path, article_count, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_recent_reports(self, days: int = 7) -> list[dict]:
        cutoff = (datetime.now() - timedelta(days=days)).date()
        rows = self._conn.execute(
            "SELECT report_date, file_path, article_count, generated_at FROM report_index WHERE report_date >= ? ORDER BY report_date DESC",
            (cutoff.isoformat(),),
        ).fetchall()
        return [
            {"report_date": r[0], "file_path": r[1], "article_count": r[2], "generated_at": r[3]}
            for r in rows
        ]


def compute_content_hash(title: str, description: str) -> str:
    raw = f"{title}|{description}".strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
