"""Tenant-isolated, read-only Audit Center query service."""

import base64
import csv
import io
import uuid
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.audit.schemas import (
    AuditFilters,
    AuditPageResponse,
    AuditRecordResponse,
)
from meetinghq_api.modules.users.models import User


class AuditService:
    """Read immutable records with cursor or offset pagination."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_records(
        self,
        organization_id: uuid.UUID,
        filters: AuditFilters,
        *,
        cursor: str | None,
        offset: int,
        limit: int,
    ) -> AuditPageResponse:
        query = self._filtered_query(organization_id, filters)
        if cursor:
            query = query.where(AuditLog.created_at < self._decode_cursor(cursor))
        count_query = select(func.count()).select_from(
            self._filtered_query(organization_id, filters).subquery()
        )
        total = int(await self.session.scalar(count_query) or 0)
        rows = (
            await self.session.execute(
                query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset(0 if cursor else offset)
                .limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [self._response(log, user) for log, user in rows]
        next_cursor = self._encode_cursor(items[-1].created_at) if has_more and items else None
        action_values = list(
            (
                await self.session.scalars(
                    select(AuditLog.action)
                    .where(AuditLog.organization_id == organization_id)
                    .distinct()
                    .order_by(AuditLog.action)
                )
            ).all()
        )
        resource_values = (
            await self.session.scalars(
                select(AuditLog.resource)
                .where(AuditLog.organization_id == organization_id)
                .distinct()
                .order_by(AuditLog.resource)
            )
        ).all()
        return AuditPageResponse(
            items=items,
            total=total,
            next_cursor=next_cursor,
            categories=sorted({resource.replace("_", " ").title() for resource in resource_values}),
            actions=action_values,
        )

    async def export_csv(self, organization_id: uuid.UUID, filters: AuditFilters) -> str:
        rows = (
            await self.session.execute(
                self._filtered_query(organization_id, filters)
                .order_by(AuditLog.created_at.desc())
                .limit(10_000)
            )
        ).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Timestamp",
                "User",
                "Action",
                "Category",
                "Resource",
                "Resource ID",
                "IP Address",
                "Browser",
                "Device",
                "Request ID",
            ]
        )
        for log, user in rows:
            record = self._response(log, user)
            writer.writerow(
                [
                    record.created_at.isoformat(),
                    record.user_name,
                    record.action,
                    record.category,
                    record.resource,
                    record.resource_id or "",
                    record.ip_address or "",
                    record.browser or "",
                    record.device or "",
                    record.request_id or "",
                ]
            )
        return output.getvalue()

    def _filtered_query(
        self, organization_id: uuid.UUID, filters: AuditFilters
    ) -> Select[tuple[AuditLog, User]]:
        query = (
            select(AuditLog, User)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.organization_id == organization_id)
        )
        if filters.search:
            term = f"%{filters.search.strip()}%"
            query = query.where(
                or_(
                    AuditLog.action.ilike(term),
                    AuditLog.resource.ilike(term),
                    User.email.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                )
            )
        if filters.category:
            normalized_category = filters.category.strip().lower().replace(" ", "_")
            query = query.where(
                or_(
                    func.lower(AuditLog.resource) == normalized_category,
                    func.lower(AuditLog.action).startswith(f"{normalized_category}."),
                )
            )
        if filters.action:
            query = query.where(AuditLog.action == filters.action)
        if filters.user_id:
            query = query.where(AuditLog.user_id == filters.user_id)
        if filters.from_date:
            query = query.where(AuditLog.created_at >= filters.from_date)
        if filters.to_date:
            query = query.where(AuditLog.created_at <= filters.to_date)
        return query

    def _response(self, log: AuditLog, user: User | None) -> AuditRecordResponse:
        metadata = dict(log.audit_metadata or {})
        return AuditRecordResponse(
            id=log.id,
            organization_id=log.organization_id,
            user_id=log.user_id,
            user_name=(f"{user.first_name} {user.last_name}".strip() if user else "System"),
            action=log.action,
            category=self._category(log.action, log.resource),
            resource=log.resource,
            resource_id=log.resource_id,
            request_id=log.request_id,
            ip_address=log.ip_address,
            browser=self._optional_string(metadata, "browser"),
            device=self._optional_string(metadata, "device"),
            metadata=metadata,
            created_at=log.created_at,
        )

    @staticmethod
    def _category(action: str, resource: str) -> str:
        value = action.split(".", maxsplit=1)[0] if "." in action else resource
        return value.replace("_", " ").title()

    @staticmethod
    def _optional_string(metadata: dict[str, object], key: str) -> str | None:
        value = metadata.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _encode_cursor(value: datetime) -> str:
        return base64.urlsafe_b64encode(value.isoformat().encode()).decode()

    @staticmethod
    def _decode_cursor(value: str) -> datetime:
        try:
            return datetime.fromisoformat(base64.urlsafe_b64decode(value).decode())
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Invalid audit cursor") from error
