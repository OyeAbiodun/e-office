"""Reuse the isolated organization schema for Payroll tests."""

from tests.organization.conftest import admin_headers, organization_client

__all__ = ["admin_headers", "organization_client"]
