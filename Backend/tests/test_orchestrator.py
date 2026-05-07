# Feature: multi-agent-research-system, Property 4: SSE step events are structurally valid

import asyncio
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator import Orchestrator
from models.session import ResearchSession, SessionStatus
from models.config import Config, DepthLevel, OutputFormat, SourceTypes


def make_config(depth=DepthLevel.standard) -> Config:
    return Config(depth=depth, sources=SourceTypes(), maxSources=20, format=OutputFormat.markdown)


def make_session(query: str, config: Config) -> ResearchSession:
    return ResearchSession(
        session_id="test-session-id",
        query=query,
        config=config,
        status=SessionStatus.pending,
        created_at=datetime.now(tz=timezone.utc),
    )


def run_pipeline_and_collect_events(query: str, config: Config) -> list[dict]:
    session = make_session(query, config)
    with patch("agents.orchestrator.DecomposerAgent") as MockDecomposer, \
         patch("agents.orchestrator.PlannerAgent") as MockPlanner, \
         patch("agents.orchestrator.SearchAgent") as MockSearch, \
         patch("agents.orchestrator.AnalyzerAgent") as MockAnalyzer, \
         patch("agents.orchestrator.GapDetectorAgent") as MockGapDetector, \
         patch("agents.orchestrator.IdeaGeneratorAgent") as MockIdeaGenerator, \
         patch("agents.orchestrator.SynthesizerAgent") as MockSynthesizer, \
         patch("agents.orchestrator.db") as mock_db:
        MockDecomposer.return_value.decompose = AsyncMock(return_value=["sub-q1", "sub-q2", "sub-q3"])
        MockPlanner.return_value.plan = AsyncMock(return_value=[])
        MockSearch.return_value.search = AsyncMock(return_value=[])
        MockAnalyzer.return_value.analyze = AsyncMock(return_value=[])
        MockGapDetector.return_value.detect_gaps = AsyncMock(return_value=[])
        MockIdeaGenerator.return_value.generate_ideas = AsyncMock(return_value=[])
        MockSynthesizer.return_value.synthesize = AsyncMock(return_value="Report text")
        mock_db.save_session = AsyncMock()
        queue: asyncio.Queue = asyncio.Queue()
        orchestrator = Orchestrator(llm_client=None)
        asyncio.run(orchestrator.run_pipeline(session, queue))
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
    return events


@settings(max_examples=50, deadline=None)
@given(
    query=st.text(min_size=1, max_size=2000).filter(lambda s: s.strip()),
    depth=st.sampled_from(list(DepthLevel)),
)
def test_step_events_are_structurally_valid(query: str, depth: DepthLevel):
    """Property 4: SSE step events are structurally valid. Validates: Requirements 2.2, 2.3"""
    config = make_config(depth=depth)
    events = run_pipeline_and_collect_events(query, config)

    step_start_events = [e for e in events if e.get("type") == "step_start"]
    step_complete_events = [e for e in events if e.get("type") == "step_complete"]

    # The pipeline has 8 steps after OpenClaw integration:
    # decompose, plan, search, analyze, build_graph, detect_gaps, generate_ideas, synthesize
    assert len(step_start_events) == 8, f"Expected 8 step_start events, got {len(step_start_events)}"
    assert len(step_complete_events) == 8, f"Expected 8 step_complete events, got {len(step_complete_events)}"

    for event in step_start_events:
        data = event["data"]
        assert isinstance(data["step_name"], str) and len(data["step_name"]) > 0
        assert isinstance(data["step_index"], int) and 0 <= data["step_index"] <= 7
        assert isinstance(data["label"], str) and len(data["label"]) > 0

    for event in step_complete_events:
        data = event["data"]
        assert isinstance(data["step_name"], str) and len(data["step_name"]) > 0
        assert isinstance(data["step_index"], int) and 0 <= data["step_index"] <= 7
        assert isinstance(data["summary"], str) and len(data["summary"]) > 0
