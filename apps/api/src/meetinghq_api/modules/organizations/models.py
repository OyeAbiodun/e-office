"""Organization persistence model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base
from meetinghq_api.shared.soft_delete import SoftDeleteMixin


class OrganizationStatus(enum.StrEnum):
    """Organization lifecycle state."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class OrganizationUnitType(enum.StrEnum):
    """Supported organizational structure nodes."""

    DEPARTMENT = "department"
    BRANCH = "branch"
    LOCATION = "location"


class Organization(SoftDeleteMixin, Base):
    """Tenant root."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, native_enum=False), default=OrganizationStatus.ACTIVE
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    country: Mapped[str | None] = mapped_column(String(2))
    default_language: Mapped[str] = mapped_column(String(10), default="en")
    brand_color: Mapped[str] = mapped_column(String(7), default="#2563eb")
    settings: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrganizationUnit(SoftDeleteMixin, Base):
    """Tenant-owned department, branch, or physical office."""

    __tablename__ = "organization_units"
    __table_args__ = (UniqueConstraint("organization_id", "unit_type", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    unit_type: Mapped[OrganizationUnitType] = mapped_column(
        Enum(OrganizationUnitType, native_enum=False), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(String(1000))
    address: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    timezone: Mapped[str | None] = mapped_column(String(64))
    working_hours: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
