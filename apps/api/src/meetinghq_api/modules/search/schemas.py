"""Global search response contracts."""

from typing import Literal

from pydantic import BaseModel

SearchResultType = Literal[
    "navigation",
    "meeting",
    "user",
    "team",
    "role",
    "mail",
    "notification",
    "help",
    "audit",
    "integration",
]


class SearchResult(BaseModel):
    id: str
    type: SearchResultType
    title: str
    subtitle: str
    url: str
    icon: str
    score: int


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
