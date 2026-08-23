"""RBAC-protected meeting lifecycle REST API."""

# ruff: noqa: E501

import io
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.meetings.models import (
    MeetingActionItem,
    MeetingAgenda,
    MeetingDecision,
    MeetingNote,
)
from meetinghq_api.modules.meetings.schemas import (
    ActionItemInput,
    AgendaInput,
    AgendaOrder,
    ArtifactInput,
    AttendanceEventInput,
    AttendeeCreate,
    DecisionInput,
    FollowUpInput,
    MeetingAnalytics,
    MeetingCreate,
    MeetingDashboard,
    MeetingDetail,
    MeetingResponse,
    MeetingUpdate,
    NoteInput,
    PresenterControlInput,
    RecordingInput,
    RescheduleRequest,
    RSVPRequest,
    TemplateInput,
    TransitionRequest,
)
from meetinghq_api.modules.meetings.service import MeetingService, serialize
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(tags=["meetings"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
ReadUser = Annotated[User, require_permission(Permissions.MEETINGS_READ)]
DateQuery = Annotated[datetime | None, Query()]
StatusQuery = Annotated[str | None, Query(alias="status")]
AppSettings = Annotated[Settings, Depends(get_settings)]
ArtifactUpload = Annotated[UploadFile, File()]


@router.get("/meetings/dashboard", response_model=MeetingDashboard)
async def meeting_dashboard(session: Session, user: ReadUser) -> MeetingDashboard:
    return MeetingDashboard.model_validate(
        await MeetingService(session).dashboard(user.organization_id, user.id)
    )


@router.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(
    session: Session,
    user: ReadUser,
    start: DateQuery = None,
    end: DateQuery = None,
    meeting_status: StatusQuery = None,
) -> list[MeetingResponse]:
    rows = await MeetingService(session).find(
        user.organization_id, user.id, start, end, meeting_status
    )
    return [MeetingResponse.model_validate(row) for row in rows]


@router.post("/meetings", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    body: MeetingCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_CREATE)],
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        await MeetingService(session).create(user.organization_id, body, user.id)
    )


@router.get("/meetings/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(meeting_id: uuid.UUID, session: Session, user: ReadUser) -> MeetingDetail:
    return MeetingDetail.model_validate(
        await MeetingService(session).detail(user.organization_id, meeting_id, user.id)
    )


@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: uuid.UUID,
    body: MeetingUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_UPDATE)],
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        await MeetingService(session).update(user.organization_id, meeting_id, body, user.id)
    )


@router.post("/meetings/{meeting_id}/transition", response_model=MeetingResponse)
async def transition_meeting(
    meeting_id: uuid.UUID,
    body: TransitionRequest,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        await MeetingService(session).transition(
            user.organization_id, meeting_id, body.status, user.id
        )
    )


@router.post("/meetings/{meeting_id}/cancel", response_model=MeetingResponse)
async def cancel_meeting(
    meeting_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_CANCEL)],
) -> MeetingResponse:
    from meetinghq_api.modules.meetings.models import MeetingStatus

    return MeetingResponse.model_validate(
        await MeetingService(session).transition(
            user.organization_id, meeting_id, MeetingStatus.CANCELLED, user.id
        )
    )


@router.post("/meetings/{meeting_id}/archive", response_model=MeetingResponse)
async def archive_meeting(
    meeting_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> MeetingResponse:
    from meetinghq_api.modules.meetings.models import MeetingStatus

    return MeetingResponse.model_validate(
        await MeetingService(session).transition(
            user.organization_id, meeting_id, MeetingStatus.ARCHIVED, user.id
        )
    )


@router.post("/meetings/{meeting_id}/reschedule", response_model=MeetingResponse)
async def reschedule_meeting(
    meeting_id: uuid.UUID,
    body: RescheduleRequest,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_UPDATE)],
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        await MeetingService(session).reschedule(user.organization_id, meeting_id, body, user.id)
    )


@router.post("/meetings/{meeting_id}/duplicate", response_model=MeetingResponse, status_code=201)
async def duplicate_meeting(
    meeting_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_CREATE)],
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        await MeetingService(session).duplicate(user.organization_id, meeting_id, user.id)
    )


@router.get("/meetings/{meeting_id}/history")
async def meeting_history(
    meeting_id: uuid.UUID, session: Session, user: ReadUser
) -> list[dict[str, object]]:
    return await MeetingService(session).history(user.organization_id, meeting_id)


@router.post("/meetings/{meeting_id}/attendees", status_code=201)
async def invite_attendee(
    meeting_id: uuid.UUID,
    body: AttendeeCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_UPDATE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_attendee(user.organization_id, meeting_id, body, user.id)
    )


@router.put("/meetings/{meeting_id}/rsvp")
async def rsvp(
    meeting_id: uuid.UUID, body: RSVPRequest, session: Session, user: ReadUser
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).rsvp(user.organization_id, meeting_id, user.id, body.status)
    )


@router.post("/meetings/{meeting_id}/agenda", status_code=201)
async def add_agenda(
    meeting_id: uuid.UUID,
    body: AgendaInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AGENDA_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_agenda(user.organization_id, meeting_id, body, user.id)
    )


@router.put("/meetings/{meeting_id}/agenda/order")
async def reorder_agenda(
    meeting_id: uuid.UUID,
    body: AgendaOrder,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AGENDA_MANAGE)],
) -> list[dict[str, object]]:
    return [
        serialize(item)
        for item in await MeetingService(session).reorder_agenda(
            user.organization_id, meeting_id, body.agenda_ids, user.id
        )
    ]


@router.delete("/meetings/{meeting_id}/agenda/{item_id}", response_model=OperationResponse)
async def delete_agenda(
    meeting_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.AGENDA_MANAGE)],
) -> OperationResponse:
    await MeetingService(session).delete_item(
        user.organization_id, meeting_id, MeetingAgenda, item_id, user.id, "AgendaUpdated"
    )
    return OperationResponse(message="Agenda item deleted")


@router.post("/meetings/{meeting_id}/decisions", status_code=201)
async def add_decision(
    meeting_id: uuid.UUID,
    body: DecisionInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_UPDATE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_decision(user.organization_id, meeting_id, body, user.id)
    )


@router.delete("/meetings/{meeting_id}/decisions/{item_id}", response_model=OperationResponse)
async def delete_decision(
    meeting_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_UPDATE)],
) -> OperationResponse:
    await MeetingService(session).delete_item(
        user.organization_id, meeting_id, MeetingDecision, item_id, user.id, "MeetingUpdated"
    )
    return OperationResponse(message="Decision deleted")


@router.post("/meetings/{meeting_id}/actions", status_code=201)
async def add_action(
    meeting_id: uuid.UUID,
    body: ActionItemInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ACTION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_action(user.organization_id, meeting_id, body, user.id)
    )


@router.delete("/meetings/{meeting_id}/actions/{item_id}", response_model=OperationResponse)
async def delete_action(
    meeting_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ACTION_MANAGE)],
) -> OperationResponse:
    await MeetingService(session).delete_item(
        user.organization_id, meeting_id, MeetingActionItem, item_id, user.id, "MeetingUpdated"
    )
    return OperationResponse(message="Action item deleted")


@router.post("/meetings/{meeting_id}/notes", status_code=201)
async def add_note(
    meeting_id: uuid.UUID, body: NoteInput, session: Session, user: ReadUser
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_note(user.organization_id, meeting_id, body, user.id)
    )


@router.delete("/meetings/{meeting_id}/notes/{item_id}", response_model=OperationResponse)
async def delete_note(
    meeting_id: uuid.UUID, item_id: uuid.UUID, session: Session, user: ReadUser
) -> OperationResponse:
    await MeetingService(session).delete_item(
        user.organization_id, meeting_id, MeetingNote, item_id, user.id, "MeetingUpdated"
    )
    return OperationResponse(message="Note deleted")


@router.post("/meetings/{meeting_id}/artifacts", status_code=201)
async def add_artifact(
    meeting_id: uuid.UUID,
    body: ArtifactInput,
    session: Session,
    user: ReadUser,
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_artifact(user.organization_id, meeting_id, body, user.id)
    )


@router.post("/meetings/{meeting_id}/artifacts/upload", status_code=201)
async def upload_artifact(
    meeting_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    file: ArtifactUpload,
    user: ReadUser,
) -> dict[str, object]:
    content = await file.read()
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValueError("Meeting attachments must be between 1 byte and 25 MB")
    if settings.storage_provider != "local":
        raise RuntimeError("Configured storage provider is unavailable")
    stored = await LocalStorageProvider(
        settings.local_storage_path,
        settings.public_storage_url,
        settings.jwt_secret,
    ).put(
        f"organizations/{user.organization_id}/meetings/{meeting_id}",
        io.BytesIO(content),
        file.content_type or "application/octet-stream",
        len(content),
    )
    return serialize(
        await MeetingService(session).add_artifact(
            user.organization_id,
            meeting_id,
            ArtifactInput(
                artifact_type="attachment",
                title=file.filename or "Meeting attachment",
                storage_key=stored.key,
                content_type=stored.content_type,
                size=stored.size,
                metadata_json={"url": stored.url},
            ),
            user.id,
        )
    )


@router.post("/meetings/{meeting_id}/recordings", status_code=201)
async def add_recording(
    meeting_id: uuid.UUID,
    body: RecordingInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).add_recording(user.organization_id, meeting_id, body, user.id)
    )


@router.post("/meetings/{meeting_id}/attendance", status_code=201)
async def record_attendance(
    meeting_id: uuid.UUID,
    body: AttendanceEventInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).attendance(user.organization_id, meeting_id, body, user.id)
    )


@router.put("/meetings/{meeting_id}/presenter-controls")
async def update_presenter_control(
    meeting_id: uuid.UUID,
    body: PresenterControlInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).presenter_control(
            user.organization_id, meeting_id, body, user.id
        )
    )


@router.post("/meetings/{meeting_id}/follow-ups", status_code=201)
async def schedule_follow_up(
    meeting_id: uuid.UUID,
    body: FollowUpInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ACTION_MANAGE)],
) -> dict[str, object]:
    return serialize(
        await MeetingService(session).schedule_follow_up(
            user.organization_id, meeting_id, body, user.id
        )
    )


@router.get("/meetings/{meeting_id}/analytics", response_model=MeetingAnalytics)
async def meeting_analytics(
    meeting_id: uuid.UUID,
    session: Session,
    user: ReadUser,
) -> MeetingAnalytics:
    return MeetingAnalytics.model_validate(
        await MeetingService(session).analytics(user.organization_id, meeting_id)
    )


@router.get("/meeting-templates")
async def list_templates(session: Session, user: ReadUser) -> list[dict[str, object]]:
    return [
        serialize(item) for item in await MeetingService(session).templates(user.organization_id)
    ]


@router.post("/meeting-templates", status_code=201)
async def create_template(
    body: TemplateInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.MEETINGS_MANAGE)],
) -> dict[str, object]:
    return serialize(await MeetingService(session).create_template(user.organization_id, body))
