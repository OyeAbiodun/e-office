"""WebSocket transport and reconnect-safe subscription registry."""

import uuid
from collections import defaultdict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class RealtimeHub:
    def __init__(self) -> None:
        self._conversations: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._users: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID, socket: WebSocket
    ) -> None:
        await socket.accept()
        self._users[user_id].add(socket)
        self._conversations[conversation_id].add(socket)

    def disconnect(self, user_id: uuid.UUID, conversation_id: uuid.UUID, socket: WebSocket) -> None:
        self._users[user_id].discard(socket)
        self._conversations[conversation_id].discard(socket)
        if not self._users[user_id]:
            self._users.pop(user_id, None)
        if not self._conversations[conversation_id]:
            self._conversations.pop(conversation_id, None)

    async def publish(self, conversation_id: uuid.UUID, event: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for socket in tuple(self._conversations.get(conversation_id, ())):
            try:
                await socket.send_json(jsonable_encoder(event))
            except RuntimeError:
                stale.append(socket)
        for socket in stale:
            self._conversations[conversation_id].discard(socket)

    async def personal(self, user_id: uuid.UUID, event: dict[str, object]) -> None:
        for socket in tuple(self._users.get(user_id, ())):
            try:
                await socket.send_json(jsonable_encoder(event))
            except RuntimeError:
                self._users[user_id].discard(socket)


realtime_hub = RealtimeHub()
