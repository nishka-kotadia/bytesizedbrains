"""
Search Agent for the Multi-Agent Research Intelligence System.

Executes search tasks against arXiv and GitHub, scores each result for
relevance against the original research query, and pushes ``source_found``
SSE events to the session queue as sources are discovered.
"""

import asyncio
import logging
import re
import string

import arxiv
import httpx

from models.config import Config
from models.search import SearchTarget, SearchTask
from models.source import Source, SourceType
from knowledge_graph.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

_ARXIV_TIMEOUT_SECONDS = 30
_GITHUB_TIMEOUT_SECONDS = 10
_GITHUB_RATE_LIMIT_WAIT_SECONDS = 60
_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

# Per-task result cap — keeps each arXiv call fast
_RESULTS_PER_TASK = 5
# Max concurrent search tasks — prevents overwhelming arXiv rate limits
_MAX_CONCURRENT_TASKS = 4
# Hard cap on tasks processed regardless of planner output
_MAX_TASKS = 8


class SearchAgent:
    """Searches arXiv and GitHub for sources relevant to a research query."""

    def __init__(
        self,
        llm_client,
        original_query: str,
        embedding_service: EmbeddingService = None,
    ) -> None:
        self.llm_client = llm_client
        self.original_query = original_query
        self.embedding_service = embedding_service  # may be None — embeddings are optional

    async def search(
        self,
        tasks: list[SearchTask],
        config: Config,
        queue: asyncio.Queue,
    ) -> list[Source]:
        """Execute search tasks concurrently and return combined sources."""
        # Cap tasks to avoid timeout
        capped_tasks = tasks[:_MAX_TASKS]
        if len(tasks) > _MAX_TASKS:
            logger.info("SearchAgent: capping tasks %d→%d", len(tasks), _MAX_TASKS)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_TASKS)
        all_sources: list[Source] = []

        async def run_task(task: SearchTask) -> list[Source]:
            async with semaphore:
                if task.target == SearchTarget.arxiv:
                    return await self._search_arxiv(task, config)
                else:
                    return await self._search_github(task, config)

        results = await asyncio.gather(*[run_task(t) for t in capped_tasks], return_exceptions=True)

        for outcome in results:
            if isinstance(outcome, Exception):
                logger.warning("SearchAgent: task failed: %s", outcome)
                continue
            for source in outcome:
                if self.embedding_service is not None:
                    try:
                        source.embedding = await self.embedding_service.embed_single(
                            f"{source.title}. {source.abstract or ''}"
                        )
                    except Exception as e:
                        logger.warning("Embedding failed for %s: %s", source.title, e)
                await queue.put({
                    "type": "source_found",
                    "data": {
                        "title": source.title, "authors": source.authors,
                        "venue": source.venue, "year": source.year,
                        "relevance": source.relevance, "type": source.type.value,
                        "url": source.url,
                    },
                })
            all_sources.extend(outcome)

        return all_sources

    def _compute_relevance(self, text: str) -> int:
        """Compute a 0–100 relevance score for *text* against the original query."""
        query_words = self._tokenize(self.original_query)
        text_words = self._tokenize(text)
        common_words = query_words & text_words
        overlap_ratio = len(common_words) / max(len(query_words), 1)
        return min(100, int(overlap_ratio * 100))

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Lowercase and strip punctuation from *text*, returning a word set."""
        lowered = text.lower()
        no_punct = lowered.translate(str.maketrans("", "", string.punctuation))
        return set(no_punct.split())

    async def _search_arxiv(
        self, task: SearchTask, config: Config
    ) -> list[Source]:
        """Search arXiv for papers matching *task.query*."""
        if not config.sources.papers:
            return []

        for attempt in range(1, 3):
            try:
                sources = await asyncio.wait_for(
                    self._fetch_arxiv(task.query, _RESULTS_PER_TASK),
                    timeout=_ARXIV_TIMEOUT_SECONDS,
                )
                return sources
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "SearchAgent: arXiv attempt %d failed for query %r: %s",
                    attempt, task.query, exc,
                )

        return []

    async def _fetch_arxiv(self, query: str, max_results: int) -> list[Source]:
        """Perform the actual arXiv API call and map results to Source objects."""
        # page_size=max_results avoids fetching 100-result pages when we only need 5
        client = arxiv.Client(page_size=max_results, delay_seconds=1, num_retries=2)
        search = arxiv.Search(query=query, max_results=max_results)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda: list(client.results(search))
        )

        sources: list[Source] = []
        for result in results:
            authors = ", ".join(str(a) for a in result.authors)
            relevance = self._compute_relevance(result.title + " " + result.summary)
            source = Source(
                id=result.entry_id,
                type=SourceType.paper,
                title=result.title,
                authors=authors,
                venue="arXiv",
                year=result.published.year,
                url=result.entry_id,
                abstract=result.summary,
                relevance=relevance,
            )
            sources.append(source)

        return sources

    async def _search_github(
        self, task: SearchTask, config: Config
    ) -> list[Source]:
        """Search GitHub for repositories matching *task.query*."""
        if not config.sources.web:
            return []

        for attempt in range(1, 3):
            try:
                sources = await asyncio.wait_for(
                    self._fetch_github(task.query),
                    timeout=_GITHUB_TIMEOUT_SECONDS,
                )
                return sources
            except _GitHubRateLimitError:
                if attempt == 1:
                    logger.warning(
                        "SearchAgent: GitHub rate limit hit for query %r; waiting %ds.",
                        task.query, _GITHUB_RATE_LIMIT_WAIT_SECONDS,
                    )
                    await asyncio.sleep(_GITHUB_RATE_LIMIT_WAIT_SECONDS)
                else:
                    logger.error(
                        "SearchAgent: GitHub rate limit persists for query %r; returning empty.",
                        task.query,
                    )
                    return []
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "SearchAgent: GitHub attempt %d failed for query %r: %s",
                    attempt, task.query, exc,
                )
                return []

        return []

    async def _fetch_github(self, query: str) -> list[Source]:
        """Perform the actual GitHub Search API call."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _GITHUB_SEARCH_URL,
                params={"q": query, "per_page": 10},
                headers={"Accept": "application/vnd.github+json"},
                timeout=_GITHUB_TIMEOUT_SECONDS,
            )

        if response.status_code == 403:
            raise _GitHubRateLimitError(
                f"GitHub API returned 403 for query {query!r}"
            )

        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        sources: list[Source] = []
        for item in items:
            description = item.get("description") or ""
            updated_at = item.get("updated_at", "")
            year = self._parse_year(updated_at)
            relevance = self._compute_relevance(
                (item.get("full_name") or "") + " " + description
            )
            source = Source(
                id=item.get("full_name", ""),
                type=SourceType.repo,
                title=item.get("full_name", ""),
                authors="",
                venue="GitHub",
                year=year,
                url=item.get("html_url", ""),
                abstract=description,
                relevance=relevance,
            )
            sources.append(source)

        return sources

    @staticmethod
    def _parse_year(iso_date: str) -> int:
        """Extract the year from an ISO 8601 date string."""
        match = re.match(r"(\d{4})", iso_date)
        if match:
            return int(match.group(1))
        return 0


class _GitHubRateLimitError(Exception):
    """Raised internally when the GitHub API returns HTTP 403."""
