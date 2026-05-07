from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchSessionORM(Base):
    __tablename__ = "research_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    gaps_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    ideas_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    graph_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
