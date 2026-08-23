"""Knowledge management, contextual help, and product-tour endpoints."""

import uuid
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import CurrentUser, require_permission
from meetinghq_api.modules.help_center.models import HelpAttachment
from meetinghq_api.modules.help_center.schemas import (
    HelpAnalyticsResponse,
    HelpArticleInput,
    HelpArticleResponse,
    HelpArticleUpdate,
    HelpAttachmentResponse,
    HelpContextResponse,
    ProductTourInput,
    ProductTourResponse,
)
from meetinghq_api.modules.help_center.service import HelpCenterService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/help", tags=["help-center"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AdminUser = Annotated[User, require_permission(Permissions.ADMIN_MANAGE)]


@router.get("/articles", response_model=list[HelpArticleResponse])
async def articles(
    session: Session,
    user: CurrentUser,
    search: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=120),
    include_unpublished: bool = False,
) -> list[HelpArticleResponse]:
    if include_unpublished and not any(role.name == "Super Admin" for role in user.roles):
        include_unpublished = False
    return [
        HelpArticleResponse.model_validate(row)
        for row in await HelpCenterService(session).list(
            user.organization_id, search, category, include_unpublished
        )
    ]


@router.get("/context/{context_id}", response_model=HelpContextResponse)
async def context_help(context_id: str, session: Session, user: CurrentUser) -> HelpContextResponse:
    article, tour = await HelpCenterService(session).resolve_context(
        user.organization_id, context_id, user.id
    )
    return HelpContextResponse(
        context_id=context_id,
        article=HelpArticleResponse.model_validate(article) if article else None,
        tour=ProductTourResponse.model_validate(tour) if tour else None,
    )


@router.get("/favorites", response_model=list[HelpArticleResponse])
async def favorites(session: Session, user: CurrentUser) -> list[HelpArticleResponse]:
    return [
        HelpArticleResponse.model_validate(row)
        for row in await HelpCenterService(session).favorites(user.organization_id, user.id)
    ]


@router.get("/recent", response_model=list[HelpArticleResponse])
async def recent(session: Session, user: CurrentUser) -> list[HelpArticleResponse]:
    return [
        HelpArticleResponse.model_validate(row)
        for row in await HelpCenterService(session).recent(user.organization_id, user.id)
    ]


@router.get("/analytics", response_model=HelpAnalyticsResponse)
async def analytics(session: Session, user: AdminUser) -> HelpAnalyticsResponse:
    return await HelpCenterService(session).analytics(user.organization_id)


@router.get("/articles/{slug}", response_model=HelpArticleResponse)
async def article(slug: str, session: Session, user: CurrentUser) -> HelpArticleResponse:
    return HelpArticleResponse.model_validate(
        await HelpCenterService(session).get(user.organization_id, slug, user.id)
    )


@router.get("/articles/{slug}/versions", response_model=list[HelpArticleResponse])
async def versions(slug: str, session: Session, user: AdminUser) -> list[HelpArticleResponse]:
    return [
        HelpArticleResponse.model_validate(row)
        for row in await HelpCenterService(session).versions(user.organization_id, slug)
    ]


@router.post("/articles", response_model=HelpArticleResponse, status_code=201)
async def create_article(
    body: HelpArticleInput, session: Session, user: AdminUser
) -> HelpArticleResponse:
    return HelpArticleResponse.model_validate(
        await HelpCenterService(session).create(user.organization_id, body, user.id)
    )


@router.post("/articles/{slug}/revisions", response_model=HelpArticleResponse, status_code=201)
async def revise_article(
    slug: str, body: HelpArticleUpdate, session: Session, user: AdminUser
) -> HelpArticleResponse:
    return HelpArticleResponse.model_validate(
        await HelpCenterService(session).revise(user.organization_id, slug, body, user.id)
    )


@router.post("/articles/{article_id}/favorite")
async def favorite(article_id: uuid.UUID, session: Session, user: CurrentUser) -> dict[str, bool]:
    value = await HelpCenterService(session).toggle_favorite(
        user.organization_id, article_id, user.id
    )
    return {"favorite": value}


@router.get("/articles/{article_id}/attachments", response_model=list[HelpAttachmentResponse])
async def attachments(
    article_id: uuid.UUID, session: Session, user: CurrentUser
) -> list[HelpAttachmentResponse]:
    rows = (
        await session.scalars(
            select(HelpAttachment).where(
                HelpAttachment.article_id == article_id,
                HelpAttachment.organization_id == user.organization_id,
            )
        )
    ).all()
    return [HelpAttachmentResponse.model_validate(row) for row in rows]


@router.post(
    "/articles/{article_id}/attachments",
    response_model=HelpAttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    article_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: AdminUser,
    upload: Annotated[UploadFile, File()],
) -> HelpAttachmentResponse:
    service = HelpCenterService(session)
    await service._tenant_article(user.organization_id, article_id)  # tenant boundary
    content = await upload.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Maximum size is 20 MB")
    content_type = upload.content_type or "application/octet-stream"
    provider = LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    )
    stored = await provider.put(
        f"organizations/{user.organization_id}/help/{article_id}",
        BytesIO(content),
        content_type,
        len(content),
    )
    attachment = HelpAttachment(
        organization_id=user.organization_id,
        article_id=article_id,
        filename=upload.filename or "attachment",
        content_type=stored.content_type,
        size=stored.size,
        storage_key=stored.key,
        url=stored.url,
        uploaded_by=user.id,
    )
    session.add(attachment)
    await session.flush()
    return HelpAttachmentResponse.model_validate(attachment)


@router.post("/tours", response_model=ProductTourResponse, status_code=201)
async def create_tour(
    body: ProductTourInput, session: Session, user: AdminUser
) -> ProductTourResponse:
    return ProductTourResponse.model_validate(
        await HelpCenterService(session).create_tour(user.organization_id, body, user.id)
    )
