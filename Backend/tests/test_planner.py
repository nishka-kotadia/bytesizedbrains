# Feature: multi-agent-research-system, Property 6: Planner task count respects the config bound
# Feature: multi-agent-research-system, Property 7: Planner tasks are ordered by priority descending

"""
Property tests for the PlannerAgent.

Property 6: Planner task count respects the config bound
Property 7: Planner tasks are ordered by priority descending

Validates: Requirements 4.2, 4.3
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.planner import PlannerAgent
from models.config import Config


def make_mock_response(sub_questions: list[str], n_tasks_per_question: int = 2) -> str:
    tasks = []
    for i, q in enumerate(sub_questions):
        for target in ["arxiv", "github"]:
            tasks.append(
                {
                    "sub_question": q,
                    "target": target,
                    "query": f"{q} {target}",
                    "priority": (i % 10) + 1,
                }
            )
    return json.dumps(tasks[: n_tasks_per_question * len(sub_questions)])


@settings(max_examples=100)
@given(
    sub_questions=st.lists(
        st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
        min_size=1,
        max_size=10,
    ),
    max_sources=st.integers(min_value=5, max_value=50),
)
def test_planner_task_count_bound(sub_questions: list[str], max_sources: int):
    """Property 6: Planner task count respects the config bound. Validates: Requirements 4.2"""
    config = Config(maxSources=max_sources)
    mock_response = make_mock_response(sub_questions)
    planner = PlannerAgent(llm_client=None)
    with patch.object(PlannerAgent, "_call_llm", new=AsyncMock(return_value=mock_response)):
        result = asyncio.run(planner.plan(sub_questions, config))
    assert len(result) <= config.maxSources * 2, (
        f"Expected at most {config.maxSources * 2} tasks, got {len(result)}"
    )


@settings(max_examples=100)
@given(
    sub_questions=st.lists(
        st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
        min_size=1,
        max_size=10,
    ),
    max_sources=st.integers(min_value=5, max_value=50),
)
def test_planner_task_ordering(sub_questions: list[str], max_sources: int):
    """Property 7: Planner tasks are ordered by priority descending. Validates: Requirements 4.3"""
    config = Config(maxSources=max_sources)
    mock_response = make_mock_response(sub_questions)
    planner = PlannerAgent(llm_client=None)
    with patch.object(PlannerAgent, "_call_llm", new=AsyncMock(return_value=mock_response)):
        result = asyncio.run(planner.plan(sub_questions, config))
    for i in range(len(result) - 1):
        assert result[i].priority >= result[i + 1].priority, (
            f"Tasks not sorted by priority descending at index {i}: "
            f"priority[{i}]={result[i].priority} < priority[{i + 1}]={result[i + 1].priority}"
        )
