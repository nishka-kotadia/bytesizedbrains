# Feature: multi-agent-research-system, Property 9: Source deduplication removes all title duplicates
# Feature: multi-agent-research-system, Property 10: Analyzer output is sorted by relevance descending
# Feature: multi-agent-research-system, Property 11: Analyzer output respects the maxSources bound

import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.analyzer import AnalyzerAgent
from models.config import Config
from models.source import Source, SourceType


def _make_source(title: str = "Test Paper", relevance: int = 50, source_id: str | None = None) -> Source:
    return Source(
        id=source_id or title,
        type=SourceType.paper,
        title=title,
        authors="Author One",
        venue="arXiv",
        year=2024,
        url=f"https://example.com/{title}",
        abstract=f"Abstract for {title}.",
        relevance=relevance,
    )


def _make_config(max_sources: int = 20) -> Config:
    return Config(maxSources=max_sources)


_source_strategy = st.builds(
    Source,
    id=st.text(min_size=1, max_size=50),
    type=st.just(SourceType.paper),
    title=st.text(min_size=1, max_size=100),
    authors=st.just("Author"),
    venue=st.just("arXiv"),
    year=st.integers(min_value=2000, max_value=2024),
    url=st.just("https://example.com"),
    abstract=st.just("Abstract text."),
    relevance=st.integers(min_value=0, max_value=100),
)

_config_strategy = st.builds(Config, maxSources=st.integers(min_value=5, max_value=50))


@settings(max_examples=100)
@given(sources=st.lists(_source_strategy, min_size=0, max_size=30))
def test_deduplication_removes_all_title_duplicates(sources: list[Source]):
    """Property 9: Source deduplication removes all title duplicates. Validates: Requirements 7.1"""
    agent = AnalyzerAgent(llm_client=None)
    result = agent._deduplicate(sources)
    normalized_titles = [agent._normalize_title(s.title) for s in result]
    assert len(normalized_titles) == len(set(normalized_titles))


@settings(max_examples=100)
@given(sources=st.lists(_source_strategy, min_size=0, max_size=30))
def test_analyzer_output_sorted_by_relevance_descending(sources: list[Source]):
    """Property 10: Analyzer output is sorted by relevance descending. Validates: Requirements 7.2"""
    agent = AnalyzerAgent(llm_client=None)
    deduplicated = agent._deduplicate(sources)
    deduplicated.sort(key=lambda s: s.relevance, reverse=True)
    for i in range(len(deduplicated) - 1):
        assert deduplicated[i].relevance >= deduplicated[i + 1].relevance


@settings(max_examples=100)
@given(
    sources=st.lists(_source_strategy, min_size=0, max_size=60),
    config=_config_strategy,
)
def test_analyzer_output_respects_max_sources_bound(sources: list[Source], config: Config):
    """Property 11: Analyzer output respects the maxSources bound. Validates: Requirements 7.3"""
    agent = AnalyzerAgent(llm_client=None)
    with patch.object(AnalyzerAgent, "_call_llm_for_findings", new=AsyncMock(return_value="Summary.")):
        result = asyncio.run(agent.analyze(sources, config))
    assert len(result) <= config.maxSources
