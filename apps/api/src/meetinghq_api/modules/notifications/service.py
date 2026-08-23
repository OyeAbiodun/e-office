"""Meeting invitation delivery and reminder orchestration."""

import asyncio
import smtplib
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.meetings.models import Meeting, MeetingAttendee
from meetinghq_api.modules.notifications.models import (
    MeetingInvitationDelivery,
    MeetingReminder,
    Notification,
    NotificationPreference,
)
from meetinghq_api.modules.notifications.schemas import NotificationPreferenceUpdate
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.pagination import decode_cursor, encode_cursor


class MeetingEmailSender:
    """SMTP delivery with a standards-compliant local outbox transport."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(
        self,
        recipient: str,
        subject: str,
        text: str,
        ics: str | None = None,
    ) -> str:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message_id = f"<{uuid.uuid4()}@meetinghq>"
        message["Message-ID"] = message_id
        message.set_content(text)
        if ics:
            message.add_attachment(
                ics.encode(),
                maintype="text",
                subtype="calendar",
                filename="meeting.ics",
                params={"method": "REQUEST"},
            )
        if self.settings.smtp_host:
            await asyncio.to_thread(self._smtp_send, message)
        else:
            await asyncio.to_thread(self._write_outbox, message)
        return message_id

    def _write_outbox(self, message: EmailMessage) -> None:
        outbox = Path(self.settings.email_outbox_path).resolve()
        outbox.mkdir(parents=True, exist_ok=True)
        (outbox / f"{uuid.uuid4()}.eml").write_bytes(message.as_bytes())

    def _smtp_send(self, message: EmailMessage) -> None:
        host = self.settings.smtp_host
        if host is None:
            raise RuntimeError("SMTP host is not configured")
        with smtplib.SMTP(
            host,
            self.settings.smtp_port,
            timeout=20,
        ) as smtp:
            if self.settings.smtp_starttls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(
                    self.settings.smtp_username,
                    self.settings.smtp_password or "",
                )
            smtp.send_message(message)


class NotificationService:
    """Tenant-safe meeting notifications, invitation delivery, and reminders."""

    REMINDER_OFFSETS = (15, 30, 60, 1440)

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.email = MeetingEmailSender(settings)

    async def list_for_user(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str | None = None,
        priority: str | None = None,
        unread_only: bool = False,
        include_archived: bool = False,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        cursor: str | None = None,
    ) -> tuple[list[Notification], int, int, str | None, dict[str, int]]:
        query = select(Notification).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
        )
        if not include_archived:
            query = query.where(Notification.archived_at.is_(None))
        if category:
            query = query.where(Notification.category == category)
        if priority:
            query = query.where(Notification.priority == priority)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Notification.title.ilike(pattern),
                    Notification.body.ilike(pattern),
                )
            )
        if cursor:
            try:
                cursor_at, cursor_id = decode_cursor(cursor)
                cursor_uuid = uuid.UUID(cursor_id)
            except (ValueError, TypeError) as exc:
                raise ValidationError("Invalid notification cursor") from exc
            query = query.where(
                or_(
                    Notification.delivered_at < cursor_at,
                    (Notification.delivered_at == cursor_at) & (Notification.id < cursor_uuid),
                )
            )
        count_query = select(func.count()).select_from(query.subquery())
        total = int(await self.session.scalar(count_query) or 0)
        if not cursor:
            query = query.offset((page - 1) * page_size)
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        Notification.delivered_at.desc(),
                        Notification.id.desc(),
                    ).limit(page_size + 1)
                )
            ).all()
        )
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        next_cursor = (
            encode_cursor(rows[-1].delivered_at, str(rows[-1].id)) if has_more and rows else None
        )
        unread = (
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.organization_id == organization_id,
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                )
            )
            or 0
        )
        attention: dict[str, int] = {}
        for key in ("mentions", "meetings", "approvals", "tasks"):
            attention[key] = int(
                await self.session.scalar(
                    select(func.count(Notification.id)).where(
                        Notification.organization_id == organization_id,
                        Notification.user_id == user_id,
                        Notification.archived_at.is_(None),
                        Notification.read_at.is_(None),
                        Notification.category == key,
                    )
                )
                or 0
            )
        return rows, int(unread), total, next_cursor, attention

    async def bulk_action(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_ids: list[uuid.UUID],
        action: str,
    ) -> int:
        rows = list(
            (
                await self.session.scalars(
                    select(Notification).where(
                        Notification.organization_id == organization_id,
                        Notification.user_id == user_id,
                        Notification.id.in_(notification_ids),
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            if action == "read":
                row.read_at = now
            else:
                row.archived_at = now
        return len(rows)

    async def mark_read(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
        if item is None:
            raise NotFoundError("Notification not found")
        item.read_at = datetime.now(UTC)
        return item

    async def mark_all_read(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
        rows = (
            await self.session.scalars(
                select(Notification).where(
                    Notification.organization_id == organization_id,
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
        ).all()
        now = datetime.now(UTC)
        for row in rows:
            row.read_at = now
        return len(rows)

    async def archive(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self._owned_notification(organization_id, user_id, notification_id)
        item.archived_at = datetime.now(UTC)
        return item

    async def preferences(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationPreference:
        item = await self.session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.organization_id == organization_id,
                NotificationPreference.user_id == user_id,
            )
        )
        if item is None:
            item = NotificationPreference(
                organization_id=organization_id,
                user_id=user_id,
                in_app_enabled=True,
                email_enabled=True,
                browser_enabled=False,
                quiet_hours_enabled=False,
                timezone="UTC",
                category_rules={},
                delivery_rules={},
            )
            self.session.add(item)
            await self.session.flush()
        return item

    async def update_preferences(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        item = await self.preferences(organization_id, user_id)
        for field, value in body.model_dump().items():
            setattr(item, field, value)
        item.updated_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="notifications.preferences_updated",
                resource="notification_preferences",
                resource_id=item.id,
                audit_metadata={},
            )
        )
        await self.session.flush()
        return item

    async def _owned_notification(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
        if item is None:
            raise NotFoundError("Notification not found")
        return item

    async def invite_participants(
        self, meeting: Meeting, organizer: User, participant_ids: set[uuid.UUID]
    ) -> None:
        if not participant_ids:
            return
        participants = list(
            (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == meeting.organization_id,
                        User.id.in_(participant_ids),
                    )
                )
            ).all()
        )
        ics = self.ics(meeting, organizer, participants)
        for participant in participants:
            notification = Notification(
                organization_id=meeting.organization_id,
                user_id=participant.id,
                meeting_id=meeting.id,
                notification_type="meeting_invitation",
                title=f"Meeting invitation: {meeting.title}",
                body=self._invitation_text(meeting, organizer),
                action_url=f"/meetings/{meeting.id}",
            )
            self.session.add(notification)
            in_app = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="in_app",
                recipient=str(participant.id),
                status="sent",
                sent_at=datetime.now(UTC),
            )
            email_delivery = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="email",
                recipient=participant.email,
            )
            ics_delivery = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="ics",
                recipient=participant.email,
            )
            self.session.add_all([in_app, email_delivery, ics_delivery])
            try:
                transport_id = await self.email.send(
                    participant.email,
                    f"Invitation: {meeting.title}",
                    self._invitation_text(meeting, organizer),
                    ics,
                )
                for delivery in (email_delivery, ics_delivery):
                    delivery.status = "sent"
                    delivery.transport_id = transport_id
                    delivery.sent_at = datetime.now(UTC)
            except Exception as exc:
                for delivery in (email_delivery, ics_delivery):
                    delivery.status = "failed"
                    delivery.error = str(exc)[:2000]
                raise
            for offset in self.REMINDER_OFFSETS:
                scheduled_for = meeting.start_datetime - timedelta(minutes=offset)
                if scheduled_for > datetime.now(UTC):
                    self.session.add(
                        MeetingReminder(
                            organization_id=meeting.organization_id,
                            meeting_id=meeting.id,
                            user_id=participant.id,
                            offset_minutes=offset,
                            scheduled_for=scheduled_for,
                        )
                    )

    async def schedule_reminders(self, meeting: Meeting, user_ids: set[uuid.UUID]) -> None:
        now = datetime.now(UTC)
        for user_id in user_ids:
            for offset in self.REMINDER_OFFSETS:
                scheduled_for = meeting.start_datetime - timedelta(minutes=offset)
                if scheduled_for > now:
                    self.session.add(
                        MeetingReminder(
                            organization_id=meeting.organization_id,
                            meeting_id=meeting.id,
                            user_id=user_id,
                            offset_minutes=offset,
                            scheduled_for=scheduled_for,
                        )
                    )

    async def notify_organizer(
        self,
        meeting: Meeting,
        notification_type: str,
        title: str,
        body: str,
    ) -> None:
        self.session.add(
            Notification(
                organization_id=meeting.organization_id,
                user_id=meeting.organizer_id,
                meeting_id=meeting.id,
                notification_type=notification_type,
                title=title,
                body=body,
                action_url=f"/meetings/{meeting.id}",
            )
        )

    async def notify_participants(
        self,
        meeting: Meeting,
        notification_type: str,
        subject: str,
        body: str,
        include_organizer: bool = False,
    ) -> None:
        attendee_ids = set(
            (
                await self.session.scalars(
                    select(MeetingAttendee.user_id).where(MeetingAttendee.meeting_id == meeting.id)
                )
            ).all()
        )
        if not include_organizer:
            attendee_ids.discard(meeting.organizer_id)
        users = list(
            (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == meeting.organization_id,
                        User.id.in_(attendee_ids),
                    )
                )
            ).all()
        )
        for user in users:
            self.session.add(
                Notification(
                    organization_id=meeting.organization_id,
                    user_id=user.id,
                    meeting_id=meeting.id,
                    notification_type=notification_type,
                    title=subject,
                    body=body,
                    action_url=f"/meetings/{meeting.id}",
                )
            )
            await self.email.send(user.email, subject, body)

    async def process_due_reminders(self) -> int:
        now = datetime.now(UTC)
        reminders = list(
            (
                await self.session.scalars(
                    select(MeetingReminder)
                    .where(
                        MeetingReminder.status == "pending",
                        MeetingReminder.scheduled_for <= now,
                    )
                    .order_by(MeetingReminder.scheduled_for)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        delivered = 0
        for reminder in reminders:
            meeting = await self.session.get(Meeting, reminder.meeting_id)
            user = await self.session.get(User, reminder.user_id)
            if meeting is None or user is None or meeting.status.value == "cancelled":
                reminder.status = "cancelled"
                continue
            reminder.status = "processing"
            body = (
                f"{meeting.title} starts in {self._offset_label(reminder.offset_minutes)} "
                f"at {meeting.start_datetime.isoformat()} ({meeting.timezone})."
            )
            try:
                await self.email.send(
                    user.email,
                    f"Reminder: {meeting.title}",
                    body,
                )
                self.session.add(
                    Notification(
                        organization_id=meeting.organization_id,
                        user_id=user.id,
                        meeting_id=meeting.id,
                        notification_type="meeting_reminder",
                        title=f"Upcoming: {meeting.title}",
                        body=body,
                        action_url=f"/meetings/{meeting.id}",
                    )
                )
                reminder.status = "sent"
                reminder.delivered_at = datetime.now(UTC)
                delivered += 1
            except Exception as exc:
                reminder.status = "failed"
                reminder.error = str(exc)[:2000]
        return delivered

    @classmethod
    def ics(cls, meeting: Meeting, organizer: User, participants: list[User]) -> str:
        attendees = [
            f"ATTENDEE;CN={cls._escape(user.display_name)};RSVP=TRUE:mailto:{user.email}"
            for user in participants
        ]
        location = getattr(meeting, "location", None) or meeting.meeting_url or ""
        return "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//MeetingHQ//Meeting Invitation//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:REQUEST",
                "BEGIN:VEVENT",
                f"UID:{meeting.id}@meetinghq",
                f"DTSTAMP:{cls._ics_datetime(datetime.now(UTC))}",
                f"DTSTART:{cls._ics_datetime(meeting.start_datetime)}",
                f"DTEND:{cls._ics_datetime(meeting.end_datetime)}",
                f"SUMMARY:{cls._escape(meeting.title)}",
                f"DESCRIPTION:{cls._escape(meeting.description or '')}",
                f"LOCATION:{cls._escape(location)}",
                f"ORGANIZER;CN={cls._escape(organizer.display_name)}:mailto:{organizer.email}",
                *attendees,
                "STATUS:CONFIRMED",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )

    @staticmethod
    def _invitation_text(meeting: Meeting, organizer: User) -> str:
        location = getattr(meeting, "location", None) or meeting.meeting_url or "Not specified"
        return (
            f"{organizer.display_name} invited you to {meeting.title}.\n\n"
            f"Agenda: {meeting.description or 'No agenda provided'}\n"
            f"Starts: {meeting.start_datetime.isoformat()} ({meeting.timezone})\n"
            f"Ends: {meeting.end_datetime.isoformat()} ({meeting.timezone})\n"
            f"Location: {location}\n"
            f"Meeting link: {meeting.meeting_url or 'Not specified'}\n\n"
            "Open MeetingHQ to Accept, Decline, or respond Tentative."
        )

    @staticmethod
    def _ics_datetime(value: datetime) -> str:
        aware = value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)
        return aware.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        )

    @staticmethod
    def _offset_label(minutes: int) -> str:
        if minutes >= 1440:
            return f"{minutes // 1440} day"
        if minutes >= 60:
            return f"{minutes // 60} hour"
        return f"{minutes} minutes"
