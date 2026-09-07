"""Voucher documents use the shared storage adapter behind record authorization."""

import io
import uuid
from pathlib import Path

from sqlalchemy import select

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.finance.models import Voucher, VoucherAttachment, VoucherComment
from meetinghq_api.modules.finance.schemas import AttachmentResponse
from meetinghq_api.modules.finance.service import OPEN_EDITABLE, FinanceService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import AuthorizationError, NotFoundError, ValidationError

MAX_BYTES = 25 * 1024 * 1024


def validate_file(content: bytes, content_type: str) -> None:
    if not content or len(content) > MAX_BYTES:
        raise ValidationError("Upload a non-empty file up to 25 MB")
    signatures = {
        "application/pdf": b"%PDF-",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
    }
    if content_type in signatures:
        if not content.startswith(signatures[content_type]):
            raise ValidationError("File content does not match its type")
    elif content_type in {"text/plain", "text/csv"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError("Text attachments must use UTF-8") from error
        if "\x00" in text:
            raise ValidationError("Invalid text attachment")
    else:
        raise ValidationError("Use PDF, PNG, JPEG, plain text, or CSV documents")


class VoucherDocuments:
    def __init__(self, service: FinanceService, settings: Settings) -> None:
        self.service, self.settings = service, settings
        self.session = service.session

    async def editable(self, actor: User, voucher_id: uuid.UUID) -> Voucher:
        self.service.require(actor, "vouchers.edit_draft")
        voucher = await self.service._voucher(actor, voucher_id, lock=True)
        if voucher.requester_id != actor.id or voucher.status not in OPEN_EDITABLE:
            raise AuthorizationError("Documents can only be changed by the requester before review")
        return voucher

    def storage(self) -> LocalStorageProvider:
        if self.settings.storage_provider != "local":
            raise ValidationError("Document storage is unavailable")
        return LocalStorageProvider(
            self.settings.local_storage_path,
            self.settings.public_storage_url,
            self.settings.jwt_secret,
        )

    async def upload(
        self, actor: User, voucher: Voucher, filename: str, content_type: str, content: bytes
    ) -> AttachmentResponse:
        # The caller acquires authorization and the voucher lock before reading/writing storage.
        validate_file(content, content_type)
        filename = Path(filename.replace("\\", "/")).name
        filename = (
            "".join(c for c in filename if c.isprintable() and c not in '\r\n"')[:255] or "document"
        )
        storage = self.storage()
        stored = await storage.put(
            f"organizations/{actor.organization_id}/vouchers/{voucher.id}",
            io.BytesIO(content),
            content_type,
            len(content),
        )
        row = VoucherAttachment(
            id=uuid.uuid4(),
            organization_id=actor.organization_id,
            voucher_id=voucher.id,
            filename=filename,
            content_type=content_type,
            size=len(content),
            storage_key=stored.key,
            uploaded_by_id=actor.id,
            url="",
        )
        row.url = f"/api/v1/vouchers/{voucher.id}/attachments/{row.id}/download"
        try:
            self.session.add(row)
            await self.service._history(voucher, actor, "attachment_added", filename=filename)
            await self.session.flush()
        except Exception:
            await storage.delete(stored.key)
            raise
        return AttachmentResponse.model_validate(row)

    async def attachment(
        self, actor: User, voucher_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> VoucherAttachment:
        await self.service._voucher(actor, voucher_id)
        row = await self.session.scalar(
            select(VoucherAttachment).where(
                VoucherAttachment.organization_id == actor.organization_id,
                VoucherAttachment.voucher_id == voucher_id,
                VoucherAttachment.id == attachment_id,
                VoucherAttachment.deleted_at.is_(None),
            )
        )
        if row is None:
            raise NotFoundError("Voucher document not found")
        return row

    async def delete(self, actor: User, voucher_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        voucher = await self.editable(actor, voucher_id)
        row = await self.attachment(actor, voucher_id, attachment_id)
        row.soft_delete(actor.id)
        # Retain the underlying object for evidence/retention. All delivery checks soft deletion.
        await self.service._history(voucher, actor, "attachment_removed", filename=row.filename)

    async def comment(self, actor: User, voucher_id: uuid.UUID, body: str) -> None:
        self.service.require(actor, "vouchers.comment")
        voucher = await self.service._voucher(actor, voucher_id)
        self.session.add(
            VoucherComment(
                organization_id=actor.organization_id,
                voucher_id=voucher.id,
                author_id=actor.id,
                body=body,
            )
        )
        await self.service._history(voucher, actor, "commented")
