"""Persisted configuration overrides."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base


class ConfigurationEntry(Base):
    """Namespaced platform or tenant configuration value."""

    __tablename__ = "configuration_entries"
    __table_args__ = (UniqueConstraint("scope", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(80), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    is_secret: Mapped[bool] = mapped_column(default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeatureFlag(Base):
    """Organization-scoped module availability and release state."""

    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    release_stage: Mapped[str] = mapped_column(String(24), default="public")
    availability_status: Mapped[str] = mapped_column(String(24), default="available")
    implementation_status: Mapped[str] = mapped_column(String(120), default="Implemented")
    planned_version: Mapped[str | None] = mapped_column(String(40))
    estimated_availability: Mapped[str | None] = mapped_column(String(80))
    dependencies: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list
    )
    navigation_path: Mapped[str | None] = mapped_column(String(240))
    documentation_path: Mapped[str | None] = mapped_column(String(240))
    ui_available: Mapped[bool] = mapped_column(Boolean, default=False)
    backend_available: Mapped[bool] = mapped_column(Boolean, default=False)
    navigation_available: Mapped[bool] = mapped_column(Boolean, default=False)
    search_available: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions_available: Mapped[bool] = mapped_column(Boolean, default=False)
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MenuDefinition(Base):
    """Persisted sidebar definition evaluated with feature and permission state."""

    __tablename__ = "menu_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(80))
    path: Mapped[str] = mapped_column(String(240))
    icon: Mapped[str] = mapped_column(String(80), default="circle")
    permission: Mapped[str] = mapped_column(String(120))
    required_role: Mapped[str | None] = mapped_column(String(80))
    feature_key: Mapped[str | None] = mapped_column(String(80))
    badge: Mapped[str | None] = mapped_column(String(40))
    parent_key: Mapped[str | None] = mapped_column(String(80))
    section: Mapped[str] = mapped_column(String(80), default="work")
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
