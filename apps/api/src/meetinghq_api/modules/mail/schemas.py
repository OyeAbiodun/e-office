"""Validated Internal Mail API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class MailRecipient(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=160)


class MailDraftInput(BaseModel):
    to_recipients: list[MailRecipient] = Field(default_factory=list, max_length=200)
    cc_recipients: list[MailRecipient] = Field(default_factory=list, max_length=200)
    bcc_recipients: list[MailRecipient] = Field(default_factory=list, max_length=200)
    subject: str = Field(default="", max_length=998)
    body_html: str = Field(default="", max_length=500_000)
    body_text: str = Field(default="", max_length=500_000)
    read_receipt_requested: bool = False
    reply_to_id: uuid.UUID | None = None


class MailMoveInput(BaseModel):
    folder: str = Field(min_length=1, max_length=80)


class MailLabelInput(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    enabled: bool = True


class MailAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str


class MailMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    thread_id: uuid.UUID
    folder: str
    status: str
    from_email: str
    from_name: str
    to_recipients: list[dict[str, str | None]]
    cc_recipients: list[dict[str, str | None]]
    bcc_recipients: list[dict[str, str | None]]
    subject: str
    body_html: str
    body_text: str
    preview: str
    labels: list[str]
    is_read: bool
    is_starred: bool
    read_receipt_requested: bool
    delivery_status: str
    delivery_error: str | None
    delivery_attempt_count: int
    delivery_last_attempt_at: datetime | None
    delivery_next_attempt_at: datetime | None
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attachments: list[MailAttachmentResponse] = Field(default_factory=list)


class MailPageResponse(BaseModel):
    items: list[MailMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    unread: int


class MailFolderInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")


class MailFolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID | None = None
    name: str
    color: str
    system: bool = False
    count: int = 0
    unread: int = 0


class MailTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(default="", max_length=998)
    body_html: str = Field(default="", max_length=500_000)


class MailTemplateResponse(MailTemplateInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime


class MailSignatureInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    body_html: str = Field(min_length=1, max_length=100_000)
    is_default: bool = False


class MailSignatureResponse(MailSignatureInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime


class MailSendInput(BaseModel):
    """Allows an atomic create-and-send flow from the composer."""

    draft: MailDraftInput

    @model_validator(mode="after")
    def recipients_required(self) -> "MailSendInput":
        if not (self.draft.to_recipients or self.draft.cc_recipients or self.draft.bcc_recipients):
            raise ValueError("At least one recipient is required")
        return self
