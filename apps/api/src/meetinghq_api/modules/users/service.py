"""User management application service."""

import base64
import io
import re
import secrets
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

import qrcode  # type: ignore[import-untyped]
import qrcode.image.svg  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.activity.service import Activity, DatabaseActivityPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.auth.infrastructure.email import IdentityEmailSender
from meetinghq_api.modules.auth.infrastructure.passwords import hash_password, verify_password
from meetinghq_api.modules.auth.infrastructure.tokens import create_opaque_token, hash_token
from meetinghq_api.modules.auth.infrastructure.totp import (
    create_totp_secret,
    provisioning_uri,
    verify_totp,
)
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import (
    Permission,
    Role,
    User,
    UserApiToken,
    UserProfileCenter,
    UserStatus,
)
from meetinghq_api.modules.users.schemas import (
    ApiTokenCreate,
    ProfileCenterUpdate,
    RoleCreate,
    RoleUpdate,
    UserCreate,
    UserProfileUpdate,
    UserUpdate,
)
from meetinghq_api.modules.workspaces.models import Workspace
from meetinghq_api.shared.constants import ALLOWED_IMAGE_CONTENT_TYPES, MAX_UPLOAD_BYTES
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError


class UserService:
    """Tenant-safe user lifecycle and profile use cases."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.activity = DatabaseActivityPublisher(session)
        self.email = IdentityEmailSender()

    async def get(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> User:
        user = await self.session.scalar(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.removed_at.is_(None),
            )
        )
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def list_users(
        self,
        organization_id: uuid.UUID,
        search: str | None = None,
        status: UserStatus | None = None,
        role_id: uuid.UUID | None = None,
        department: str | None = None,
        include_removed: bool = False,
    ) -> list[User]:
        statement = (
            select(User)
            .where(User.organization_id == organization_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        if not include_removed:
            statement = statement.where(User.removed_at.is_(None))
        if search:
            term = f"%{search.strip().lower()}%"
            statement = statement.where(User.email.ilike(term) | User.display_name.ilike(term))
        if status:
            statement = statement.where(User.status == status)
        if department:
            statement = statement.where(User.department == department)
        if role_id:
            statement = statement.join(User.roles).where(Role.id == role_id)
        return list((await self.session.scalars(statement.order_by(User.display_name))).all())

    async def create(
        self,
        organization_id: uuid.UUID,
        body: UserCreate,
        actor_id: uuid.UUID,
    ) -> tuple[User, str]:
        email = str(body.email).lower()
        if await self.session.scalar(select(User.id).where(User.email == email)):
            raise ConflictError("Email is already assigned to a MeetingHQ account")
        roles = await self._roles(organization_id, body.role_ids)
        await self._validate_context(organization_id, body.workspace_id, body.team_id)
        temporary_password = body.temporary_password or self._temporary_password()
        username_base = re.sub(r"[^a-z0-9_.-]", "-", email.split("@", 1)[0])
        username = username_base[:56] or f"user-{uuid.uuid4().hex[:8]}"
        if await self.session.scalar(
            select(User.id).where(
                User.organization_id == organization_id,
                User.username == username,
            )
        ):
            username = f"{username[:48]}-{uuid.uuid4().hex[:7]}"
        user = User(
            organization_id=organization_id,
            email=email,
            username=username,
            first_name=body.first_name,
            last_name=body.last_name,
            display_name=f"{body.first_name} {body.last_name}".strip(),
            phone=body.phone,
            job_title=body.job_title,
            department=body.department,
            location=body.location,
            workspace_id=body.workspace_id,
            team_id=body.team_id,
            password_hash=hash_password(temporary_password),
            force_password_change=True,
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=roles,
        )
        self.session.add(user)
        await self.session.flush()
        await self.activity.publish(
            Activity(
                organization_id=organization_id,
                actor_id=actor_id,
                event_type="user.created",
                subject_type="user",
                subject_id=user.id,
            )
        )
        if body.send_welcome_email:
            await self.email.send_temporary_password(email, temporary_password)
        return user, temporary_password

    async def update(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: UserUpdate,
        actor_id: uuid.UUID,
    ) -> User:
        user = await self.get(organization_id, user_id)
        values = body.model_dump(exclude_unset=True, exclude={"role_ids"})
        if "email" in values:
            email = str(values["email"]).lower()
            duplicate = await self.session.scalar(
                select(User.id).where(User.email == email, User.id != user.id)
            )
            if duplicate:
                raise ConflictError("Email is already assigned to a MeetingHQ account")
            values["email"] = email
        await self._validate_context(
            organization_id,
            values.get("workspace_id", user.workspace_id),
            values.get("team_id", user.team_id),
        )
        for field, value in values.items():
            setattr(user, field, value)
        if body.first_name is not None or body.last_name is not None:
            user.display_name = f"{user.first_name} {user.last_name}".strip()
        if body.role_ids is not None:
            user.roles = await self._roles(organization_id, body.role_ids)
        await self.activity.publish(
            Activity(
                organization_id=organization_id,
                actor_id=actor_id,
                event_type="user.updated",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return user

    async def reset_password(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID
    ) -> str:
        user = await self.get(organization_id, user_id)
        temporary_password = self._temporary_password()
        user.password_hash = hash_password(temporary_password)
        user.force_password_change = True
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.email.send_temporary_password(user.email, temporary_password)
        await self.activity.publish(
            Activity(
                organization_id=organization_id,
                actor_id=actor_id,
                event_type="user.password_reset",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return temporary_password

    async def roles(self, organization_id: uuid.UUID) -> list[Role]:
        return list(
            (
                await self.session.scalars(
                    select(Role)
                    .where(Role.organization_id == organization_id)
                    .options(selectinload(Role.permissions))
                    .order_by(Role.name)
                )
            ).all()
        )

    async def permissions(self) -> list[Permission]:
        return list(
            (
                await self.session.scalars(
                    select(Permission).order_by(Permission.resource, Permission.action)
                )
            ).all()
        )

    async def create_role(self, organization_id: uuid.UUID, body: RoleCreate) -> Role:
        if await self.session.scalar(
            select(Role.id).where(Role.organization_id == organization_id, Role.name == body.name)
        ):
            raise ConflictError("Role name already exists")
        role = Role(
            organization_id=organization_id,
            name=body.name,
            description=body.description,
            permissions=await self._permissions(body.permission_ids),
        )
        self.session.add(role)
        await self.session.flush()
        return role

    async def update_role(
        self, organization_id: uuid.UUID, role_id: uuid.UUID, body: RoleUpdate
    ) -> Role:
        role = await self._role(organization_id, role_id)
        if body.name is not None:
            duplicate = await self.session.scalar(
                select(Role.id).where(
                    Role.organization_id == organization_id,
                    Role.name == body.name,
                    Role.id != role.id,
                )
            )
            if duplicate:
                raise ConflictError("Role name already exists")
            role.name = body.name
        if body.description is not None:
            role.description = body.description
        if body.permission_ids is not None:
            role.permissions = await self._permissions(body.permission_ids)
        return role

    async def delete_role(self, organization_id: uuid.UUID, role_id: uuid.UUID) -> None:
        role = await self._role(organization_id, role_id)
        if role.system_role:
            raise ConflictError("Default roles cannot be deleted")
        await self.session.delete(role)

    async def update_profile(self, user: User, body: UserProfileUpdate) -> User:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        if body.first_name is not None or body.last_name is not None:
            if body.display_name is None:
                user.display_name = f"{user.first_name} {user.last_name}".strip()
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.identity_updated",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return user

    async def profile_center(self, user: User) -> UserProfileCenter:
        row = await self.session.scalar(
            select(UserProfileCenter).where(
                UserProfileCenter.organization_id == user.organization_id,
                UserProfileCenter.user_id == user.id,
            )
        )
        if row is None:
            row = UserProfileCenter(
                organization_id=user.organization_id,
                user_id=user.id,
                working_hours={
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    "start": "09:00",
                    "end": "17:00",
                },
                preferences={
                    "appearance": {"theme": "system", "density": "comfortable"},
                    "accessibility": {
                        "high_contrast": False,
                        "reduce_motion": False,
                    },
                    "calendar": {"default_view": "week", "week_starts_on": "monday"},
                    "meetings": {"default_reminder_minutes": 15},
                    "chat": {"send_on_enter": True},
                    "mail": {"conversation_view": True},
                    "notifications": {"sound": True, "browser": False},
                    "privacy": {"show_presence": True},
                    "keyboard_shortcuts": True,
                },
            )
            self.session.add(row)
            await self.session.flush()
        return row

    async def update_profile_center(
        self, user: User, body: ProfileCenterUpdate
    ) -> UserProfileCenter:
        row = await self.profile_center(user)
        values = body.model_dump(exclude_unset=True)
        if "manager_id" in values and values["manager_id"] is not None:
            manager = await self.session.scalar(
                select(User.id).where(
                    User.id == values["manager_id"],
                    User.organization_id == user.organization_id,
                    User.removed_at.is_(None),
                )
            )
            if manager is None:
                raise NotFoundError("Manager not found in this organization")
        if aliases := values.get("email_aliases"):
            values["email_aliases"] = [str(alias).lower() for alias in aliases]
        for field, value in values.items():
            setattr(row, field, value)
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.updated",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return row

    async def api_tokens(self, user: User) -> list[UserApiToken]:
        return list(
            (
                await self.session.scalars(
                    select(UserApiToken)
                    .where(
                        UserApiToken.organization_id == user.organization_id,
                        UserApiToken.user_id == user.id,
                    )
                    .order_by(UserApiToken.created_at.desc())
                )
            ).all()
        )

    async def security_history(self, user: User) -> list[AuditLog]:
        return list(
            (
                await self.session.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.organization_id == user.organization_id,
                        AuditLog.user_id == user.id,
                        AuditLog.action.like("auth.%") | AuditLog.action.like("profile.%"),
                    )
                    .order_by(AuditLog.created_at.desc())
                    .limit(50)
                )
            ).all()
        )

    async def create_api_token(self, user: User, body: ApiTokenCreate) -> tuple[UserApiToken, str]:
        available = {permission.name for role in user.roles for permission in role.permissions}
        requested = set(body.scopes) if body.scopes else available
        if not requested.issubset(available):
            raise ConflictError("API token scopes exceed your current permissions")
        if body.expires_at is not None:
            expires_at = body.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                raise ConflictError("API token expiry must be in the future")
        else:
            expires_at = None
        raw_token = f"mhq_{create_opaque_token()}"
        row = UserApiToken(
            organization_id=user.organization_id,
            user_id=user.id,
            name=body.name,
            token_hash=hash_token(raw_token),
            token_prefix=raw_token[:12],
            scopes=sorted(requested),
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row, raw_token

    async def revoke_api_token(self, user: User, token_id: uuid.UUID) -> None:
        row = await self.session.scalar(
            select(UserApiToken).where(
                UserApiToken.id == token_id,
                UserApiToken.organization_id == user.organization_id,
                UserApiToken.user_id == user.id,
            )
        )
        if row is None:
            raise NotFoundError("API token not found")
        row.revoked_at = datetime.now(UTC)

    async def setup_mfa(self, user: User) -> tuple[str, str, str]:
        row = await self.profile_center(user)
        secret = create_totp_secret()
        row.mfa_secret = {"secret": secret}
        row.mfa_enabled = False
        row.recovery_code_hashes = []
        await self.session.flush()
        uri = provisioning_uri(secret, "MeetingHQ", user.email)
        image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
        output = io.BytesIO()
        image.save(output)
        encoded = base64.b64encode(output.getvalue()).decode()
        return secret, uri, f"data:image/svg+xml;base64,{encoded}"

    async def verify_mfa(self, user: User, code: str) -> list[str]:
        row = await self.profile_center(user)
        secret = row.mfa_secret.get("secret") if isinstance(row.mfa_secret, dict) else None
        if not isinstance(secret, str) or not verify_totp(secret, code):
            raise ConflictError("Invalid multi-factor authentication code")
        recovery_codes = self._new_recovery_codes()
        row.recovery_code_hashes = [hash_token(code.lower()) for code in recovery_codes]
        row.mfa_enabled = True
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.mfa_enabled",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return recovery_codes

    async def disable_mfa(self, user: User, current_password: str, code: str | None = None) -> None:
        if not verify_password(user.password_hash, current_password):
            raise ConflictError("Current password is incorrect")
        row = await self.profile_center(user)
        secret = row.mfa_secret.get("secret") if isinstance(row.mfa_secret, dict) else None
        if row.mfa_enabled and isinstance(secret, str):
            if not code or not verify_totp(secret, code):
                raise ConflictError("Valid multi-factor authentication code required")
        row.mfa_enabled = False
        row.mfa_secret = None
        row.recovery_code_hashes = []
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.mfa_disabled",
                subject_type="user",
                subject_id=user.id,
            )
        )

    async def regenerate_recovery_codes(
        self, user: User, current_password: str, code: str
    ) -> list[str]:
        if not verify_password(user.password_hash, current_password):
            raise ConflictError("Current password is incorrect")
        row = await self.profile_center(user)
        secret = row.mfa_secret.get("secret") if isinstance(row.mfa_secret, dict) else None
        if not row.mfa_enabled or not isinstance(secret, str) or not verify_totp(secret, code):
            raise ConflictError("Valid multi-factor authentication code required")
        recovery_codes = self._new_recovery_codes()
        row.recovery_code_hashes = [hash_token(value.lower()) for value in recovery_codes]
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.mfa_recovery_codes_regenerated",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return recovery_codes

    async def set_status(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: UserStatus,
        actor_id: uuid.UUID,
    ) -> User:
        if user_id == actor_id and status != UserStatus.ACTIVE:
            raise ConflictError("You cannot deactivate your own account")
        user = await self.get(organization_id, user_id)
        user.status = status
        await self.activity.publish(
            Activity(
                organization_id=organization_id,
                actor_id=actor_id,
                event_type=f"user.{status.value}",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return user

    async def remove(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        if user_id == actor_id:
            raise ConflictError("You cannot remove your own account")
        user = await self.get(organization_id, user_id)
        user.removed_at = datetime.now(UTC)
        user.status = UserStatus.SUSPENDED

    async def restore(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> User:
        user = await self.session.scalar(
            select(User).where(User.id == user_id, User.organization_id == organization_id)
        )
        if user is None:
            raise NotFoundError("User not found")
        user.removed_at = None
        user.status = UserStatus.ACTIVE
        return user

    async def upload_avatar(self, user: User, content: bytes, content_type: str) -> User:
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationError("Unsupported avatar content type")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ValidationError("Avatar must be between 1 byte and 5 MB")
        if not self._matches_image_signature(content, content_type):
            raise ValidationError("Avatar content does not match its declared image type")
        if self.settings.storage_provider != "local":
            raise RuntimeError("Configured storage provider is unavailable")
        provider = LocalStorageProvider(
            self.settings.local_storage_path,
            self.settings.public_storage_url,
            self.settings.jwt_secret,
        )
        previous_key = self._storage_key(user.avatar_url, user.organization_id)
        stored = await provider.put(
            f"organizations/{user.organization_id}/avatars",
            io.BytesIO(content),
            content_type,
            len(content),
        )
        user.avatar_url = stored.url
        if previous_key:
            await provider.delete(previous_key)
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.avatar_updated",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return user

    async def remove_avatar(self, user: User) -> User:
        if user.avatar_url and self.settings.storage_provider == "local":
            provider = LocalStorageProvider(
                self.settings.local_storage_path,
                self.settings.public_storage_url,
                self.settings.jwt_secret,
            )
            key = self._storage_key(user.avatar_url, user.organization_id)
            if key:
                await provider.delete(key)
        user.avatar_url = None
        await self.activity.publish(
            Activity(
                organization_id=user.organization_id,
                actor_id=user.id,
                event_type="profile.avatar_removed",
                subject_type="user",
                subject_id=user.id,
            )
        )
        return user

    async def _roles(self, organization_id: uuid.UUID, role_ids: list[uuid.UUID]) -> list[Role]:
        roles = list(
            (
                await self.session.scalars(
                    select(Role)
                    .where(
                        Role.organization_id == organization_id,
                        Role.id.in_(role_ids),
                    )
                    .options(selectinload(Role.permissions))
                )
            ).all()
        )
        if len(roles) != len(set(role_ids)):
            raise NotFoundError("One or more roles were not found")
        return roles

    async def _role(self, organization_id: uuid.UUID, role_id: uuid.UUID) -> Role:
        role = await self.session.scalar(
            select(Role)
            .where(Role.organization_id == organization_id, Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        if role is None:
            raise NotFoundError("Role not found")
        return role

    async def _permissions(self, permission_ids: list[uuid.UUID]) -> list[Permission]:
        permissions = list(
            (
                await self.session.scalars(
                    select(Permission).where(Permission.id.in_(permission_ids))
                )
            ).all()
        )
        if len(permissions) != len(set(permission_ids)):
            raise NotFoundError("One or more permissions were not found")
        return permissions

    async def _validate_context(
        self,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
    ) -> None:
        if workspace_id and not await self.session.scalar(
            select(Workspace.id).where(
                Workspace.id == workspace_id,
                Workspace.organization_id == organization_id,
            )
        ):
            raise NotFoundError("Workspace not found")
        if team_id and not await self.session.scalar(
            select(Team.id).where(
                Team.id == team_id,
                Team.organization_id == organization_id,
            )
        ):
            raise NotFoundError("Team not found")

    @staticmethod
    def _temporary_password() -> str:
        return f"Mhq!{secrets.token_urlsafe(12)}9aA"

    @staticmethod
    def _new_recovery_codes() -> list[str]:
        return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(10)]

    @staticmethod
    def _matches_image_signature(content: bytes, content_type: str) -> bool:
        if content_type == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if content_type == "image/jpeg":
            return content.startswith(b"\xff\xd8\xff")
        if content_type == "image/webp":
            return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        return False

    @staticmethod
    def _storage_key(url: str | None, organization_id: uuid.UUID) -> str | None:
        if not url:
            return None
        path = unquote(urlparse(url).path)
        marker = "/storage/"
        if marker not in path:
            return None
        key = path.split(marker, 1)[1]
        expected = f"organizations/{organization_id}/"
        return key if key.startswith(expected) else None
