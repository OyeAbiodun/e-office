"""All Internal Mail persistence access, with mandatory tenant and owner predicates."""

import uuid
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.mail.models import (
    MailAttachment,
    MailFolder,
    MailMessage,
    MailSignature,
    MailTemplate,
)


class MailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def message(
        self, organization_id: uuid.UUID, owner_id: uuid.UUID, message_id: uuid.UUID
    ) -> MailMessage | None:
        return cast(
            MailMessage | None,
            await self.session.scalar(
                select(MailMessage).where(
                    MailMessage.id == message_id,
                    MailMessage.organization_id == organization_id,
                    MailMessage.owner_id == owner_id,
                    MailMessage.deleted_at.is_(None),
                )
            ),
        )

    async def messages(
        self,
        organization_id: uuid.UUID,
        owner_id: uuid.UUID,
        folder: str,
        search: str | None,
        label: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MailMessage], int]:
        filters = [
            MailMessage.organization_id == organization_id,
            MailMessage.owner_id == owner_id,
            MailMessage.folder == folder,
            MailMessage.deleted_at.is_(None),
        ]
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    MailMessage.subject.ilike(term),
                    MailMessage.preview.ilike(term),
                    MailMessage.from_email.ilike(term),
                    MailMessage.from_name.ilike(term),
                )
            )
        if label:
            filters.append(MailMessage.labels.contains([label]))
        total = int(
            await self.session.scalar(select(func.count()).select_from(MailMessage).where(*filters))
            or 0
        )
        rows = (
            await self.session.scalars(
                select(MailMessage)
                .where(*filters)
                .order_by(
                    MailMessage.sent_at.desc().nullslast(),
                    MailMessage.updated_at.desc(),
                    MailMessage.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return list(rows), total

    async def attachments(
        self, message_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[MailAttachment]]:
        if not message_ids:
            return {}
        grouped: dict[uuid.UUID, list[MailAttachment]] = {}
        for item in (
            await self.session.scalars(
                select(MailAttachment).where(MailAttachment.message_id.in_(message_ids))
            )
        ).all():
            grouped.setdefault(item.message_id, []).append(item)
        return grouped

    async def thread(
        self, organization_id: uuid.UUID, owner_id: uuid.UUID, thread_id: uuid.UUID
    ) -> list[MailMessage]:
        return list(
            (
                await self.session.scalars(
                    select(MailMessage)
                    .where(
                        MailMessage.organization_id == organization_id,
                        MailMessage.owner_id == owner_id,
                        MailMessage.thread_id == thread_id,
                        MailMessage.deleted_at.is_(None),
                    )
                    .order_by(MailMessage.created_at)
                )
            ).all()
        )

    async def unread(self, organization_id: uuid.UUID, owner_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(MailMessage)
                .where(
                    MailMessage.organization_id == organization_id,
                    MailMessage.owner_id == owner_id,
                    MailMessage.folder == "inbox",
                    MailMessage.is_read.is_(False),
                    MailMessage.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def folders(self, organization_id: uuid.UUID, owner_id: uuid.UUID) -> list[MailFolder]:
        return list(
            (
                await self.session.scalars(
                    select(MailFolder)
                    .where(
                        MailFolder.organization_id == organization_id,
                        MailFolder.owner_id == owner_id,
                    )
                    .order_by(MailFolder.name)
                )
            ).all()
        )

    async def templates(
        self, organization_id: uuid.UUID, owner_id: uuid.UUID
    ) -> list[MailTemplate]:
        return list(
            (
                await self.session.scalars(
                    select(MailTemplate)
                    .where(
                        MailTemplate.organization_id == organization_id,
                        MailTemplate.owner_id == owner_id,
                    )
                    .order_by(MailTemplate.name)
                )
            ).all()
        )

    async def signatures(
        self, organization_id: uuid.UUID, owner_id: uuid.UUID
    ) -> list[MailSignature]:
        return list(
            (
                await self.session.scalars(
                    select(MailSignature)
                    .where(
                        MailSignature.organization_id == organization_id,
                        MailSignature.owner_id == owner_id,
                    )
                    .order_by(MailSignature.name)
                )
            ).all()
        )
