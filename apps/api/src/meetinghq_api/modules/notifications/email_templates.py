# ruff: noqa: E501
"""Safe, reusable transactional email rendering for MeetingHQ.

The renderer deliberately uses conservative table-based markup and inline styles.  It has
no template-language evaluation surface: every dynamic value is escaped before it reaches
HTML, and every URL is validated before it can become a link target.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from meetinghq_api.modules.organizations.models import Organization

TemplateKey = Literal[
    "auth.password_reset",
    "auth.email_verification",
    "user.invitation",
    "user.temporary_password",
    "meeting.invitation",
    "meeting.updated",
    "meeting.cancelled",
    "meeting.reminder",
    "voucher.submitted",
    "voucher.returned",
    "voucher.approved",
    "voucher.rejected",
    "voucher.partially_disbursed",
    "voucher.disbursed",
    "voucher.reversed",
    "smtp.test",
]

TEMPLATE_VERSION = "2026.09.1"
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class EmailBranding:
    """Safe display-only tenant branding with durable MeetingHQ fallbacks."""

    organization_name: str = "MeetingHQ"
    accent_color: str = "#2563eb"
    logo_url: str | None = None
    support_url: str | None = None
    support_email: str | None = None

    def __post_init__(self) -> None:
        """Defend the renderer even when callers construct a branding object directly."""
        object.__setattr__(
            self, "organization_name", _safe_text(self.organization_name, "MeetingHQ", 160)
        )
        object.__setattr__(self, "accent_color", _safe_color(self.accent_color))
        object.__setattr__(self, "logo_url", _safe_url(self.logo_url))
        object.__setattr__(self, "support_url", _safe_url(self.support_url))
        object.__setattr__(self, "support_email", _safe_email(self.support_email))

    @classmethod
    def from_organization(cls, organization: Organization | None) -> EmailBranding:
        if organization is None:
            return cls()
        settings = organization.settings if isinstance(organization.settings, dict) else {}
        return cls(
            organization_name=_safe_text(organization.name, "MeetingHQ", 160),
            accent_color=_safe_color(organization.brand_color),
            logo_url=_safe_url(organization.logo_url),
            support_url=_safe_url(settings.get("support_url")),
            support_email=_safe_email(settings.get("support_email")),
        )


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    key: TemplateKey
    subject: str
    text: str
    html: str
    version: str = TEMPLATE_VERSION


@dataclass(frozen=True, slots=True)
class PasswordResetEmailData:
    reset_url: str
    expires_in: str = "20 minutes"


@dataclass(frozen=True, slots=True)
class VerificationEmailData:
    verification_url: str


@dataclass(frozen=True, slots=True)
class UserInvitationEmailData:
    invitation_url: str
    organization_name: str


@dataclass(frozen=True, slots=True)
class TemporaryPasswordEmailData:
    login_url: str
    temporary_password: str


@dataclass(frozen=True, slots=True)
class MeetingEmailData:
    meeting_url: str
    title: str
    organizer_name: str
    start_time: str
    end_time: str
    timezone: str
    location: str | None = None
    join_url: str | None = None
    description: str | None = None
    agenda: str | None = None
    previous_start_time: str | None = None
    previous_end_time: str | None = None
    cancellation_reason: str | None = None
    reminder_label: str | None = None


@dataclass(frozen=True, slots=True)
class SmtpTestEmailData:
    accepted_at: str
    environment: str


@dataclass(frozen=True, slots=True)
class VoucherEmailData:
    """Display-safe data for a controlled voucher-workflow delivery."""

    voucher_url: str
    voucher_number: str
    title: str
    requested_amount: str
    approved_amount: str
    disbursed_amount: str
    outstanding_amount: str
    reason: str | None = None


EmailTemplateData = (
    PasswordResetEmailData
    | VerificationEmailData
    | UserInvitationEmailData
    | TemporaryPasswordEmailData
    | MeetingEmailData
    | SmtpTestEmailData
    | VoucherEmailData
)


class EmailTemplateRegistry:
    """Typed registry for every currently generated system email."""

    @classmethod
    def render(
        cls,
        key: TemplateKey,
        data: EmailTemplateData,
        branding: EmailBranding | None = None,
    ) -> RenderedEmail:
        brand = branding or EmailBranding()
        if key == "auth.password_reset" and isinstance(data, PasswordResetEmailData):
            return cls._password_reset(data, brand)
        if key == "auth.email_verification" and isinstance(data, VerificationEmailData):
            return cls._verification(data, brand)
        if key == "user.invitation" and isinstance(data, UserInvitationEmailData):
            return cls._invitation(data, brand)
        if key == "user.temporary_password" and isinstance(data, TemporaryPasswordEmailData):
            return cls._temporary_password(data, brand)
        if key in {
            "meeting.invitation",
            "meeting.updated",
            "meeting.cancelled",
            "meeting.reminder",
        } and isinstance(data, MeetingEmailData):
            return cls._meeting(key, data, brand)
        if key == "smtp.test" and isinstance(data, SmtpTestEmailData):
            return cls._smtp_test(data, brand)
        if key in {
            "voucher.submitted",
            "voucher.returned",
            "voucher.approved",
            "voucher.rejected",
            "voucher.partially_disbursed",
            "voucher.disbursed",
            "voucher.reversed",
        } and isinstance(data, VoucherEmailData):
            return cls._voucher(key, data, brand)
        raise TypeError(f"Template {key} received incompatible data")

    @classmethod
    def preview(cls, key: TemplateKey, branding: EmailBranding | None = None) -> RenderedEmail:
        """Render safe sample data only; preview never reads or sends secrets."""
        app = "https://app.meetinghq.example"
        samples: dict[TemplateKey, EmailTemplateData] = {
            "auth.password_reset": PasswordResetEmailData(f"{app}/reset-password?token=example"),
            "auth.email_verification": VerificationEmailData(f"{app}/verify-email?token=example"),
            "user.invitation": UserInvitationEmailData(
                f"{app}/invitations/accept?token=example", "Acme Corporation"
            ),
            "user.temporary_password": TemporaryPasswordEmailData(
                f"{app}/login", "Temporary-password-example"
            ),
            "meeting.invitation": MeetingEmailData(
                f"{app}/meetings/example",
                "Quarterly planning",
                "Alex Morgan",
                "Tuesday, September 8 · 10:00 AM",
                "11:00 AM",
                "Africa/Lagos",
                "Conference Room A",
                "https://meet.example/quarterly",
                "Set priorities and owners for the next quarter.",
                "Review objectives and action items.",
            ),
            "meeting.updated": MeetingEmailData(
                f"{app}/meetings/example",
                "Quarterly planning",
                "Alex Morgan",
                "Tuesday, September 8 · 11:00 AM",
                "12:00 PM",
                "Africa/Lagos",
                "Conference Room A",
                "https://meet.example/quarterly",
                previous_start_time="Tuesday, September 8 · 10:00 AM",
                previous_end_time="11:00 AM",
            ),
            "meeting.cancelled": MeetingEmailData(
                f"{app}/meetings/example",
                "Quarterly planning",
                "Alex Morgan",
                "Tuesday, September 8 · 10:00 AM",
                "11:00 AM",
                "Africa/Lagos",
                cancellation_reason="Scheduling conflict",
            ),
            "meeting.reminder": MeetingEmailData(
                f"{app}/meetings/example",
                "Quarterly planning",
                "Alex Morgan",
                "Tuesday, September 8 · 10:00 AM",
                "11:00 AM",
                "Africa/Lagos",
                join_url="https://meet.example/quarterly",
                reminder_label="15 minutes",
            ),
            "voucher.submitted": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 0.00",
                "NGN 0.00",
                "NGN 0.00",
            ),
            "voucher.returned": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 0.00",
                "NGN 0.00",
                "NGN 0.00",
                "Please add the missing receipt.",
            ),
            "voucher.approved": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 500,000.00",
                "NGN 0.00",
                "NGN 500,000.00",
            ),
            "voucher.rejected": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 0.00",
                "NGN 0.00",
                "NGN 0.00",
                "This request is outside the approved budget.",
            ),
            "voucher.partially_disbursed": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 500,000.00",
                "NGN 300,000.00",
                "NGN 200,000.00",
            ),
            "voucher.disbursed": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 500,000.00",
                "NGN 500,000.00",
                "NGN 0.00",
            ),
            "voucher.reversed": VoucherEmailData(
                f"{app}/vouchers/example",
                "VCH-20260907-0001",
                "Quarterly planning supplies",
                "NGN 500,000.00",
                "NGN 500,000.00",
                "NGN 300,000.00",
                "NGN 200,000.00",
                "Payment returned by the bank.",
            ),
            "smtp.test": SmtpTestEmailData(
                datetime.now(UTC).strftime("%B %d, %Y · %H:%M UTC"), "development"
            ),
        }
        return cls.render(key, samples[key], branding)

    @staticmethod
    def _password_reset(data: PasswordResetEmailData, brand: EmailBranding) -> RenderedEmail:
        url = _required_url(data.reset_url)
        text = (
            "Reset your MeetingHQ password\n\n"
            f"Use this secure link within {data.expires_in}:\n{url}\n\n"
            "If you did not request this, you can safely ignore this email."
        )
        body = "".join(
            [
                _heading("Reset your password"),
                _paragraph("We received a request to reset your MeetingHQ password."),
                _button(url, "Reset password", brand),
                _paragraph(
                    f"This link expires in {_safe_text(data.expires_in, '20 minutes', 80)}."
                ),
                _notice(
                    "If you did not request this, you can safely ignore this email. Your password will not change."
                ),
                _fallback_link(url, "Reset password"),
            ]
        )
        return _render(
            "auth.password_reset",
            "MeetingHQ | Reset your password",
            text,
            body,
            brand,
            security=True,
        )

    @staticmethod
    def _verification(data: VerificationEmailData, brand: EmailBranding) -> RenderedEmail:
        url = _required_url(data.verification_url)
        text = f"Verify your MeetingHQ email\n\nVerify your email address:\n{url}"
        body = (
            _heading("Verify your email")
            + _paragraph("Confirm your email address to finish securing your MeetingHQ account.")
            + _button(url, "Verify email", brand)
            + _fallback_link(url, "Verify email")
        )
        return _render(
            "auth.email_verification",
            "MeetingHQ | Verify your email",
            text,
            body,
            brand,
            security=True,
        )

    @staticmethod
    def _invitation(data: UserInvitationEmailData, brand: EmailBranding) -> RenderedEmail:
        url = _required_url(data.invitation_url)
        organization = _safe_text(data.organization_name, brand.organization_name, 160)
        text = f"You're invited to {organization} on MeetingHQ\n\nAccept your invitation:\n{url}"
        body = (
            _heading("You’re invited")
            + _paragraph(f"You have been invited to join {organization} in MeetingHQ.")
            + _button(url, "Accept invitation", brand)
            + _fallback_link(url, "Accept invitation")
        )
        return _render("user.invitation", "MeetingHQ | You’re invited", text, body, brand)

    @staticmethod
    def _temporary_password(
        data: TemporaryPasswordEmailData, brand: EmailBranding
    ) -> RenderedEmail:
        url = _required_url(data.login_url)
        password = _safe_text(data.temporary_password, "", 512)
        text = f"Your MeetingHQ account is ready\n\nSign in: {url}\nTemporary password: {password}\n\nYou must change this password at first sign-in."
        body = (
            _heading("Your account is ready")
            + _paragraph("An administrator created your MeetingHQ account.")
            + _detail_rows(
                [
                    ("Temporary password", password),
                    ("Next step", "Change this password at your first sign-in."),
                ]
            )
            + _button(url, "Sign in to MeetingHQ", brand)
            + _notice(
                "Keep this temporary password private. MeetingHQ support will never ask you to share it."
            )
            + _fallback_link(url, "Sign in to MeetingHQ")
        )
        return _render(
            "user.temporary_password",
            "MeetingHQ | Your account is ready",
            text,
            body,
            brand,
            security=True,
        )

    @classmethod
    def _meeting(
        cls, key: TemplateKey, data: MeetingEmailData, brand: EmailBranding
    ) -> RenderedEmail:
        title = _safe_text(data.title, "Untitled meeting", 250)
        meeting_url = _required_url(data.meeting_url)
        subject_prefix = {
            "meeting.invitation": "Invitation",
            "meeting.updated": "Meeting updated",
            "meeting.cancelled": "Meeting cancelled",
            "meeting.reminder": "Reminder",
        }[key]
        if key == "meeting.reminder":
            lead = f"{title} starts in {_safe_text(data.reminder_label, 'soon', 80)}."
            heading = "Meeting reminder"
        elif key == "meeting.cancelled":
            lead, heading = "This meeting has been cancelled.", "Meeting cancelled"
        elif key == "meeting.updated":
            lead, heading = "This meeting has been updated.", "Meeting updated"
        else:
            lead, heading = "You’re invited to a meeting.", "You’re invited"
        rows: list[tuple[str, str | None]] = [
            ("Organizer", data.organizer_name),
            ("Date & time", data.start_time),
            ("Ends", data.end_time),
            ("Time zone", data.timezone),
        ]
        if data.location:
            rows.append(("Location", data.location))
        if key == "meeting.updated" and data.previous_start_time:
            rows.insert(
                1,
                (
                    "Previously",
                    f"{data.previous_start_time} – {data.previous_end_time or ''}".strip(),
                ),
            )
        text_lines = [
            heading,
            "",
            title,
            lead,
            "",
            f"Organizer: {data.organizer_name}",
            f"Starts: {data.start_time} ({data.timezone})",
            f"Ends: {data.end_time}",
        ]
        if data.location:
            text_lines.append(f"Location: {data.location}")
        if data.join_url:
            text_lines.append(f"Join: {_required_url(data.join_url)}")
        if data.description:
            text_lines.extend(["", f"Details: {data.description}"])
        if data.cancellation_reason:
            text_lines.extend(["", f"Reason: {data.cancellation_reason}"])
        text_lines.extend(["", f"View meeting: {meeting_url}"])
        body = _heading(heading) + _paragraph(lead) + _meeting_card(title, rows, brand)
        if data.description and key not in {"meeting.reminder", "meeting.cancelled"}:
            body += _section("Details", data.description)
        if data.agenda and key == "meeting.invitation":
            body += _section("Agenda", data.agenda)
        if data.cancellation_reason and key == "meeting.cancelled":
            body += _section("Cancellation reason", data.cancellation_reason)
        button_label = (
            "Join meeting" if key == "meeting.reminder" and data.join_url else "View meeting"
        )
        body += _button(
            (
                _required_url(data.join_url)
                if button_label == "Join meeting" and data.join_url
                else meeting_url
            ),
            button_label,
            brand,
        )
        if key == "meeting.invitation":
            body += _paragraph("Use MeetingHQ to respond: Accept, Tentative, or Decline.")
        body += _fallback_link(meeting_url, "View meeting")
        return _render(
            key, f"MeetingHQ | {subject_prefix}: {title}", "\n".join(text_lines), body, brand
        )

    @staticmethod
    def _smtp_test(data: SmtpTestEmailData, brand: EmailBranding) -> RenderedEmail:
        text = (
            "MeetingHQ SMTP test successful\n\n"
            "The configured SMTP provider accepted this test message.\n"
            f"Accepted at: {_safe_text(data.accepted_at, 'Unknown', 120)}\n"
            f"Environment: {_safe_text(data.environment, 'Unknown', 80)}\n\n"
            "SMTP acceptance does not by itself prove final mailbox delivery."
        )
        body = (
            _heading("SMTP test successful")
            + _paragraph(
                "MeetingHQ submitted this message through the configured outbound email path."
            )
            + _detail_rows(
                [("Provider acceptance", data.accepted_at), ("Environment", data.environment)]
            )
            + _notice(
                "SMTP acceptance does not by itself prove final mailbox delivery. Confirm receipt in this mailbox."
            )
        )
        return _render("smtp.test", "MeetingHQ | SMTP test successful", text, body, brand)

    @staticmethod
    def _voucher(key: TemplateKey, data: VoucherEmailData, brand: EmailBranding) -> RenderedEmail:
        voucher_url = _required_url(data.voucher_url)
        voucher_number = _safe_text(data.voucher_number, "Voucher", 64)
        title = _safe_text(data.title, "Untitled voucher", 250)
        labels = {
            "voucher.submitted": ("Voucher submitted", "A voucher is ready for review."),
            "voucher.returned": (
                "Voucher returned",
                "This voucher needs an update before it can be reviewed again.",
            ),
            "voucher.approved": (
                "Voucher approved",
                "This voucher is approved and ready for disbursement.",
            ),
            "voucher.rejected": ("Voucher rejected", "This voucher was not approved."),
            "voucher.partially_disbursed": (
                "Voucher partially disbursed",
                "A partial payment has been recorded.",
            ),
            "voucher.disbursed": (
                "Voucher fully disbursed",
                "The approved amount has been disbursed.",
            ),
            "voucher.reversed": (
                "Voucher payment reversed",
                "A related payment has been reversed.",
            ),
        }
        heading, lead = labels[key]
        rows: list[tuple[str, str | None]] = [
            ("Voucher", voucher_number),
            ("Purpose", title),
            ("Requested", data.requested_amount),
            ("Approved", data.approved_amount),
            ("Disbursed", data.disbursed_amount),
            ("Outstanding", data.outstanding_amount),
        ]
        text_lines = [heading, "", voucher_number, title, lead, ""]
        text_lines.extend(f"{label}: {_safe_text(value, '—', 120)}" for label, value in rows[2:])
        if data.reason:
            text_lines.extend(["", f"Note: {_safe_text(data.reason, '', 2000)}"])
        text_lines.extend(["", f"View voucher: {voucher_url}"])
        body = _heading(heading) + _paragraph(lead) + _detail_rows(rows)
        if data.reason:
            body += _section("Note", data.reason)
        body += _button(voucher_url, "View voucher", brand) + _fallback_link(
            voucher_url, "View voucher"
        )
        return _render(
            key,
            f"MeetingHQ | {heading}: {voucher_number}",
            "\n".join(text_lines),
            body,
            brand,
        )


def _render(
    key: TemplateKey,
    subject: str,
    text: str,
    content: str,
    brand: EmailBranding,
    security: bool = False,
) -> RenderedEmail:
    logo = (
        f'<img src="{html.escape(brand.logo_url, quote=True)}" width="32" height="32" alt="{html.escape(brand.organization_name)} logo" style="display:block;border:0;border-radius:6px;" />'
        if brand.logo_url
        else f'<div style="width:32px;height:32px;line-height:32px;text-align:center;background:{brand.accent_color};border-radius:6px;color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:700;">M</div>'
    )
    support = (
        f'<a href="{html.escape(brand.support_url, quote=True)}" style="color:#475569;text-decoration:underline;">Help and support</a>'
        if brand.support_url
        else html.escape(brand.support_email or "Contact your MeetingHQ administrator")
    )
    security_notice = (
        '<p style="margin:16px 0 0;color:#64748b;font-family:Arial,sans-serif;font-size:12px;line-height:18px;">For your security, MeetingHQ will never ask you to send your password or verification code by email.</p>'
        if security
        else ""
    )
    year = datetime.now(UTC).year
    html_body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f1f5f9;color:#0f172a;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f1f5f9;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #dbe3ee;border-radius:12px;overflow:hidden;">
<tr><td style="padding:24px 28px;border-bottom:1px solid #e2e8f0;"><table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td style="padding-right:12px;vertical-align:middle;">{logo}</td><td style="vertical-align:middle;"><div style="font-family:Arial,sans-serif;font-size:18px;font-weight:700;color:#0f172a;">MeetingHQ</div><div style="font-family:Arial,sans-serif;font-size:12px;color:#64748b;margin-top:2px;">Schedule. Meet. Collaborate.</div></td></tr></table></td></tr>
<tr><td style="padding:30px 28px 24px;">{content}</td></tr>
<tr><td style="padding:20px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;"><p style="margin:0;color:#64748b;font-family:Arial,sans-serif;font-size:12px;line-height:18px;">This email was sent by MeetingHQ for {html.escape(brand.organization_name)}.</p>{security_notice}<p style="margin:12px 0 0;color:#64748b;font-family:Arial,sans-serif;font-size:12px;line-height:18px;">{support} · © {year} MeetingHQ</p></td></tr>
</table></td></tr></table></body></html>"""
    return RenderedEmail(key=key, subject=subject, text=text, html=html_body)


def _heading(value: str) -> str:
    return f'<h1 style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:24px;line-height:32px;color:#0f172a;">{html.escape(_safe_text(value, "MeetingHQ", 250))}</h1>'


def _paragraph(value: str) -> str:
    return f'<p style="margin:0 0 18px;font-family:Arial,sans-serif;font-size:15px;line-height:24px;color:#334155;">{_multiline(value)}</p>'


def _notice(value: str) -> str:
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:20px 0;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;"><tr><td style="padding:14px 16px;font-family:Arial,sans-serif;font-size:13px;line-height:20px;color:#1e3a8a;">{_multiline(value)}</td></tr></table>'


def _section(label: str, value: str) -> str:
    return f'<h2 style="margin:24px 0 8px;font-family:Arial,sans-serif;font-size:15px;line-height:22px;color:#0f172a;">{html.escape(_safe_text(label, "Details", 100))}</h2><p style="margin:0;font-family:Arial,sans-serif;font-size:14px;line-height:21px;color:#475569;">{_multiline(value)}</p>'


def _detail_rows(rows: list[tuple[str, str | None]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:13px;color:#64748b;width:38%;vertical-align:top;">{html.escape(_safe_text(label, "", 100))}</td><td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:13px;line-height:19px;color:#0f172a;">{_multiline(value or "Not specified")}</td></tr>'
        for label, value in rows
    )
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:20px 0;border:1px solid #dbe3ee;border-radius:8px;overflow:hidden;">{cells}</table>'


def _meeting_card(title: str, rows: list[tuple[str, str | None]], brand: EmailBranding) -> str:
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:20px 0;border:1px solid #dbe3ee;border-left:4px solid {brand.accent_color};border-radius:8px;"><tr><td style="padding:16px 16px 4px;font-family:Arial,sans-serif;font-size:18px;line-height:24px;font-weight:700;color:#0f172a;">{html.escape(_safe_text(title, "Untitled meeting", 250))}</td></tr><tr><td style="padding:0 4px 4px 4px;">{_detail_rows(rows)}</td></tr></table>'


def _button(url: str, label: str, brand: EmailBranding) -> str:
    safe_url = _required_url(url)
    safe_label = html.escape(_safe_text(label, "Open MeetingHQ", 100))
    return f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;"><tr><td bgcolor="{brand.accent_color}" style="border-radius:6px;"><a href="{html.escape(safe_url, quote=True)}" style="display:inline-block;padding:12px 18px;font-family:Arial,sans-serif;font-size:14px;font-weight:700;line-height:20px;color:#ffffff;text-decoration:none;">{safe_label}</a></td></tr></table>'


def _fallback_link(url: str, label: str) -> str:
    safe_url = _required_url(url)
    return f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;line-height:18px;color:#64748b;word-break:break-word;">If the button does not work, use this link to {html.escape(_safe_text(label, "continue", 100)).lower()}: <a href="{html.escape(safe_url, quote=True)}" style="color:#2563eb;">{html.escape(safe_url)}</a></p>'


def _multiline(value: str) -> str:
    return html.escape(_safe_text(value, "", 5000)).replace("\n", "<br>")


def _safe_text(value: object, fallback: str, limit: int) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned[:limit] if cleaned else fallback


def _safe_color(value: object) -> str:
    return value if isinstance(value, str) and _HEX_COLOR.fullmatch(value) else "#2563eb"


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _safe_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if "@" not in candidate or len(candidate) > 320:
        return None
    return candidate


def _required_url(value: object) -> str:
    safe = _safe_url(value)
    if safe is None:
        return "https://app.meetinghq.example"
    return safe
