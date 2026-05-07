"""
Async SQLAlchemy database layer for the Multi-Agent Research System.

Provides:
- Async engine and session factory
- init_db() to create all tables
- CRUD helpers: save_session, get_session, list_sessions, delete_session
"""

import json
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, ResearchSessionORM
from models.config import Config
from models.events import SessionSummary
from models.session import ResearchSession, SessionStatus
from models.source import Source

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./research.db")

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all ORM-defined tables if they do not already exist.
    
    Also runs lightweight migrations to add new columns to existing tables.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: add gaps_json, ideas_json, graph_json if they don't exist yet
        for col, default in [
            ("gaps_json",  "[]"),
            ("ideas_json", "[]"),
            ("graph_json", "NULL"),
        ]:
            try:
                if col == "graph_json":
                    await conn.exec_driver_sql(
                        f"ALTER TABLE research_sessions ADD COLUMN {col} TEXT"
                    )
                else:
                    await conn.exec_driver_sql(
                        f"ALTER TABLE research_sessions ADD COLUMN {col} TEXT DEFAULT '{default}'"
                    )
            except Exception:
                pass  # Column already exists


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def save_session(session: ResearchSession) -> None:
    """Upsert a ResearchSession into the database.

    Serialises ``config`` and ``sources`` to JSON before persisting.
    """
    config_json: str = session.config.model_dump_json()
    sources_json: str = json.dumps([s.model_dump() for s in session.sources])
    gaps_json: str = json.dumps(session.gaps or [])
    ideas_json: str = json.dumps(session.ideas or [])
    graph_json: str | None = json.dumps(session.knowledge_graph) if session.knowledge_graph else None

    orm_record = ResearchSessionORM(
        session_id=session.session_id,
        query=session.query,
        config_json=config_json,
        status=session.status.value,
        sources_json=sources_json,
        report=session.report,
        gaps_json=gaps_json,
        ideas_json=ideas_json,
        graph_json=graph_json,
        error_msg=session.error_msg,
        created_at=session.created_at,
        completed_at=session.completed_at,
    )

    async with AsyncSessionLocal() as db:
        await db.merge(orm_record)
        await db.commit()


async def get_session(session_id: str) -> ResearchSession | None:
    """Retrieve a ResearchSession by primary key.

    Returns ``None`` if no matching record exists.
    """
    async with AsyncSessionLocal() as db:
        orm_record: ResearchSessionORM | None = await db.get(
            ResearchSessionORM, session_id
        )

    if orm_record is None:
        return None

    config = Config.model_validate_json(orm_record.config_json)
    sources = [Source.model_validate(s) for s in json.loads(orm_record.sources_json)]
    gaps = json.loads(orm_record.gaps_json or "[]")
    ideas = json.loads(orm_record.ideas_json or "[]")
    knowledge_graph = json.loads(orm_record.graph_json) if orm_record.graph_json else None

    return ResearchSession(
        session_id=orm_record.session_id,
        query=orm_record.query,
        config=config,
        status=SessionStatus(orm_record.status),
        sources=sources,
        report=orm_record.report,
        gaps=gaps,
        ideas=ideas,
        knowledge_graph=knowledge_graph,
        error_msg=orm_record.error_msg,
        created_at=orm_record.created_at,
        completed_at=orm_record.completed_at,
    )


async def list_sessions() -> list[SessionSummary]:
    """Return all completed sessions ordered by ``completed_at`` descending.

    Only sessions where ``completed_at`` is not ``None`` are included.
    """
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ResearchSessionORM)
            .where(ResearchSessionORM.completed_at.is_not(None))
            .order_by(ResearchSessionORM.completed_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

    return [
        SessionSummary(
            session_id=row.session_id,
            query=row.query,
            completed_at=row.completed_at,  # type: ignore[arg-type]
        )
        for row in rows
    ]


async def delete_session(session_id: str) -> bool:
    """Delete a session by primary key.

    Returns ``True`` if a record was deleted, ``False`` if it was not found.
    """
    async with AsyncSessionLocal() as db:
        orm_record: ResearchSessionORM | None = await db.get(
            ResearchSessionORM, session_id
        )
        if orm_record is None:
            return False
        await db.delete(orm_record)
        await db.commit()

    return True
