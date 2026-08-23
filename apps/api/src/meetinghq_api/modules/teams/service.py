"""Team application service."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.calendar.models import Calendar
from meetinghq_api.modules.chat.models import (
    AttachmentReference,
    Conversation,
    ConversationMember,
    ConversationType,
    Message,
    Presence,
)
from meetinghq_api.modules.meetings.models import (
    Meeting,
    MeetingActionItem,
    MeetingArtifact,
)
from meetinghq_api.modules.teams.models import (
    ChannelPreference,
    Team,
    TeamDocument,
    TeamIntegration,
    TeamMember,
    TeamMemberRole,
)
from meetinghq_api.modules.teams.schemas import (
    ChannelCreate,
    ChannelPreferenceUpdate,
    ChannelResponse,
    ChannelUpdate,
    TeamBulkResult,
    TeamCreate,
    TeamDocumentInput,
    TeamIntegrationInput,
    TeamOverview,
    TeamResponse,
    TeamUpdate,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import Workspace
from meetinghq_api.shared.events import DomainEvent, DomainEventPublisher
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError


class TeamService:
    """Tenant-safe team and membership use cases."""

    def __init__(self, session: AsyncSession, events: DomainEventPublisher | None = None) -> None:
        self.session = session
        self.events = events or TransactionalDomainEventPublisher(session)

    async def get(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> Team:
        team = await self.session.scalar(
            select(Team).where(Team.id == team_id, Team.organization_id == organization_id)
        )
        if team is None:
            raise NotFoundError("Team not found")
        return team

    async def list_teams(
        self,
        organization_id: uuid.UUID,
        *,
        workspace_id: uuid.UUID | None = None,
        search: str | None = None,
        archived: bool | None = None,
        visibility: str | None = None,
    ) -> list[Team]:
        query = select(Team).where(
            Team.organization_id == organization_id,
            Team.deleted_at.is_(None),
        )
        if workspace_id:
            query = query.where(Team.workspace_id == workspace_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(Team.name.ilike(term), Team.slug.ilike(term)))
        if archived is not None:
            query = query.where(
                Team.archived_at.is_not(None) if archived else Team.archived_at.is_(None)
            )
        if visibility:
            query = query.where(Team.visibility == visibility)
        return list(
            (
                await self.session.scalars(query.order_by(Team.archived_at.is_not(None), Team.name))
            ).all()
        )

    async def create(
        self, organization_id: uuid.UUID, body: TeamCreate, actor_id: uuid.UUID
    ) -> Team:
        workspace = await self.session.scalar(
            select(Workspace.id).where(
                Workspace.id == body.workspace_id,
                Workspace.organization_id == organization_id,
                Workspace.archived_at.is_(None),
            )
        )
        if workspace is None:
            raise NotFoundError("Workspace not found")
        if await self.session.scalar(
            select(Team.id).where(Team.workspace_id == body.workspace_id, Team.slug == body.slug)
        ):
            raise ConflictError("Team slug is already in use")
        team = Team(
            organization_id=organization_id,
            owner_id=actor_id,
            **body.model_dump(),
        )
        self.session.add(team)
        await self.session.flush()
        self.session.add(TeamMember(team_id=team.id, user_id=actor_id, role=TeamMemberRole.OWNER))
        await self.events.publish(
            DomainEvent(
                name="TeamCreated",
                organization_id=organization_id,
                workspace_id=team.workspace_id,
                actor_id=actor_id,
                aggregate_type="team",
                aggregate_id=team.id,
                payload={"name": team.name},
            )
        )
        return team

    async def update(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        body: TeamUpdate,
        actor_id: uuid.UUID,
    ) -> Team:
        team = await self.get(organization_id, team_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(team, field, value)
        await self.events.publish(
            DomainEvent(
                name="TeamUpdated",
                organization_id=organization_id,
                workspace_id=team.workspace_id,
                actor_id=actor_id,
                aggregate_type="team",
                aggregate_id=team.id,
            )
        )
        return team

    async def members(
        self, organization_id: uuid.UUID, team_id: uuid.UUID
    ) -> Sequence[tuple[TeamMember, User]]:
        await self.get(organization_id, team_id)
        rows = await self.session.execute(
            select(TeamMember, User)
            .join(User, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id)
            .order_by(User.display_name)
        )
        return list(rows.tuples().all())

    async def add_member(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        role: TeamMemberRole,
        actor_id: uuid.UUID,
    ) -> TeamMember:
        team = await self.get(organization_id, team_id)
        if (
            await self.session.scalar(
                select(User.id).where(User.id == user_id, User.organization_id == organization_id)
            )
            is None
        ):
            raise NotFoundError("User not found")
        existing = await self.session.scalar(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        if existing:
            raise ConflictError("User is already a team member")
        member = TeamMember(team_id=team_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.events.publish(
            DomainEvent(
                name="TeamMemberAdded",
                organization_id=organization_id,
                workspace_id=team.workspace_id,
                actor_id=actor_id,
                aggregate_type="user",
                aggregate_id=user_id,
                payload={"team_id": str(team_id), "role": role.value},
            )
        )
        return member

    async def remove_member(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self.get(organization_id, team_id)
        member = await self.session.scalar(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        if member is None:
            raise NotFoundError("Team member not found")
        if member.role == TeamMemberRole.OWNER:
            raise ConflictError("Transfer ownership before removing the owner")
        await self.session.delete(member)

    async def set_role(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        role: TeamMemberRole,
    ) -> TeamMember:
        await self.get(organization_id, team_id)
        member = await self.session.scalar(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        if member is None:
            raise NotFoundError("Team member not found")
        if role == TeamMemberRole.OWNER:
            raise ConflictError("Use ownership transfer")
        if member.role == TeamMemberRole.OWNER:
            raise ConflictError("Transfer ownership before changing the owner role")
        member.role = role
        return member

    async def transfer(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        new_owner_id: uuid.UUID,
    ) -> None:
        await self.get(organization_id, team_id)
        owner = await self.session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.role == TeamMemberRole.OWNER,
            )
        )
        new_owner = await self.session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == new_owner_id
            )
        )
        if owner is None or new_owner is None:
            raise NotFoundError("Team owner or member not found")
        owner.role = TeamMemberRole.MANAGER
        new_owner.role = TeamMemberRole.OWNER

    async def leave(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self.remove_member(organization_id, team_id, user_id)

    async def lifecycle(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        archived: bool,
        actor_id: uuid.UUID,
    ) -> Team:
        team = await self.get(organization_id, team_id)
        team.archived_at = datetime.now(UTC) if archived else None
        await self._record(
            team,
            actor_id,
            "team.archived" if archived else "team.restored",
        )
        return team

    async def overview(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> TeamOverview:
        team = await self.get(organization_id, team_id)

        async def count(model: type[object], *conditions: Any) -> int:
            value = await self.session.scalar(
                select(func.count()).select_from(model).where(*conditions)
            )
            return int(value or 0)

        channel_ids = select(Conversation.id).where(
            Conversation.organization_id == organization_id,
            Conversation.team_id == team_id,
        )
        meeting_ids = select(Meeting.id).where(
            Meeting.organization_id == organization_id,
            Meeting.workspace_id == team.workspace_id,
        )
        # Meetings currently inherit the Team's workspace boundary until a
        # direct team_id is added to the meeting aggregate.
        meeting_scope = (
            Meeting.organization_id == organization_id,
            Meeting.workspace_id == team.workspace_id,
        )
        now = datetime.now(UTC)
        recent_channels = (
            await self.session.scalars(
                select(Conversation)
                .where(
                    Conversation.organization_id == organization_id,
                    Conversation.team_id == team_id,
                )
                .order_by(Conversation.updated_at.desc())
                .limit(6)
            )
        ).all()
        upcoming = (
            await self.session.scalars(
                select(Meeting)
                .where(
                    Meeting.organization_id == organization_id,
                    Meeting.workspace_id == team.workspace_id,
                    Meeting.start_datetime >= now,
                )
                .order_by(Meeting.start_datetime)
                .limit(6)
            )
        ).all()
        activities = (
            await self.session.scalars(
                select(ActivityEvent)
                .where(
                    ActivityEvent.organization_id == organization_id,
                    ActivityEvent.workspace_id == team.workspace_id,
                    ActivityEvent.subject_type == "team",
                    ActivityEvent.subject_id == team.id,
                )
                .order_by(ActivityEvent.occurred_at.desc())
                .limit(12)
            )
        ).all()
        chat_bytes = await self.session.scalar(
            select(func.coalesce(func.sum(AttachmentReference.size), 0)).where(
                AttachmentReference.message_id.in_(
                    select(Message.id).where(Message.conversation_id.in_(channel_ids))
                )
            )
        )
        artifact_bytes = await self.session.scalar(
            select(func.coalesce(func.sum(MeetingArtifact.size), 0)).where(
                MeetingArtifact.meeting_id.in_(meeting_ids)
            )
        )
        members = await count(TeamMember, TeamMember.team_id == team_id)
        active_members = await count(
            Presence,
            Presence.user_id.in_(select(TeamMember.user_id).where(TeamMember.team_id == team_id)),
            Presence.status != "offline",
        )
        channels = await count(
            Conversation,
            Conversation.organization_id == organization_id,
            Conversation.team_id == team_id,
            Conversation.archived_at.is_(None),
        )
        files = await count(
            AttachmentReference,
            AttachmentReference.message_id.in_(
                select(Message.id).where(Message.conversation_id.in_(channel_ids))
            ),
        ) + await count(MeetingArtifact, MeetingArtifact.meeting_id.in_(meeting_ids))
        health = 40
        health += 15 if members > 1 else 0
        health += 15 if channels else 0
        health += 10 if team.description else 0
        health += 10 if active_members else 0
        health += 10 if team.settings else 0
        return TeamOverview(
            team=TeamResponse.model_validate(team),
            owner_count=await count(
                TeamMember,
                TeamMember.team_id == team_id,
                TeamMember.role == TeamMemberRole.OWNER,
            ),
            administrator_count=await count(
                TeamMember,
                TeamMember.team_id == team_id,
                TeamMember.role == TeamMemberRole.MANAGER,
            ),
            member_count=members,
            guest_count=0,
            channel_count=channels,
            meeting_count=await count(Meeting, *meeting_scope),
            upcoming_meeting_count=len(upcoming),
            calendar_count=await count(
                Calendar,
                Calendar.organization_id == organization_id,
                Calendar.team_id == team_id,
                Calendar.deleted_at.is_(None),
            ),
            file_count=files,
            storage_bytes=int(chat_bytes or 0) + int(artifact_bytes or 0),
            wiki_count=await count(
                TeamDocument,
                TeamDocument.organization_id == organization_id,
                TeamDocument.team_id == team_id,
                TeamDocument.document_type == "wiki",
            ),
            note_count=await count(
                TeamDocument,
                TeamDocument.organization_id == organization_id,
                TeamDocument.team_id == team_id,
                TeamDocument.document_type == "note",
            ),
            app_count=await count(
                TeamIntegration,
                TeamIntegration.organization_id == organization_id,
                TeamIntegration.team_id == team_id,
                TeamIntegration.enabled.is_(True),
            ),
            active_member_count=active_members,
            open_action_count=await count(
                MeetingActionItem,
                MeetingActionItem.meeting_id.in_(meeting_ids),
                MeetingActionItem.status != "completed",
            ),
            announcement_count=await count(
                Conversation,
                Conversation.organization_id == organization_id,
                Conversation.team_id == team_id,
                Conversation.channel_kind == "announcement",
            ),
            health_score=min(health, 100),
            recent_activity=[
                {
                    "id": str(item.id),
                    "event_type": item.event_type,
                    "occurred_at": item.occurred_at,
                }
                for item in activities
            ],
            recent_conversations=[
                {
                    "id": str(item.id),
                    "name": item.name or "Channel",
                    "channel_kind": item.channel_kind,
                    "updated_at": item.updated_at,
                }
                for item in recent_channels
            ],
            upcoming_meetings=[
                {
                    "id": str(item.id),
                    "title": item.title,
                    "start_datetime": item.start_datetime,
                    "status": item.status.value,
                }
                for item in upcoming
            ],
        )

    async def channels(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        search: str | None = None,
        archived: bool | None = None,
        channel_kind: str | None = None,
    ) -> list[ChannelResponse]:
        await self.get(organization_id, team_id)
        query = select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.team_id == team_id,
        )
        if search:
            query = query.where(Conversation.name.ilike(f"%{search.strip()}%"))
        if archived is not None:
            query = query.where(
                Conversation.archived_at.is_not(None)
                if archived
                else Conversation.archived_at.is_(None)
            )
        if channel_kind:
            query = query.where(Conversation.channel_kind == channel_kind)
        rows = (await self.session.scalars(query.order_by(Conversation.name))).all()
        result: list[ChannelResponse] = []
        for channel in rows:
            preference = await self.session.scalar(
                select(ChannelPreference).where(
                    ChannelPreference.organization_id == organization_id,
                    ChannelPreference.conversation_id == channel.id,
                    ChannelPreference.user_id == actor_id,
                )
            )
            message_count = await count_scalar(
                self.session,
                Message,
                Message.conversation_id == channel.id,
                Message.deleted_at.is_(None),
            )
            member_count = await count_scalar(
                self.session,
                ConversationMember,
                ConversationMember.conversation_id == channel.id,
            )
            last_activity = await self.session.scalar(
                select(func.max(Message.created_at)).where(Message.conversation_id == channel.id)
            )
            result.append(
                ChannelResponse(
                    id=channel.id,
                    name=channel.name or "Channel",
                    description=channel.description,
                    channel_kind=channel.channel_kind,
                    visibility=channel.visibility,
                    moderation_enabled=channel.moderation_enabled,
                    read_only=channel.read_only,
                    favorite=preference.favorite if preference else False,
                    pinned=preference.pinned if preference else False,
                    archived_at=channel.archived_at,
                    message_count=message_count,
                    member_count=member_count,
                    last_activity=last_activity,
                )
            )
        return result

    async def create_channel(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        body: ChannelCreate,
        actor_id: uuid.UUID,
    ) -> Conversation:
        team = await self.get(organization_id, team_id)
        duplicate = await self.session.scalar(
            select(Conversation.id).where(
                Conversation.organization_id == organization_id,
                Conversation.team_id == team_id,
                Conversation.name == body.name,
                Conversation.archived_at.is_(None),
            )
        )
        if duplicate:
            raise ConflictError("Channel name is already in use")
        conversation = Conversation(
            organization_id=organization_id,
            workspace_id=team.workspace_id,
            team_id=team_id,
            type=(
                ConversationType.PRIVATE_TEAM
                if body.visibility == "private"
                else ConversationType.PUBLIC_TEAM
            ),
            created_by=actor_id,
            **body.model_dump(),
        )
        self.session.add(conversation)
        await self.session.flush()
        self.session.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=actor_id,
                role="owner",
                notification_preference="all",
            )
        )
        await self._record(team, actor_id, "team.channel_created")
        return conversation

    async def update_channel(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        channel_id: uuid.UUID,
        body: ChannelUpdate,
        actor_id: uuid.UUID,
    ) -> Conversation:
        team = await self.get(organization_id, team_id)
        channel = await self._channel(organization_id, team_id, channel_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(channel, field, value)
        await self._record(team, actor_id, "team.channel_updated")
        return channel

    async def channel_lifecycle(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        channel_id: uuid.UUID,
        archived: bool,
        actor_id: uuid.UUID,
    ) -> Conversation:
        team = await self.get(organization_id, team_id)
        channel = await self._channel(organization_id, team_id, channel_id)
        channel.archived_at = datetime.now(UTC) if archived else None
        await self._record(
            team,
            actor_id,
            "team.channel_archived" if archived else "team.channel_restored",
        )
        return channel

    async def set_channel_preference(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        channel_id: uuid.UUID,
        actor_id: uuid.UUID,
        body: ChannelPreferenceUpdate,
    ) -> ChannelPreference:
        await self._channel(organization_id, team_id, channel_id)
        preference = await self.session.scalar(
            select(ChannelPreference).where(
                ChannelPreference.organization_id == organization_id,
                ChannelPreference.conversation_id == channel_id,
                ChannelPreference.user_id == actor_id,
            )
        )
        if preference is None:
            preference = ChannelPreference(
                organization_id=organization_id,
                conversation_id=channel_id,
                user_id=actor_id,
            )
            self.session.add(preference)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(preference, field, value)
        return preference

    async def documents(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, document_type: str
    ) -> list[TeamDocument]:
        await self.get(organization_id, team_id)
        return list(
            (
                await self.session.scalars(
                    select(TeamDocument)
                    .where(
                        TeamDocument.organization_id == organization_id,
                        TeamDocument.team_id == team_id,
                        TeamDocument.document_type == document_type,
                    )
                    .order_by(TeamDocument.updated_at.desc())
                )
            ).all()
        )

    async def create_document(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        body: TeamDocumentInput,
        actor_id: uuid.UUID,
    ) -> TeamDocument:
        team = await self.get(organization_id, team_id)
        document = TeamDocument(
            organization_id=organization_id,
            team_id=team_id,
            created_by=actor_id,
            updated_by=actor_id,
            **body.model_dump(),
        )
        self.session.add(document)
        await self.session.flush()
        await self._record(team, actor_id, f"team.{body.document_type}_created")
        return document

    async def integrations(
        self, organization_id: uuid.UUID, team_id: uuid.UUID
    ) -> list[TeamIntegration]:
        await self.get(organization_id, team_id)
        return list(
            (
                await self.session.scalars(
                    select(TeamIntegration)
                    .where(
                        TeamIntegration.organization_id == organization_id,
                        TeamIntegration.team_id == team_id,
                    )
                    .order_by(TeamIntegration.display_name)
                )
            ).all()
        )

    async def upsert_integration(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        body: TeamIntegrationInput,
        actor_id: uuid.UUID,
    ) -> TeamIntegration:
        team = await self.get(organization_id, team_id)
        integration = await self.session.scalar(
            select(TeamIntegration).where(
                TeamIntegration.organization_id == organization_id,
                TeamIntegration.team_id == team_id,
                TeamIntegration.provider == body.provider,
            )
        )
        if integration is None:
            integration = TeamIntegration(
                organization_id=organization_id,
                team_id=team_id,
                created_by=actor_id,
                **body.model_dump(),
            )
            self.session.add(integration)
            await self.session.flush()
        else:
            for field, value in body.model_dump().items():
                setattr(integration, field, value)
        await self._record(team, actor_id, "team.integration_updated")
        return integration

    async def bulk_members(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        action: str,
    ) -> TeamBulkResult:
        await self.get(organization_id, team_id)
        updated: list[uuid.UUID] = []
        skipped: list[uuid.UUID] = []
        for user_id in dict.fromkeys(user_ids):
            try:
                if action == "remove":
                    await self.remove_member(organization_id, team_id, user_id)
                else:
                    await self.set_role(
                        organization_id,
                        team_id,
                        user_id,
                        (
                            TeamMemberRole.MANAGER
                            if action == "make_manager"
                            else TeamMemberRole.MEMBER
                        ),
                    )
                updated.append(user_id)
            except (NotFoundError, ConflictError):
                skipped.append(user_id)
        return TeamBulkResult(updated_ids=updated, skipped_ids=skipped)

    async def _channel(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        channel_id: uuid.UUID,
    ) -> Conversation:
        channel = await self.session.scalar(
            select(Conversation).where(
                Conversation.id == channel_id,
                Conversation.organization_id == organization_id,
                Conversation.team_id == team_id,
            )
        )
        if channel is None:
            raise NotFoundError("Channel not found")
        return channel

    async def _record(self, team: Team, actor_id: uuid.UUID, action: str) -> None:
        self.session.add(
            ActivityEvent(
                organization_id=team.organization_id,
                workspace_id=team.workspace_id,
                actor_id=actor_id,
                event_type=action,
                subject_type="team",
                subject_id=team.id,
                payload={},
            )
        )
        self.session.add(
            AuditLog(
                organization_id=team.organization_id,
                user_id=actor_id,
                action=action,
                resource="team",
                resource_id=team.id,
                audit_metadata={},
            )
        )


async def count_scalar(session: AsyncSession, model: type[object], *conditions: Any) -> int:
    value = await session.scalar(select(func.count()).select_from(model).where(*conditions))
    return int(value or 0)
