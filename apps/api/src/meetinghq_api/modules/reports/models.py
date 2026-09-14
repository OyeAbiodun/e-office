"""Tenant-scoped reporting workflow and historically stable snapshots."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base

json_type = JSON().with_variant(JSONB(), "postgresql")


class ReportPolicy(Base):
    __tablename__ = "report_policies"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_report_policy_org"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    monthly_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    review_before_send: Mapped[bool] = mapped_column(Boolean, default=True)
    automatic_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    week_start: Mapped[int] = mapped_column(Integer, default=0)
    week_end: Mapped[int] = mapped_column(Integer, default=6)
    generation_time: Mapped[time] = mapped_column(Time, default=time(18, 0))
    submission_deadline_hours: Mapped[int] = mapped_column(Integer, default=24)
    manager_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_hours_before: Mapped[int] = mapped_column(Integer, default=4)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    enabled_report_types: Mapped[list[str]] = mapped_column(
        json_type, default=lambda: ["daily", "weekly", "monthly", "custom"]
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "generation_key", name="uq_generated_reports_generation_key"
        ),
        Index(
            "ix_generated_reports_org_subject_period",
            "organization_id",
            "subject_type",
            "subject_id",
            "period_start",
            "period_end",
        ),
        Index("ix_generated_reports_org_status_created", "organization_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    subject_type: Mapped[str] = mapped_column(String(24), index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    subject_name: Mapped[str] = mapped_column(String(240))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    period_type: Mapped[str] = mapped_column(String(24), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    status: Mapped[str] = mapped_column(String(32), default="generated_draft", index=True)
    submission_mode: Mapped[str | None] = mapped_column(String(16))
    generation_key: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=1)
    authoritative_snapshot: Mapped[dict[str, object]] = mapped_column(json_type, default=dict)
    narrative: Mapped[dict[str, object]] = mapped_column(json_type, default=dict)
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(json_type, default=list)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(json_type, default=dict)
    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_comment: Mapped[str | None] = mapped_column(Text)
    return_reason: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version", name="uq_report_versions_report_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, object]] = mapped_column(json_type)
    narrative: Mapped[dict[str, object]] = mapped_column(json_type)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportReviewHistory(Base):
    __tablename__ = "report_review_history"
    __table_args__ = (Index("ix_report_review_history_report_created", "report_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
