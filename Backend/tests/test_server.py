# Feature: multi-agent-research-system, Property 1: Valid queries always produce unique session IDs

import sys
import os
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from api.server import app


def _is_valid_query(s: str) -> bool:
    """Return True if the string would pass ResearchRequest validation."""
    stripped = "".join(
        ch for ch in s
        if unicodedata.category(ch) not in ("Zs", "Cc") and not ch.isspace()
    )
    return bool(stripped)


_valid_query = st.text(min_size=1, max_size=200).filter(_is_valid_query)


@settings(max_examples=100)
@given(query1=_valid_query, query2=_valid_query)
def test_valid_queries_produce_unique_session_ids(query1: str, query2: str):
    """Property 1: Valid queries always produce unique session IDs. Validates: Requirements 1.2"""
    # Patch LLM_API_KEY at the server module level (it's a module-level constant
    # read at import time from api.llm, so we patch the name in api.server directly).
    with patch("api.server.LLM_API_KEY", "test-key"), \
         patch("api.server.get_llm_client", return_value=None), \
         patch("api.server.Orchestrator") as MockOrch:
        MockOrch.return_value.run_pipeline = AsyncMock()

        client = TestClient(app)

        resp1 = client.post("/api/research", json={"query": query1})
        resp2 = client.post("/api/research", json={"query": query2})

        assert resp1.status_code == 200, f"Expected 200 for query1={query1!r}, got {resp1.status_code}: {resp1.text}"
        assert resp2.status_code == 200, f"Expected 200 for query2={query2!r}, got {resp2.status_code}: {resp2.text}"

        id1 = resp1.json()["session_id"]
        id2 = resp2.json()["session_id"]

        assert id1 != id2, f"Expected unique session IDs, got {id1!r} == {id2!r}"
