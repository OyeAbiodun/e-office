"""RBAC-protected calendar and scheduling REST API."""

# ruff: noqa: E501

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.calendar.schemas import (
    AvailabilityCreate,
    AvailabilityResponse,
    BusyBlockCreate,
    BusyBlockResponse,
    CalendarCreate,
    CalendarResponse,
    CalendarShareCreate,
    CalendarShareResponse,
    CalendarUpdate,
    EventCategoryCreate,
    EventCategoryResponse,
    EventCreate,
    EventResponse,
    EventUpdate,
    HolidayCreate,
    HolidayResponse,
    RecurrenceExceptionCreate,
    RecurrenceRuleInput,
    RecurrenceRuleResponse,
    ReservationCreate,
    ReservationResponse,
    ResourceCreate,
    ResourceResponse,
    ScheduleValidationRequest,
    ScheduleValidationResponse,
    SlotSuggestionRequest,
    TimeSlot,
)
from meetinghq_api.modules.calendar.service import (
    CalendarRulesService,
    CalendarService,
    ResourceService,
    SchedulingService,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(tags=["calendar"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
DateQuery = Annotated[datetime | None, Query()]
IcsUpload = Annotated[UploadFile, File()]


@router.get("/calendars", response_model=list[CalendarResponse])
async def list_calendars(
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[CalendarResponse]:
    return [
        CalendarResponse.model_validate(item)
        for item in await CalendarService(session).list_calendars(user.organization_id, user.id)
    ]


@router.post("/calendars", response_model=CalendarResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar(
    body: CalendarCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> CalendarResponse:
    return CalendarResponse.model_validate(
        await CalendarService(session).create(user.organization_id, body, user.id)
    )


@router.get("/calendars/{calendar_id}", response_model=CalendarResponse)
async def get_calendar(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> CalendarResponse:
    return CalendarResponse.model_validate(
        await CalendarService(session).get(user.organization_id, calendar_id)
    )


@router.patch("/calendars/{calendar_id}", response_model=CalendarResponse)
async def update_calendar(
    calendar_id: uuid.UUID,
    body: CalendarUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> CalendarResponse:
    return CalendarResponse.model_validate(
        await CalendarService(session).update(user.organization_id, calendar_id, body, user.id)
    )


@router.delete("/calendars/{calendar_id}", response_model=OperationResponse)
async def delete_calendar(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_MANAGE)],
) -> OperationResponse:
    await CalendarService(session).delete(user.organization_id, calendar_id, user.id)
    return OperationResponse(message="Calendar deleted")


@router.get("/calendars/{calendar_id}/events", response_model=list[EventResponse])
async def list_events(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
    start: DateQuery = None,
    end: DateQuery = None,
) -> list[EventResponse]:
    events = await CalendarService(session).list_events(
        user.organization_id, calendar_id, start, end
    )
    return [EventResponse.model_validate(item) for item in events]


@router.post("/calendars/{calendar_id}/events", response_model=EventResponse, status_code=201)
async def create_event(
    calendar_id: uuid.UUID,
    body: EventCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> EventResponse:
    return EventResponse.model_validate(
        await CalendarService(session).create_event(
            user.organization_id, calendar_id, body, user.id
        )
    )


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> EventResponse:
    return EventResponse.model_validate(
        await CalendarService(session).update_event(user.organization_id, event_id, body, user.id)
    )


@router.delete("/events/{event_id}", response_model=OperationResponse)
async def delete_event(
    event_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> OperationResponse:
    await CalendarService(session).delete_event(user.organization_id, event_id, user.id)
    return OperationResponse(message="Event deleted")


@router.get("/events/{event_id}/recurrence", response_model=RecurrenceRuleResponse | None)
async def get_recurrence(
    event_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> RecurrenceRuleResponse | None:
    rule = await CalendarService(session).recurrence(user.organization_id, event_id)
    return RecurrenceRuleResponse.model_validate(rule) if rule else None


@router.put("/events/{event_id}/recurrence", response_model=RecurrenceRuleResponse)
async def set_recurrence(
    event_id: uuid.UUID,
    body: RecurrenceRuleInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> RecurrenceRuleResponse:
    return RecurrenceRuleResponse.model_validate(
        await CalendarService(session).set_recurrence(user.organization_id, event_id, body, user.id)
    )


@router.post(
    "/events/{event_id}/exceptions",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurrence_exception(
    event_id: uuid.UUID,
    body: RecurrenceExceptionCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> EventResponse:
    return EventResponse.model_validate(
        await CalendarService(session).create_exception(
            user.organization_id, event_id, body, user.id
        )
    )


@router.get("/calendars/{calendar_id}/shares", response_model=list[CalendarShareResponse])
async def list_calendar_shares(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[CalendarShareResponse]:
    return [
        CalendarShareResponse.model_validate(item)
        for item in await CalendarService(session).list_shares(user.organization_id, calendar_id)
    ]


@router.post(
    "/calendars/{calendar_id}/shares",
    response_model=CalendarShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def share_calendar(
    calendar_id: uuid.UUID,
    body: CalendarShareCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_MANAGE)],
) -> CalendarShareResponse:
    return CalendarShareResponse.model_validate(
        await CalendarService(session).share(
            user.organization_id,
            calendar_id,
            body.user_id,
            body.permission,
            user.id,
        )
    )


@router.delete("/calendars/{calendar_id}/shares/{share_id}", response_model=OperationResponse)
async def revoke_calendar_share(
    calendar_id: uuid.UUID,
    share_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_MANAGE)],
) -> OperationResponse:
    await CalendarService(session).revoke_share(
        user.organization_id, calendar_id, share_id, user.id
    )
    return OperationResponse(message="Calendar access revoked")


@router.get("/event-categories", response_model=list[EventCategoryResponse])
async def list_event_categories(
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[EventCategoryResponse]:
    return [
        EventCategoryResponse.model_validate(item)
        for item in await CalendarService(session).list_categories(user.organization_id)
    ]


@router.post(
    "/event-categories",
    response_model=EventCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event_category(
    body: EventCategoryCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_MANAGE)],
) -> EventCategoryResponse:
    return EventCategoryResponse.model_validate(
        await CalendarService(session).create_category(user.organization_id, body, user.id)
    )


@router.get("/calendars/{calendar_id}/export.ics")
async def export_calendar(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> Response:
    payload = await CalendarService(session).export_ics(user.organization_id, calendar_id)
    return Response(
        payload,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="meetinghq-calendar.ics"'},
    )


@router.post(
    "/calendars/{calendar_id}/import.ics",
    response_model=list[EventResponse],
)
async def import_calendar(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
    file: IcsUpload,
) -> list[EventResponse]:
    payload = (await file.read()).decode("utf-8-sig")
    return [
        EventResponse.model_validate(item)
        for item in await CalendarService(session).import_ics(
            user.organization_id, calendar_id, payload, user.id
        )
    ]


@router.get("/calendars/{calendar_id}/availability", response_model=list[AvailabilityResponse])
async def list_availability(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[AvailabilityResponse]:
    rules = await CalendarRulesService(session).list_availability(user.organization_id, calendar_id)
    return [AvailabilityResponse.model_validate(item) for item in rules]


@router.post(
    "/calendars/{calendar_id}/availability", response_model=AvailabilityResponse, status_code=201
)
async def create_availability(
    calendar_id: uuid.UUID,
    body: AvailabilityCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> AvailabilityResponse:
    return AvailabilityResponse.model_validate(
        await CalendarRulesService(session).create_availability(
            user.organization_id, calendar_id, body, user.id
        )
    )


@router.put("/availability/{rule_id}", response_model=AvailabilityResponse)
async def update_availability(
    rule_id: uuid.UUID,
    body: AvailabilityCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> AvailabilityResponse:
    rule = await CalendarRulesService(session).update_availability(
        user.organization_id, rule_id, body, user.id
    )
    return AvailabilityResponse.model_validate(rule)


@router.delete("/availability/{rule_id}", response_model=OperationResponse)
async def delete_availability(
    rule_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> OperationResponse:
    await CalendarRulesService(session).delete_availability(user.organization_id, rule_id, user.id)
    return OperationResponse(message="Availability rule deleted")


@router.get("/calendars/{calendar_id}/busy-blocks", response_model=list[BusyBlockResponse])
async def list_busy_blocks(
    calendar_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[BusyBlockResponse]:
    blocks = await CalendarRulesService(session).list_busy(user.organization_id, calendar_id)
    return [BusyBlockResponse.model_validate(item) for item in blocks]


@router.post(
    "/calendars/{calendar_id}/busy-blocks", response_model=BusyBlockResponse, status_code=201
)
async def create_busy_block(
    calendar_id: uuid.UUID,
    body: BusyBlockCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> BusyBlockResponse:
    return BusyBlockResponse.model_validate(
        await CalendarRulesService(session).create_busy(
            user.organization_id, calendar_id, body, user.id
        )
    )


@router.put("/busy-blocks/{block_id}", response_model=BusyBlockResponse)
async def update_busy_block(
    block_id: uuid.UUID,
    body: BusyBlockCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> BusyBlockResponse:
    block = await CalendarRulesService(session).update_busy(
        user.organization_id, block_id, body, user.id
    )
    return BusyBlockResponse.model_validate(block)


@router.delete("/busy-blocks/{block_id}", response_model=OperationResponse)
async def delete_busy_block(
    block_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AVAILABILITY_MANAGE)],
) -> OperationResponse:
    await CalendarRulesService(session).delete_busy(user.organization_id, block_id, user.id)
    return OperationResponse(message="Busy block deleted")


@router.get("/holidays", response_model=list[HolidayResponse])
async def list_holidays(
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[HolidayResponse]:
    return [
        HolidayResponse.model_validate(item)
        for item in await CalendarRulesService(session).list_holidays(user.organization_id)
    ]


@router.post("/holidays", response_model=HolidayResponse, status_code=201)
async def create_holiday(
    body: HolidayCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.HOLIDAY_MANAGE)],
) -> HolidayResponse:
    return HolidayResponse.model_validate(
        await CalendarRulesService(session).create_holiday(user.organization_id, body, user.id)
    )


@router.put("/holidays/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: uuid.UUID,
    body: HolidayCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.HOLIDAY_MANAGE)],
) -> HolidayResponse:
    holiday = await CalendarRulesService(session).update_holiday(
        user.organization_id, holiday_id, body, user.id
    )
    return HolidayResponse.model_validate(holiday)


@router.delete("/holidays/{holiday_id}", response_model=OperationResponse)
async def delete_holiday(
    holiday_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.HOLIDAY_MANAGE)],
) -> OperationResponse:
    await CalendarRulesService(session).delete_holiday(user.organization_id, holiday_id, user.id)
    return OperationResponse(message="Holiday deleted")


@router.get("/resources", response_model=list[ResourceResponse])
async def list_resources(
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[ResourceResponse]:
    return [
        ResourceResponse.model_validate(item)
        for item in await ResourceService(session).list(user.organization_id)
    ]


@router.post("/resources", response_model=ResourceResponse, status_code=201)
async def create_resource(
    body: ResourceCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.RESOURCE_MANAGE)],
) -> ResourceResponse:
    return ResourceResponse.model_validate(
        await ResourceService(session).create(user.organization_id, body, user.id)
    )


@router.put("/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: uuid.UUID,
    body: ResourceCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.RESOURCE_MANAGE)],
) -> ResourceResponse:
    resource = await ResourceService(session).update(
        user.organization_id, resource_id, body, user.id
    )
    return ResourceResponse.model_validate(resource)


@router.delete("/resources/{resource_id}", response_model=OperationResponse)
async def delete_resource(
    resource_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.RESOURCE_MANAGE)],
) -> OperationResponse:
    await ResourceService(session).delete(user.organization_id, resource_id, user.id)
    return OperationResponse(message="Resource deleted")


@router.post("/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(
    body: ReservationCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> ReservationResponse:
    return ReservationResponse.model_validate(
        await ResourceService(session).reserve(user.organization_id, body, user.id)
    )


@router.delete("/reservations/{reservation_id}", response_model=OperationResponse)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_WRITE)],
) -> OperationResponse:
    await ResourceService(session).cancel(user.organization_id, reservation_id, user.id)
    return OperationResponse(message="Reservation cancelled")


@router.post("/scheduling/validate", response_model=ScheduleValidationResponse)
async def validate_schedule(
    body: ScheduleValidationRequest,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> ScheduleValidationResponse:
    result = await SchedulingService(session).validate(user.organization_id, body)
    return ScheduleValidationResponse(
        valid=result.valid, reasons=list(result.reasons), conflict_count=len(result.conflicts)
    )


@router.post("/scheduling/suggestions", response_model=list[TimeSlot])
async def suggest_slots(
    body: SlotSuggestionRequest,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CALENDAR_READ)],
) -> list[TimeSlot]:
    slots = await SchedulingService(session).suggest(user.organization_id, body)
    return [TimeSlot(start_datetime=item.start, end_datetime=item.end) for item in slots]
