"""Shared runtime health signals for separately deployed workers."""

import json
import os
import socket
from datetime import UTC, datetime
from typing import Any, cast

from redis.asyncio import Redis


class SharedRuntimeHealth:
    """Publish sanitized worker and scheduler state through Redis."""

    KEY = "officeflow:runtime-health"

    def __init__(self, client: Redis) -> None:
        self.client = client
        self.started_at = datetime.now(UTC)

    @staticmethod
    def worker_identity() -> str:
        return f"{socket.gethostname()}:{os.getpid()}"

    async def started(self) -> None:
        now = datetime.now(UTC).isoformat()
        await cast(Any, self.client.hset)(
            self.KEY,
            mapping={
                "worker_identity": self.worker_identity(),
                "worker_started_at": now,
                "worker_heartbeat_at": now,
                "worker_last_error": "",
            },
        )

    async def heartbeat(self) -> None:
        await cast(Any, self.client.hset)(
            self.KEY,
            mapping={"worker_heartbeat_at": datetime.now(UTC).isoformat()},
        )

    async def succeeded(self, counts: dict[str, int]) -> None:
        now = datetime.now(UTC).isoformat()
        await cast(Any, self.client.hset)(
            self.KEY,
            mapping={
                "worker_heartbeat_at": now,
                "worker_last_success_at": now,
                "worker_last_error": "",
                "worker_counts": json.dumps(counts, separators=(",", ":")),
                "scheduler_heartbeat_at": now,
                "scheduler_last_success_at": now,
                "scheduler_last_error": "",
            },
        )

    async def failed(self, error: Exception) -> None:
        now = datetime.now(UTC).isoformat()
        safe_error = type(error).__name__
        await cast(Any, self.client.hset)(
            self.KEY,
            mapping={
                "worker_heartbeat_at": now,
                "worker_last_error": safe_error,
                "scheduler_heartbeat_at": now,
                "scheduler_last_error": safe_error,
            },
        )

    async def read(self) -> dict[str, Any]:
        return dict(await cast(Any, self.client.hgetall)(self.KEY))
