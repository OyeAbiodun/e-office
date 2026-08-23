"""HTTP exception translation and security middleware."""

import json
import uuid
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from meetinghq_api.core.errors import ApplicationError

logger = structlog.get_logger(__name__)


class MutationAuditMiddleware(BaseHTTPMiddleware):
    """Capture successful authenticated mutations as an immutable safety net."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if (
            request.method not in {"POST", "PUT", "PATCH", "DELETE"}
            or response.status_code >= 400
            or not request.url.path.startswith("/api/v1/")
            or request.url.path.startswith("/api/v1/auth/")
        ):
            return response
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return response
        try:
            from meetinghq_api.core.config import get_settings
            from meetinghq_api.modules.audit.models import AuditLog
            from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService

            claims = AccessTokenService(get_settings()).decode(
                authorization.split(" ", maxsplit=1)[1]
            )
            user_id = uuid.UUID(str(claims["sub"]))
            organization_id = uuid.UUID(str(claims["org"]))
            segments = [
                segment
                for segment in request.url.path.removeprefix("/api/v1/").split("/")
                if segment
            ]
            resource = segments[0] if segments else "system"
            action = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }[request.method]
            user_agent = request.headers.get("user-agent")
            audit_factory = getattr(request.app.state, "audit_session_factory", None)
            if audit_factory is None:
                return response
            async with audit_factory() as session:
                session.add(
                    AuditLog(
                        organization_id=organization_id,
                        user_id=user_id,
                        action=f"{resource}.{action}",
                        resource=resource,
                        request_id=request.headers.get("x-request-id"),
                        ip_address=request.client.host if request.client else None,
                        audit_metadata={
                            "path": request.url.path,
                            "method": request.method,
                            "browser": user_agent,
                            "device": request.headers.get("sec-ch-ua-platform"),
                        },
                    )
                )
                await session.commit()
        except Exception:
            await logger.aexception(
                "mutation_audit_capture_failed",
                method=request.method,
                path=request.url.path,
            )
        return response


class ApiEnvelopeMiddleware(BaseHTTPMiddleware):
    """Apply the canonical envelope to every JSON API response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path in {"/api/openapi.json", "/api/docs", "/api/redoc"}:
            return response
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        body_iterator = cast(Any, response).body_iterator
        body = b"".join([chunk async for chunk in body_iterator])
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return Response(body, response.status_code, media_type="application/json")
        if isinstance(payload, dict) and "success" in payload:
            wrapped = payload
        else:
            successful = response.status_code < 400
            message = (
                "Request completed successfully."
                if successful
                else "The request could not be completed."
            )
            wrapped = {
                "success": successful,
                "message": message,
                "data": payload if successful else None,
                "meta": {},
            }
            if not successful:
                wrapped["error"] = {
                    "code": "request_error",
                    "message": message,
                    "details": payload if isinstance(payload, dict) else {},
                }
        wrapped_response = JSONResponse(
            wrapped,
            status_code=response.status_code,
            headers={
                key: value
                for key, value in response.headers.items()
                if key.lower() not in {"content-length", "content-type", "set-cookie"}
            },
            background=response.background,
        )
        for key, value in response.raw_headers:
            if key.lower() == b"set-cookie":
                wrapped_response.raw_headers.append((key, value))
        return wrapped_response


def install_error_handlers(application: FastAPI) -> None:
    """Translate expected failures and hide unexpected exception details."""

    @application.exception_handler(ApplicationError)
    async def handle_application_error(_: Request, error: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "message": error.message,
                "data": None,
                "meta": {},
                "error": {"code": error.code, "message": error.message, "details": {}},
            },
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        await logger.aexception(
            "unhandled_request_error", request_id=request_id, path=request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "An unexpected error occurred",
                "data": None,
                "meta": {"request_id": request_id},
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                    "details": {},
                },
            },
        )
