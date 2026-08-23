"""Permission catalog and RBAC tests."""

from meetinghq_api.modules.auth.domain.permissions import (
    PERMISSION_CATALOG,
    ROLE_PERMISSIONS,
    Permissions,
)


def test_permission_catalog_names_are_unique() -> None:
    """Permission declarations cannot become ambiguous."""
    names = [item.name for item in PERMISSION_CATALOG]
    assert len(names) == len(set(names))


def test_role_capabilities_follow_least_privilege() -> None:
    """Guest access remains materially narrower than administrator access."""
    assert Permissions.ADMIN_MANAGE in ROLE_PERMISSIONS["Admin"]
    assert Permissions.ADMIN_MANAGE not in ROLE_PERMISSIONS["Guest"]
    assert ROLE_PERMISSIONS["Guest"] < ROLE_PERMISSIONS["Admin"]
