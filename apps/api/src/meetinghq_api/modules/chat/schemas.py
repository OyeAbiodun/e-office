"""Chat API and realtime contracts."""

import uuid

from pydantic import BaseModel, Field

from meetinghq_api.modules.chat.models import ConversationType, PresenceStatus


class ConversationCreate(BaseModel):
    workspace_id: uuid.UUID
    team_id: uuid.UUID | None = None
    type: ConversationType
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    visibility: str = "members"
    channel_kind: str = Field(default="standard", pattern=r"^(standard|private|shared)$")
    member_ids: list[uuid.UUID] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    visibility: str | None = None
    channel_kind: str | None = Field(default=None, pattern=r"^(standard|private|shared)$")


class MemberInput(BaseModel):
    user_id: uuid.UUID
    role: str = "member"


class MessageInput(BaseModel):
    body: str = Field(min_length=1, max_length=100000)
    message_type: str = "rich_text"
    parent_message_id: uuid.UUID | None = None
    client_message_id: uuid.UUID | None = None
    attachments: list[dict[str, object]] = Field(default_factory=list)


class MessageEdit(BaseModel):
    body: str = Field(min_length=1, max_length=100000)


class ReactionInput(BaseModel):
    emoji: str = Field(min_length=1, max_length=64)


class ReadReceiptInput(BaseModel):
    message_id: uuid.UUID


class PresenceInput(BaseModel):
    status: PresenceStatus


class ChannelTabInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tab_type: str = Field(pattern=r"^(posts|files|meetings|wiki|notes|calendar|apps)$")
    configuration: str = Field(default="{}", max_length=10000)
    sort_order: int = Field(default=0, ge=0)


class DraftInput(BaseModel):
    body: str = Field(max_length=100000)


class SavedMessageInput(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ChatDashboard(BaseModel):
    unread_messages: int
    recent_conversations: list[dict[str, object]]
    active_channels: int
    online_members: int


class CursorMessages(BaseModel):
    items: list[dict[str, object]]
    next_cursor: str | None
    has_more: bool
