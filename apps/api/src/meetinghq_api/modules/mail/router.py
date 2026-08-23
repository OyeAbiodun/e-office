"""RBAC-protected Internal Mail endpoints."""

import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.mail.schemas import (
    MailAttachmentResponse,
    MailDraftInput,
    MailFolderInput,
    MailFolderResponse,
    MailLabelInput,
    MailMessageResponse,
    MailMoveInput,
    MailPageResponse,
    MailSignatureInput,
    MailSignatureResponse,
    MailTemplateInput,
    MailTemplateResponse,
)
from meetinghq_api.modules.mail.service import MailService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/mail", tags=["mail"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
MailReader = Annotated[User, require_permission("mail.view")]
MailCreator = Annotated[User, require_permission("mail.create")]
MailEditor = Annotated[User, require_permission("mail.edit")]
AttachmentUpload = Annotated[UploadFile, File()]


@router.get("/status")
async def provider_status(
    session: Session, settings: AppSettings, user: MailReader
) -> dict[str, object]:
    return await MailService(session, settings).provider_status(user)


@router.get("/messages", response_model=MailPageResponse)
async def messages(
    session: Session,
    settings: AppSettings,
    user: MailReader,
    folder: str = Query(default="inbox", max_length=80),
    search: str | None = Query(default=None, max_length=200),
    label: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25),
) -> MailPageResponse:
    return await MailService(session, settings).list_messages(
        user, folder, search, label, page, page_size
    )


@router.get("/messages/{message_id}", response_model=MailMessageResponse)
async def message(
    message_id: uuid.UUID, session: Session, settings: AppSettings, user: MailReader
) -> MailMessageResponse:
    return await MailService(session, settings).get_message(user, message_id)


@router.get("/threads/{thread_id}", response_model=list[MailMessageResponse])
async def thread(
    thread_id: uuid.UUID, session: Session, settings: AppSettings, user: MailReader
) -> list[MailMessageResponse]:
    return await MailService(session, settings).thread(user, thread_id)


@router.post("/drafts", response_model=MailMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    body: MailDraftInput, session: Session, settings: AppSettings, user: MailCreator
) -> MailMessageResponse:
    return await MailService(session, settings).create_draft(user, body)


@router.put("/drafts/{message_id}", response_model=MailMessageResponse)
async def update_draft(
    message_id: uuid.UUID,
    body: MailDraftInput,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
) -> MailMessageResponse:
    return await MailService(session, settings).update_draft(user, message_id, body)


@router.post("/drafts/{message_id}/send", response_model=MailMessageResponse)
async def send_draft(
    message_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: MailCreator,
) -> MailMessageResponse:
    return await MailService(session, settings).send_draft(user, message_id)


@router.post(
    "/drafts/{message_id}/attachments",
    response_model=MailAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    message_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
    file: AttachmentUpload,
) -> MailAttachmentResponse:
    content = await file.read()
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValueError("Mail attachments must be between 1 byte and 25 MB")
    stored = await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).put(
        f"organizations/{user.organization_id}/mail/{message_id}",
        io.BytesIO(content),
        file.content_type or "application/octet-stream",
        len(content),
    )
    attachment = await MailService(session, settings).add_attachment(
        user,
        message_id,
        file.filename or "attachment",
        stored.content_type,
        stored.size,
        stored.key,
        stored.url,
    )
    return MailAttachmentResponse.model_validate(attachment)


@router.post("/messages/{message_id}/read", response_model=MailMessageResponse)
async def mark_read(
    message_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
    value: bool = True,
) -> MailMessageResponse:
    row = await MailService(session, settings).mark_read(user, message_id, value)
    return await MailService(session, settings).get_message(user, row.id)


@router.post("/messages/{message_id}/star", response_model=MailMessageResponse)
async def star(
    message_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
    value: bool = True,
) -> MailMessageResponse:
    row = await MailService(session, settings).star(user, message_id, value)
    return await MailService(session, settings).get_message(user, row.id)


@router.post("/messages/{message_id}/labels", response_model=MailMessageResponse)
async def label(
    message_id: uuid.UUID,
    body: MailLabelInput,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
) -> MailMessageResponse:
    row = await MailService(session, settings).label(user, message_id, body.label, body.enabled)
    return await MailService(session, settings).get_message(user, row.id)


@router.post("/messages/{message_id}/move", response_model=MailMessageResponse)
async def move(
    message_id: uuid.UUID,
    body: MailMoveInput,
    session: Session,
    settings: AppSettings,
    user: MailEditor,
) -> MailMessageResponse:
    row = await MailService(session, settings).move(user, message_id, body.folder)
    return await MailService(session, settings).get_message(user, row.id)


@router.get("/folders", response_model=list[MailFolderResponse])
async def folders(
    session: Session, settings: AppSettings, user: MailReader
) -> list[MailFolderResponse]:
    return await MailService(session, settings).folders(user)


@router.post("/folders", response_model=MailFolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: MailFolderInput, session: Session, settings: AppSettings, user: MailEditor
) -> MailFolderResponse:
    return MailFolderResponse.model_validate(
        await MailService(session, settings).create_folder(user, body)
    )


@router.get("/templates", response_model=list[MailTemplateResponse])
async def templates(
    session: Session, settings: AppSettings, user: MailReader
) -> list[MailTemplateResponse]:
    return [
        MailTemplateResponse.model_validate(item)
        for item in await MailService(session, settings).templates(user)
    ]


@router.post("/templates", response_model=MailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: MailTemplateInput, session: Session, settings: AppSettings, user: MailCreator
) -> MailTemplateResponse:
    return MailTemplateResponse.model_validate(
        await MailService(session, settings).create_template(user, body)
    )


@router.get("/signatures", response_model=list[MailSignatureResponse])
async def signatures(
    session: Session, settings: AppSettings, user: MailReader
) -> list[MailSignatureResponse]:
    return [
        MailSignatureResponse.model_validate(item)
        for item in await MailService(session, settings).signatures(user)
    ]


@router.post(
    "/signatures", response_model=MailSignatureResponse, status_code=status.HTTP_201_CREATED
)
async def create_signature(
    body: MailSignatureInput, session: Session, settings: AppSettings, user: MailCreator
) -> MailSignatureResponse:
    return MailSignatureResponse.model_validate(
        await MailService(session, settings).create_signature(user, body)
    )
