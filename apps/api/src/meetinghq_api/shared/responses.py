"""Standard API success and failure envelopes."""

from typing import Any

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    """Optional response metadata such as pagination and request correlation."""

    request_id: str | None = None
    pagination: dict[str, Any] | None = None


class ApiResponse[T](BaseModel):
    """Canonical successful API response."""

    success: bool = True
    message: str
    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ApiErrorDetail(BaseModel):
    """Safe, machine-readable failure details."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Canonical failed API response."""

    success: bool = False
    message: str
    data: None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
    error: ApiErrorDetail


class OperationResponse(ApiResponse[None]):
    """Successful state transition response."""

    data: None = None
