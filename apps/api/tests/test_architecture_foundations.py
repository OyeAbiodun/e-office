"""Acceptance tests for shared architecture foundations."""

import uuid
from datetime import UTC, datetime

import pytest

from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.shared.events import DomainEvent
from meetinghq_api.shared.pagination import (
    PaginationParams,
    decode_cursor,
    encode_cursor,
)


def test_cursor_round_trip_and_strategy_validation() -> None:
    """Compound cursors are opaque, stable, and mutually exclusive with offsets."""
    timestamp = datetime.now(UTC)
    cursor = encode_cursor(timestamp, "entity-1")
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == timestamp
    assert decoded_id == "entity-1"
    with pytest.raises(ValueError):
        PaginationParams(offset=0, cursor=cursor)


def test_soft_delete_is_attributed_and_reversible() -> None:
    """Soft-deletable entities retain actor attribution and can be restored."""
    actor_id = uuid.uuid4()
    organization = Organization(name="Example", slug="example")
    organization.soft_delete(actor_id)
    assert organization.deleted_at is not None
    assert organization.deleted_by == actor_id
    organization.restore()
    assert organization.deleted_at is None
    assert organization.deleted_by is None


def test_domain_event_is_immutable_business_fact() -> None:
    """Domain events carry a stable identity and business aggregate context."""
    organization_id = uuid.uuid4()
    event = DomainEvent(
        name="WorkspaceCreated",
        organization_id=organization_id,
        aggregate_type="workspace",
        aggregate_id=uuid.uuid4(),
    )
    assert event.organization_id == organization_id
    with pytest.raises(AttributeError):
        event.name = "Changed"  # type: ignore[misc]
