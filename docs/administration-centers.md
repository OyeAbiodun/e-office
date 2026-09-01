# Administration Centers

MeetingHQ exposes Super Admin-only operational modules under the dynamic
Administration menu.

## Platform Management

Platform Management is the governance plane. It controls whether capabilities
and provider adapters are available, visible, in maintenance, or released to a
particular stage. Its dashboard provides live platform health, capability,
configuration, navigation, scheduler, worker, licensing, and module views.

Provider cards in External Connections intentionally show only:

- Enabled or disabled state
- Configuration and health state
- A link to configure the provider in Integration Center

Disabling a capability requires confirmation and retains existing data.
Successful changes are recorded in the Audit Center.

## Integration Center

Integration Center is the external-provider configuration boundary. It supports
mail, calendar, storage, AI, meeting, productivity, and developer providers.
Platform Management must enable a provider before MeetingHQ uses it, while
Integration Center stores its connection settings and credentials.

Every provider exposes the same administration contract: Overview,
Authentication, Permissions, Configuration, Health, Logs, Synchronization,
Advanced, Audit, and Test Connection. Tests perform a bounded live network and
authentication probe and persist only health metadata.

Secret configurations are encrypted at rest before they are committed and are
never returned by either the Integration Center or the generic Platform
Management configuration API. Installations upgrading from the earlier
plaintext format seal existing provider records during application startup.
Provider responses expose only a `configured` boolean, health, availability,
and last-updated time. The installation JWT secret is currently the root of the
local credential-encryption key, so it must be supplied from a secret manager
and kept stable during restore or migration.

SMTP has a dedicated production workflow under **Integration Center → Email → SMTP**.
It exposes connection, authentication, sender, and delivery settings that the backend
actually supports. Passwords are write-only: the API returns only a masked configured
state, and a blank password during an edit preserves the sealed value. STARTTLS and
implicit SSL/TLS are supported; unencrypted SMTP requires an explicit insecure-transport
acknowledgement. **Test Connection** validates the live network/TLS/authentication path,
while **Send Test Email** submits through the same transport used by meetings, identity,
notifications, reminders, and external Internal Mail. An `accepted` result means the SMTP
server accepted the message; it does not claim final inbox delivery. Configuration,
validation, test submission, secret rotation, enable/disable changes, latency, revision,
and safe diagnostics are recorded without credentials.

## Roles and permissions

Role policies are collapsed by default and expose permissions in searchable
resource groups. Administrators can expand or collapse all groups, enable or
disable an entire group, review permission descriptions and dependencies, and
save a role only after confirming the tenant-wide access change.

The same permission policy drives both API authorization and dynamic menu
visibility.

## System Health

`GET /api/v1/system-health` returns a bounded live snapshot of:

- API, database, Redis, worker, and reminder scheduler status
- SMTP, storage, WebSocket, and configured integration status
- Pending, delivered, and failed invitation/reminder jobs
- Runtime version, environment, uptime, health score, warnings, and recommendations

Checks never return provider credentials or tenant content. A missing optional
provider is reported as `not_configured`; an unreachable configured provider is
reported as `degraded` or `unavailable`. The dashboard refreshes automatically
every 30 seconds and supports an explicit refresh.

## Audit Center

Audit records are append-only and organization-scoped. The Audit Center supports:

- Search by actor, action, and resource
- Category and action filtering
- Cursor and offset pagination at the API layer
- Event detail inspection with request, network, browser, and device context
- CSV export of the current tenant and filter scope

Authenticated create, update, archive, disable, and delete operations are
captured by the mutation audit safety net in addition to module-specific domain
audits. Audit records cannot be updated or deleted through the application API.

## Feedback and destructive actions

All API mutations use the shared feedback layer. Successful operations display
an accessible toast; failures surface the server message; pending work displays
a global progress indicator. Delete, disable, and archive requests are
intercepted by the shared confirmation service before the API call is sent.
