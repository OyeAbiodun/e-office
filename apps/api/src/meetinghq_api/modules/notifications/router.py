"""Authenticated in-app notification endpoints."""

import asyncio
import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session, session_factory
from meetinghq_api.modules.auth.application.service import AuthService
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.auth.presentation.dependencies import CurrentUser
from meetinghq_api.modules.notifications.models import Notification
from meetinghq_api.modules.notifications.schemas import (
    NotificationBulkAction,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationSummary,
)
from meetinghq_api.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.websocket("/ws")
async def notification_socket(websocket: WebSocket, token: str = Query()) -> None:
    """Push attention-count changes over a reconnect-safe authenticated channel."""
    settings = get_settings()
    try:
        claims = AccessTokenService(settings).decode(token)
        subject = claims.get("sub")
        organization = claims.get("org")
        if not isinstance(subject, str) or not isinstance(organization, str):
            raise ValueError
        user_id = uuid.UUID(subject)
        organization_id = uuid.UUID(organization)
    except (jwt.InvalidTokenError, ValueError):
        await websocket.close(code=4401)
        return
    async with session_factory() as session:
        user = await AuthService(session, settings)._load_user(user_id)
        if user is None or user.organization_id != organization_id:
            await websocket.close(code=4401)
            return
    await websocket.accept()
    previous = -1
    try:
        while True:
            # Waiting for a client frame with a timeout both paces polling and
            # consumes the ASGI disconnect event. Without this receive, a tab
            # closed while its unread count was unchanged could leave a zombie
            # polling task behind indefinitely.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2)
            except TimeoutError:
                pass
            # A WebSocket can remain open for hours. Never pin one database
            # connection for that lifetime: briefly acquire a session for each
            # unread-count snapshot and return it to the pool immediately.
            async with session_factory() as session:
                unread = int(
                    await session.scalar(
                        select(func.count(Notification.id)).where(
                            Notification.organization_id == organization_id,
                            Notification.user_id == user_id,
                            Notification.read_at.is_(None),
                            Notification.archived_at.is_(None),
                        )
                    )
                    or 0
                )
                if unread != previous:
                    await websocket.send_json(
                        {"type": "notifications.unread_changed", "unread": unread}
                    )
                    previous = unread
    except (WebSocketDisconnect, RuntimeError):
        return


@router.get("", response_model=NotificationSummary)
async def list_notifications(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
    category: str | None = Query(default=None, max_length=48),
    priority: str | None = Query(default=None, max_length=24),
    unread_only: bool = False,
    include_archived: bool = False,
    search: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> NotificationSummary:
    rows, unread, total, next_cursor, attention = await NotificationService(
        session, settings
    ).list_for_user(
        user.organization_id,
        user.id,
        category=category,
        priority=priority,
        unread_only=unread_only,
        include_archived=include_archived,
        search=search,
        page=page,
        page_size=page_size,
        cursor=cursor,
    )
    return NotificationSummary(
        unread=unread,
        **attention,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
        next_cursor=next_cursor,
        notifications=[NotificationResponse.model_validate(row) for row in rows],
    )


@router.post("/actions/bulk")
async def bulk_notifications(
    body: NotificationBulkAction,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> dict[str, int]:
    count = await NotificationService(session, settings).bulk_action(
        user.organization_id,
        user.id,
        body.notification_ids,
        body.action,
    )
    return {"updated": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> NotificationResponse:
    return NotificationResponse.model_validate(
        await NotificationService(session, settings).mark_read(
            user.organization_id, user.id, notification_id
        )
    )


@router.post("/read-all")
async def mark_all_read(
    session: Session, settings: AppSettings, user: CurrentUser
) -> dict[str, int]:
    count = await NotificationService(session, settings).mark_all_read(
        user.organization_id, user.id
    )
    return {"updated": count}


@router.post("/{notification_id}/archive", response_model=NotificationResponse)
async def archive_notification(
    notification_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> NotificationResponse:
    return NotificationResponse.model_validate(
        await NotificationService(session, settings).archive(
            user.organization_id, user.id, notification_id
        )
    )


@router.get("/preferences/me", response_model=NotificationPreferenceResponse)
async def notification_preferences(
    session: Session, settings: AppSettings, user: CurrentUser
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse.model_validate(
        await NotificationService(session, settings).preferences(user.organization_id, user.id)
    )


@router.put("/preferences/me", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(
    body: NotificationPreferenceUpdate,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse.model_validate(
        await NotificationService(session, settings).update_preferences(
            user.organization_id, user.id, body
        )
    )
