"""Profile and RBAC-protected user management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import CurrentUser, require_permission
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.modules.users.schemas import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenResponse,
    EmployeeDirectoryResponse,
    EmployeeLifecycleRequest,
    EmploymentHistoryResponse,
    MfaDisableRequest,
    MfaRecoveryCodesResponse,
    MfaRecoveryRegenerateRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    PermissionResponse,
    ProfileCenterResponse,
    ProfileCenterUpdate,
    RoleClone,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    SecurityEventResponse,
    TemporaryPasswordResponse,
    UserBulkAction,
    UserCreate,
    UserProfileUpdate,
    UserResponse,
    UserUpdate,
)
from meetinghq_api.modules.users.service import UserService
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(tags=["users"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_READ)],
    search: str | None = Query(default=None, max_length=160),
    status: UserStatus | None = None,
    role_id: uuid.UUID | None = None,
    department: str | None = Query(default=None, max_length=120),
    include_removed: bool = False,
) -> list[UserResponse]:
    return [
        UserResponse.model_validate(item)
        for item in await UserService(session, settings).list_users(
            user.organization_id,
            search=search,
            status=status,
            role_id=role_id,
            department=department,
            include_removed=include_removed,
        )
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    created, _ = await UserService(session, settings).create(user.organization_id, body, user.id)
    return UserResponse.model_validate(created)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_READ)],
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).get(user.organization_id, user_id)
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).update(user.organization_id, user_id, body, user.id)
    )


@router.post(
    "/users/{user_id}/reset-password",
    response_model=TemporaryPasswordResponse,
)
async def reset_user_password(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> TemporaryPasswordResponse:
    temporary_password = await UserService(session, settings).reset_password(
        user.organization_id, user_id, user.id
    )
    return TemporaryPasswordResponse(temporary_password=temporary_password)


@router.post("/users/actions/bulk", response_model=OperationResponse)
async def bulk_users(
    body: UserBulkAction,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> OperationResponse:
    service = UserService(session, settings)
    for user_id in set(body.user_ids):
        if body.action == "activate":
            await service.set_status(user.organization_id, user_id, UserStatus.ACTIVE, user.id)
        elif body.action == "disable":
            await service.set_status(user.organization_id, user_id, UserStatus.SUSPENDED, user.id)
        elif body.action == "delete":
            await service.remove(user.organization_id, user_id, user.id)
        else:
            await service.restore(user.organization_id, user_id)
    return OperationResponse(message=f"Bulk {body.action} completed")


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_READ)],
) -> list[RoleResponse]:
    return [
        RoleResponse.model_validate(item)
        for item in await UserService(session, settings).roles(user.organization_id)
    ]


@router.post("/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    body: RoleCreate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ADMIN_MANAGE)],
) -> RoleResponse:
    return RoleResponse.model_validate(
        await UserService(session, settings).create_role(user.organization_id, body, user.id)
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ADMIN_MANAGE)],
) -> RoleResponse:
    return RoleResponse.model_validate(
        await UserService(session, settings).update_role(
            user.organization_id, role_id, body, user.id
        )
    )


@router.delete("/roles/{role_id}", response_model=OperationResponse)
async def delete_role(
    role_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ADMIN_MANAGE)],
) -> OperationResponse:
    await UserService(session, settings).delete_role(user.organization_id, role_id, user.id)
    return OperationResponse(message="Role deleted")


@router.post("/roles/{role_id}/clone", response_model=RoleResponse, status_code=201)
async def clone_role(
    role_id: uuid.UUID,
    body: RoleClone,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ADMIN_MANAGE)],
) -> RoleResponse:
    return RoleResponse.model_validate(
        await UserService(session, settings).clone_role(
            user.organization_id, role_id, body, user.id
        )
    )


@router.get("/employees", response_model=EmployeeDirectoryResponse)
async def employee_directory(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_READ)],
    search: str | None = Query(default=None, max_length=160),
    role_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    manager_id: uuid.UUID | None = None,
    employment_status: str | None = Query(default=None, max_length=32),
    employment_type: str | None = Query(default=None, max_length=32),
    location: str | None = Query(default=None, max_length=160),
    account_status: UserStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> EmployeeDirectoryResponse:
    rows, total = await UserService(session, settings).list_employees(
        user.organization_id,
        search=search,
        role_id=role_id,
        department_id=department_id,
        manager_id=manager_id,
        employment_status=employment_status,
        employment_type=employment_type,
        location=location,
        account_status=account_status,
        page=page,
        page_size=page_size,
    )
    return EmployeeDirectoryResponse(
        items=[UserResponse.model_validate(item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/employees/{user_id}/history")
async def employee_history(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_READ)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> dict[str, object]:
    rows, total = await UserService(session, settings).employment_history(
        user.organization_id, user_id, page=page, page_size=page_size
    )
    return {
        "items": [EmploymentHistoryResponse.model_validate(item).model_dump() for item in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/employees/{user_id}/terminate", response_model=UserResponse)
async def terminate_employee(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
    payload: EmployeeLifecycleRequest,
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).terminate(
            user.organization_id,
            user_id,
            user.id,
            payload.effective_date,
            payload.reason,
            payload.disable_account,
        )
    )


@router.post("/employees/{user_id}/rehire", response_model=UserResponse)
async def rehire_employee(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
    payload: EmployeeLifecycleRequest,
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).rehire(
            user.organization_id, user_id, user.id, payload.effective_date, payload.reason
        )
    )


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ADMIN_MANAGE)],
) -> list[PermissionResponse]:
    return [
        PermissionResponse.model_validate(item)
        for item in await UserService(session, settings).permissions()
    ]


async def transition(
    session: AsyncSession,
    settings: Settings,
    actor: User,
    user_id: uuid.UUID,
    status: UserStatus,
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).set_status(
            actor.organization_id, user_id, status, actor.id
        )
    )


@router.post("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    return await transition(session, settings, user, user_id, UserStatus.ACTIVE)


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    return await transition(session, settings, user, user_id, UserStatus.INVITED)


@router.post("/users/{user_id}/suspend", response_model=UserResponse)
async def suspend_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    return await transition(session, settings, user, user_id, UserStatus.SUSPENDED)


@router.delete("/users/{user_id}", response_model=OperationResponse)
async def remove_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> OperationResponse:
    await UserService(session, settings).remove(user.organization_id, user_id, user.id)
    return OperationResponse(message="User removed")


@router.post("/users/{user_id}/restore", response_model=UserResponse)
async def restore_user(
    user_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.USERS_WRITE)],
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).restore(user.organization_id, user_id)
    )


@router.get("/profile", response_model=UserResponse)
async def profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UserProfileUpdate,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session, settings).update_profile(user, body)
    )


@router.post("/profile/avatar", response_model=UserResponse)
async def upload_avatar(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
    avatar: Annotated[UploadFile, File()],
) -> UserResponse:
    content = await avatar.read()
    return UserResponse.model_validate(
        await UserService(session, settings).upload_avatar(
            user, content, avatar.content_type or "application/octet-stream"
        )
    )


@router.delete("/profile/avatar", response_model=UserResponse)
async def remove_avatar(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> UserResponse:
    return UserResponse.model_validate(await UserService(session, settings).remove_avatar(user))


@router.get("/profile/center", response_model=ProfileCenterResponse)
async def profile_center(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> ProfileCenterResponse:
    return ProfileCenterResponse.model_validate(
        await UserService(session, settings).profile_center(user)
    )


@router.get("/profile/security-history", response_model=list[SecurityEventResponse])
async def profile_security_history(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> list[SecurityEventResponse]:
    return [
        SecurityEventResponse(
            action=row.action,
            created_at=row.created_at,
            ip_address=row.ip_address,
            metadata=row.audit_metadata,
        )
        for row in await UserService(session, settings).security_history(user)
    ]


@router.patch("/profile/center", response_model=ProfileCenterResponse)
async def update_profile_center(
    body: ProfileCenterUpdate,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> ProfileCenterResponse:
    return ProfileCenterResponse.model_validate(
        await UserService(session, settings).update_profile_center(user, body)
    )


@router.get("/profile/api-tokens", response_model=list[ApiTokenResponse])
async def api_tokens(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> list[ApiTokenResponse]:
    return [
        ApiTokenResponse.model_validate(row)
        for row in await UserService(session, settings).api_tokens(user)
    ]


@router.post("/profile/api-tokens", response_model=ApiTokenCreated)
async def create_api_token(
    body: ApiTokenCreate,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> ApiTokenCreated:
    row, token = await UserService(session, settings).create_api_token(user, body)
    return ApiTokenCreated(
        **ApiTokenResponse.model_validate(row).model_dump(),
        token=token,
    )


@router.delete(
    "/profile/api-tokens/{token_id}",
    response_model=OperationResponse,
)
async def revoke_api_token(
    token_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> OperationResponse:
    await UserService(session, settings).revoke_api_token(user, token_id)
    return OperationResponse(message="API token revoked")


@router.post("/profile/mfa/setup", response_model=MfaSetupResponse)
async def setup_mfa(
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> MfaSetupResponse:
    secret, uri, qr_code = await UserService(session, settings).setup_mfa(user)
    return MfaSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_data_url=qr_code,
    )


@router.post("/profile/mfa/verify", response_model=MfaRecoveryCodesResponse)
async def verify_mfa(
    body: MfaVerifyRequest,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> MfaRecoveryCodesResponse:
    return MfaRecoveryCodesResponse(
        recovery_codes=await UserService(session, settings).verify_mfa(user, body.code)
    )


@router.post("/profile/mfa/disable", response_model=OperationResponse)
async def disable_mfa(
    body: MfaDisableRequest,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> OperationResponse:
    await UserService(session, settings).disable_mfa(user, body.current_password, body.code)
    return OperationResponse(message="Multi-factor authentication disabled")


@router.post(
    "/profile/mfa/recovery-codes",
    response_model=MfaRecoveryCodesResponse,
)
async def regenerate_mfa_recovery_codes(
    body: MfaRecoveryRegenerateRequest,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> MfaRecoveryCodesResponse:
    return MfaRecoveryCodesResponse(
        recovery_codes=await UserService(session, settings).regenerate_recovery_codes(
            user, body.current_password, body.code
        )
    )
