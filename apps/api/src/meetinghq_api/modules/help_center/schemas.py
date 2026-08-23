"""Help center API contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HelpArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    category: str
    content: str
    version: int
    position: int
    published: bool
    workflow_status: str
    search_weight: int
    context_ids: list[str]
    related_slugs: list[str]
    video_metadata: dict[str, object] | None
    updated_at: datetime


class HelpArticleInput(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=2, max_length=500)
    category: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2)
    version: int = Field(default=1, ge=1)
    position: int = Field(default=0, ge=0)
    published: bool = True
    workflow_status: Literal["draft", "review", "published", "archived"] = "published"
    search_weight: int = Field(default=100, ge=0, le=1000)
    context_ids: list[str] = Field(default_factory=list, max_length=30)
    related_slugs: list[str] = Field(default_factory=list, max_length=30)
    video_metadata: dict[str, object] | None = None


class HelpArticleUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=2, max_length=500)
    category: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2)
    workflow_status: Literal["draft", "review", "published", "archived"] = "draft"
    search_weight: int = Field(default=100, ge=0, le=1000)
    context_ids: list[str] = Field(default_factory=list, max_length=30)
    related_slugs: list[str] = Field(default_factory=list, max_length=30)
    video_metadata: dict[str, object] | None = None


class HelpAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str
    created_at: datetime


class ProductTourInput(BaseModel):
    context_id: str = Field(min_length=2, max_length=180)
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(min_length=2, max_length=500)
    steps: list[dict[str, object]] = Field(min_length=1, max_length=30)
    version: int = Field(default=1, ge=1)
    enabled: bool = True


class ProductTourResponse(ProductTourInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime


class HelpContextResponse(BaseModel):
    context_id: str
    article: HelpArticleResponse | None
    tour: ProductTourResponse | None


class HelpAnalyticsResponse(BaseModel):
    total_articles: int
    published_articles: int
    total_views: int
    unique_readers: int
    favorite_count: int
    popular_articles: list[dict[str, object]]
