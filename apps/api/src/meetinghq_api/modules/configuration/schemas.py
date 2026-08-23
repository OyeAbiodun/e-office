"""Configuration-driven platform administration contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FeatureFlagResponse(OrmModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    enabled: bool
    hidden: bool
    maintenance_mode: bool
    release_stage: str
    availability_status: str
    implementation_status: str
    planned_version: str | None
    estimated_availability: str | None
    dependencies: list[str]
    navigation_path: str | None
    documentation_path: str | None
    ui_available: bool
    backend_available: bool
    navigation_available: bool
    search_available: bool
    permissions_available: bool
    installed: bool
    updated_at: datetime


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    hidden: bool | None = None
    maintenance_mode: bool | None = None
    release_stage: str | None = Field(default=None, pattern=r"^(internal|beta|public)$")


class MenuResponse(OrmModel):
    id: uuid.UUID
    key: str
    label: str
    path: str
    icon: str
    permission: str
    required_role: str | None
    feature_key: str | None
    badge: str | None
    parent_key: str | None
    section: str
    position: int
    enabled: bool
    hidden: bool


class MenuUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    icon: str | None = Field(default=None, min_length=1, max_length=80)
    permission: str | None = Field(default=None, min_length=1, max_length=120)
    required_role: str | None = Field(default=None, max_length=80)
    badge: str | None = Field(default=None, max_length=40)
    parent_key: str | None = Field(default=None, max_length=80)
    section: str | None = Field(default=None, max_length=80)
    position: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    hidden: bool | None = None


class MenuBulkItem(MenuUpdate):
    key: str = Field(min_length=1, max_length=80)


class MenuBulkUpdate(BaseModel):
    items: list[MenuBulkItem] = Field(min_length=1, max_length=100)


class MenuImport(BaseModel):
    version: int = Field(default=1, ge=1)
    items: list[MenuBulkItem] = Field(min_length=1, max_length=100)


class MenuExport(BaseModel):
    version: int = 1
    exported_at: datetime
    items: list[MenuResponse]


class ConfigurationResponse(OrmModel):
    id: uuid.UUID
    key: str
    value: dict[str, object]
    category: str
    is_secret: bool
    updated_at: datetime


class ConfigurationUpdate(BaseModel):
    value: dict[str, object]
    category: str = Field(min_length=1, max_length=80)
    is_secret: bool = False
