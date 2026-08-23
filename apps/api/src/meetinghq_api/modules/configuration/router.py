"""Configuration-driven platform administration API."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import CurrentUser, require_permission
from meetinghq_api.modules.configuration.platform_service import PlatformService
from meetinghq_api.modules.configuration.schemas import (
    ConfigurationResponse,
    ConfigurationUpdate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    MenuBulkUpdate,
    MenuExport,
    MenuImport,
    MenuResponse,
    MenuUpdate,
)
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/platform", tags=["platform-management"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AdminUser = Annotated[User, require_permission(Permissions.ADMIN_MANAGE)]


@router.get("/navigation", response_model=list[MenuResponse])
async def navigation(session: Session, user: CurrentUser) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row) for row in await PlatformService(session).navigation(user)
    ]


@router.get("/features", response_model=list[FeatureFlagResponse])
async def features(session: Session, user: AdminUser) -> list[FeatureFlagResponse]:
    return [
        FeatureFlagResponse.model_validate(row)
        for row in await PlatformService(session).features(user.organization_id)
    ]


@router.patch("/features/{key}", response_model=FeatureFlagResponse)
async def update_feature(
    key: str, body: FeatureFlagUpdate, session: Session, user: AdminUser
) -> FeatureFlagResponse:
    return FeatureFlagResponse.model_validate(
        await PlatformService(session).update_feature(user.organization_id, key, body, user)
    )


@router.get("/menus", response_model=list[MenuResponse])
async def menus(session: Session, user: AdminUser) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).menus(user.organization_id)
    ]


@router.post("/menus/preview", response_model=list[MenuResponse])
async def preview_menus(
    body: MenuBulkUpdate, session: Session, user: AdminUser
) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).preview_menus(user.organization_id, body.items)
    ]


@router.put("/menus/publish", response_model=list[MenuResponse])
async def publish_menus(
    body: MenuBulkUpdate, session: Session, user: AdminUser
) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).publish_menus(
            user.organization_id, body.items, user
        )
    ]


@router.post("/menus/reset", response_model=list[MenuResponse])
async def reset_menus(session: Session, user: AdminUser) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).reset_menus(user.organization_id, user)
    ]


@router.get("/menus/export", response_model=MenuExport)
async def export_menus(session: Session, user: AdminUser) -> MenuExport:
    items = [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).menus(user.organization_id)
    ]
    return MenuExport(exported_at=datetime.now(UTC), items=items)


@router.post("/menus/import", response_model=list[MenuResponse])
async def import_menus(body: MenuImport, session: Session, user: AdminUser) -> list[MenuResponse]:
    return [
        MenuResponse.model_validate(row)
        for row in await PlatformService(session).publish_menus(
            user.organization_id, body.items, user
        )
    ]


@router.patch("/menus/{key}", response_model=MenuResponse)
async def update_menu(
    key: str, body: MenuUpdate, session: Session, user: AdminUser
) -> MenuResponse:
    return MenuResponse.model_validate(
        await PlatformService(session).update_menu(user.organization_id, key, body, user)
    )


@router.get("/configuration", response_model=list[ConfigurationResponse])
async def configurations(session: Session, user: AdminUser) -> list[ConfigurationResponse]:
    rows = await PlatformService(session).configurations(user.organization_id)
    return [ConfigurationResponse.model_validate(row) for row in rows if not row.is_secret]


@router.put("/configuration/{key}", response_model=ConfigurationResponse)
async def set_configuration(
    key: str, body: ConfigurationUpdate, session: Session, user: AdminUser
) -> ConfigurationResponse:
    row = await PlatformService(session).set_configuration(user.organization_id, key, body, user)
    response = ConfigurationResponse.model_validate(row)
    if row.is_secret:
        response.value = {"configured": True}
    return response
