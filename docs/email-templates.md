# Transactional email templates

MeetingHQ sends product email through one typed, centrally versioned template registry.
The registry is the presentation layer for transactional messages; it does not open a
second SMTP path or store provider credentials.

## Covered messages

- Password reset and email verification
- Organization invitation and temporary-password handoff
- Meeting invitation, update, cancellation, and reminder
- SMTP test email

Every render supplies both HTML and plain text. Meeting messages retain their existing
ICS attachments and stable delivery behaviour. Each outbound message is tagged with its
template key and version; delivery audits record that metadata without recording secrets.

## Branding and safety

The template base uses MeetingHQ's responsive, table-based email layout with inline CSS
and a system-font stack. It takes the organization display name, safe logo URL, and safe
brand accent colour from the organization configuration. Invalid colours and non-HTTP(S)
URLs fall back to safe MeetingHQ defaults.

Template variables are escaped before rendering. The service accepts structured template
data rather than arbitrary administrator-supplied HTML, so rich content cannot turn into
an executable email template. Password-reset links are delivered only as action/fallback
URLs; reset tokens are not placed in application logs or delivery audit metadata.

## Reviewing templates

Super Admins can open **Administration → Integration Center → Email → SMTP → Email
preview** and select any supported template. The preview uses representative safe sample
data, runs in an isolated iframe, does not send a message, and never exposes SMTP
credentials.

Preview is intentionally not a general HTML-template editor. A future customization
feature should retain typed variables, tenant isolation, preview sanitization, audit
events, and the shared `MeetingEmailSender` transport.

## Delivery semantics

The SMTP Integration Center remains the authoritative place to configure and test an
email provider. A successful test reports only provider acceptance; it is not evidence of
external inbox delivery. Real delivery evidence requires a configured provider and a
controlled mailbox acceptance test. Local outbox files are development evidence only.
