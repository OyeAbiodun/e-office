"""Persisted feature, menu, and runtime configuration services."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.configuration.models import (
    ConfigurationEntry,
    FeatureFlag,
    MenuDefinition,
)
from meetinghq_api.modules.configuration.schemas import (
    ConfigurationUpdate,
    FeatureFlagUpdate,
    MenuBulkItem,
    MenuUpdate,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError

FEATURES = (
    "calendar",
    "meetings",
    "chat",
    "mail",
    "notifications",
    "tasks",
    "vouchers",
    "finance",
    "help-center",
    "reports",
    "teams",
    "resources",
    "rooms",
    "ai",
    "recordings",
    "waiting-room",
    "external-calendar",
    "zoom",
    "google-meet",
    "microsoft-teams",
    "outlook",
    "google-calendar",
    "smtp",
    "slack",
    "webhook",
    "api-access",
    "microsoft-365",
    "google-workspace",
    "gmail",
    "yahoo",
    "imap",
    "microsoft-calendar",
    "apple-calendar",
    "google-drive",
    "onedrive",
    "dropbox",
    "box",
    "amazon-s3",
    "azure-blob",
    "openai",
    "azure-openai",
    "anthropic",
    "gemini",
    "rest-api",
    "webhooks",
)

IMPLEMENTED_CAPABILITIES: dict[str, str] = {
    "calendar": "/calendar",
    "meetings": "/meetings",
    "chat": "/chat",
    "mail": "/mail",
    "notifications": "/notifications",
    "help-center": "/help",
    "teams": "/teams",
    "resources": "/calendar/resources",
    "rooms": "/calendar/resources",
    "external-calendar": "/calendar/settings",
    "tasks": "/tasks",
    "vouchers": "/vouchers",
    "finance": "/finance",
}
COMING_SOON_CAPABILITIES = {
    "reports": ("4.0", "Sprint 4", ["search", "files"]),
    "ai": ("4.0", "Sprint 4", ["openai", "files", "search"]),
    "recordings": ("4.1", "Post-Sprint 4", ["meetings", "files"]),
    "waiting-room": ("4.1", "Post-Sprint 4", ["meetings"]),
}
PROVIDER_CAPABILITIES = (
    set(FEATURES) - set(IMPLEMENTED_CAPABILITIES) - set(COMING_SOON_CAPABILITIES)
)
PROVIDER_NAVIGATION_ALIASES = {
    "api-access": "rest-api",
    "webhook": "webhooks",
}

DEFAULT_MENUS = (
    ("dashboard", "Dashboard", "/", "layout-dashboard", "dashboard.view", None, "work"),
    ("tasks", "My Work", "/tasks", "check-square", "tasks.view_own", "tasks", "work"),
    ("vouchers", "Vouchers", "/vouchers", "file-clock", "vouchers.view_own", "vouchers", "work"),
    (
        "finance",
        "Finance Center",
        "/finance",
        "building",
        "finance.accounts.view",
        "finance",
        "work",
    ),
    ("meetings", "Meetings", "/meetings", "video", "meetings.view", "meetings", "work"),
    ("calendar", "Calendar", "/calendar", "calendar-days", "calendar.view", "calendar", "work"),
    ("chat", "Chat", "/chat", "messages", "chat.view", "chat", "work"),
    ("mail", "Mail", "/mail", "mail", "mail.view", "mail", "work"),
    (
        "notifications",
        "Notifications",
        "/notifications",
        "bell",
        "notifications.view",
        "notifications",
        "work",
    ),
    ("members", "Members", "/members", "users", "members.view", None, "work"),
    (
        "administration",
        "Administration",
        "/administration",
        "settings",
        "admin.manage",
        None,
        "administration",
    ),
    ("users", "Users", "/users", "user-cog", "users.manage", None, "admin"),
    ("roles", "Roles & Permissions", "/roles", "shield", "roles.manage", None, "admin"),
    ("platform", "Platform Management", "/platform", "settings", "admin.manage", None, "admin"),
    (
        "organization-settings",
        "Organization Settings",
        "/organization/settings",
        "building",
        "admin.manage",
        None,
        "admin",
    ),
    ("health", "System Health", "/system-health", "activity", "admin.manage", None, "admin"),
    ("audit", "Audit Center", "/audit", "file-clock", "admin.manage", None, "admin"),
    (
        "integrations",
        "Integration Center",
        "/integrations",
        "plug",
        "admin.manage",
        None,
        "admin",
    ),
    ("help", "Help Center", "/help", "circle-help", "dashboard.view", "help-center", "support"),
)


class PlatformService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_defaults(self, organization_id: uuid.UUID) -> None:
        feature_keys = set(
            (
                await self.session.scalars(
                    select(FeatureFlag.key).where(FeatureFlag.organization_id == organization_id)
                )
            ).all()
        )
        for key in FEATURES:
            metadata = self._capability_metadata(key)
            if key not in feature_keys:
                self.session.add(
                    FeatureFlag(
                        organization_id=organization_id,
                        key=key,
                        name=key.replace("-", " ").title(),
                        description=f"Controls availability of {key.replace('-', ' ')}.",
                        enabled=metadata["installed"]
                        and metadata["availability_status"] != "coming_soon",
                        hidden=metadata["availability_status"] == "coming_soon",
                        release_stage=(
                            "internal"
                            if metadata["availability_status"] == "coming_soon"
                            else "public"
                        ),
                        **metadata,
                    )
                )
            else:
                feature = await self.session.scalar(
                    select(FeatureFlag).where(
                        FeatureFlag.organization_id == organization_id,
                        FeatureFlag.key == key,
                    )
                )
                if feature is not None:
                    for name, value in metadata.items():
                        setattr(feature, name, value)
                    if not feature.installed or feature.availability_status == "coming_soon":
                        feature.enabled = False
                        feature.hidden = True
        menu_keys = set(
            (
                await self.session.scalars(
                    select(MenuDefinition.key).where(
                        MenuDefinition.organization_id == organization_id
                    )
                )
            ).all()
        )
        for position, values in enumerate(DEFAULT_MENUS):
            key, label, path, icon, permission, feature_key, section = values
            if key not in menu_keys:
                self.session.add(
                    MenuDefinition(
                        organization_id=organization_id,
                        key=key,
                        label=label,
                        path=path,
                        icon=icon,
                        permission=permission,
                        feature_key=feature_key,
                        section=section,
                        position=position,
                        required_role=(
                            "Super Admin" if section in {"admin", "administration"} else None
                        ),
                        parent_key="administration" if section == "admin" else None,
                        enabled=True,
                    )
                )
        await self.session.flush()

    async def features(self, organization_id: uuid.UUID) -> list[FeatureFlag]:
        await self.ensure_defaults(organization_id)
        return list(
            (
                await self.session.scalars(
                    select(FeatureFlag)
                    .where(FeatureFlag.organization_id == organization_id)
                    .order_by(FeatureFlag.name)
                )
            ).all()
        )

    async def update_feature(
        self, organization_id: uuid.UUID, key: str, body: FeatureFlagUpdate, actor: User
    ) -> FeatureFlag:
        feature = await self.session.scalar(
            select(FeatureFlag).where(
                FeatureFlag.organization_id == organization_id, FeatureFlag.key == key
            )
        )
        if feature is None:
            raise NotFoundError("Feature not found")
        if body.enabled and (not feature.installed or feature.availability_status == "coming_soon"):
            raise ConflictError(
                "Coming Soon capabilities cannot be enabled until their implementation is installed"
            )
        for name, value in body.model_dump(exclude_unset=True).items():
            setattr(feature, name, value)
        feature.updated_by = actor.id
        return feature

    async def menus(self, organization_id: uuid.UUID) -> list[MenuDefinition]:
        await self.ensure_defaults(organization_id)
        return list(
            (
                await self.session.scalars(
                    select(MenuDefinition)
                    .where(MenuDefinition.organization_id == organization_id)
                    .order_by(MenuDefinition.section, MenuDefinition.position)
                )
            ).all()
        )

    async def navigation(self, user: User) -> list[MenuDefinition]:
        menus = await self.menus(user.organization_id)
        features = {row.key: row for row in await self.features(user.organization_id)}
        permissions = {permission.name for role in user.roles for permission in role.permissions}
        roles = {role.name for role in user.roles}
        return [
            item
            for item in menus
            if item.enabled
            and not item.hidden
            and item.permission in permissions
            and (item.required_role is None or item.required_role in roles)
            and (
                item.feature_key is None
                or (
                    features[item.feature_key].enabled
                    and not features[item.feature_key].hidden
                    and not features[item.feature_key].maintenance_mode
                )
            )
        ]

    async def update_menu(
        self, organization_id: uuid.UUID, key: str, body: MenuUpdate, actor: User
    ) -> MenuDefinition:
        item = await self.session.scalar(
            select(MenuDefinition).where(
                MenuDefinition.organization_id == organization_id, MenuDefinition.key == key
            )
        )
        if item is None:
            raise NotFoundError("Menu item not found")
        for name, value in body.model_dump(exclude_unset=True).items():
            setattr(item, name, value)
        item.updated_by = actor.id
        return item

    async def preview_menus(
        self,
        organization_id: uuid.UUID,
        items: list[MenuBulkItem],
    ) -> list[MenuDefinition]:
        rows = await self.menus(organization_id)
        overlays = {item.key: item for item in items}
        self._validate_menu_items(rows, overlays)
        preview_rows = [self._clone_menu(row) for row in rows]
        for row in preview_rows:
            if body := overlays.get(row.key):
                for name, value in body.model_dump(exclude={"key"}, exclude_unset=True).items():
                    setattr(row, name, value)
        return sorted(
            preview_rows,
            key=lambda item: (item.section, item.position, item.label),
        )

    @staticmethod
    def _clone_menu(row: MenuDefinition) -> MenuDefinition:
        """Create a transient preview so previews can never change persisted navigation."""
        return MenuDefinition(
            id=row.id,
            organization_id=row.organization_id,
            key=row.key,
            label=row.label,
            path=row.path,
            icon=row.icon,
            section=row.section,
            parent_key=row.parent_key,
            position=row.position,
            hidden=row.hidden,
            enabled=row.enabled,
            required_role=row.required_role,
            permission=row.permission,
            feature_key=row.feature_key,
            badge=row.badge,
            updated_at=row.updated_at,
            updated_by=row.updated_by,
        )

    async def publish_menus(
        self,
        organization_id: uuid.UUID,
        items: list[MenuBulkItem],
        actor: User,
    ) -> list[MenuDefinition]:
        rows = await self.menus(organization_id)
        overlays = {item.key: item for item in items}
        self._validate_menu_items(rows, overlays)
        by_key = {row.key: row for row in rows}
        for key, body in overlays.items():
            row = by_key[key]
            for name, value in body.model_dump(exclude={"key"}, exclude_unset=True).items():
                setattr(row, name, value)
            row.updated_by = actor.id
        await self.session.flush()
        return sorted(rows, key=lambda item: (item.section, item.position, item.label))

    async def reset_menus(self, organization_id: uuid.UUID, actor: User) -> list[MenuDefinition]:
        await self.ensure_defaults(organization_id)
        rows = {row.key: row for row in await self.menus(organization_id)}
        for position, values in enumerate(DEFAULT_MENUS):
            key, label, path, icon, permission, feature_key, section = values
            row = rows[key]
            row.label = label
            row.path = path
            row.icon = icon
            row.permission = permission
            row.feature_key = feature_key
            row.section = section
            row.position = position
            row.required_role = "Super Admin" if section in {"admin", "administration"} else None
            row.parent_key = "administration" if section == "admin" else None
            row.enabled = True
            row.hidden = False
            row.badge = None
            row.updated_by = actor.id
        await self.session.flush()
        return list(rows.values())

    async def configurations(self, organization_id: uuid.UUID) -> list[ConfigurationEntry]:
        return list(
            (
                await self.session.scalars(
                    select(ConfigurationEntry)
                    .where(ConfigurationEntry.organization_id == organization_id)
                    .order_by(ConfigurationEntry.category, ConfigurationEntry.key)
                )
            ).all()
        )

    async def set_configuration(
        self, organization_id: uuid.UUID, key: str, body: ConfigurationUpdate, actor: User
    ) -> ConfigurationEntry:
        scope = f"organization:{organization_id}"
        entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.scope == scope, ConfigurationEntry.key == key
            )
        )
        if entry is None:
            entry = ConfigurationEntry(
                scope=scope,
                organization_id=organization_id,
                key=key,
                value=body.value,
                category=body.category,
                is_secret=body.is_secret,
                updated_by=actor.id,
            )
            self.session.add(entry)
        else:
            entry.value = body.value
            entry.category = body.category
            entry.is_secret = body.is_secret
            entry.updated_by = actor.id
        await self.session.flush()
        return entry

    @staticmethod
    def _capability_metadata(key: str) -> dict[str, object]:
        if key in IMPLEMENTED_CAPABILITIES:
            path = IMPLEMENTED_CAPABILITIES[key]
            return {
                "availability_status": "available",
                "implementation_status": "Production implementation available",
                "planned_version": None,
                "estimated_availability": None,
                "dependencies": [],
                "navigation_path": path,
                "documentation_path": "/help",
                "ui_available": True,
                "backend_available": True,
                "navigation_available": True,
                "search_available": True,
                "permissions_available": True,
                "installed": True,
            }
        if key in COMING_SOON_CAPABILITIES:
            version, availability, dependencies = COMING_SOON_CAPABILITIES[key]
            return {
                "availability_status": "coming_soon",
                "implementation_status": "Planned; implementation not installed",
                "planned_version": version,
                "estimated_availability": availability,
                "dependencies": dependencies,
                "navigation_path": None,
                "documentation_path": None,
                "ui_available": False,
                "backend_available": False,
                "navigation_available": False,
                "search_available": False,
                "permissions_available": False,
                "installed": False,
            }
        provider_key = PROVIDER_NAVIGATION_ALIASES.get(key, key)
        return {
            "availability_status": "preview",
            "implementation_status": "Provider setup UI available; adapter activation required",
            "planned_version": "3.x",
            "estimated_availability": "Provider dependent",
            "dependencies": ["integration-center"],
            "navigation_path": f"/integrations?provider={provider_key}",
            "documentation_path": "/help",
            "ui_available": True,
            "backend_available": key in {"smtp", "imap", "webhook", "webhooks", "rest-api"},
            "navigation_available": True,
            "search_available": True,
            "permissions_available": True,
            "installed": key in PROVIDER_CAPABILITIES,
        }

    @staticmethod
    def _validate_menu_items(rows: list[MenuDefinition], overlays: dict[str, MenuBulkItem]) -> None:
        keys = {row.key for row in rows}
        if len(overlays) != len(set(overlays)):
            raise ValidationError("Menu configuration contains duplicate keys")
        unknown = set(overlays) - keys
        if unknown:
            raise ValidationError(f"Unknown menu keys: {', '.join(sorted(unknown))}")
        parents = {item.parent_key for item in overlays.values() if item.parent_key is not None}
        if not parents.issubset(keys):
            raise ValidationError("Menu parent must reference an existing menu item")
        if any(item.parent_key == item.key for item in overlays.values()):
            raise ValidationError("A menu item cannot be its own parent")
        effective_parents: dict[str, str | None] = {}
        for row in rows:
            overlay = overlays.get(row.key)
            effective_parents[row.key] = (
                overlay.parent_key
                if overlay is not None and overlay.parent_key is not None
                else row.parent_key
            )
        for key in effective_parents:
            seen: set[str] = set()
            current: str | None = key
            while current is not None:
                if current in seen:
                    raise ValidationError("Menu hierarchy cannot contain a cycle")
                seen.add(current)
                current = effective_parents.get(current)
