"""Permanent first-run installation bootstrap."""

import re
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.auth.domain.permissions import (
    PERMISSION_CATALOG,
    ROLE_PERMISSIONS,
)
from meetinghq_api.modules.auth.infrastructure.passwords import hash_password
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import Permission, Role, User, UserStatus
from meetinghq_api.modules.workspaces.models import Workspace, WorkspaceMembership


class BootstrapConfigurationError(RuntimeError):
    """An empty installation is missing required bootstrap configuration."""


class BootstrapInitializationService:
    """Create the permanent initial tenant exactly once."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def initialize(self) -> bool:
        """Return true only when this call created the first installation records."""
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            await self.session.execute(text("SELECT pg_advisory_xact_lock(498461927)"))
        if (await self.session.scalar(select(func.count(Organization.id)))) or 0:
            return False

        values = self._required_values()
        organization = Organization(
            name=values["organization_name"],
            slug=self._slug(values["organization_name"]),
        )
        self.session.add(organization)
        await self.session.flush()
        workspace = Workspace(
            organization_id=organization.id,
            name=values["workspace_name"],
            slug="main",
            description="Default workspace",
        )
        self.session.add(workspace)

        existing_permissions = {
            item.name: item
            for item in (
                await self.session.scalars(
                    select(Permission).where(
                        Permission.name.in_([definition.name for definition in PERMISSION_CATALOG])
                    )
                )
            ).all()
        }
        for definition in PERMISSION_CATALOG:
            if definition.name not in existing_permissions:
                permission = Permission(
                    name=definition.name,
                    resource=definition.resource,
                    action=definition.action,
                    description=definition.description,
                )
                self.session.add(permission)
                existing_permissions[definition.name] = permission
        await self.session.flush()

        roles: dict[str, Role] = {}
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = Role(
                organization_id=organization.id,
                name=role_name,
                description=f"Default {role_name} role",
                system_role=True,
                permissions=[existing_permissions[name] for name in sorted(permission_names)],
            )
            self.session.add(role)
            roles[role_name] = role

        email = values["email"].lower()
        first_name = values["first_name"]
        last_name = values["last_name"]
        user = User(
            organization_id=organization.id,
            email=email,
            username=self._username(email),
            first_name=first_name,
            last_name=last_name,
            display_name=f"{first_name} {last_name}".strip(),
            password_hash=hash_password(values["password"]),
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=[roles["Super Admin"]],
        )
        self.session.add(user)
        await self.session.flush()
        organization.owner_id = user.id
        workspace.owner_id = user.id
        self.session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
        )
        await self.session.flush()
        return True

    def _required_values(self) -> dict[str, str]:
        configured = {
            "email": self.settings.initial_super_admin_email,
            "password": self.settings.initial_super_admin_password,
            "first_name": self.settings.initial_super_admin_first_name,
            "last_name": self.settings.initial_super_admin_last_name,
            "organization_name": self.settings.initial_organization_name,
            "workspace_name": self.settings.initial_workspace_name,
        }
        missing = [
            name
            for name, value in configured.items()
            if name != "last_name" and (value is None or not value.strip())
        ]
        if missing:
            environment_names = {
                "email": "INITIAL_SUPER_ADMIN_EMAIL",
                "password": "INITIAL_SUPER_ADMIN_PASSWORD",
                "first_name": "INITIAL_SUPER_ADMIN_FIRST_NAME",
                "last_name": "INITIAL_SUPER_ADMIN_LAST_NAME",
                "organization_name": "INITIAL_ORGANIZATION_NAME",
                "workspace_name": "INITIAL_WORKSPACE_NAME",
            }
            names = ", ".join(environment_names[name] for name in missing)
            raise BootstrapConfigurationError(
                f"Empty installation requires bootstrap variables: {names}"
            )
        return {name: value or "" for name, value in configured.items()}

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:80] or "meetinghq"

    @staticmethod
    def _username(email: str) -> str:
        base = re.sub(r"[^a-z0-9._-]", "-", email.split("@", 1)[0].lower())
        return (base or f"admin-{uuid.uuid4().hex[:8]}")[:64]


class RbacInitializationService:
    """Synchronize the stable permission catalog and default roles."""

    LEGACY_ROLE_NAMES = {
        "Organization Admin": "Admin",
        "Manager": "Team Manager",
        "Member": "Employee",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def synchronize(self) -> None:
        existing_permissions = {
            item.name: item for item in (await self.session.scalars(select(Permission))).all()
        }
        for definition in PERMISSION_CATALOG:
            permission = existing_permissions.get(definition.name)
            if permission is None:
                permission = Permission(
                    name=definition.name,
                    resource=definition.resource,
                    action=definition.action,
                    description=definition.description,
                )
                self.session.add(permission)
                existing_permissions[definition.name] = permission
            else:
                permission.resource = definition.resource
                permission.action = definition.action
                permission.description = definition.description
        await self.session.flush()

        organization_ids = (await self.session.scalars(select(Organization.id))).all()
        for organization_id in organization_ids:
            existing_roles = {
                role.name: role
                for role in (
                    await self.session.scalars(
                        select(Role)
                        .where(Role.organization_id == organization_id)
                        .options(selectinload(Role.permissions))
                    )
                ).all()
            }
            for old_name, new_name in self.LEGACY_ROLE_NAMES.items():
                role = existing_roles.get(old_name)
                if role and new_name not in existing_roles:
                    role.name = new_name
                    existing_roles[new_name] = role
            for role_name, permission_names in ROLE_PERMISSIONS.items():
                role = existing_roles.get(role_name)
                if role is None:
                    role = Role(
                        organization_id=organization_id,
                        name=role_name,
                        description=f"Default {role_name} role",
                        system_role=True,
                    )
                    self.session.add(role)
                    existing_roles[role_name] = role
                role.system_role = True
                role.permissions = [existing_permissions[name] for name in sorted(permission_names)]
