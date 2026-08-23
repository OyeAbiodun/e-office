"""Organization application service."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.configuration.service import ConfigurationRegistry
from meetinghq_api.modules.invitations.models import Invitation, InvitationStatus
from meetinghq_api.modules.organizations.models import (
    Organization,
    OrganizationUnit,
    OrganizationUnitType,
)
from meetinghq_api.modules.organizations.repository import OrganizationRepository
from meetinghq_api.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationOverview,
    OrganizationResponse,
    OrganizationUnitInput,
    OrganizationUpdate,
)
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import Role, User, UserStatus, user_roles
from meetinghq_api.modules.workspaces.models import Workspace
from meetinghq_api.shared.events import DomainEvent, DomainEventPublisher
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError


class OrganizationService:
    """Tenant-safe organization use cases."""

    def __init__(self, session: AsyncSession, events: DomainEventPublisher | None = None) -> None:
        self.session = session
        self.repository = OrganizationRepository(session)
        self.events = events or TransactionalDomainEventPublisher(session)

    async def get(self, organization_id: uuid.UUID) -> Organization:
        organization = await self.repository.get_active(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    async def create(self, body: OrganizationCreate, actor_id: uuid.UUID) -> Organization:
        if await self.repository.slug_exists(body.slug):
            raise ConflictError("Organization slug is already in use")
        organization = Organization(name=body.name, slug=body.slug)
        await self.repository.add(organization)
        await self.events.publish(
            DomainEvent(
                name="OrganizationCreated",
                organization_id=organization.id,
                actor_id=actor_id,
                aggregate_type="organization",
                aggregate_id=organization.id,
                payload={"name": organization.name},
            )
        )
        return organization

    async def units(
        self,
        organization_id: uuid.UUID,
        unit_type: OrganizationUnitType | None = None,
    ) -> list[OrganizationUnit]:
        statement = select(OrganizationUnit).where(
            OrganizationUnit.organization_id == organization_id,
            OrganizationUnit.deleted_at.is_(None),
        )
        if unit_type is not None:
            statement = statement.where(OrganizationUnit.unit_type == unit_type)
        return list(
            (
                await self.session.scalars(
                    statement.order_by(OrganizationUnit.unit_type, OrganizationUnit.name)
                )
            ).all()
        )

    async def create_unit(
        self,
        organization_id: uuid.UUID,
        body: OrganizationUnitInput,
        actor_id: uuid.UUID,
    ) -> OrganizationUnit:
        if body.parent_id is not None:
            parent = await self.session.scalar(
                select(OrganizationUnit.id).where(
                    OrganizationUnit.id == body.parent_id,
                    OrganizationUnit.organization_id == organization_id,
                    OrganizationUnit.deleted_at.is_(None),
                )
            )
            if parent is None:
                raise NotFoundError("Parent organization unit not found")
        unit = OrganizationUnit(organization_id=organization_id, **body.model_dump())
        self.session.add(unit)
        await self.session.flush()
        await self.events.publish(
            DomainEvent(
                name="OrganizationUnitCreated",
                organization_id=organization_id,
                actor_id=actor_id,
                aggregate_type="organization_unit",
                aggregate_id=unit.id,
                payload={"name": unit.name, "unit_type": unit.unit_type},
            )
        )
        return unit

    async def delete_unit(
        self, organization_id: uuid.UUID, unit_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        unit = await self.session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.id == unit_id,
                OrganizationUnit.organization_id == organization_id,
                OrganizationUnit.deleted_at.is_(None),
            )
        )
        if unit is None:
            raise NotFoundError("Organization unit not found")
        unit.soft_delete(actor_id)

    async def policies(
        self, organization_id: uuid.UUID, settings: Settings
    ) -> dict[str, dict[str, object]]:
        registry = ConfigurationRegistry(self.session, settings, organization_id)
        categories = (
            "security",
            "meeting",
            "chat",
            "storage",
            "ai",
            "notification",
        )
        return {
            category: await registry.get(
                f"{category}_policy",
                {
                    "enabled": True,
                    "enforcement": "organization_default",
                },
            )
            for category in categories
        }

    async def set_policy(
        self,
        organization_id: uuid.UUID,
        settings: Settings,
        category: str,
        values: dict[str, object],
        actor_id: uuid.UUID,
    ) -> dict[str, object]:
        if category not in {
            "security",
            "meeting",
            "chat",
            "storage",
            "ai",
            "notification",
        }:
            raise NotFoundError("Policy category not found")
        await ConfigurationRegistry(self.session, settings, organization_id).set(
            f"{category}_policy", values, "organization_policy", actor_id
        )
        return values

    async def overview(self, organization_id: uuid.UUID) -> OrganizationOverview:
        organization = await self.get(organization_id)

        async def count(model: Any, *criteria: Any) -> int:
            return (await self.session.scalar(select(func.count(model.id)).where(*criteria))) or 0

        admin_rows = (
            await self.session.execute(
                select(User, Role.name)
                .join(user_roles, user_roles.c.user_id == User.id)
                .join(Role, Role.id == user_roles.c.role_id)
                .where(
                    User.organization_id == organization_id,
                    Role.organization_id == organization_id,
                    Role.name.in_(("Super Admin", "Admin")),
                    User.removed_at.is_(None),
                )
                .order_by(User.display_name)
            )
        ).all()
        activity = (
            await self.session.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.organization_id == organization_id)
                .order_by(ActivityEvent.occurred_at.desc())
                .limit(8)
            )
        ).all()
        audits = (
            await self.session.scalars(
                select(AuditLog)
                .where(AuditLog.organization_id == organization_id)
                .order_by(AuditLog.created_at.desc())
                .limit(8)
            )
        ).all()
        return OrganizationOverview(
            organization=OrganizationResponse.model_validate(organization),
            member_count=await count(User, User.organization_id == organization_id),
            active_member_count=await count(
                User,
                User.organization_id == organization_id,
                User.status == UserStatus.ACTIVE,
                User.removed_at.is_(None),
            ),
            workspace_count=await count(
                Workspace,
                Workspace.organization_id == organization_id,
                Workspace.deleted_at.is_(None),
            ),
            team_count=await count(
                Team,
                Team.organization_id == organization_id,
                Team.deleted_at.is_(None),
            ),
            pending_invitation_count=await count(
                Invitation,
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING,
            ),
            department_count=await count(
                OrganizationUnit,
                OrganizationUnit.organization_id == organization_id,
                OrganizationUnit.unit_type == OrganizationUnitType.DEPARTMENT,
                OrganizationUnit.deleted_at.is_(None),
            ),
            branch_count=await count(
                OrganizationUnit,
                OrganizationUnit.organization_id == organization_id,
                OrganizationUnit.unit_type == OrganizationUnitType.BRANCH,
                OrganizationUnit.deleted_at.is_(None),
            ),
            location_count=await count(
                OrganizationUnit,
                OrganizationUnit.organization_id == organization_id,
                OrganizationUnit.unit_type == OrganizationUnitType.LOCATION,
                OrganizationUnit.deleted_at.is_(None),
            ),
            administrators=[
                {
                    "id": str(user.id),
                    "display_name": user.display_name,
                    "email": user.email,
                    "role": role_name,
                }
                for user, role_name in admin_rows
            ],
            recent_activity=[
                {
                    "id": str(item.id),
                    "event_type": item.event_type,
                    "subject_type": item.subject_type,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in activity
            ],
            audit_history=[
                {
                    "id": str(item.id),
                    "action": item.action,
                    "resource": item.resource,
                    "created_at": item.created_at.isoformat(),
                }
                for item in audits
            ],
        )

    async def update(
        self, organization_id: uuid.UUID, body: OrganizationUpdate, actor_id: uuid.UUID
    ) -> Organization:
        organization = await self.get(organization_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(
                organization,
                field,
                value.model_dump() if hasattr(value, "model_dump") else value,
            )
        await self.events.publish(
            DomainEvent(
                name="OrganizationUpdated",
                organization_id=organization.id,
                actor_id=actor_id,
                aggregate_type="organization",
                aggregate_id=organization.id,
            )
        )
        return organization

    async def soft_delete(self, organization_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        organization = await self.get(organization_id)
        organization.soft_delete(actor_id)
        await self.events.publish(
            DomainEvent(
                name="OrganizationDeleted",
                organization_id=organization.id,
                actor_id=actor_id,
                aggregate_type="organization",
                aggregate_id=organization.id,
            )
        )
