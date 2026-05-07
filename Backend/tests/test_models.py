# Feature: multi-agent-research-system, Property 2: Invalid queries are always rejected

import pytest
from pydantic import ValidationError
from hypothesis import given, settings
from hypothesis import strategies as st

import sys
import os

# Ensure Backend/ is on the path so `models.events` can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.events import ResearchRequest


# --- Property 2: Invalid queries are always rejected ---
# Validates: Requirements 1.3, 1.4


@settings(max_examples=100)
@given(query=st.just(""))
def test_empty_string_query_raises_validation_error(query):
    """Empty string queries must be rejected by ResearchRequest."""
    with pytest.raises(ValidationError):
        ResearchRequest(query=query)


@settings(max_examples=100)
@given(
    query=st.text(
        alphabet=st.characters(whitelist_categories=("Zs", "Cc")),
        min_size=1,
    )
)
def test_whitespace_only_query_raises_validation_error(query):
    """Whitespace-only string queries must be rejected by ResearchRequest."""
    with pytest.raises(ValidationError):
        ResearchRequest(query=query)


@settings(max_examples=100)
@given(query=st.text(min_size=2001))
def test_too_long_query_raises_validation_error(query):
    """Queries longer than 2000 characters must be rejected by ResearchRequest."""
    with pytest.raises(ValidationError):
        ResearchRequest(query=query)
