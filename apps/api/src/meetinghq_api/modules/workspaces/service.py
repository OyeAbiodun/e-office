"""Workspace application service."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.calendar.models import Calendar
from meetinghq_api.modules.chat.models import AttachmentReference, Conversation, Message
from meetinghq_api.modules.meetings.models import Meeting, MeetingArtifact
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import (
    Workspace,
    WorkspaceIntegration,
    WorkspaceMembership,
    WorkspaceTemplate,
)
from meetinghq_api.modules.workspaces.repository import WorkspaceRepository
from meetinghq_api.modules.workspaces.schemas import (
    WorkspaceBulkResult,
    WorkspaceCreate,
    WorkspaceIntegrationInput,
    WorkspaceMemberInput,
    WorkspaceMemberResponse,
    WorkspaceOverview,
    WorkspaceTemplateInput,
    WorkspaceUpdate,
)
from meetinghq_api.shared.events import DomainEvent, DomainEventPublisher
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError


class WorkspaceService:
    """Tenant-safe workspace use cases."""

    def __init__(self, session: AsyncSession, events: DomainEventPublisher | None = None) -> None:
        self.session = session
        self.repository = WorkspaceRepository(session)
        self.events = events or TransactionalDomainEventPublisher(session)

    async def get(self, organization_id: uuid.UUID, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self.repository.get_for_organization(organization_id, workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found")
        return workspace

    async def list_workspaces(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        archived: bool | None = None,
        classification: str | None = None,
    ) -> list[Workspace]:
        return await self.repository.list_for_organization(
            organization_id,
            search=search,
            archived=archived,
            classification=classification,
        )

    async def create(
        self, organization_id: uuid.UUID, body: WorkspaceCreate, actor_id: uuid.UUID
    ) -> Workspace:
        if await self.repository.slug_exists(organization_id, body.slug):
            raise ConflictError("Workspace slug is already in use")
        workspace = Workspace(
            organization_id=organization_id,
            owner_id=actor_id,
            **body.model_dump(),
        )
        await self.repository.add(workspace)
        await self.session.flush()
        self.session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=actor_id,
                role="owner",
            )
        )
        await self.events.publish(
            DomainEvent(
                name="WorkspaceCreated",
                organization_id=organization_id,
                workspace_id=workspace.id,
                actor_id=actor_id,
                aggregate_type="workspace",
                aggregate_id=workspace.id,
                payload={"name": workspace.name},
            )
        )
        return workspace

    async def update(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        body: WorkspaceUpdate,
        actor_id: uuid.UUID,
    ) -> Workspace:
        workspace = await self.get(organization_id, workspace_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(workspace, field, value.model_dump() if hasattr(value, "model_dump") else value)
        await self.events.publish(
            DomainEvent(
                name="WorkspaceUpdated",
                organization_id=organization_id,
                workspace_id=workspace.id,
                actor_id=actor_id,
                aggregate_type="workspace",
                aggregate_id=workspace.id,
            )
        )
        return workspace

    async def archive(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        archived: bool,
        actor_id: uuid.UUID,
    ) -> Workspace:
        workspace = await self.get(organization_id, workspace_id)
        if archived and workspace.archived_at is None:
            active_count = await self.session.scalar(
                select(func.count(Workspace.id)).where(
                    Workspace.organization_id == organization_id,
                    Workspace.archived_at.is_(None),
                    Workspace.deleted_at.is_(None),
                )
            )
            if active_count == 1:
                raise ConflictError("An organization must retain at least one active workspace")
        workspace.archived_at = datetime.now(UTC) if archived else None
        await self._record(
            organization_id,
            workspace_id,
            actor_id,
            "workspace.archived" if archived else "workspace.restored",
        )
        return workspace

    async def overview(
        self, organization_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceOverview:
        workspace = await self.get(organization_id, workspace_id)

        async def count(model: type[object], *conditions: Any) -> int:
            value = await self.session.scalar(
                select(func.count()).select_from(model).where(*conditions)
            )
            return int(value or 0)

        files = await count(
            AttachmentReference,
            AttachmentReference.message_id.in_(
                select(Message.id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(
                    Conversation.organization_id == organization_id,
                    Conversation.workspace_id == workspace_id,
                )
            ),
        )
        chat_bytes = await self.session.scalar(
            select(func.coalesce(func.sum(AttachmentReference.size), 0)).where(
                AttachmentReference.message_id.in_(
                    select(Message.id)
                    .join(Conversation, Conversation.id == Message.conversation_id)
                    .where(
                        Conversation.organization_id == organization_id,
                        Conversation.workspace_id == workspace_id,
                    )
                )
            )
        )
        artifact_count = await count(
            MeetingArtifact,
            MeetingArtifact.meeting_id.in_(
                select(Meeting.id).where(
                    Meeting.organization_id == organization_id,
                    Meeting.workspace_id == workspace_id,
                )
            ),
        )
        artifact_bytes = await self.session.scalar(
            select(func.coalesce(func.sum(MeetingArtifact.size), 0)).where(
                MeetingArtifact.meeting_id.in_(
                    select(Meeting.id).where(
                        Meeting.organization_id == organization_id,
                        Meeting.workspace_id == workspace_id,
                    )
                )
            )
        )
        recent = (
            await self.session.scalars(
                select(ActivityEvent)
                .where(
                    ActivityEvent.organization_id == organization_id,
                    ActivityEvent.workspace_id == workspace_id,
                )
                .order_by(ActivityEvent.occurred_at.desc())
                .limit(12)
            )
        ).all()
        audits = (
            await self.session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.organization_id == organization_id,
                    AuditLog.resource == "workspace",
                    AuditLog.resource_id == workspace_id,
                )
                .order_by(AuditLog.created_at.desc())
                .limit(12)
            )
        ).all()
        members = await count(WorkspaceMembership, WorkspaceMembership.workspace_id == workspace_id)
        administrators = await count(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role.in_(["administrator", "owner"]),
        )
        from meetinghq_api.modules.workspaces.schemas import WorkspaceResponse

        return WorkspaceOverview(
            workspace=WorkspaceResponse.model_validate(workspace),
            team_count=await count(
                Team,
                Team.organization_id == organization_id,
                Team.workspace_id == workspace_id,
                Team.deleted_at.is_(None),
            ),
            member_count=members,
            administrator_count=administrators,
            channel_count=await count(
                Conversation,
                Conversation.organization_id == organization_id,
                Conversation.workspace_id == workspace_id,
                Conversation.archived_at.is_(None),
            ),
            meeting_count=await count(
                Meeting,
                Meeting.organization_id == organization_id,
                Meeting.workspace_id == workspace_id,
            ),
            calendar_count=await count(
                Calendar,
                Calendar.organization_id == organization_id,
                Calendar.workspace_id == workspace_id,
                Calendar.deleted_at.is_(None),
            ),
            file_count=files + artifact_count,
            storage_bytes=int(chat_bytes or 0) + int(artifact_bytes or 0),
            app_count=await count(
                WorkspaceIntegration,
                WorkspaceIntegration.organization_id == organization_id,
                WorkspaceIntegration.workspace_id == workspace_id,
                WorkspaceIntegration.enabled.is_(True),
            ),
            recent_activity=[
                {
                    "id": str(item.id),
                    "event_type": item.event_type,
                    "occurred_at": item.occurred_at,
                }
                for item in recent
            ],
            audit_history=[
                {
                    "id": str(item.id),
                    "action": item.action,
                    "created_at": item.created_at,
                }
                for item in audits
            ],
        )

    async def members(
        self, organization_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[WorkspaceMemberResponse]:
        await self.get(organization_id, workspace_id)
        rows = (
            await self.session.execute(
                select(WorkspaceMembership, User)
                .join(User, User.id == WorkspaceMembership.user_id)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    User.organization_id == organization_id,
                    User.removed_at.is_(None),
                )
                .order_by(User.display_name)
            )
        ).all()
        return [
            WorkspaceMemberResponse(
                id=membership.id,
                user_id=user.id,
                display_name=user.display_name,
                email=user.email,
                role=membership.role,
                created_at=membership.created_at,
            )
            for membership, user in rows
        ]

    async def add_member(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        body: WorkspaceMemberInput,
        actor_id: uuid.UUID,
    ) -> WorkspaceMemberResponse:
        await self.get(organization_id, workspace_id)
        user = await self.session.scalar(
            select(User).where(
                User.id == body.user_id,
                User.organization_id == organization_id,
                User.removed_at.is_(None),
            )
        )
        if user is None:
            raise NotFoundError("User not found")
        existing = await self.session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == body.user_id,
            )
        )
        if existing:
            existing.role = body.role
            membership = existing
        else:
            membership = WorkspaceMembership(
                workspace_id=workspace_id, user_id=body.user_id, role=body.role
            )
            self.session.add(membership)
            await self.session.flush()
        await self._record(organization_id, workspace_id, actor_id, "workspace.member_assigned")
        return WorkspaceMemberResponse(
            id=membership.id,
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            role=membership.role,
            created_at=membership.created_at,
        )

    async def remove_member(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        workspace = await self.get(organization_id, workspace_id)
        membership = await self.session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        if membership is None:
            raise NotFoundError("Workspace member not found")
        if workspace.owner_id == user_id or membership.role == "owner":
            raise ConflictError("Transfer workspace ownership before removing the owner")
        await self.session.delete(membership)
        await self._record(organization_id, workspace_id, actor_id, "workspace.member_removed")

    async def integrations(
        self, organization_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[WorkspaceIntegration]:
        await self.get(organization_id, workspace_id)
        return list(
            (
                await self.session.scalars(
                    select(WorkspaceIntegration)
                    .where(
                        WorkspaceIntegration.organization_id == organization_id,
                        WorkspaceIntegration.workspace_id == workspace_id,
                    )
                    .order_by(WorkspaceIntegration.display_name)
                )
            ).all()
        )

    async def upsert_integration(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        body: WorkspaceIntegrationInput,
        actor_id: uuid.UUID,
    ) -> WorkspaceIntegration:
        await self.get(organization_id, workspace_id)
        integration = await self.session.scalar(
            select(WorkspaceIntegration).where(
                WorkspaceIntegration.organization_id == organization_id,
                WorkspaceIntegration.workspace_id == workspace_id,
                WorkspaceIntegration.provider == body.provider,
            )
        )
        if integration is None:
            integration = WorkspaceIntegration(
                organization_id=organization_id,
                workspace_id=workspace_id,
                created_by=actor_id,
                **body.model_dump(),
            )
            self.session.add(integration)
            await self.session.flush()
        else:
            for field, value in body.model_dump().items():
                setattr(integration, field, value)
        await self._record(organization_id, workspace_id, actor_id, "workspace.integration_updated")
        return integration

    async def templates(self, organization_id: uuid.UUID) -> list[WorkspaceTemplate]:
        return list(
            (
                await self.session.scalars(
                    select(WorkspaceTemplate)
                    .where(WorkspaceTemplate.organization_id == organization_id)
                    .order_by(WorkspaceTemplate.name)
                )
            ).all()
        )

    async def create_template(
        self,
        organization_id: uuid.UUID,
        body: WorkspaceTemplateInput,
        actor_id: uuid.UUID,
    ) -> WorkspaceTemplate:
        duplicate = await self.session.scalar(
            select(WorkspaceTemplate.id).where(
                WorkspaceTemplate.organization_id == organization_id,
                WorkspaceTemplate.name == body.name,
            )
        )
        if duplicate:
            raise ConflictError("Workspace template name is already in use")
        template = WorkspaceTemplate(
            organization_id=organization_id,
            created_by=actor_id,
            **body.model_dump(),
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def bulk_lifecycle(
        self,
        organization_id: uuid.UUID,
        workspace_ids: list[uuid.UUID],
        action: str,
        actor_id: uuid.UUID,
    ) -> WorkspaceBulkResult:
        updated: list[uuid.UUID] = []
        skipped: list[uuid.UUID] = []
        workspace_id: uuid.UUID
        for workspace_id in dict.fromkeys(workspace_ids):
            try:
                await self.archive(
                    organization_id,
                    workspace_id,
                    action == "archive",
                    actor_id,
                )
                updated.append(workspace_id)
            except (NotFoundError, ConflictError):
                skipped.append(workspace_id)
        return WorkspaceBulkResult(updated_ids=updated, skipped_ids=skipped)

    async def _record(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
    ) -> None:
        self.session.add(
            ActivityEvent(
                organization_id=organization_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type=action,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={},
            )
        )
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=actor_id,
                action=action,
                resource="workspace",
                resource_id=workspace_id,
                audit_metadata={},
            )
        )
