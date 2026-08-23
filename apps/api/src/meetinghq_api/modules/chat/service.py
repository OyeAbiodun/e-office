"""Enterprise chat storage and collaboration application services."""

# ruff: noqa: E501

import re
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.chat.delivery import MessageDelivery, NullMessageDelivery
from meetinghq_api.modules.chat.models import (
    AttachmentReference,
    ChannelTab,
    ChatThread,
    Conversation,
    ConversationMember,
    ConversationType,
    Message,
    MessageDraft,
    PinnedMessage,
    Presence,
    PresenceStatus,
    Reaction,
    SavedMessage,
)
from meetinghq_api.modules.chat.repository import ChatRepository
from meetinghq_api.modules.chat.schemas import (
    ConversationCreate,
    ConversationUpdate,
    MemberInput,
    MessageInput,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import Workspace
from meetinghq_api.shared.events import DomainEvent
from meetinghq_api.shared.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


def serialize(model: object) -> dict[str, object]:
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns  # type: ignore[attr-defined]
    }


class ChatService:
    def __init__(self, session: AsyncSession, delivery: MessageDelivery | None = None) -> None:
        self.session = session
        self.repository = ChatRepository(session)
        self.events = TransactionalDomainEventPublisher(session)
        self.delivery = delivery or NullMessageDelivery()

    async def list_conversations(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, archived: bool = False
    ) -> list[dict[str, object]]:
        conversations = await self.repository.conversations(organization_id, user_id, archived)
        return [await self._conversation_summary(item, user_id) for item in conversations]

    async def get_conversation(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, object]:
        conversation = await self._require_member(organization_id, conversation_id, user_id)
        return await self._conversation_summary(conversation, user_id)

    async def create_conversation(
        self, organization_id: uuid.UUID, body: ConversationCreate, actor_id: uuid.UUID
    ) -> Conversation:
        workspace = await self.session.scalar(
            select(Workspace.id).where(
                Workspace.id == body.workspace_id,
                Workspace.organization_id == organization_id,
            )
        )
        if workspace is None:
            raise NotFoundError("Workspace not found")
        member_ids = set(body.member_ids) | {actor_id}
        if body.type == ConversationType.DIRECT and len(member_ids) != 2:
            raise ValidationError("Direct messages require exactly two members")
        await self._validate_users(organization_id, member_ids)
        if body.type == ConversationType.DIRECT:
            existing = await self._existing_direct(organization_id, member_ids)
            if existing:
                return existing
        conversation = Conversation(
            organization_id=organization_id,
            created_by=actor_id,
            **body.model_dump(exclude={"member_ids"}),
        )
        self.session.add(conversation)
        await self.session.flush()
        for user_id in member_ids:
            self.session.add(
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    role="owner" if user_id == actor_id else "member",
                )
            )
        if body.team_id is not None:
            for sort_order, (name, tab_type) in enumerate(
                (
                    ("Posts", "posts"),
                    ("Files", "files"),
                    ("Meetings", "meetings"),
                    ("Wiki", "wiki"),
                    ("Notes", "notes"),
                    ("Calendar", "calendar"),
                    ("Apps", "apps"),
                )
            ):
                self.session.add(
                    ChannelTab(
                        conversation_id=conversation.id,
                        name=name,
                        tab_type=tab_type,
                        sort_order=sort_order,
                        created_by=actor_id,
                    )
                )
        await self._record("ConversationCreated", conversation, actor_id)
        return conversation

    async def update_conversation(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        body: ConversationUpdate,
        actor_id: uuid.UUID,
    ) -> Conversation:
        conversation = await self._require_manager(organization_id, conversation_id, actor_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(conversation, field, value)
        await self._record("ConversationUpdated", conversation, actor_id)
        return conversation

    async def archive(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Conversation:
        conversation = await self._require_manager(organization_id, conversation_id, actor_id)
        conversation.archived_at = datetime.now(UTC)
        await self._record("ConversationArchived", conversation, actor_id)
        return conversation

    async def add_member(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        body: MemberInput,
        actor_id: uuid.UUID,
    ) -> ConversationMember:
        conversation = await self._require_manager(organization_id, conversation_id, actor_id)
        await self._validate_users(organization_id, {body.user_id})
        existing = await self.repository.member(conversation.id, body.user_id)
        if existing:
            return existing
        member = ConversationMember(conversation_id=conversation.id, **body.model_dump())
        self.session.add(member)
        await self.session.flush()
        await self._record(
            "ConversationMemberAdded", conversation, actor_id, {"user_id": str(body.user_id)}
        )
        return member

    async def remove_member(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        member_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        conversation = await self._require_manager(organization_id, conversation_id, actor_id)
        member = await self.session.scalar(
            select(ConversationMember).where(
                ConversationMember.id == member_id,
                ConversationMember.conversation_id == conversation.id,
            )
        )
        if member is None:
            raise NotFoundError("Conversation member not found")
        await self.session.delete(member)
        await self._record(
            "ConversationMemberRemoved", conversation, actor_id, {"user_id": str(member.user_id)}
        )

    async def list_messages(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        cursor: str | None,
        limit: int,
        parent_id: uuid.UUID | None = None,
    ) -> tuple[list[dict[str, object]], str | None, bool]:
        await self._require_member(organization_id, conversation_id, user_id)
        messages, next_cursor, has_more = await self.repository.messages(
            conversation_id, cursor, limit, parent_id
        )
        return (
            [await self.message_detail(item) for item in reversed(messages)],
            next_cursor,
            has_more,
        )

    async def send_message(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        body: MessageInput,
        sender_id: uuid.UUID,
    ) -> Message:
        conversation = await self._require_member(organization_id, conversation_id, sender_id)
        if conversation.archived_at:
            raise ConflictError("Archived conversations are read only")
        if conversation.type == ConversationType.ANNOUNCEMENT:
            member = await self.repository.member(conversation.id, sender_id)
            if member is None or member.role not in {"owner", "admin"}:
                raise AuthorizationError("Only channel managers can post announcements")
        parent = None
        if body.parent_message_id:
            parent = await self.session.scalar(
                select(Message).where(
                    Message.id == body.parent_message_id,
                    Message.conversation_id == conversation.id,
                    Message.deleted_at.is_(None),
                )
            )
            if parent is None:
                raise NotFoundError("Thread root not found")
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            **body.model_dump(exclude={"attachments"}),
        )
        self.session.add(message)
        await self.session.flush()
        for metadata in body.attachments:
            required = {"storage_key", "filename", "content_type", "size"}
            if not required <= metadata.keys():
                raise ValidationError("Attachment metadata is incomplete")
            self.session.add(AttachmentReference(message_id=message.id, **metadata))
        if parent:
            thread = await self.session.scalar(
                select(ChatThread).where(ChatThread.root_message_id == parent.id)
            )
            if thread is None:
                thread = ChatThread(
                    conversation_id=conversation.id,
                    root_message_id=parent.id,
                    reply_count=0,
                )
                self.session.add(thread)
                await self._record(
                    "ThreadCreated", conversation, sender_id, {"root_message_id": str(parent.id)}
                )
            thread.reply_count += 1
            thread.latest_reply_id = message.id
        conversation.updated_at = datetime.now(UTC)
        draft = await self.draft(organization_id, conversation_id, sender_id)
        if draft is not None:
            await self.session.delete(draft)
        payload = await self.message_detail(message)
        payload["mentions"] = sorted(set(re.findall(r"@([A-Za-z0-9_.-]+)", body.body)))
        await self._record(
            "MessageSent",
            conversation,
            sender_id,
            {
                "message_id": str(message.id),
                "parent_message_id": str(parent.id) if parent else None,
            },
        )
        await self.delivery.publish(conversation.id, {"type": "message.new", "data": payload})
        return message

    async def edit_message(
        self,
        organization_id: uuid.UUID,
        message_id: uuid.UUID,
        body: str,
        actor_id: uuid.UUID,
    ) -> Message:
        message, conversation = await self._message(organization_id, message_id, actor_id)
        if message.sender_id != actor_id:
            raise AuthorizationError("Only the sender can edit this message")
        message.body = body
        message.edited = True
        message.edited_at = datetime.now(UTC)
        await self._record("MessageEdited", conversation, actor_id, {"message_id": str(message.id)})
        await self.delivery.publish(
            conversation.id, {"type": "message.edited", "data": await self.message_detail(message)}
        )
        return message

    async def delete_message(
        self, organization_id: uuid.UUID, message_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Message:
        message, conversation = await self._message(organization_id, message_id, actor_id)
        member = await self.repository.member(conversation.id, actor_id)
        if message.sender_id != actor_id and (
            member is None or member.role not in {"owner", "admin"}
        ):
            raise AuthorizationError("Message deletion is not permitted")
        message.deleted_at = datetime.now(UTC)
        message.body = ""
        await self._record(
            "MessageDeleted", conversation, actor_id, {"message_id": str(message.id)}
        )
        await self.delivery.publish(
            conversation.id, {"type": "message.deleted", "data": {"id": str(message.id)}}
        )
        return message

    async def reaction(
        self,
        organization_id: uuid.UUID,
        message_id: uuid.UUID,
        emoji: str,
        user_id: uuid.UUID,
        remove: bool = False,
    ) -> Reaction | None:
        message, conversation = await self._message(organization_id, message_id, user_id)
        reaction = await self.session.scalar(
            select(Reaction).where(
                Reaction.message_id == message.id,
                Reaction.user_id == user_id,
                Reaction.emoji == emoji,
            )
        )
        if remove:
            if reaction:
                await self.session.delete(reaction)
            await self._record(
                "ReactionRemoved",
                conversation,
                user_id,
                {"message_id": str(message.id), "emoji": emoji},
            )
            await self.delivery.publish(
                conversation.id,
                {
                    "type": "reaction.removed",
                    "data": {
                        "message_id": str(message.id),
                        "emoji": emoji,
                        "user_id": str(user_id),
                    },
                },
            )
            return None
        if reaction is None:
            reaction = Reaction(message_id=message.id, user_id=user_id, emoji=emoji)
            self.session.add(reaction)
            await self.session.flush()
            await self._record(
                "ReactionAdded",
                conversation,
                user_id,
                {"message_id": str(message.id), "emoji": emoji},
            )
            await self.delivery.publish(
                conversation.id, {"type": "reaction.added", "data": serialize(reaction)}
            )
        return reaction

    async def pin(
        self, organization_id: uuid.UUID, message_id: uuid.UUID, actor_id: uuid.UUID
    ) -> PinnedMessage:
        message, conversation = await self._message(organization_id, message_id, actor_id)
        existing = await self.session.scalar(
            select(PinnedMessage).where(PinnedMessage.message_id == message.id)
        )
        if existing:
            return existing
        pin = PinnedMessage(
            conversation_id=conversation.id, message_id=message.id, pinned_by=actor_id
        )
        self.session.add(pin)
        await self.session.flush()
        await self._record("MessagePinned", conversation, actor_id, {"message_id": str(message.id)})
        await self.delivery.publish(
            conversation.id, {"type": "message.pinned", "data": serialize(pin)}
        )
        return pin

    async def pins(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict[str, object]]:
        await self._require_member(organization_id, conversation_id, user_id)
        rows = (
            await self.session.scalars(
                select(PinnedMessage)
                .where(PinnedMessage.conversation_id == conversation_id)
                .order_by(PinnedMessage.pinned_at.desc())
            )
        ).all()
        return [serialize(row) for row in rows]

    async def tabs(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ChannelTab]:
        await self._require_member(organization_id, conversation_id, user_id)
        return list(
            (
                await self.session.scalars(
                    select(ChannelTab)
                    .where(ChannelTab.conversation_id == conversation_id)
                    .order_by(ChannelTab.sort_order, ChannelTab.name)
                )
            ).all()
        )

    async def add_tab(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        name: str,
        tab_type: str,
        configuration: str,
        sort_order: int,
        actor_id: uuid.UUID,
    ) -> ChannelTab:
        conversation = await self._require_manager(organization_id, conversation_id, actor_id)
        existing = await self.session.scalar(
            select(ChannelTab.id).where(
                ChannelTab.conversation_id == conversation.id,
                ChannelTab.name == name,
            )
        )
        if existing is not None:
            raise ConflictError("A channel tab with this name already exists")
        tab = ChannelTab(
            conversation_id=conversation.id,
            name=name,
            tab_type=tab_type,
            configuration=configuration,
            sort_order=sort_order,
            created_by=actor_id,
        )
        self.session.add(tab)
        await self.session.flush()
        await self._record("ChannelTabAdded", conversation, actor_id, {"tab_id": str(tab.id)})
        return tab

    async def draft(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> MessageDraft | None:
        await self._require_member(organization_id, conversation_id, user_id)
        return cast(
            MessageDraft | None,
            await self.session.scalar(
                select(MessageDraft).where(
                    MessageDraft.conversation_id == conversation_id,
                    MessageDraft.user_id == user_id,
                )
            ),
        )

    async def save_draft(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        body: str,
        user_id: uuid.UUID,
    ) -> MessageDraft:
        await self._require_member(organization_id, conversation_id, user_id)
        draft = await self.draft(organization_id, conversation_id, user_id)
        if draft is None:
            draft = MessageDraft(conversation_id=conversation_id, user_id=user_id, body=body)
            self.session.add(draft)
            await self.session.flush()
        else:
            draft.body = body
            draft.updated_at = datetime.now(UTC)
        return draft

    async def save_message(
        self,
        organization_id: uuid.UUID,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        note: str | None,
    ) -> SavedMessage:
        message, _ = await self._message(organization_id, message_id, user_id)
        saved = await self.session.scalar(
            select(SavedMessage).where(
                SavedMessage.user_id == user_id,
                SavedMessage.message_id == message.id,
            )
        )
        if saved is None:
            saved = SavedMessage(user_id=user_id, message_id=message.id, note=note)
            self.session.add(saved)
            await self.session.flush()
        else:
            saved.note = note
        return saved

    async def saved_messages(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict[str, object]]:
        rows = (
            await self.session.execute(
                select(SavedMessage, Message, Conversation)
                .join(Message, Message.id == SavedMessage.message_id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(
                    SavedMessage.user_id == user_id,
                    Conversation.organization_id == organization_id,
                )
                .order_by(SavedMessage.saved_at.desc())
            )
        ).all()
        return [
            {
                **serialize(saved),
                "message": {
                    **serialize(message),
                    "conversation_name": conversation.name,
                },
            }
            for saved, message, conversation in rows
        ]

    async def mark_read(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ConversationMember:
        conversation = await self._require_member(organization_id, conversation_id, user_id)
        member = await self.repository.member(conversation.id, user_id)
        message = await self.session.scalar(
            select(Message.id).where(
                Message.id == message_id, Message.conversation_id == conversation.id
            )
        )
        if member is None or message is None:
            raise NotFoundError("Message not found")
        member.last_read_message_id = message_id
        await self.delivery.publish(
            conversation.id,
            {
                "type": "message.read",
                "data": {"message_id": str(message_id), "user_id": str(user_id)},
            },
        )
        return member

    async def message_detail(self, message: Message) -> dict[str, object]:
        payload = serialize(message)
        sender = await self.session.get(User, message.sender_id)
        payload["sender_name"] = sender.display_name if sender else "Unknown member"
        reactions = (
            await self.session.scalars(select(Reaction).where(Reaction.message_id == message.id))
        ).all()
        attachments = (
            await self.session.scalars(
                select(AttachmentReference).where(AttachmentReference.message_id == message.id)
            )
        ).all()
        thread = await self.session.scalar(
            select(ChatThread).where(ChatThread.root_message_id == message.id)
        )
        payload["reactions"] = [serialize(item) for item in reactions]
        payload["attachments"] = [serialize(item) for item in attachments]
        payload["thread"] = serialize(thread) if thread else None
        payload["delivery_status"] = "delivered"
        return payload

    async def dashboard(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        conversations = await self.repository.conversations(organization_id, user_id, False)
        summaries = [await self._conversation_summary(item, user_id) for item in conversations[:6]]
        unread = sum(
            value if isinstance(value := item["unread_count"], int) else 0 for item in summaries
        )
        active_channels = sum(item.type != ConversationType.DIRECT for item in conversations)
        online = (
            await self.session.scalar(
                select(func.count(Presence.user_id))
                .join(User, User.id == Presence.user_id)
                .where(
                    User.organization_id == organization_id,
                    Presence.status != PresenceStatus.OFFLINE,
                )
            )
            or 0
        )
        return {
            "unread_messages": unread,
            "recent_conversations": summaries,
            "active_channels": active_channels,
            "online_members": online,
        }

    async def _conversation_summary(
        self, conversation: Conversation, user_id: uuid.UUID
    ) -> dict[str, object]:
        payload = serialize(conversation)
        member = await self.repository.member(conversation.id, user_id)
        last_message = await self.session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        unread_query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id,
            Message.sender_id != user_id,
            Message.deleted_at.is_(None),
        )
        if member and member.last_read_message_id:
            last_read = await self.session.get(Message, member.last_read_message_id)
            if last_read:
                unread_query = unread_query.where(Message.created_at > last_read.created_at)
        payload["last_message"] = await self.message_detail(last_message) if last_message else None
        payload["unread_count"] = await self.session.scalar(unread_query) or 0
        payload["member_count"] = (
            await self.session.scalar(
                select(func.count(ConversationMember.id)).where(
                    ConversationMember.conversation_id == conversation.id
                )
            )
            or 0
        )
        return payload

    async def _require_member(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        conversation = await self.repository.conversation(organization_id, conversation_id)
        if conversation is None or await self.repository.member(conversation_id, user_id) is None:
            raise NotFoundError("Conversation not found")
        return conversation

    async def _require_manager(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        conversation = await self._require_member(organization_id, conversation_id, user_id)
        member = await self.repository.member(conversation_id, user_id)
        if member is None or member.role not in {"owner", "admin"}:
            raise AuthorizationError("Conversation manager access is required")
        return conversation

    async def _message(
        self, organization_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Message, Conversation]:
        message = await self.session.get(Message, message_id)
        if message is None:
            raise NotFoundError("Message not found")
        conversation = await self._require_member(organization_id, message.conversation_id, user_id)
        return message, conversation

    async def _validate_users(self, organization_id: uuid.UUID, user_ids: set[uuid.UUID]) -> None:
        found = set(
            (
                await self.session.scalars(
                    select(User.id).where(
                        User.organization_id == organization_id,
                        User.id.in_(user_ids),
                        User.removed_at.is_(None),
                    )
                )
            ).all()
        )
        if found != user_ids:
            raise ValidationError("Every conversation member must belong to the organization")

    async def _existing_direct(
        self, organization_id: uuid.UUID, member_ids: set[uuid.UUID]
    ) -> Conversation | None:
        candidates = (
            await self.session.scalars(
                select(Conversation).where(
                    Conversation.organization_id == organization_id,
                    Conversation.type == ConversationType.DIRECT,
                    Conversation.archived_at.is_(None),
                )
            )
        ).all()
        for conversation in candidates:
            members = set(
                (
                    await self.session.scalars(
                        select(ConversationMember.user_id).where(
                            ConversationMember.conversation_id == conversation.id
                        )
                    )
                ).all()
            )
            if members == member_ids:
                return conversation
        return None

    async def _record(
        self,
        name: str,
        conversation: Conversation,
        actor_id: uuid.UUID,
        payload: dict[str, object] | None = None,
    ) -> None:
        await self.events.publish(
            DomainEvent(
                name=name,
                organization_id=conversation.organization_id,
                workspace_id=conversation.workspace_id,
                actor_id=actor_id,
                aggregate_type="conversation",
                aggregate_id=conversation.id,
                payload=payload or {},
            )
        )
        self.session.add(
            AuditLog(
                organization_id=conversation.organization_id,
                user_id=actor_id,
                action=name,
                resource="conversation",
                resource_id=conversation.id,
                audit_metadata=payload or {},
            )
        )
