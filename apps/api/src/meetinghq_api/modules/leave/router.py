"""Leave Management HTTP boundary."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.leave.schemas import (
    AdjustmentInput,
    BalanceResponse,
    EntitlementInput,
    EntitlementResponse,
    LeavePeriodInput,
    LeavePeriodResponse,
    LeaveRequestInput,
    LeaveRequestResponse,
    LeaveTypeInput,
    LeaveTypeResponse,
    RejectInput,
    ReviewInput,
    WorkingDayPreview,
    WorkingDayResult,
)
from meetinghq_api.modules.leave.service import LeaveService
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/leave", tags=["leave"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("/types", response_model=list[LeaveTypeResponse])
async def list_types(
    session: Session, user: Annotated[User, require_permission("leave.types.view")]
) -> list[LeaveTypeResponse]:
    return [
        LeaveTypeResponse.model_validate(v) for v in await LeaveService(session).list_types(user)
    ]


@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_type(
    body: LeaveTypeInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(await LeaveService(session).create_type(user, body))


@router.put("/types/{type_id}", response_model=LeaveTypeResponse)
async def update_type(
    type_id: uuid.UUID,
    body: LeaveTypeInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await LeaveService(session).update_type(user, type_id, body)
    )


@router.get("/periods", response_model=list[LeavePeriodResponse])
async def list_periods(
    session: Session, user: Annotated[User, require_permission("leave.types.view")]
) -> list[LeavePeriodResponse]:
    return [
        LeavePeriodResponse.model_validate(v)
        for v in await LeaveService(session).list_periods(user)
    ]


@router.post("/periods", response_model=LeavePeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_period(
    body: LeavePeriodInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeavePeriodResponse:
    return LeavePeriodResponse.model_validate(await LeaveService(session).create_period(user, body))


@router.post(
    "/entitlements", response_model=EntitlementResponse, status_code=status.HTTP_201_CREATED
)
async def create_entitlement(
    body: EntitlementInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> EntitlementResponse:
    return EntitlementResponse.model_validate(await LeaveService(session).entitlement(user, body))


@router.get("/balances/{entitlement_id}", response_model=BalanceResponse)
async def get_balance(
    entitlement_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.view")],
) -> BalanceResponse:
    return await LeaveService(session).balance(user, entitlement_id)


@router.post("/balances/{entitlement_id}/adjustments", response_model=BalanceResponse)
async def adjust_balance(
    entitlement_id: uuid.UUID,
    body: AdjustmentInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> BalanceResponse:
    return await LeaveService(session).adjust(user, entitlement_id, body)


@router.post("/working-days", response_model=WorkingDayResult)
async def preview_days(
    body: WorkingDayPreview,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> WorkingDayResult:
    return await LeaveService(session).working_days(
        user, body.start_date, body.end_date, body.half_day
    )


@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: LeaveRequestInput,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).create_request(user, body)
    )


@router.post("/requests/{request_id}/submit", response_model=LeaveRequestResponse)
async def submit_request(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(await LeaveService(session).submit(user, request_id))


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestResponse)
async def approve_request(
    request_id: uuid.UUID,
    body: ReviewInput,
    session: Session,
    user: Annotated[User, require_permission("leave.approve")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).review(user, request_id, "approved", body.comment)
    )


@router.post("/requests/{request_id}/reject", response_model=LeaveRequestResponse)
async def reject_request(
    request_id: uuid.UUID,
    body: RejectInput,
    session: Session,
    user: Annotated[User, require_permission("leave.reject")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).review(user, request_id, "rejected", body.comment)
    )


@router.post("/requests/{request_id}/withdraw", response_model=LeaveRequestResponse)
async def withdraw_request(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.withdraw_own")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).withdraw(user, request_id)
    )


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
async def cancel_request(
    request_id: uuid.UUID,
    body: ReviewInput,
    session: Session,
    user: Annotated[User, require_permission("leave.withdraw_own")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).cancel(user, request_id, body.comment)
    )
