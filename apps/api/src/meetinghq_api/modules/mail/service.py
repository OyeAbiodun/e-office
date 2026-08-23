"""Internal Mail business logic and provider delivery boundary."""

import asyncio
import html
import re
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import nh3
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.core.secrets import SecretVault
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.configuration.models import ConfigurationEntry
from meetinghq_api.modules.mail.models import (
    MailAttachment,
    MailFolder,
    MailMessage,
    MailSignature,
    MailTemplate,
)
from meetinghq_api.modules.mail.repository import MailRepository
from meetinghq_api.modules.mail.schemas import (
    MailDraftInput,
    MailFolderInput,
    MailFolderResponse,
    MailMessageResponse,
    MailPageResponse,
    MailSignatureInput,
    MailTemplateInput,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError

SYSTEM_FOLDERS = ("inbox", "drafts", "sent", "trash")
MAIL_HTML_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
MAIL_HTML_ATTRIBUTES = {
    "a": {"href", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


class MailDeliveryAdapter:
    """Deliver external mail using the organization SMTP configuration."""

    def __init__(self, settings: Settings, values: dict[str, object]) -> None:
        self.settings = settings
        self.values = values

    async def send(
        self,
        sender: User,
        recipients: list[str],
        draft: MailMessage,
        attachments: list[MailAttachment],
    ) -> str:
        host = self._string("host")
        if not host:
            raise ConflictError(
                "External mail delivery is not configured. Configure SMTP in Integration Center."
            )
        message = EmailMessage()
        message["From"] = self._string("from_email") or sender.email
        message["To"] = ", ".join(recipients)
        message["Subject"] = draft.subject or "(No subject)"
        message_id = f"<{uuid.uuid4()}@meetinghq>"
        message["Message-ID"] = message_id
        message.set_content(draft.body_text or self._plain_text(draft.body_html))
        if draft.body_html:
            message.add_alternative(draft.body_html, subtype="html")
        for attachment in attachments:
            content = await asyncio.to_thread(self._attachment_content, attachment.storage_key)
            if content is None:
                continue
            maintype, _, subtype = attachment.content_type.partition("/")
            message.add_attachment(
                content,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        await asyncio.to_thread(self._smtp_send, host, message)
        return message_id

    def _smtp_send(self, host: str, message: EmailMessage) -> None:
        raw_port = self.values.get("port")
        port = int(raw_port) if isinstance(raw_port, (int, str)) else 587
        with smtplib.SMTP(host, port, timeout=20) as client:
            if self.values.get("starttls", True):
                client.starttls()
            username = self._string("username")
            if username:
                client.login(username, self._string("password") or "")
            client.send_message(message)

    def _string(self, key: str) -> str | None:
        value = self.values.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _attachment_content(self, storage_key: str) -> bytes | None:
        storage_root = Path(self.settings.local_storage_path).resolve()
        target = (storage_root / storage_key).resolve()
        if storage_root not in target.parents or not target.is_file():
            return None
        return target.read_bytes()

    @staticmethod
    def _plain_text(value: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()


class MailService:
    """Coordinate mailbox persistence, internal delivery, external providers, and audit."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = MailRepository(session)

    async def list_messages(
        self,
        user: User,
        folder: str,
        search: str | None,
        label: str | None,
        page: int,
        page_size: int,
    ) -> MailPageResponse:
        self._validate_page_size(page_size)
        rows, total = await self.repository.messages(
            user.organization_id, user.id, folder, search, label, page, page_size
        )
        attachments = await self.repository.attachments([item.id for item in rows])
        return MailPageResponse(
            items=[self._response(item, attachments.get(item.id, [])) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
            unread=await self.repository.unread(user.organization_id, user.id),
        )

    async def get_message(self, user: User, message_id: uuid.UUID) -> MailMessageResponse:
        message = await self._message(user, message_id)
        attachments = await self.repository.attachments([message.id])
        if not message.is_read and message.folder == "inbox":
            await self.mark_read(user, message.id, True)
        return self._response(message, attachments.get(message.id, []))

    async def thread(self, user: User, thread_id: uuid.UUID) -> list[MailMessageResponse]:
        rows = await self.repository.thread(user.organization_id, user.id, thread_id)
        attachments = await self.repository.attachments([item.id for item in rows])
        return [self._response(item, attachments.get(item.id, [])) for item in rows]

    async def create_draft(self, user: User, body: MailDraftInput) -> MailMessageResponse:
        message = MailMessage(
            organization_id=user.organization_id,
            owner_id=user.id,
            sender_id=user.id,
            folder="drafts",
            status="draft",
            delivery_status="draft",
            from_email=user.email,
            from_name=user.display_name,
            **self._draft_values(body),
        )
        self.session.add(message)
        await self.session.flush()
        await self._audit(user, "mail.draft.create", message.id)
        return self._response(message, [])

    async def update_draft(
        self, user: User, message_id: uuid.UUID, body: MailDraftInput
    ) -> MailMessageResponse:
        message = await self._message(user, message_id)
        if message.folder != "drafts" or message.status != "draft":
            raise ConflictError("Only draft messages can be edited")
        for key, value in self._draft_values(body).items():
            setattr(message, key, value)
        message.updated_at = datetime.now(UTC)
        await self.session.flush()
        attachments = await self.repository.attachments([message.id])
        return self._response(message, attachments.get(message.id, []))

    async def send_draft(self, user: User, message_id: uuid.UUID) -> MailMessageResponse:
        message = await self._message(user, message_id)
        if message.folder != "drafts" or message.status != "draft":
            raise ConflictError("Only draft messages can be sent")
        all_recipients = self._unique_recipients(message)
        if not all_recipients:
            raise ValidationError("At least one recipient is required")
        attachments = (await self.repository.attachments([message.id])).get(message.id, [])
        internal_users = {
            row.email.lower(): row
            for row in (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == user.organization_id,
                        func.lower(User.email).in_(all_recipients),
                        User.removed_at.is_(None),
                    )
                )
            ).all()
        }
        now = datetime.now(UTC)
        for recipient in internal_users.values():
            if recipient.id == user.id:
                continue
            delivered = MailMessage(
                organization_id=user.organization_id,
                owner_id=recipient.id,
                sender_id=user.id,
                thread_id=message.thread_id,
                source_message_id=message.id,
                folder="inbox",
                status="delivered",
                delivery_status="delivered",
                from_email=user.email,
                from_name=user.display_name,
                to_recipients=message.to_recipients,
                cc_recipients=message.cc_recipients,
                bcc_recipients=[],
                subject=message.subject,
                body_html=message.body_html,
                body_text=message.body_text,
                preview=message.preview,
                labels=[],
                is_read=False,
                read_receipt_requested=message.read_receipt_requested,
                reply_to_id=message.reply_to_id,
                sent_at=now,
            )
            self.session.add(delivered)
            await self.session.flush()
            for attachment in attachments:
                self.session.add(
                    MailAttachment(
                        organization_id=user.organization_id,
                        message_id=delivered.id,
                        filename=attachment.filename,
                        content_type=attachment.content_type,
                        size=attachment.size,
                        storage_key=attachment.storage_key,
                        url=attachment.url,
                    )
                )
        external = [address for address in all_recipients if address not in internal_users]
        delivery_error: str | None = None
        if external:
            configuration = await self._smtp_configuration(user.organization_id)
            try:
                await MailDeliveryAdapter(self.settings, configuration).send(
                    user, external, message, attachments
                )
            except Exception as error:
                delivery_error = str(error)[:500]
        message.folder = "sent"
        message.status = "sent" if not delivery_error else "failed"
        message.delivery_status = "delivered" if not delivery_error else "failed"
        message.delivery_error = delivery_error
        message.sent_at = now
        message.is_read = True
        message.updated_at = now
        await self.session.flush()
        await self._audit(
            user,
            "mail.message.send",
            message.id,
            {"internal_recipients": len(internal_users), "external_recipients": len(external)},
        )
        return self._response(message, attachments)

    async def add_attachment(
        self,
        user: User,
        message_id: uuid.UUID,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
        url: str,
    ) -> MailAttachment:
        message = await self._message(user, message_id)
        if message.folder != "drafts":
            raise ConflictError("Attachments can only be added to drafts")
        attachment = MailAttachment(
            organization_id=user.organization_id,
            message_id=message.id,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_key=storage_key,
            url=url,
        )
        self.session.add(attachment)
        await self.session.flush()
        return attachment

    async def mark_read(self, user: User, message_id: uuid.UUID, value: bool) -> MailMessage:
        message = await self._message(user, message_id)
        message.is_read = value
        message.read_at = datetime.now(UTC) if value else None
        message.updated_at = datetime.now(UTC)
        if value and message.source_message_id and message.read_receipt_requested:
            await self.session.execute(
                update(MailMessage)
                .where(
                    MailMessage.id == message.source_message_id,
                    MailMessage.organization_id == user.organization_id,
                )
                .values(delivery_status="read")
            )
        return message

    async def star(self, user: User, message_id: uuid.UUID, value: bool) -> MailMessage:
        message = await self._message(user, message_id)
        message.is_starred = value
        message.updated_at = datetime.now(UTC)
        return message

    async def label(
        self, user: User, message_id: uuid.UUID, label: str, enabled: bool
    ) -> MailMessage:
        message = await self._message(user, message_id)
        labels = set(message.labels)
        labels.add(label) if enabled else labels.discard(label)
        message.labels = sorted(labels)
        message.updated_at = datetime.now(UTC)
        return message

    async def move(self, user: User, message_id: uuid.UUID, folder: str) -> MailMessage:
        message = await self._message(user, message_id)
        valid = set(SYSTEM_FOLDERS) | {
            item.name for item in await self.repository.folders(user.organization_id, user.id)
        }
        if folder not in valid:
            raise ValidationError("Mailbox folder does not exist")
        message.folder = folder
        message.updated_at = datetime.now(UTC)
        await self._audit(user, "mail.message.move", message.id, {"folder": folder})
        return message

    async def folders(self, user: User) -> list[MailFolderResponse]:
        custom = await self.repository.folders(user.organization_id, user.id)
        result: list[MailFolderResponse] = []
        for name in SYSTEM_FOLDERS:
            total, unread = await self._folder_counts(user, name)
            result.append(
                MailFolderResponse(
                    name=name,
                    color="#64748b",
                    system=True,
                    count=total,
                    unread=unread,
                )
            )
        for item in custom:
            total, unread = await self._folder_counts(user, item.name)
            result.append(
                MailFolderResponse(
                    id=item.id,
                    name=item.name,
                    color=item.color,
                    system=False,
                    count=total,
                    unread=unread,
                )
            )
        return result

    async def create_folder(self, user: User, body: MailFolderInput) -> MailFolder:
        if body.name.lower() in SYSTEM_FOLDERS:
            raise ConflictError("That name is reserved for a system folder")
        folder = MailFolder(
            organization_id=user.organization_id, owner_id=user.id, **body.model_dump()
        )
        self.session.add(folder)
        await self.session.flush()
        return folder

    async def templates(self, user: User) -> list[MailTemplate]:
        return await self.repository.templates(user.organization_id, user.id)

    async def create_template(self, user: User, body: MailTemplateInput) -> MailTemplate:
        template = MailTemplate(
            organization_id=user.organization_id, owner_id=user.id, **body.model_dump()
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def signatures(self, user: User) -> list[MailSignature]:
        return await self.repository.signatures(user.organization_id, user.id)

    async def create_signature(self, user: User, body: MailSignatureInput) -> MailSignature:
        if body.is_default:
            await self.session.execute(
                update(MailSignature)
                .where(
                    MailSignature.organization_id == user.organization_id,
                    MailSignature.owner_id == user.id,
                )
                .values(is_default=False)
            )
        signature = MailSignature(
            organization_id=user.organization_id, owner_id=user.id, **body.model_dump()
        )
        self.session.add(signature)
        await self.session.flush()
        return signature

    async def provider_status(self, user: User) -> dict[str, object]:
        values = await self._smtp_configuration(user.organization_id, required=False)
        return {
            "internal_delivery": True,
            "external_delivery": bool(values.get("host")),
            "provider": "SMTP" if values.get("host") else None,
            "configuration_url": "/integrations",
        }

    async def _message(self, user: User, message_id: uuid.UUID) -> MailMessage:
        message = await self.repository.message(user.organization_id, user.id, message_id)
        if message is None:
            raise NotFoundError("Mail message not found")
        return message

    async def _smtp_configuration(
        self, organization_id: uuid.UUID, *, required: bool = True
    ) -> dict[str, object]:
        entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == "integration.smtp",
            )
        )
        if entry is None:
            if required:
                raise ConflictError(
                    "External mail delivery is not configured. "
                    "Configure SMTP in Integration Center."
                )
            return {}
        return SecretVault(self.settings.jwt_secret).open(dict(entry.value))

    async def _folder_counts(self, user: User, folder: str) -> tuple[int, int]:
        total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(MailMessage)
                .where(
                    MailMessage.organization_id == user.organization_id,
                    MailMessage.owner_id == user.id,
                    MailMessage.folder == folder,
                    MailMessage.deleted_at.is_(None),
                )
            )
            or 0
        )
        unread = int(
            await self.session.scalar(
                select(func.count())
                .select_from(MailMessage)
                .where(
                    MailMessage.organization_id == user.organization_id,
                    MailMessage.owner_id == user.id,
                    MailMessage.folder == folder,
                    MailMessage.is_read.is_(False),
                    MailMessage.deleted_at.is_(None),
                )
            )
            or 0
        )
        return total, unread

    async def _audit(
        self,
        user: User,
        action: str,
        resource_id: uuid.UUID,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=user.organization_id,
                user_id=user.id,
                action=action,
                resource="mail_message",
                resource_id=resource_id,
                audit_metadata=metadata or {},
            )
        )

    @staticmethod
    def _draft_values(body: MailDraftInput) -> dict[str, object]:
        payload = body.model_dump(mode="json")
        safe_html = nh3.clean(
            body.body_html,
            tags=MAIL_HTML_TAGS,
            attributes=MAIL_HTML_ATTRIBUTES,
            url_schemes={"http", "https", "mailto"},
        )
        payload["body_html"] = safe_html
        text = body.body_text or MailDeliveryAdapter._plain_text(safe_html)
        payload["body_text"] = text
        payload["preview"] = re.sub(r"\s+", " ", text).strip()[:500]
        return payload

    @staticmethod
    def _unique_recipients(message: MailMessage) -> list[str]:
        return sorted(
            {
                str(item["email"]).strip().lower()
                for item in (message.to_recipients + message.cc_recipients + message.bcc_recipients)
            }
        )

    @staticmethod
    def _validate_page_size(value: int) -> None:
        if value not in {10, 25, 50, 100}:
            raise ValidationError("Page size must be 10, 25, 50, or 100")

    @staticmethod
    def _response(message: MailMessage, attachments: list[MailAttachment]) -> MailMessageResponse:
        return MailMessageResponse.model_validate(message).model_copy(
            update={"attachments": attachments}
        )
