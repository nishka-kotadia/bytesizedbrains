from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from models.config import Config
from models.source import Source


class SessionStatus(str, Enum):
    pending  = "pending"
    running  = "running"
    complete = "complete"
    error    = "error"


class ResearchSession(BaseModel):
    session_id:   str
    query:        str
    config:       Config
    status:       SessionStatus
    sources:      list[Source]    = []
    report:       str | None      = None
    gaps:         list[dict]      = []
    ideas:        list[dict]      = []
    knowledge_graph: dict | None  = None
    error_msg:    str | None      = None
    created_at:   datetime
    completed_at: datetime | None = None
