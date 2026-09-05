"""User management application service."""

import base64
import io
import re
import secrets
import uuid
from datetime import UTC, date, datetime
from urllib.parse import unquote, urlparse

import qrcode  # type: ignore[import-untyped]
import qrcode.image.svg  # type: ignore[import-untyped]
from sqlalchemy import func, or_, select
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
from meetinghq_api.modules.organizations.models import OrganizationUnit, OrganizationUnitType
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import (
    EmploymentHistory,
    Permission,
    Role,
    User,
    UserApiToken,
    UserProfileCenter,
    UserStatus,
    user_roles,
)
from meetinghq_api.modules.users.schemas import (
    ApiTokenCreate,
    ProfileCenterUpdate,
    RoleClone,
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
        self.email = IdentityEmailSender(session, settings)

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
        await self._validate_employment_context(
            organization_id, body.department_id, body.manager_id
        )
        employee_number = self._employee_number(body.employee_number)
        if employee_number and await self._employee_number_exists(organization_id, employee_number):
            raise ConflictError("Employee number is already assigned in this organization")
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
            alternative_phone=body.alternative_phone,
            job_title=body.job_title,
            department=body.department,
            department_id=body.department_id,
            manager_id=body.manager_id,
            employee_number=employee_number,
            employment_status=body.employment_status,
            employment_type=body.employment_type,
            employment_start_date=body.employment_start_date or date.today(),
            employment_confirmation_date=body.employment_confirmation_date,
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
        await self._record_employment_history(
            user,
            actor_id,
            "hired",
            {},
            self._employment_values(user),
            user.employment_start_date or date.today(),
            None,
        )
        self._audit(organization_id, actor_id, "employee.created", user.id, {})
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
            await self.email.send_temporary_password(email, temporary_password, organization_id)
        return user, temporary_password

    async def update(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: UserUpdate,
        actor_id: uuid.UUID,
    ) -> User:
        user = await self.get(organization_id, user_id)
        values = body.model_dump(
            exclude_unset=True,
            exclude={"role_ids", "effective_date", "employment_change_reason"},
        )
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
        await self._validate_employment_context(
            organization_id,
            values.get("department_id", user.department_id),
            values.get("manager_id", user.manager_id),
            user.id,
        )
        if "employee_number" in values:
            values["employee_number"] = self._employee_number(values["employee_number"])
            if values["employee_number"] and await self._employee_number_exists(
                organization_id, values["employee_number"], user.id
            ):
                raise ConflictError("Employee number is already assigned in this organization")
        before = self._employment_values(user)
        for field, value in values.items():
            setattr(user, field, value)
        if body.first_name is not None or body.last_name is not None:
            user.display_name = f"{user.first_name} {user.last_name}".strip()
        if body.role_ids is not None:
            user.roles = await self._roles(organization_id, body.role_ids)
            self._audit(organization_id, actor_id, "employee.roles_updated", user.id, {})
        after = self._employment_values(user)
        changed = {key: value for key, value in after.items() if before.get(key) != value}
        if changed:
            await self._record_employment_history(
                user,
                actor_id,
                self._employment_change_type(changed),
                {key: before[key] for key in changed},
                changed,
                body.effective_date or date.today(),
                body.employment_change_reason,
            )
            self._audit(
                organization_id,
                actor_id,
                "employee.employment_updated",
                user.id,
                {
                    "fields": sorted(changed),
                },
            )
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
        await self.email.send_temporary_password(user.email, temporary_password, organization_id)
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

    async def create_role(
        self, organization_id: uuid.UUID, body: RoleCreate, actor_id: uuid.UUID
    ) -> Role:
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
        self._audit(organization_id, actor_id, "role.created", role.id, {}, resource="role")
        # A freshly inserted ORM instance has not loaded its correlated
        # ``member_count`` property. Re-query before FastAPI serializes the
        # response, otherwise async lazy loading would fail at the API edge.
        return await self._role(organization_id, role.id)

    async def update_role(
        self, organization_id: uuid.UUID, role_id: uuid.UUID, body: RoleUpdate, actor_id: uuid.UUID
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
        self._audit(organization_id, actor_id, "role.updated", role.id, {}, resource="role")
        return role

    async def clone_role(
        self,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        body: RoleClone,
        actor_id: uuid.UUID,
    ) -> Role:
        source = await self._role(organization_id, role_id)
        return await self.create_role(
            organization_id,
            RoleCreate(
                name=body.name,
                description=(
                    body.description if body.description is not None else source.description
                ),
                permission_ids=[permission.id for permission in source.permissions],
            ),
            actor_id,
        )

    async def delete_role(
        self, organization_id: uuid.UUID, role_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        role = await self._role(organization_id, role_id)
        if role.system_role:
            raise ConflictError("Default roles cannot be deleted")
        member_count = await self.session.scalar(
            select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role.id)
        )
        if member_count:
            raise ConflictError("Reassign members before deleting this role")
        self._audit(organization_id, actor_id, "role.deleted", role.id, {}, resource="role")
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

    async def list_employees(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        role_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        manager_id: uuid.UUID | None = None,
        employment_status: str | None = None,
        employment_type: str | None = None,
        location: str | None = None,
        account_status: UserStatus | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[User], int]:
        statement = (
            select(User)
            .where(User.organization_id == organization_id, User.removed_at.is_(None))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        if search:
            term = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    User.display_name.ilike(term),
                    User.email.ilike(term),
                    User.employee_number.ilike(term),
                    User.job_title.ilike(term),
                )
            )
        if department_id:
            statement = statement.where(User.department_id == department_id)
        if role_id:
            statement = statement.join(User.roles).where(Role.id == role_id)
        if manager_id:
            statement = statement.where(User.manager_id == manager_id)
        if employment_status:
            statement = statement.where(User.employment_status == employment_status)
        if employment_type:
            statement = statement.where(User.employment_type == employment_type)
        if location:
            statement = statement.where(User.location == location)
        if account_status:
            statement = statement.where(User.status == account_status)
        total = int(
            await self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    statement.order_by(User.display_name, User.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, total

    async def employment_history(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[EmploymentHistory], int]:
        await self.get(organization_id, user_id)
        statement = select(EmploymentHistory).where(
            EmploymentHistory.organization_id == organization_id,
            EmploymentHistory.user_id == user_id,
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    statement.order_by(
                        EmploymentHistory.effective_date.desc(),
                        EmploymentHistory.created_at.desc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, total

    async def terminate(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        effective_date: date,
        reason: str | None,
        disable_account: bool,
    ) -> User:
        user = await self.get(organization_id, user_id)
        before = self._employment_values(user)
        user.employment_status = "terminated"
        user.employment_end_date = effective_date
        if disable_account:
            if user.id == actor_id:
                raise ConflictError("You cannot disable your own account")
            user.status = UserStatus.SUSPENDED
        after = self._employment_values(user)
        await self._record_employment_history(
            user, actor_id, "terminated", before, after, effective_date, reason
        )
        self._audit(
            organization_id,
            actor_id,
            "employee.terminated",
            user.id,
            {"account_disabled": disable_account},
        )
        return user

    async def rehire(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        effective_date: date,
        reason: str | None,
    ) -> User:
        user = await self.get(organization_id, user_id)
        before = self._employment_values(user)
        user.employment_status = "active"
        user.employment_start_date = effective_date
        user.employment_end_date = None
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
        after = self._employment_values(user)
        await self._record_employment_history(
            user, actor_id, "rehired", before, after, effective_date, reason
        )
        self._audit(organization_id, actor_id, "employee.rehired", user.id, {})
        return user

    async def _validate_employment_context(
        self,
        organization_id: uuid.UUID,
        department_id: uuid.UUID | None,
        manager_id: uuid.UUID | None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        if department_id is not None:
            department = await self.session.scalar(
                select(OrganizationUnit).where(
                    OrganizationUnit.id == department_id,
                    OrganizationUnit.organization_id == organization_id,
                    OrganizationUnit.unit_type == OrganizationUnitType.DEPARTMENT,
                    OrganizationUnit.deleted_at.is_(None),
                )
            )
            if department is None:
                raise NotFoundError("Department not found")
        if manager_id is None:
            return
        if user_id is not None and manager_id == user_id:
            raise ConflictError("An employee cannot manage themselves")
        manager = await self.session.scalar(
            select(User).where(
                User.id == manager_id,
                User.organization_id == organization_id,
                User.removed_at.is_(None),
            )
        )
        if manager is None:
            raise NotFoundError("Manager not found in this organization")
        if user_id is None:
            return
        ancestor_id = manager.manager_id
        seen = {user_id, manager_id}
        while ancestor_id is not None:
            if ancestor_id in seen:
                raise ConflictError("Manager assignment would create a reporting cycle")
            seen.add(ancestor_id)
            ancestor_id = await self.session.scalar(
                select(User.manager_id).where(
                    User.id == ancestor_id,
                    User.organization_id == organization_id,
                )
            )

    async def _employee_number_exists(
        self,
        organization_id: uuid.UUID,
        employee_number: str,
        exclude_user_id: uuid.UUID | None = None,
    ) -> bool:
        statement = select(User.id).where(
            User.organization_id == organization_id,
            User.employee_number == employee_number,
        )
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        return await self.session.scalar(statement) is not None

    async def _record_employment_history(
        self,
        user: User,
        actor_id: uuid.UUID,
        change_type: str,
        old_values: dict[str, object],
        new_values: dict[str, object],
        effective_date: date,
        reason: str | None,
    ) -> None:
        self.session.add(
            EmploymentHistory(
                organization_id=user.organization_id,
                user_id=user.id,
                changed_by=actor_id,
                change_type=change_type,
                old_values=old_values,
                new_values=new_values,
                effective_date=effective_date,
                reason=reason,
            )
        )

    def _audit(
        self,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        resource_id: uuid.UUID,
        metadata: dict[str, object],
        resource: str = "employee",
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=actor_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                audit_metadata=metadata,
            )
        )

    @staticmethod
    def _employee_number(value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None

    @staticmethod
    def _employment_values(user: User) -> dict[str, object]:
        return {
            "employee_number": user.employee_number,
            "job_title": user.job_title,
            "department_id": str(user.department_id) if user.department_id else None,
            "manager_id": str(user.manager_id) if user.manager_id else None,
            "employment_status": user.employment_status,
            "employment_type": user.employment_type,
            "employment_start_date": (
                user.employment_start_date.isoformat() if user.employment_start_date else None
            ),
            "employment_confirmation_date": (
                user.employment_confirmation_date.isoformat()
                if user.employment_confirmation_date
                else None
            ),
            "employment_end_date": (
                user.employment_end_date.isoformat() if user.employment_end_date else None
            ),
            "location": user.location,
            # Include role assignments so a privilege change is visible in the
            # effective-dated employment record as well as the immutable audit log.
            "role_ids": sorted(str(role.id) for role in user.roles),
        }

    @staticmethod
    def _employment_change_type(changed: dict[str, object]) -> str:
        if "employment_status" in changed:
            return "status_changed"
        if "department_id" in changed:
            return "department_transferred"
        if "manager_id" in changed:
            return "manager_changed"
        if "job_title" in changed:
            return "job_changed"
        if "role_ids" in changed:
            return "roles_changed"
        return "employment_updated"

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
