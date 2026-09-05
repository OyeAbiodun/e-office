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

## Employee directory and departments

The existing organization-owned `User` is the employee record; MeetingHQ does not
create a second identity system for employment data. Each employee can have an
organization-unique employee number, department, manager, employment type and
status, employment dates, workspace, team, and role assignments. Departments are
organization units with optional managers and active/inactive lifecycle status.

Employment changes are effective-dated. Hiring, job-context updates, role changes,
termination, and rehire actions create an `employment_history` record with before/
after values, the actor, effective date, and optional reason. Termination suspends
the account by default; rehire restores active account access. All IDs are resolved
inside the authenticated organization, including manager, department, role, and
history lookups, so another tenant cannot discover or assign its records.

`GET /api/v1/employees` provides a paginated, server-filtered directory by search,
department, manager, role, account status, employment status/type, and location.
`GET /api/v1/employees/{user_id}/history` returns the tenant-scoped history. The
Users screen uses these APIs for the employee editor, lifecycle actions, and history
timeline.

Profiles expose name, avatar, timezone, language, and notification preferences. Avatar
bytes pass through the `StorageProvider` interface; local storage is the default adapter
and validates type, size, key containment, and opaque filenames.

Important actions publish structured `Activity` values to an independent publisher.
The database adapter stores them transactionally for dashboard timelines and future
notifications, reports, analytics, webhooks, and AI consumers.
