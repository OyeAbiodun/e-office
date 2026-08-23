"""Transactional authentication and identity use cases."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from meetinghq_api.core.config import Settings
from meetinghq_api.core.errors import AuthenticationError, ConflictError, NotFoundError
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.auth.domain.permissions import (
    PERMISSION_CATALOG,
    ROLE_PERMISSIONS,
)
from meetinghq_api.modules.auth.infrastructure.email import IdentityEmailSender
from meetinghq_api.modules.auth.infrastructure.models import OneTimeToken, RefreshToken, UserSession
from meetinghq_api.modules.auth.infrastructure.passwords import (
    hash_password,
    verify_password,
)
from meetinghq_api.modules.auth.infrastructure.tokens import (
    AccessTokenService,
    create_csrf_token,
    create_opaque_token,
    hash_token,
)
from meetinghq_api.modules.auth.infrastructure.totp import verify_totp
from meetinghq_api.modules.auth.presentation.schemas import (
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
)
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import (
    Permission,
    Role,
    User,
    UserProfileCenter,
    UserStatus,
)
from meetinghq_api.modules.workspaces.models import Workspace

logger = structlog.get_logger(__name__)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def permissions_for(user: User) -> set[str]:
    """Flatten role permissions for access-token and response projection."""
    return {permission.name for role in user.roles for permission in role.permissions}


def user_response(user: User) -> UserResponse:
    """Project a persistence model into the public identity contract."""
    return UserResponse(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        force_password_change=user.force_password_change,
        roles=[role.name for role in user.roles],
        permissions=sorted(permissions_for(user)),
    )


class AuthService:
    """Authentication use-case facade scoped to one database transaction."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.access_tokens = AccessTokenService(settings)
        self.email_sender = IdentityEmailSender()

    async def _load_user(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def register(
        self, request: RegisterRequest, ip_address: str | None, user_agent: str | None
    ) -> TokenResponse:
        """Create a tenant, workspace, initial admin, roles, and session atomically."""
        duplicate = await self.session.scalar(
            select(Organization.id).where(Organization.slug == request.organization_slug)
        )
        if duplicate:
            raise ConflictError("Organization slug is already in use")

        organization = Organization(name=request.organization_name, slug=request.organization_slug)
        self.session.add(organization)
        await self.session.flush()
        self.session.add(
            Workspace(
                organization_id=organization.id,
                name=request.workspace_name,
                slug="main",
                description="Primary workspace",
            )
        )
        permissions = [
            Permission(
                name=item.name,
                resource=item.resource,
                action=item.action,
                description=item.description,
            )
            for item in PERMISSION_CATALOG
        ]
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
        for permission in permissions:
            if permission.name not in existing_permissions:
                self.session.add(permission)
                existing_permissions[permission.name] = permission
        await self.session.flush()

        roles: dict[str, Role] = {}
        for role_name, role_permission_names in ROLE_PERMISSIONS.items():
            role = Role(
                organization_id=organization.id,
                name=role_name,
                description=f"Default {role_name} role",
                system_role=True,
                permissions=[existing_permissions[name] for name in sorted(role_permission_names)],
            )
            self.session.add(role)
            roles[role_name] = role

        user = User(
            organization_id=organization.id,
            email=str(request.email).lower(),
            username=request.username,
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=f"{request.first_name} {request.last_name}".strip(),
            password_hash=hash_password(request.password),
            status=UserStatus.ACTIVE,
            email_verified=False,
            roles=[roles["Admin"]],
        )
        self.session.add(user)
        await self.session.flush()
        await self._audit(organization.id, user.id, "auth.register", "user", {})
        await self._issue_one_time_token(
            user.id, "verify_email", timedelta(hours=self.settings.email_verification_ttl_hours)
        )
        await self.session.flush()
        loaded = await self._load_user(user.id)
        if loaded is None:
            raise RuntimeError("Registered user could not be loaded")
        return await self._create_session(loaded, ip_address, user_agent, "Registration")

    async def login(
        self, request: LoginRequest, ip_address: str | None, user_agent: str | None
    ) -> TokenResponse:
        """Authenticate credentials and create a rotating refresh session."""
        users = list(
            (
                await self.session.scalars(
                    select(User)
                    .where(User.email == str(request.email).lower())
                    .options(selectinload(User.roles).selectinload(Role.permissions))
                )
            ).all()
        )
        # Email is the login identifier. Ambiguous legacy duplicates are denied
        # instead of choosing a tenant implicitly.
        user = users[0] if len(users) == 1 else None
        now = utc_now()
        if user and user.locked_until and user.locked_until.replace(tzinfo=UTC) > now:
            raise AuthenticationError("Invalid credentials or account unavailable")
        if not user or not verify_password(user.password_hash, request.password):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= self.settings.login_max_failures:
                    user.locked_until = now + timedelta(minutes=self.settings.login_lock_minutes)
                await self._audit(user.organization_id, user.id, "auth.login_failed", "user", {})
            raise AuthenticationError("Invalid credentials or account unavailable")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("Invalid credentials or account unavailable")
        await self._verify_mfa_if_required(user, request.mfa_code)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = now
        await self._audit(user.organization_id, user.id, "auth.login", "user", {})
        return await self._create_session(
            user, ip_address, user_agent, request.device_name or "Unknown device"
        )

    async def _verify_mfa_if_required(self, user: User, code: str | None) -> None:
        profile = await self.session.scalar(
            select(UserProfileCenter).where(
                UserProfileCenter.organization_id == user.organization_id,
                UserProfileCenter.user_id == user.id,
            )
        )
        if not profile or not profile.mfa_enabled:
            return
        if not code:
            raise AuthenticationError("Multi-factor authentication code required")
        if isinstance(profile.mfa_secret, dict):
            secret = profile.mfa_secret.get("secret")
        else:
            secret = profile.mfa_secret
        if isinstance(secret, str) and verify_totp(secret, code):
            return
        recovery_hashes = list(profile.recovery_code_hashes or [])
        code_hash = hash_token(code.strip().lower())
        if code_hash in recovery_hashes:
            recovery_hashes.remove(code_hash)
            profile.recovery_code_hashes = recovery_hashes
            await self._audit(user.organization_id, user.id, "auth.mfa_recovery_used", "user", {})
            return
        await self._audit(user.organization_id, user.id, "auth.mfa_failed", "user", {})
        raise AuthenticationError("Invalid multi-factor authentication code")

    async def refresh(
        self, raw_token: str, ip_address: str | None, user_agent: str | None
    ) -> TokenResponse:
        """Rotate a refresh token and reject replayed token families."""
        token = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
        now = utc_now()
        if token is None or token.revoked_at or token.expires_at.replace(tzinfo=UTC) <= now:
            raise AuthenticationError("Refresh token is invalid")
        if token.used_at:
            await self._revoke_family(token.family_id, now)
            raise AuthenticationError("Refresh token reuse detected")
        user = await self._load_user(token.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("Refresh token is invalid")
        token.used_at = now
        session = await self.session.scalar(
            select(UserSession).where(UserSession.refresh_token_id == token.id)
        )
        response = await self._create_session(
            user,
            ip_address,
            user_agent,
            (session.device or "Unknown device") if session else "Unknown device",
            family_id=token.family_id,
        )
        replacement = await self.session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(response.refresh_token)
            )
        )
        if replacement:
            token.replaced_by_id = replacement.id
        if session:
            await self.session.delete(session)
        await self._audit(user.organization_id, user.id, "auth.refresh", "session", {})
        return response

    async def logout(self, raw_token: str | None, user_id: uuid.UUID) -> None:
        """Revoke the current refresh credential."""
        if raw_token:
            token = await self.session.scalar(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_token(raw_token),
                    RefreshToken.user_id == user_id,
                )
            )
            if token and token.revoked_at is None:
                token.revoked_at = utc_now()
                await self.session.execute(
                    delete(UserSession).where(UserSession.refresh_token_id == token.id)
                )

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Change the password and revoke every existing session."""
        if not verify_password(user.password_hash, current_password):
            raise AuthenticationError("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        user.force_password_change = False
        await self.logout_all(user)
        await self._audit(user.organization_id, user.id, "auth.password_changed", "user", {})

    async def forgot_password(self, email: str) -> None:
        """Issue a reset token when the identity exists."""
        user = await self._find_user_by_email(email)
        if user:
            raw_token = await self._issue_one_time_token(
                user.id,
                "password_reset",
                timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
            await self.email_sender.send_password_reset(user.email, raw_token)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        """Consume a reset token, update the password, and revoke sessions."""
        token, user = await self._consume_one_time_token(raw_token, "password_reset")
        user.password_hash = hash_password(new_password)
        user.force_password_change = False
        token.consumed_at = utc_now()
        await self.logout_all(user)
        await self._audit(user.organization_id, user.id, "auth.password_reset", "user", {})

    async def verify_email(self, raw_token: str) -> None:
        """Consume a verification token and mark the address verified."""
        token, user = await self._consume_one_time_token(raw_token, "verify_email")
        user.email_verified = True
        token.consumed_at = utc_now()
        await self._audit(user.organization_id, user.id, "auth.email_verified", "user", {})

    async def resend_verification(self, email: str) -> None:
        """Replace outstanding verification tokens and deliver a new token."""
        user = await self._find_user_by_email(email)
        if user and not user.email_verified:
            await self.session.execute(
                delete(OneTimeToken).where(
                    OneTimeToken.user_id == user.id,
                    OneTimeToken.purpose == "verify_email",
                    OneTimeToken.consumed_at.is_(None),
                )
            )
            raw_token = await self._issue_one_time_token(
                user.id, "verify_email", timedelta(hours=self.settings.email_verification_ttl_hours)
            )
            await self.email_sender.send_verification(user.email, raw_token)

    async def sessions(self, user: User, current_refresh: str | None) -> list[SessionResponse]:
        """List active device sessions for the current user."""
        rows = (
            await self.session.scalars(
                select(UserSession)
                .join(RefreshToken, UserSession.refresh_token_id == RefreshToken.id)
                .where(
                    UserSession.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                    UserSession.expires_at > utc_now(),
                )
                .order_by(UserSession.last_activity.desc())
            )
        ).all()
        current_id = None
        if current_refresh:
            token = await self.session.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == hash_token(current_refresh))
            )
            current_id = token.id if token else None
        return [
            SessionResponse(
                id=row.id,
                device=row.device,
                browser=row.browser,
                os=row.os,
                ip_address=row.ip_address,
                last_activity=row.last_activity,
                expires_at=row.expires_at,
                current=row.refresh_token_id == current_id,
            )
            for row in rows
        ]

    async def logout_session(self, user: User, session_id: uuid.UUID) -> None:
        """Revoke one owned session."""
        row = await self.session.scalar(
            select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id)
        )
        if row is None:
            raise NotFoundError("Session not found")
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == row.refresh_token_id)
            .values(revoked_at=utc_now())
        )
        await self.session.delete(row)

    async def logout_all(self, user: User) -> None:
        """Revoke every session owned by a user."""
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
        await self.session.execute(delete(UserSession).where(UserSession.user_id == user.id))

    async def _create_session(
        self,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str,
        family_id: uuid.UUID | None = None,
    ) -> TokenResponse:
        raw_refresh = create_opaque_token()
        expires_at = utc_now() + timedelta(days=self.settings.refresh_token_ttl_days)
        refresh = RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
            device_name=device_name,
            ip_address=ip_address,
        )
        self.session.add(refresh)
        await self.session.flush()
        self.session.add(
            UserSession(
                user_id=user.id,
                refresh_token_id=refresh.id,
                device=device_name,
                browser=(user_agent or "Unknown")[:100],
                os=None,
                ip_address=ip_address,
                last_activity=utc_now(),
                expires_at=expires_at,
            )
        )
        permission_names = permissions_for(user)
        response = TokenResponse(
            access_token=self.access_tokens.create(user.id, user.organization_id, permission_names),
            expires_in=self.settings.jwt_access_token_ttl_minutes * 60,
            refresh_token=raw_refresh,
            csrf_token=create_csrf_token(),
            user=user_response(user),
        )
        if self.settings.environment == "local":
            await logger.ainfo(
                "auth_tokens_created",
                user_id=str(user.id),
                organization_id=str(user.organization_id),
                access_token_ttl_seconds=response.expires_in,
                refresh_token_expires_at=expires_at.isoformat(),
            )
        return response

    async def _find_user_by_email(self, email: str) -> User | None:
        users = list(
            (
                await self.session.scalars(select(User).where(User.email == email.lower()).limit(2))
            ).all()
        )
        return users[0] if len(users) == 1 else None

    async def _issue_one_time_token(
        self, user_id: uuid.UUID, purpose: str, lifetime: timedelta
    ) -> str:
        raw_token = create_opaque_token()
        self.session.add(
            OneTimeToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=hash_token(raw_token),
                expires_at=utc_now() + lifetime,
            )
        )
        return raw_token

    async def _consume_one_time_token(
        self, raw_token: str, purpose: str
    ) -> tuple[OneTimeToken, User]:
        token = await self.session.scalar(
            select(OneTimeToken).where(
                OneTimeToken.token_hash == hash_token(raw_token),
                OneTimeToken.purpose == purpose,
            )
        )
        if (
            token is None
            or token.consumed_at is not None
            or token.expires_at.replace(tzinfo=UTC) <= utc_now()
        ):
            raise AuthenticationError("Token is invalid or expired")
        user = await self._load_user(token.user_id)
        if user is None:
            raise AuthenticationError("Token is invalid or expired")
        return token, user

    async def _revoke_family(self, family_id: uuid.UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(revoked_at=revoked_at)
        )
        token_ids = select(RefreshToken.id).where(RefreshToken.family_id == family_id)
        await self.session.execute(
            delete(UserSession).where(UserSession.refresh_token_id.in_(token_ids))
        )

    async def _audit(
        self,
        organization_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        action: str,
        resource: str,
        metadata: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource=resource,
                audit_metadata=metadata,
            )
        )
