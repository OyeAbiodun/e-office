"""Chat storage, threads, reactions, pins, permissions, and delivery tests."""

import uuid
from typing import Any

from httpx import AsyncClient

from meetinghq_api.modules.chat.realtime import RealtimeHub


async def test_channel_message_collaboration_flow(
    chat_client: AsyncClient, chat_identity: tuple[dict[str, str], str]
) -> None:
    headers, workspace_id = chat_identity
    created = await chat_client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "type": "workspace",
            "name": "Product launch",
            "description": "Cross-functional launch coordination",
        },
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["data"]["id"]

    sent = await chat_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"body": "**Launch** is ready. @chat.admin", "message_type": "rich_text"},
    )
    assert sent.status_code == 201, sent.text
    message_id = sent.json()["data"]["id"]

    reply = await chat_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"body": "Thread reply", "parent_message_id": message_id},
    )
    reaction = await chat_client.post(
        f"/api/v1/messages/{message_id}/reactions",
        headers=headers,
        json={"emoji": "👍"},
    )
    pin = await chat_client.post(f"/api/v1/messages/{message_id}/pin", headers=headers)
    read = await chat_client.put(
        f"/api/v1/conversations/{conversation_id}/read",
        headers=headers,
        json={"message_id": message_id},
    )
    statuses = {reply.status_code, reaction.status_code, pin.status_code, read.status_code}
    assert statuses == {200, 201}

    messages = await chat_client.get(
        f"/api/v1/conversations/{conversation_id}/messages?limit=1", headers=headers
    )
    assert messages.status_code == 200
    assert messages.json()["data"]["items"][0]["thread"]["reply_count"] == 1
    assert messages.json()["data"]["items"][0]["reactions"][0]["emoji"] == "👍"

    edited = await chat_client.patch(
        f"/api/v1/messages/{message_id}",
        headers=headers,
        json={"body": "Launch is approved"},
    )
    assert edited.json()["data"]["edited"] is True
    deleted = await chat_client.delete(f"/api/v1/messages/{message_id}", headers=headers)
    assert deleted.json()["data"]["deleted_at"] is not None


async def test_chat_requires_permission(chat_client: AsyncClient) -> None:
    response = await chat_client.get("/api/v1/conversations")
    assert response.status_code == 401


async def test_team_channel_tabs_drafts_and_saved_messages(
    chat_client: AsyncClient, chat_identity: tuple[dict[str, str], str]
) -> None:
    headers, workspace_id = chat_identity
    team = await chat_client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": "Leadership",
            "slug": f"leadership-{uuid.uuid4().hex[:8]}",
        },
    )
    assert team.status_code == 201, team.text
    team_id = team.json()["data"]["id"]
    created = await chat_client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "team_id": team_id,
            "type": "public_team",
            "channel_kind": "private",
            "name": "Leadership",
        },
    )
    assert created.status_code == 201, created.text
    conversation = created.json()["data"]
    conversation_id = conversation["id"]
    assert conversation["channel_kind"] == "private"

    tabs = await chat_client.get(f"/api/v1/conversations/{conversation_id}/tabs", headers=headers)
    assert tabs.status_code == 200
    assert [tab["name"] for tab in tabs.json()["data"]] == [
        "Posts",
        "Files",
        "Meetings",
        "Wiki",
        "Notes",
        "Calendar",
        "Apps",
    ]

    draft = await chat_client.put(
        f"/api/v1/conversations/{conversation_id}/draft",
        headers=headers,
        json={"body": "Persist this draft"},
    )
    assert draft.status_code == 200
    fetched = await chat_client.get(
        f"/api/v1/conversations/{conversation_id}/draft", headers=headers
    )
    assert fetched.json()["data"]["body"] == "Persist this draft"

    sent = await chat_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"body": "Persist this draft"},
    )
    assert sent.status_code == 201
    message_id = sent.json()["data"]["id"]
    cleared = await chat_client.get(
        f"/api/v1/conversations/{conversation_id}/draft", headers=headers
    )
    assert cleared.json()["data"] is None

    saved = await chat_client.post(
        f"/api/v1/messages/{message_id}/save",
        headers=headers,
        json={"note": "Review at stand-up"},
    )
    assert saved.status_code == 201
    saved_list = await chat_client.get("/api/v1/saved-messages", headers=headers)
    assert saved_list.status_code == 200
    assert saved_list.json()["data"][0]["message"]["id"] == message_id


class FakeSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.events: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)


async def test_realtime_hub_delivers_and_reconnects() -> None:
    hub = RealtimeHub()
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    first: Any = FakeSocket()
    second: Any = FakeSocket()
    await hub.connect(user_id, conversation_id, first)
    hub.disconnect(user_id, conversation_id, first)
    await hub.connect(user_id, conversation_id, second)
    await hub.publish(conversation_id, {"type": "message.new", "data": {"body": "Hello"}})
    assert second.accepted is True
    assert second.events == [{"type": "message.new", "data": {"body": "Hello"}}]
