# Internal Mail

Internal Mail is MeetingHQ's organization-scoped mailbox at `/mail`. It supports
Inbox, Drafts, Sent, Trash, custom folders, labels, search, templates,
signatures, rich-text composition, attachments, conversation threads, stars,
read receipts, and delivery status.

## Delivery model

- Messages addressed to an active user in the sender's organization are copied
  directly into that user's Inbox.
- Recipient lookup always includes the authenticated organization identifier.
  A mailbox cannot address or discover an account in another organization
  through internal delivery.
- External recipients require an enabled, configured SMTP provider in
  Integration Center. Provider credentials never live in the Mail module.
- A provider failure is persisted as a failed delivery with a bounded error
  message; it is never reported as a successful send.

Tenant SMTP configuration is shared with transactional platform email. Environment SMTP
settings remain an installation fallback only; a tenant configuration saved through
Integration Center is authoritative for external mailbox delivery.

## Security

Rich HTML is sanitized on the server with an explicit tag, attribute, and URL
scheme allowlist before it is stored or delivered. Attachments use signed,
organization-scoped storage URLs and are returned as downloads with MIME
sniffing disabled. Mail records, folders, templates, signatures, and
attachments carry the organization boundary, and repository queries require
both organization and mailbox owner identifiers.

## Administration

Configure external delivery at **Administration → Integration Center → Email → SMTP**.
Complete the Authentication and Configuration sections, save the provider, and
run **Test Connection**. Audit Center records configuration and mail mutations
without storing or exposing credentials.
