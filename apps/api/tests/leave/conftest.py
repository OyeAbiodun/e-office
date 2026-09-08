"""Reuse the isolated organization API fixtures for Leave tests."""

from collections.abc import Iterator

import pytest

from meetinghq_api.main import app
from tests.organization.conftest import admin_headers, organization_client

__all__ = ["admin_headers", "organization_client"]


@pytest.fixture(autouse=True)
def isolate_mutation_audit() -> Iterator[None]:
    """Keep Leave API tests from writing audit fallbacks to the shared runtime."""
    previous = app.state.audit_session_factory
    app.state.audit_session_factory = None
    try:
        yield
    finally:
        app.state.audit_session_factory = previous
