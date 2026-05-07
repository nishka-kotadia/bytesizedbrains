# Feature: multi-agent-research-system, Property 5: Decomposer sub-question count is bounded

"""
Property tests for the DecomposerAgent.

Property 5: Decomposer sub-question count is bounded
  For any non-empty research query string of at most 2000 characters, the
  Decomposer Agent SHALL return a list of between 3 and 7 sub-questions,
  each no longer than 200 characters.

Validates: Requirements 3.1, 3.2
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Add Backend/ to sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.decomposer import DecomposerAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_numbered_list(n: int) -> str:
    """Return a valid numbered list of *n* sub-questions, each ≤ 200 chars."""
    lines = [f"{i + 1}. What is the significance of aspect {i + 1} in this topic?" for i in range(n)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Property 5: Decomposer sub-question count is bounded
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    query=st.text(min_size=1, max_size=2000).filter(lambda s: s.strip()),
    n_questions=st.integers(min_value=3, max_value=7),
)
def test_decomposer_sub_question_count_is_bounded(query: str, n_questions: int):
    """
    Property 5: Decomposer sub-question count is bounded.

    For any valid query string, when the LLM returns a valid numbered list of
    3–7 sub-questions, decompose() must return a list whose length is in [3, 7]
    and each item must be ≤ 200 characters.

    Validates: Requirements 3.1, 3.2
    """
    mock_response = _make_numbered_list(n_questions)

    decomposer = DecomposerAgent(llm_client=None)

    with patch.object(
        DecomposerAgent,
        "_call_llm",
        new=AsyncMock(return_value=mock_response),
    ):
        result = asyncio.run(decomposer.decompose(query))

    assert 3 <= len(result) <= 7, (
        f"Expected 3–7 sub-questions, got {len(result)}"
    )
    for item in result:
        assert len(item) <= 200, (
            f"Sub-question exceeds 200 chars (len={len(item)}): {item!r}"
        )


# ---------------------------------------------------------------------------
# Fallback behaviour: LLM returns fewer than 3 sub-questions on both attempts
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    query=st.text(min_size=1, max_size=2000).filter(lambda s: s.strip()),
)
def test_decomposer_fallback_when_llm_returns_too_few(query: str):
    """
    When the LLM returns fewer than 3 sub-questions on both attempts, the
    Decomposer must fall back to returning [query].

    Validates: Requirements 3.3 (fallback behaviour)
    """
    # Return only 2 sub-questions — below the minimum of 3
    insufficient_response = "1. What is aspect one?\n2. What is aspect two?"

    decomposer = DecomposerAgent(llm_client=None)

    with patch.object(
        DecomposerAgent,
        "_call_llm",
        new=AsyncMock(return_value=insufficient_response),
    ):
        result = asyncio.run(decomposer.decompose(query))

    assert result == [query], (
        f"Expected fallback to [query], got {result!r}"
    )
