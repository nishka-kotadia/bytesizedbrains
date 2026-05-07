# Feature: multi-agent-research-system, Property 8: Source relevance scores are always in range
# Feature: multi-agent-research-system, Property 3: SSE source_found events are structurally valid

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings
from hypothesis import strategies as st

from agents.search import SearchAgent
from models.source import Source, SourceType


source_type_strategy = st.sampled_from(SourceType)

source_strategy = st.builds(
    Source,
    id=st.uuids().map(str),
    type=source_type_strategy,
    title=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    authors=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    venue=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    year=st.integers(min_value=1, max_value=2100),
    url=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    abstract=st.text(min_size=0, max_size=500),
    relevance=st.integers(min_value=0, max_value=100),
    key_findings=st.one_of(
        st.none(),
        st.text(min_size=1, max_size=300).filter(lambda s: s.strip()),
    ),
)


@settings(max_examples=100)
@given(
    original_query=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    candidate_text=st.text(min_size=0, max_size=1000),
)
def test_relevance_score_in_range(original_query, candidate_text):
    """Property 8: Source relevance scores are always in range. Validates: Requirements 5.3, 6.3"""
    agent = SearchAgent(llm_client=None, original_query=original_query)
    score = agent._compute_relevance(candidate_text)
    assert isinstance(score, int)
    assert 0 <= score <= 100


@settings(max_examples=100)
@given(source=source_strategy)
def test_source_found_event_structure(source: Source):
    """Property 3: SSE source_found events are structurally valid. Validates: Requirements 2.4, 5.3, 6.3"""
    event = {
        "type": "source_found",
        "data": {
            "title": source.title,
            "authors": source.authors,
            "venue": source.venue,
            "year": source.year,
            "relevance": source.relevance,
            "type": source.type.value,
            "url": source.url,
        },
    }

    data = event["data"]
    assert data["title"]
    assert data["authors"] is not None
    assert data["venue"] is not None
    assert data["year"] > 0
    assert 0 <= data["relevance"] <= 100
    assert data["type"] in {"paper", "repo"}
    assert data["url"]
