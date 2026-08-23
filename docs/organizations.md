# Organizations and users

Organizations are MeetingHQ tenant roots. Every management query includes the
authenticated user's organization identifier; object identifiers alone never authorize
cross-tenant access.

Organization profiles support name, logo reference, lifecycle status, timezone,
country, language, brand color, business hours, week start, meeting defaults, password
policy, session timeout, and theme. Deletion is a reversible soft-delete operation.

Users can be invited, activated, deactivated, suspended, removed, or restored.
Invitations use hashed 256-bit tokens with explicit pending, accepted, expired, and
cancelled states. Resending rotates the secret and extends expiry. Acceptance creates
the user and role assignment transactionally.

Profiles expose name, avatar, timezone, language, and notification preferences. Avatar
bytes pass through the `StorageProvider` interface; local storage is the default adapter
and validates type, size, key containment, and opaque filenames.

Important actions publish structured `Activity` values to an independent publisher.
The database adapter stores them transactionally for dashboard timelines and future
notifications, reports, analytics, webhooks, and AI consumers.

