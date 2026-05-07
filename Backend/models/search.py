from enum import Enum

from pydantic import BaseModel


class SearchTarget(str, Enum):
    arxiv  = "arxiv"
    github = "github"


class SearchTask(BaseModel):
    sub_question: str
    target:       SearchTarget
    query:        str
    priority:     int  # higher = more important
