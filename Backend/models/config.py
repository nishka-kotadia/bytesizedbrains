from enum import Enum

from pydantic import BaseModel, Field


class DepthLevel(str, Enum):
    quick = "Quick"
    standard = "Standard"
    deep = "Deep"


class OutputFormat(str, Enum):
    markdown = "Markdown"
    plain_text = "Plain Text"
    structured_json = "Structured JSON"


class SourceTypes(BaseModel):
    papers: bool = True
    web: bool = True
    patents: bool = False
    news: bool = False


class Config(BaseModel):
    depth: DepthLevel = DepthLevel.standard
    sources: SourceTypes = SourceTypes()
    maxSources: int = Field(default=20, ge=5, le=50)
    format: OutputFormat = OutputFormat.markdown
