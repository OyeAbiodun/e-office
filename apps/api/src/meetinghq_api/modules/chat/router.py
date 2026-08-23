"""REST and WebSocket transport for enterprise chat."""

# ruff: noqa: E501

import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.database import get_database_session, session_factory
from meetinghq_api.modules.auth.application.service import AuthService
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.chat.models import PresenceStatus
from meetinghq_api.modules.chat.presence import PresenceService
from meetinghq_api.modules.chat.realtime import realtime_hub
from meetinghq_api.modules.chat.schemas import (
    ChannelTabInput,
    ChatDashboard,
    ConversationCreate,
    ConversationUpdate,
    CursorMessages,
    DraftInput,
    MemberInput,
    MessageEdit,
    MessageInput,
    PresenceInput,
    ReactionInput,
    ReadReceiptInput,
    SavedMessageInput,
)
from meetinghq_api.modules.chat.service import ChatService, serialize
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(tags=["chat"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
ReadUser = Annotated[User, require_permission(Permissions.CHAT_READ)]


@router.get("/chat/dashboard", response_model=ChatDashboard)
async def chat_dashboard(session: Session, user: ReadUser) -> ChatDashboard:
    return ChatDashboard.model_validate(
        await ChatService(session).dashboard(user.organization_id, user.id)
    )


@router.get("/conversations")
async def list_conversations(
    session: Session, user: ReadUser, archived: bool = False
) -> list[dict[str, object]]:
    return await ChatService(session).list_conversations(user.organization_id, user.id, archived)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_CREATE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session).create_conversation(user.organization_id, body, user.id)
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, session: Session, user: ReadUser
) -> dict[str, object]:
    return await ChatService(session).get_conversation(
        user.organization_id, conversation_id, user.id
    )


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CONVERSATION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session).update_conversation(
            user.organization_id, conversation_id, body, user.id
        )
    )


@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CONVERSATION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session).archive(user.organization_id, conversation_id, user.id)
    )


@router.post("/conversations/{conversation_id}/members", status_code=201)
async def add_member(
    conversation_id: uuid.UUID,
    body: MemberInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CONVERSATION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session).add_member(user.organization_id, conversation_id, body, user.id)
    )


@router.delete(
    "/conversations/{conversation_id}/members/{member_id}", response_model=OperationResponse
)
async def remove_member(
    conversation_id: uuid.UUID,
    member_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CONVERSATION_MANAGE)],
) -> OperationResponse:
    await ChatService(session).remove_member(
        user.organization_id, conversation_id, member_id, user.id
    )
    return OperationResponse(message="Conversation member removed")


@router.get("/conversations/{conversation_id}/messages", response_model=CursorMessages)
async def list_messages(
    conversation_id: uuid.UUID,
    session: Session,
    user: ReadUser,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    parent_message_id: uuid.UUID | None = None,
) -> CursorMessages:
    items, next_cursor, has_more = await ChatService(session).list_messages(
        user.organization_id, conversation_id, user.id, cursor, limit, parent_message_id
    )
    return CursorMessages(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get("/conversations/{conversation_id}/tabs")
async def list_channel_tabs(
    conversation_id: uuid.UUID, session: Session, user: ReadUser
) -> list[dict[str, object]]:
    return [
        serialize(tab)
        for tab in await ChatService(session).tabs(user.organization_id, conversation_id, user.id)
    ]


@router.post("/conversations/{conversation_id}/tabs", status_code=201)
async def add_channel_tab(
    conversation_id: uuid.UUID,
    body: ChannelTabInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CONVERSATION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session).add_tab(
            user.organization_id,
            conversation_id,
            body.name,
            body.tab_type,
            body.configuration,
            body.sort_order,
            user.id,
        )
    )


@router.get("/conversations/{conversation_id}/draft")
async def get_draft(
    conversation_id: uuid.UUID, session: Session, user: ReadUser
) -> dict[str, object] | None:
    draft = await ChatService(session).draft(user.organization_id, conversation_id, user.id)
    return serialize(draft) if draft else None


@router.put("/conversations/{conversation_id}/draft")
async def save_draft(
    conversation_id: uuid.UUID,
    body: DraftInput,
    session: Session,
    user: ReadUser,
) -> dict[str, object]:
    return serialize(
        await ChatService(session).save_draft(
            user.organization_id, conversation_id, body.body, user.id
        )
    )


@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_CREATE)],
) -> dict[str, object]:
    service = ChatService(session, realtime_hub)
    message = await service.send_message(user.organization_id, conversation_id, body, user.id)
    return await service.message_detail(message)


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: uuid.UUID,
    body: MessageEdit,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_EDIT)],
) -> dict[str, object]:
    service = ChatService(session, realtime_hub)
    return await service.message_detail(
        await service.edit_message(user.organization_id, message_id, body.body, user.id)
    )


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_DELETE)],
) -> dict[str, object]:
    return serialize(
        await ChatService(session, realtime_hub).delete_message(
            user.organization_id, message_id, user.id
        )
    )


@router.post("/messages/{message_id}/reactions", status_code=201)
async def add_reaction(
    message_id: uuid.UUID, body: ReactionInput, session: Session, user: ReadUser
) -> dict[str, object]:
    reaction = await ChatService(session, realtime_hub).reaction(
        user.organization_id, message_id, body.emoji, user.id
    )
    return serialize(reaction) if reaction else {}


@router.delete("/messages/{message_id}/reactions/{emoji}", response_model=OperationResponse)
async def remove_reaction(
    message_id: uuid.UUID, emoji: str, session: Session, user: ReadUser
) -> OperationResponse:
    await ChatService(session, realtime_hub).reaction(
        user.organization_id, message_id, emoji, user.id, remove=True
    )
    return OperationResponse(message="Reaction removed")


@router.post("/messages/{message_id}/pin", status_code=201)
async def pin_message(message_id: uuid.UUID, session: Session, user: ReadUser) -> dict[str, object]:
    return serialize(
        await ChatService(session, realtime_hub).pin(user.organization_id, message_id, user.id)
    )


@router.get("/conversations/{conversation_id}/pins")
async def pinned_messages(
    conversation_id: uuid.UUID, session: Session, user: ReadUser
) -> list[dict[str, object]]:
    return await ChatService(session).pins(user.organization_id, conversation_id, user.id)


@router.post("/messages/{message_id}/save", status_code=201)
async def save_message(
    message_id: uuid.UUID,
    body: SavedMessageInput,
    session: Session,
    user: ReadUser,
) -> dict[str, object]:
    return serialize(
        await ChatService(session).save_message(
            user.organization_id, message_id, user.id, body.note
        )
    )


@router.get("/saved-messages")
async def saved_messages(session: Session, user: ReadUser) -> list[dict[str, object]]:
    return await ChatService(session).saved_messages(user.organization_id, user.id)


@router.put("/conversations/{conversation_id}/read")
async def mark_read(
    conversation_id: uuid.UUID, body: ReadReceiptInput, session: Session, user: ReadUser
) -> dict[str, object]:
    return serialize(
        await ChatService(session, realtime_hub).mark_read(
            user.organization_id, conversation_id, body.message_id, user.id
        )
    )


@router.get("/presence")
async def list_presence(session: Session, user: ReadUser) -> list[dict[str, object]]:
    return [
        {
            "user_id": presence.user_id,
            "status": presence.status,
            "last_seen": presence.last_seen,
            "display_name": display_name,
        }
        for presence, display_name in await PresenceService(session).list(user.organization_id)
    ]


@router.put("/presence")
async def set_presence(body: PresenceInput, session: Session, user: ReadUser) -> dict[str, object]:
    presence = await PresenceService(session).set(user.organization_id, user.id, body.status)
    await realtime_hub.personal(user.id, {"type": "presence.changed", "data": serialize(presence)})
    return serialize(presence)


@router.websocket("/chat/ws/{conversation_id}")
async def chat_socket(
    websocket: WebSocket, conversation_id: uuid.UUID, token: str = Query()
) -> None:
    settings = get_settings()
    try:
        subject = AccessTokenService(settings).decode(token).get("sub")
        if not isinstance(subject, str):
            raise ValueError
        user_id = uuid.UUID(subject)
    except (jwt.InvalidTokenError, ValueError):
        await websocket.close(code=4401)
        return
    async with session_factory() as session:
        user = await AuthService(session, settings)._load_user(user_id)
        if user is None:
            await websocket.close(code=4401)
            return
        try:
            await ChatService(session)._require_member(
                user.organization_id, conversation_id, user.id
            )
        except Exception:
            await websocket.close(code=4404)
            return
        await realtime_hub.connect(user.id, conversation_id, websocket)
        await PresenceService(session).set(user.organization_id, user.id, PresenceStatus.ONLINE)
        await session.commit()
        await realtime_hub.publish(
            conversation_id,
            {"type": "presence.changed", "data": {"user_id": str(user.id), "status": "online"}},
        )
        try:
            while True:
                packet = await websocket.receive_json()
                event_type = packet.get("type")
                data = packet.get("data") or {}
                if event_type == "typing":
                    await realtime_hub.publish(
                        conversation_id,
                        {
                            "type": "typing",
                            "data": {"user_id": str(user.id), "active": bool(data.get("active"))},
                        },
                    )
                elif event_type == "message.send":
                    message = await ChatService(session, realtime_hub).send_message(
                        user.organization_id,
                        conversation_id,
                        MessageInput.model_validate(data),
                        user.id,
                    )
                    await session.commit()
                    await websocket.send_json(
                        {"type": "message.ack", "data": {"id": str(message.id)}}
                    )
                elif event_type == "message.read":
                    await ChatService(session, realtime_hub).mark_read(
                        user.organization_id,
                        conversation_id,
                        uuid.UUID(str(data["message_id"])),
                        user.id,
                    )
                    await session.commit()
        except WebSocketDisconnect:
            realtime_hub.disconnect(user.id, conversation_id, websocket)
            await PresenceService(session).set(
                user.organization_id, user.id, PresenceStatus.OFFLINE
            )
            await session.commit()
            await realtime_hub.publish(
                conversation_id,
                {
                    "type": "presence.changed",
                    "data": {"user_id": str(user.id), "status": "offline"},
                },
            )
