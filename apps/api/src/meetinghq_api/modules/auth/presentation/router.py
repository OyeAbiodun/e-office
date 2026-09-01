"""Versioned authentication HTTP endpoints."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Header, Request, Response, status

from meetinghq_api.core.errors import AuthenticationError
from meetinghq_api.modules.auth.application.service import user_response
from meetinghq_api.modules.auth.infrastructure.rate_limit import AuthRateLimiter
from meetinghq_api.modules.auth.presentation.dependencies import (
    AppSettings,
    AuthServiceDependency,
    CurrentUser,
)
from meetinghq_api.modules.auth.presentation.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = structlog.get_logger(__name__)


def request_context(request: Request) -> tuple[str | None, str | None]:
    """Extract normalized request context used by sessions and audit hooks."""
    forwarded = request.headers.get("x-forwarded-for")
    ip_address = forwarded.split(",", 1)[0].strip() if forwarded else None
    if ip_address is None and request.client:
        ip_address = request.client.host
    return ip_address, request.headers.get("user-agent")


def set_auth_cookies(response: Response, token: TokenResponse, settings: AppSettings) -> None:
    """Set scoped refresh and CSRF cookies for browser clients."""
    max_age = settings.refresh_token_ttl_days * 24 * 60 * 60
    response.set_cookie(
        settings.refresh_cookie_name,
        token.refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        token.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        # The SPA runs on application routes such as /calendar. The
        # double-submit value must be readable there so it can be copied into
        # X-CSRF-Token while the HttpOnly refresh cookie remains auth-scoped.
        path="/",
    )


def clear_auth_cookies(response: Response, settings: AppSettings) -> None:
    """Expire browser authentication cookies."""
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def validate_csrf(cookie_token: str | None, header_token: str | None, *, cookie_auth: bool) -> None:
    """Validate double-submit CSRF when cookie credentials are used."""
    if cookie_auth and (not cookie_token or not header_token or cookie_token != header_token):
        raise AuthenticationError("CSRF validation failed")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> TokenResponse:
    """Register an organization and its initial administrator."""
    ip_address, user_agent = request_context(request)
    await AuthRateLimiter(settings).check("register", ip_address or "unknown")
    result = await service.register(body, ip_address, user_agent)
    set_auth_cookies(response, result, settings)
    return result


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> TokenResponse:
    """Authenticate credentials and begin a session."""
    ip_address, user_agent = request_context(request)
    await AuthRateLimiter(settings).check(
        "login", f"{ip_address or 'unknown'}:{str(body.email).lower()}"
    )
    result = await service.login(body, ip_address, user_agent)
    set_auth_cookies(response, result, settings)
    if settings.environment == "local":
        await logger.ainfo(
            "auth_login_succeeded",
            user_id=str(result.user.id),
            organization_id=str(result.user.organization_id),
            refresh_cookie_path="/api/v1/auth",
            csrf_cookie_path="/",
        )
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: AppSettings,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> TokenResponse:
    """Rotate a refresh credential and issue a new access token."""
    cookie_refresh = request.cookies.get(settings.refresh_cookie_name)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    raw_token = body.refresh_token or cookie_refresh
    if raw_token is None:
        raise AuthenticationError("Refresh token is required")
    validate_csrf(csrf_cookie, csrf_header, cookie_auth=body.refresh_token is None)
    ip_address, user_agent = request_context(request)
    result = await service.refresh(
        raw_token,
        ip_address,
        user_agent,
        allow_cookie_retry_grace=body.refresh_token is None,
    )
    set_auth_cookies(response, result, settings)
    if settings.environment == "local":
        await logger.ainfo(
            "auth_refresh_succeeded",
            user_id=str(result.user.id),
            organization_id=str(result.user.organization_id),
        )
    return result


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    user: CurrentUser,
    service: AuthServiceDependency,
    settings: AppSettings,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> MessageResponse:
    """Revoke the current browser session."""
    cookie_refresh = request.cookies.get(settings.refresh_cookie_name)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    validate_csrf(csrf_cookie, csrf_header, cookie_auth=cookie_refresh is not None)
    await service.logout(cookie_refresh, user.id)
    clear_auth_cookies(response, settings)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    """Return the authenticated identity and capabilities."""
    return user_response(user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> MessageResponse:
    """Change the authenticated user's password and revoke sessions."""
    await service.change_password(user, body.current_password, body.new_password)
    return MessageResponse(message="Password changed; sign in again")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> MessageResponse:
    """Request password recovery without disclosing account existence."""
    ip_address, _ = request_context(request)
    await AuthRateLimiter(settings).check("forgot-password", ip_address or "unknown")
    await service.forgot_password(str(body.email))
    return MessageResponse(
        message="If the account exists, password reset instructions have been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest, service: AuthServiceDependency
) -> MessageResponse:
    """Reset a password using a valid single-use token."""
    await service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest, service: AuthServiceDependency) -> MessageResponse:
    """Verify an email address using a single-use token."""
    await service.verify_email(body.token)
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> MessageResponse:
    """Request a replacement verification message."""
    ip_address, _ = request_context(request)
    await AuthRateLimiter(settings).check("verify-email", ip_address or "unknown")
    await service.resend_verification(str(body.email))
    return MessageResponse(message="If verification is required, instructions have been sent")


@router.get("/sessions", response_model=list[SessionResponse])
async def sessions(
    request: Request,
    user: CurrentUser,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> list[SessionResponse]:
    """List active sessions owned by the authenticated user."""
    return await service.sessions(user, request.cookies.get(settings.refresh_cookie_name))


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def logout_session(
    session_id: uuid.UUID,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> MessageResponse:
    """Revoke one owned session."""
    await service.logout_session(user, session_id)
    return MessageResponse(message="Session revoked")


@router.delete("/sessions", response_model=MessageResponse)
async def logout_all_sessions(
    response: Response,
    user: CurrentUser,
    service: AuthServiceDependency,
    settings: AppSettings,
) -> MessageResponse:
    """Revoke all sessions owned by the authenticated user."""
    await service.logout_all(user)
    clear_auth_cookies(response, settings)
    return MessageResponse(message="All sessions revoked")
