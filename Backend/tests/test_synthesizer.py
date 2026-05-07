# Feature: multi-agent-research-system, Property 12: Report contains all required sections in order
# Feature: multi-agent-research-system, Property 13: Report word count respects depth configuration

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.synthesizer import DEPTH_WORD_BOUNDS, SynthesizerAgent
from models.config import Config, DepthLevel
from models.source import Source, SourceType

_source_strategy = st.builds(
    Source,
    id=st.text(min_size=1, max_size=50),
    type=st.just(SourceType.paper),
    title=st.text(min_size=1, max_size=100),
    authors=st.just("Author One"),
    venue=st.just("arXiv"),
    year=st.integers(min_value=2000, max_value=2024),
    url=st.just("https://example.com/paper"),
    abstract=st.just("Abstract text."),
    relevance=st.integers(min_value=0, max_value=100),
)

VALID_REPORT = """## Executive Summary
This is the executive summary.

## Key Findings
These are the key findings.

## Research Gaps
These are the research gaps.

## Conclusion
This is the conclusion.
"""

REQUIRED_HEADINGS = ["Executive Summary", "Key Findings", "Research Gaps", "Conclusion"]


@settings(max_examples=100)
@given(sources=st.lists(_source_strategy, min_size=1, max_size=10))
def test_report_contains_required_sections_in_order(sources: list[Source]):
    """Property 12: Report contains all required sections in order. Validates: Requirements 8.2"""
    config = Config()
    agent = SynthesizerAgent(llm_client=None)
    with patch.object(SynthesizerAgent, "_call_llm", new=AsyncMock(return_value=VALID_REPORT)):
        result = asyncio.run(agent.synthesize(sources, config))
    assert isinstance(result, str)
    positions = [result.find(heading) for heading in REQUIRED_HEADINGS]
    assert all(p >= 0 for p in positions), f"Not all sections found. Positions: {dict(zip(REQUIRED_HEADINGS, positions))}"
    assert positions == sorted(positions), f"Sections not in correct order. Positions: {dict(zip(REQUIRED_HEADINGS, positions))}"


def test_depth_word_bounds_are_correct():
    """Property 13 (unit): DEPTH_WORD_BOUNDS has correct values. Validates: Requirements 8.4, 9.2, 9.3, 9.4"""
    assert DEPTH_WORD_BOUNDS[DepthLevel.quick] == (400, 800)
    assert DEPTH_WORD_BOUNDS[DepthLevel.standard] == (800, 1500)
    assert DEPTH_WORD_BOUNDS[DepthLevel.deep] == (1500, 3000)


@settings(max_examples=50)
@given(
    sources=st.lists(_source_strategy, min_size=1, max_size=5),
    depth=st.sampled_from(DepthLevel),
)
def test_report_word_count_respects_depth(sources: list[Source], depth: DepthLevel):
    """Property 13: Report word count respects depth configuration. Validates: Requirements 8.4, 9.2, 9.3, 9.4"""
    min_words, max_words = DEPTH_WORD_BOUNDS[depth]
    body_words = " ".join(["word"] * min_words)
    mock_report = (
        f"## Executive Summary\n{body_words}\n\n"
        "## Key Findings\nFindings here.\n\n"
        "## Research Gaps\nGaps here.\n\n"
        "## Conclusion\nConclusion here.\n"
    )
    config = Config(depth=depth)
    agent = SynthesizerAgent(llm_client=None)
    with patch.object(SynthesizerAgent, "_call_llm", new=AsyncMock(return_value=mock_report)):
        result = asyncio.run(agent.synthesize(sources, config))
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0
    word_count = len(result.split())
    assert word_count >= min_words
    assert word_count <= max_words + 50  # +50 for section headings
