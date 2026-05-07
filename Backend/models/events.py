from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from models.source import Source
from models.config import Config


# SSE Event Payload Models

class StepStartEvent(BaseModel):
    step_name: str
    step_index: int
    label: str


class StepCompleteEvent(BaseModel):
    step_name: str
    step_index: int
    summary: str


class SourceFoundEvent(BaseModel):
    title: str
    authors: str
    venue: str
    year: int
    relevance: int
    type: str  # "paper" or "repo"
    url: str


class PipelineCompleteEvent(BaseModel):
    report: str
    sources: list[Source]


class PipelineErrorEvent(BaseModel):
    error: str


# API Request/Response Models

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    config: Config = Config()

    @field_validator("query")
    @classmethod
    def query_must_not_be_whitespace_only(cls, v: str) -> str:
        # Reject strings that are empty after stripping Unicode whitespace
        # and control characters (categories Zs and Cc)
        import unicodedata
        stripped = "".join(
            ch for ch in v
            if unicodedata.category(ch) not in ("Zs", "Cc") and not ch.isspace()
        )
        if not stripped:
            raise ValueError("query must not be empty or whitespace-only")
        return v


class FollowUpRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class FollowUpMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ResearchResponse(BaseModel):
    session_id: str
    stream_url: str


class SessionSummary(BaseModel):
    session_id: str
    query: str
    completed_at: datetime


class HealthResponse(BaseModel):
    status: str  # "ok"
    version: str
    llm_provider: str
    llm_model: str
