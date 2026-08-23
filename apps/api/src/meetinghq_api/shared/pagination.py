"""Reusable offset and opaque cursor pagination contracts."""

import base64
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from meetinghq_api.shared.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class PageParams(BaseModel):
    """Offset pagination request."""

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class CursorParams(BaseModel):
    """Stable cursor pagination request."""

    cursor: str | None = None
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    direction: Literal["forward", "backward"] = "forward"


class PaginationParams(BaseModel):
    """One pagination strategy per request."""

    offset: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @model_validator(mode="after")
    def reject_mixed_strategies(self) -> "PaginationParams":
        if self.offset is not None and self.cursor is not None:
            raise ValueError("offset and cursor cannot be used together")
        return self


def encode_cursor(created_at: datetime, entity_id: str) -> str:
    """Encode a stable compound sort key without exposing implementation details."""
    payload = json.dumps({"created_at": created_at.isoformat(), "id": entity_id})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode and validate an opaque compound cursor."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(value["created_at"]), str(value["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid pagination cursor") from error


class Page[T](BaseModel):
    """Paginated response envelope."""

    items: list[T]
    total: int
    offset: int
    limit: int


class CursorPage[T](BaseModel):
    """Cursor-paginated result with forward/backward continuation."""

    items: list[T]
    next_cursor: str | None = None
    previous_cursor: str | None = None
    has_more: bool = False
