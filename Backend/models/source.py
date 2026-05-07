from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class SourceType(str, Enum):
    paper = "paper"
    repo = "repo"


class Source(BaseModel):
    id: str
    type: SourceType
    title: str
    authors: str          # comma-separated
    venue: str            # journal/conference name or "GitHub"
    year: int
    url: str
    abstract: str         # full abstract or repo description
    relevance: int        # 0–100
    key_findings: Optional[str] = None  # populated by Analyzer
    embedding: Optional[List[float]] = None  # Vector embedding for similarity
