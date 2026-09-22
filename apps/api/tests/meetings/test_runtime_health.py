"""Regression coverage for shared worker and scheduler health interpretation."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.system_health.service import SystemHealthService


class _Settings:
    redis_url = "redis://redis:6379/0"
    reminder_poll_seconds = 60


@pytest.mark.parametrize(
    ("age", "error", "expected"),
    [
        (10, "", "healthy"),
        (181, "", "degraded"),
        (10, "RuntimeError", "degraded"),
    ],
)
async def test_worker_health_distinguishes_healthy_stale_and_failed(
    age: int, error: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    service = SystemHealthService(cast(Any, None), cast(Settings, _Settings()))

    async def state() -> tuple[dict[str, object], str | None]:
        return {
            "worker_identity": "worker-1:42",
            "worker_heartbeat_at": (now - timedelta(seconds=age)).isoformat(),
            "worker_last_success_at": (now - timedelta(seconds=age)).isoformat(),
            "worker_last_error": error,
        }, None

    monkeypatch.setattr(service, "_runtime_state", state)
    result = await service._worker(now)
    assert result.status == expected
    assert result.details["worker_identity"] == "worker-1:42"


async def test_worker_health_recovers_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    service = SystemHealthService(cast(Any, None), cast(Settings, _Settings()))
    states = iter(
        [
            ({"worker_heartbeat_at": now.isoformat(), "worker_last_error": "RuntimeError"}, None),
            ({"worker_heartbeat_at": now.isoformat(), "worker_last_error": ""}, None),
        ]
    )

    async def state() -> tuple[dict[str, object], str | None]:
        return next(states)

    monkeypatch.setattr(service, "_runtime_state", state)
    assert (await service._worker(now)).status == "degraded"
    assert (await service._worker(now)).status == "healthy"


async def test_worker_health_is_not_healthy_when_shared_state_is_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SystemHealthService(cast(Any, None), cast(Settings, _Settings()))

    async def state() -> tuple[dict[str, object], str | None]:
        return {}, "ConnectionError"

    monkeypatch.setattr(service, "_runtime_state", state)
    result = await service._worker(datetime.now(UTC))
    assert result.status == "degraded"
    assert result.details["state_read_error"] == "ConnectionError"
