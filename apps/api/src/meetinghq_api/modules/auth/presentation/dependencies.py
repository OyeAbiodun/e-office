"""Authentication and RBAC FastAPI dependencies."""

import uuid
from typing import Annotated

import jwt
import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.core.errors import AuthenticationError, AuthorizationError
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.application.service import AuthService
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.users.models import User

logger = structlog.get_logger(__name__)
bearer = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_auth_service(session: DatabaseSession, settings: AppSettings) -> AuthService:
    """Build a transaction-scoped authentication service."""
    return AuthService(session, settings)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: AuthServiceDependency,
) -> User:
    """Resolve and validate the bearer identity."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication is required")
    try:
        claims = AccessTokenService(service.settings).decode(credentials.credentials)
        subject = claims.get("sub")
        organization = claims.get("org")
        if not isinstance(subject, str) or not isinstance(organization, str):
            raise AuthenticationError("Access token is invalid")
        user = await service._load_user(uuid.UUID(subject))
    except (jwt.InvalidTokenError, ValueError) as error:
        raise AuthenticationError("Access token is invalid or expired") from error
    if user is None:
        raise AuthenticationError("Access token is invalid or expired")
    if str(user.organization_id) != organization:
        raise AuthenticationError("Access token tenant context is invalid")
    if service.settings.environment == "local":
        await logger.ainfo(
            "auth_current_user_succeeded",
            user_id=str(user.id),
            organization_id=str(user.organization_id),
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str) -> object:
    """Create a dependency that requires one centralized permission."""

    async def permission_dependency(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        user: CurrentUser,
        settings: AppSettings,
    ) -> User:
        if credentials is None:
            raise AuthenticationError("Authentication is required")
        try:
            claims = AccessTokenService(settings).decode(credentials.credentials)
        except jwt.InvalidTokenError as error:
            raise AuthenticationError("Access token is invalid or expired") from error
        claim_permissions = claims.get("permissions")
        if not isinstance(claim_permissions, list) or permission not in claim_permissions:
            if settings.environment == "local":
                await logger.awarning(
                    "auth_permission_denied",
                    user_id=str(user.id),
                    permission=permission,
                )
            raise AuthorizationError(f"Permission required: {permission}")
        if settings.environment == "local":
            await logger.ainfo(
                "auth_permission_granted",
                user_id=str(user.id),
                permission=permission,
            )
        return user

    return Depends(permission_dependency)
