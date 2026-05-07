# Feature: multi-agent-research-system, Property 14: Session persistence round-trip

import asyncio
import sys
import os

# Ensure Backend/ is on the path so db and models can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.database as database_module
from db.models import Base
from models.config import Config, DepthLevel, OutputFormat, SourceTypes
from models.session import ResearchSession, SessionStatus
from models.source import Source, SourceType


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

source_type_strategy = st.sampled_from(SourceType)

source_strategy = st.builds(
    Source,
    id=st.uuids().map(str),
    type=source_type_strategy,
    title=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    authors=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    venue=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    year=st.integers(min_value=1900, max_value=2100),
    url=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    abstract=st.text(min_size=1, max_size=500).filter(lambda s: s.strip()),
    relevance=st.integers(min_value=0, max_value=100),
    key_findings=st.one_of(
        st.none(),
        st.text(min_size=1, max_size=300).filter(lambda s: s.strip()),
    ),
)

source_types_strategy = st.builds(
    SourceTypes,
    papers=st.booleans(),
    web=st.booleans(),
    patents=st.booleans(),
    news=st.booleans(),
)

config_strategy = st.builds(
    Config,
    depth=st.sampled_from(DepthLevel),
    sources=source_types_strategy,
    maxSources=st.integers(min_value=5, max_value=50),
    format=st.sampled_from(OutputFormat),
)

session_strategy = st.builds(
    ResearchSession,
    session_id=st.uuids().map(str),
    query=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    config=config_strategy,
    status=st.sampled_from(SessionStatus),
    sources=st.lists(source_strategy, max_size=5),
    report=st.one_of(st.none(), st.text(min_size=1, max_size=500)),
    error_msg=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    created_at=st.datetimes(allow_imaginary=False),
    completed_at=st.one_of(st.none(), st.datetimes(allow_imaginary=False)),
)


# ---------------------------------------------------------------------------
# Helper: set up a fresh in-memory database and patch the module-level engine
# ---------------------------------------------------------------------------

async def _setup_in_memory_db():
    """Create a fresh in-memory SQLite engine, patch the database module, and
    initialise the schema. Returns the engine so the caller can dispose it."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False
    )
    test_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )

    # Patch module-level globals so save_session / get_session use our engine
    database_module.engine = test_engine
    database_module.AsyncSessionLocal = test_session_factory

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return test_engine


async def _teardown_db(engine):
    await engine.dispose()


# ---------------------------------------------------------------------------
# Property 14: Session persistence round-trip
# Validates: Requirements 10.1, 10.3
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(session=session_strategy)
def test_session_persistence_round_trip(session: ResearchSession):
    """For any ResearchSession saved to the database, retrieving it by
    session_id SHALL return a record whose query, config, sources, and report
    fields are equal to the values that were saved.

    **Validates: Requirements 10.1, 10.3**
    """

    async def _run():
        engine = await _setup_in_memory_db()
        try:
            # Import here to pick up the patched module globals
            from db.database import save_session, get_session

            await save_session(session)
            result = await get_session(session.session_id)

            assert result is not None, (
                f"get_session returned None for session_id={session.session_id!r}"
            )
            assert result.query == session.query, (
                f"query mismatch: {result.query!r} != {session.query!r}"
            )
            assert result.config == session.config, (
                f"config mismatch: {result.config} != {session.config}"
            )
            assert result.sources == session.sources, (
                f"sources mismatch: {result.sources} != {session.sources}"
            )
            assert result.report == session.report, (
                f"report mismatch: {result.report!r} != {session.report!r}"
            )
        finally:
            await _teardown_db(engine)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 15: History is ordered by completion time descending
# Feature: multi-agent-research-system, Property 15: History is ordered by completion time descending
# Validates: Requirements 10.2
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    timestamps=st.lists(
        st.datetimes(allow_imaginary=False),
        min_size=2,
        max_size=10,
        unique=True,
    )
)
def test_history_ordered_by_completion_time_descending(timestamps: list):
    """For any set of completed ResearchSession records saved to the database,
    list_sessions() SHALL return them ordered such that
    sessions[i].completed_at >= sessions[i+1].completed_at for all valid i.

    **Validates: Requirements 10.2**
    """

    async def _run():
        engine = await _setup_in_memory_db()
        try:
            from db.database import save_session, list_sessions

            # Build one session per timestamp, each with a distinct session_id
            # and completed_at set to the generated timestamp (not None)
            sessions_to_save = []
            for i, ts in enumerate(timestamps):
                # Use session_strategy to get a valid base session, then override
                # session_id and completed_at to ensure uniqueness and non-None
                import uuid
                base = ResearchSession(
                    session_id=str(uuid.uuid4()),
                    query="test query",
                    config=Config(),
                    status=SessionStatus.complete,
                    sources=[],
                    report=None,
                    error_msg=None,
                    created_at=ts,
                    completed_at=ts,
                )
                sessions_to_save.append(base)

            # Save all sessions
            for s in sessions_to_save:
                await save_session(s)

            # Retrieve history
            result = await list_sessions()

            # All saved sessions have completed_at set, so all should appear
            assert len(result) == len(timestamps), (
                f"Expected {len(timestamps)} sessions, got {len(result)}"
            )

            # Verify descending order
            for i in range(len(result) - 1):
                assert result[i].completed_at >= result[i + 1].completed_at, (
                    f"Order violation at index {i}: "
                    f"{result[i].completed_at} < {result[i + 1].completed_at}"
                )
        finally:
            await _teardown_db(engine)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 16: Deleted sessions are not retrievable
# Feature: multi-agent-research-system, Property 16: Deleted sessions are not retrievable
# Validates: Requirements 10.5
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(session=session_strategy)
def test_deleted_session_not_retrievable(session: ResearchSession):
    """For any ResearchSession saved to the database, after deleting it:
    - delete_session() SHALL return True on the first call
    - get_session() SHALL return None after deletion
    - delete_session() SHALL return False on a second call (already deleted)

    **Validates: Requirements 10.5**
    """

    async def _run():
        engine = await _setup_in_memory_db()
        try:
            from db.database import save_session, get_session, delete_session

            # Save the session
            await save_session(session)

            # First delete should succeed
            first_delete = await delete_session(session.session_id)
            assert first_delete is True, (
                f"Expected delete_session to return True on first call, "
                f"got {first_delete!r} for session_id={session.session_id!r}"
            )

            # Session should no longer be retrievable
            retrieved = await get_session(session.session_id)
            assert retrieved is None, (
                f"Expected get_session to return None after deletion, "
                f"got {retrieved!r} for session_id={session.session_id!r}"
            )

            # Second delete should return False (already gone)
            second_delete = await delete_session(session.session_id)
            assert second_delete is False, (
                f"Expected delete_session to return False on second call, "
                f"got {second_delete!r} for session_id={session.session_id!r}"
            )
        finally:
            await _teardown_db(engine)

    asyncio.run(_run())
