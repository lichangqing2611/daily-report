import asyncio
import logging
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.cache import compute_content_hash
from src.models import Article
from src.sources.base import SourcePlugin, SourceError

logger = logging.getLogger(__name__)

BASE_URL = "https://hub.baai.ac.cn"


class BAAIHub(SourcePlugin):
    @property
    def name(self) -> str:
        return "BAAI Hub"

    async def fetch(self) -> list[Article]:
        max_papers = self._config.get("max_papers", 30)
        article_list: list[Article] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed, falling back to static scrape (10 papers max)")
            return await self._fetch_static(max_papers)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(
                    f"{BASE_URL}/papers?model=hotness&time=week",
                    wait_until="networkidle",
                    timeout=30000,
                )

                # Scroll down to trigger infinite scroll until we have enough papers
                prev_count = 0
                for _ in range(10):  # Max 10 scroll attempts
                    paper_items = await page.query_selector_all(".paper-item")
                    current_count = len(paper_items)
                    if current_count >= max_papers:
                        break
                    if current_count == prev_count:
                        # No new papers loaded, wait a bit more
                        await asyncio.sleep(1)
                        paper_items = await page.query_selector_all(".paper-item")
                        if len(paper_items) == prev_count:
                            break
                    prev_count = current_count
                    # Scroll to bottom
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                # Get the full HTML after scrolling
                html = await page.content()
                await browser.close()
        except Exception as e:
            logger.warning(f"Playwright fetch failed ({e}), falling back to static scrape")
            return await self._fetch_static(max_papers)

        soup = BeautifulSoup(html, "html.parser")
        paper_items = soup.select(".paper-item")[:max_papers]

        for paper in paper_items:
            try:
                link_el = paper.select_one("a[href]")
                if not link_el:
                    continue
                paper_url = urljoin(BASE_URL, link_el["href"])

                title_el = paper.select_one(".paper-item-title")
                title = title_el.get_text(strip=True) if title_el else ""

                summary_el = paper.select_one(".paper-item-summary")
                summary = ""
                if summary_el:
                    summary = summary_el.get("title", "") or summary_el.get_text(strip=True)

                content_hash = compute_content_hash(title, paper_url)
                article_list.append(Article(
                    title=title,
                    url=paper_url,
                    source_name=self.name,
                    source_type="paper_ranking",
                    description=summary,
                    content_hash=content_hash,
                    fetch_timestamp=datetime.now(),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse BAAI Hub paper: {e}")
                continue

        logger.info(f"BAAI Hub: fetched {len(article_list)} papers")
        return article_list

    async def _fetch_static(self, max_papers: int) -> list[Article]:
        """Fallback: static HTML scrape (limited to initial SSR render)."""
        import httpx

        article_list: list[Article] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{BASE_URL}/papers",
                    params={"model": "hotness", "time": "week"},
                    follow_redirects=True,
                )
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            paper_items = soup.select(".paper-item")[:max_papers]

            for paper in paper_items:
                try:
                    link_el = paper.select_one("a[href]")
                    if not link_el:
                        continue
                    paper_url = urljoin(BASE_URL, link_el["href"])

                    title_el = paper.select_one(".paper-item-title")
                    title = title_el.get_text(strip=True) if title_el else ""

                    summary_el = paper.select_one(".paper-item-summary")
                    summary = ""
                    if summary_el:
                        summary = summary_el.get("title", "") or summary_el.get_text(strip=True)

                    content_hash = compute_content_hash(title, paper_url)
                    article_list.append(Article(
                        title=title,
                        url=paper_url,
                        source_name=self.name,
                        source_type="paper_ranking",
                        description=summary,
                        content_hash=content_hash,
                        fetch_timestamp=datetime.now(),
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse BAAI Hub paper: {e}")
                    continue

        except Exception as e:
            logger.error(f"BAAI Hub static fetch failed: {e}")
            raise SourceError(f"BAAI Hub error: {e}") from e

        logger.info(f"BAAI Hub (static): fetched {len(article_list)} papers")
        return article_list

    async def validate(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{BASE_URL}/papers", follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False
