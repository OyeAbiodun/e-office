"""High-volume chat persistence adapters."""

import uuid
from typing import cast

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.chat.models import (
    Conversation,
    ConversationMember,
    Message,
)
from meetinghq_api.shared.pagination import decode_cursor, encode_cursor


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def conversation(
        self, organization_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Conversation | None:
        return cast(
            Conversation | None,
            await self.session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.organization_id == organization_id,
                )
            ),
        )

    async def member(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationMember | None:
        return cast(
            ConversationMember | None,
            await self.session.scalar(
                select(ConversationMember).where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            ),
        )

    async def conversations(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, archived: bool
    ) -> list[Conversation]:
        query = (
            select(Conversation)
            .join(ConversationMember)
            .where(
                Conversation.organization_id == organization_id,
                ConversationMember.user_id == user_id,
                (
                    Conversation.archived_at.is_not(None)
                    if archived
                    else Conversation.archived_at.is_(None)
                ),
            )
            .order_by(Conversation.updated_at.desc())
        )
        return list((await self.session.scalars(query)).all())

    async def messages(
        self,
        conversation_id: uuid.UUID,
        cursor: str | None,
        limit: int,
        parent_id: uuid.UUID | None = None,
    ) -> tuple[list[Message], str | None, bool]:
        query = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.parent_message_id == parent_id,
        )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    Message.created_at < created_at,
                    and_(
                        Message.created_at == created_at,
                        Message.id < uuid.UUID(entity_id),
                    ),
                )
            )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_cursor(items[-1].created_at, str(items[-1].id)) if has_more and items else None
        )
        return items, next_cursor, has_more
