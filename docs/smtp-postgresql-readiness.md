# SMTP and PostgreSQL readiness checkpoint

Last verified: 2026-09-01

This checkpoint records the local evidence for the SMTP administration and PostgreSQL
production-target pass. It deliberately distinguishes implementation evidence, SMTP server
acceptance, and final external mailbox delivery. Credentials are not recorded here.

## 2026-08-30 SMTP acceptance-gate correction

The outbound transport was hardened without claiming external delivery. MeetingHQ-generated
messages now include an RFC 5322 `Date` header and preserve one stable `Message-ID` across
bounded retries. Meeting invitations, updates, and cancellations carry a durable delivery-row
identifier, while their ICS payloads advance `SEQUENCE` from creation through reschedule and
cancellation. Internal Mail uses the same stable identity and configured sender metadata.

Accepted meeting deliveries, reminders, SMTP test requests/results, and password-reset requests
now generate immutable audit evidence containing only safe metadata such as recipient domain.
Failed SMTP test-email attempts return a typed failed result instead of raising before the audit
transaction can commit. The Integration Center displays that result as an error, so transport
rejection can no longer appear as success.

Migration `0030_calendar_delivery_sequence` adds the persisted meeting sequence. A metadata-only
successor widens Alembic's default 32-character revision column and adopts the canonical revision
identifier `0030_email_calendar_delivery_integrity`. This preserves compatibility with the
already-applied short identifier while allowing the requested descriptive revision to be the
live migration head.

The preserved PostgreSQL 17.6 cluster now runs natively on configuration-driven port `5433`,
which was verified free and outside every Windows reserved range. WinNAT, Docker/WSL networking,
and Office Platform ports `5173/8000` were not touched.

Before startup, `5433` had no listener and did not appear in any Windows excluded TCP range.
The existing data directory was reused without restore or reinitialization. The API, Alembic,
worker, scheduler, readiness checks, and System Health all consume the same
`MEETINGHQ_DATABASE_URL`; backup and restore scripts continue to use the standard PostgreSQL
environment, including `PGPORT`. Container and production defaults were left unchanged.

No SMTP hostname, username, or password is configured in the isolated installation. Therefore
provider connection, controlled-mailbox receipt, external invitation/update/cancellation/reminder,
password-reset delivery, and Internal Mail delivery remain **not run**, not passed. Secrets were
not printed, logged, screenshotted, traced, or added to source control.

## SMTP administration

- The authoritative UI is **Administration → Integration Center → Email → SMTP**. It owns
  connection, authentication, sender, delivery, enablement, validation, test-email, and
  operational-history controls. Platform Management controls capability availability only.
- Explicit `integrations.view`, `integrations.manage`, and `integrations.test` permissions
  govern read, mutation, and validation operations. The bootstrap Super Admin permission
  catalog is refreshed idempotently at startup.
- Tenant SMTP configuration is encrypted through the application secret vault before it is
  persisted. API responses never contain the password. A blank password preserves the
  current secret, a new value rotates it, and the UI exposes only a masked stored state.
- Configuration create/update, enable/disable, secret rotation, connection test, accepted
  test email, and failed test email produce immutable audit events with safe metadata.
- Integration Center connection tests, its test-email action, meeting lifecycle messages,
  reminders, authentication mail, notifications, and external Internal Mail all delegate to
  the same `MeetingEmailSender` transport. SMTP acceptance is reported as `Sent`; the product
  does not claim final mailbox delivery without provider or mailbox evidence.
- System Health reports configured/enabled state, requirement classification, validation
  time, latency, and recorded failures. SMTP is required in staging/production and recommended
  locally.

The current isolated installation has no SMTP provider configured. Its truthful state is
`not_configured`, outbound messages use the local outbox, and external delivery is therefore
not proven. Real test-email, invitation, reschedule, cancellation, and reminder delivery remain
a release blocker until an operator supplies a real provider and controlled recipient mailbox.

## PostgreSQL runtime

| Item | Verified result |
| --- | --- |
| Server | PostgreSQL 17.6 |
| Isolation | Dedicated `meetinghq` role/database on `127.0.0.1:5433`; Office Platform ports `5173/8000` were not stopped or reconfigured |
| Redis | MeetingHQ-only runtime on `127.0.0.1:6380` |
| API / web | `127.0.0.1:8001` / `127.0.0.1:5174` |
| Last PostgreSQL-verified migration | `0030_email_calendar_delivery_integrity` |
| Current source migration head | `0030_email_calendar_delivery_integrity` |
| Clean migration | Empty PostgreSQL database migrated from `0001` through `0029` |
| Drift | `alembic check`: `No new upgrade operations detected` on clean, restored, and active schemas |
| Database timezone | UTC |
| Bootstrap cardinality | One organization (`meetinghq`), one default workspace, one bootstrap user, and one Super Admin assignment after restart |
| Schema | 76 tables, 138 primary-key constraints, 174 foreign keys, 87 unique constraints, 310 indexes after `0029` |
| PostgreSQL types | 41 JSONB columns and 133 timestamp-with-time-zone columns |
| Index validity | Zero invalid or unready indexes |
| Pool | Size 10, max overflow 20, 30-second acquisition timeout, 1,800-second recycle |

Forward migration `0028_postgres_alignment` resolves PostgreSQL-specific model drift without
rewriting migration history. It aligns JSONB, nullability, foreign keys, indexes, and unique
constraints. Migration `0029_tenant_query_indexes` adds tenant-first cursor indexes for
meeting, notification, and audit timelines plus the notification unread-count path. Query-plan
inspection confirmed those indexes and the user email unique index are selectable for their
critical lookups.

The Compose PostgreSQL service now uses UTC. Externally managed installations must set the
MeetingHQ database timezone to UTC as documented in [environment.md](./environment.md).

## Recovery and failure evidence

- A custom-format `pg_dump` of the isolated database was created with restrictive local
  handling, its catalog was parsed by `pg_restore --list`, and a SHA-256 digest was recorded.
- The dump restored into a new isolated database with organization/user counts preserved,
  migration revision `0029`, zero invalid indexes, and a clean Alembic drift check.
- During an earlier controlled outage of only the isolated PostgreSQL service,
  `/api/v1/ready` returned `503`.
  After restart it recovered to `200` without restarting the API.
- A 100-request concurrent readiness probe returned 100 successes. PostgreSQL showed the
  configured 10 idle application pool connections plus the active inspection connection.
- Reference backup and guarded restore procedures are documented in
  [disaster-recovery.md](./disaster-recovery.md) and implemented by the scripts under
  `infrastructure/scripts/`; they take credentials only from the execution environment.

## PostgreSQL meeting lifecycle

The running API completed a real transaction journey against PostgreSQL `5433`: the Super
Admin created a participant, the participant rotated a temporary password, and the organizer
created a meeting with that participant. The participant received one unread invitation,
transitioned through Tentative, Declined, and Accepted, and the organizer observed Accepted.
The embedded worker generated the due reminder, rescheduling updated the meeting, and
cancellation propagated to the participant's single synchronized calendar event.

The final notification set contained invitation, reminder, update, and cancellation events.
The immutable audit set contained meeting creation, invitation, all attendee transitions,
reschedule/update, and cancellation. Persistence inspection showed email and ICS invitation,
update, and cancellation delivery records, two sent reminder records, and an exact meeting ↔
calendar timestamp match. Five local-outbox messages were generated; MIME parsing proved three
calendar attachments with two `REQUEST` methods and one `CANCEL` method. This proves the shared
local delivery architecture and ICS semantics, not external SMTP mailbox delivery.

## Authenticated browser acceptance

The isolated browser and Playwright runs used web `127.0.0.1:5174`, API
`127.0.0.1:8001`, PostgreSQL `127.0.0.1:5433`, and Redis `127.0.0.1:6380`.
Office Platform ports `5173/8000` were not stopped or reconfigured. Bootstrap credentials
were loaded from the ignored local environment and were not recorded in output, screenshots,
traces, or this document.

- Interactive login reached the live Dashboard. Hard refresh and a second tab retained the
  authenticated session.
- Dashboard, Profile, Users, Roles, Platform Management, Integration Center, System Health,
  Audit, Notifications, Mail, Calendar, Meetings, Chat, Members, Teams, Help, and
  Administration all opened without a login redirect or permission error.
- A refresh-safe `/profile/security/mfa` deep link retained its hierarchical Profile Center →
  Security & MFA breadcrumbs. Browser back navigation, command-palette navigation, and a new
  authenticated tab are now permanent desktop/mobile Playwright assertions.
- The browser lifecycle creates a participant, rotates the required temporary password,
  creates a meeting, verifies invitation and reminder notifications, exercises Tentative →
  Declined → Accepted, verifies organizer state, reschedules, validates the synchronized
  calendar event, cancels, and verifies immutable creation/reschedule/cancellation audit
  actions. The unread count is asserted before and after marking the reminder read.

Three acceptance defects were corrected:

1. Port `5174` browser preflights were rejected because the isolated API launch used a
   misspelled CORS override while `.env` allowed only `5173`. The runtime now uses the correct
   `MEETINGHQ_API_CORS_ORIGINS` setting.
2. A successful meeting transition could be overwritten by an immediate pre-commit detail
   refetch, leaving cancellation visually `scheduled`. The mutation response now anchors the
   detail query cache after related data refreshes.
3. An aborted cookie-refresh response could make a rapid navigation/reload look like malicious
   token replay and revoke the session family. CSRF-protected browser cookies now have a
   bounded 10-second retry grace. Explicit refresh-token replay remains rejected.

## Quality gates

| Gate | Result |
| --- | --- |
| Ruff | Passed |
| Black full check | Passed after formatting two pre-existing Alembic files |
| MyPy strict | Passed; 158 source files |
| Pytest | Passed; 90 tests, 79% measured coverage |
| Prettier | Passed |
| ESLint | Passed |
| TypeScript | Passed |
| Vitest | Passed; 28 tests in 13 files |
| Production frontend build | Passed; 5,767 modules transformed |
| npm audit | Passed; zero vulnerabilities |
| Python dependency consistency | `pip check` passed |
| Docker Compose validation | Not run; Docker CLI is not installed on this host |
| Playwright authenticated acceptance | Passed; 12 tests across desktop Chromium and mobile Chromium |

The backend suite emits non-failing Python 3.14/aiosqlite cleanup warnings in its SQLite test
harness. They do not occur in the running asyncpg PostgreSQL runtime but remain technical debt
for the test environment.

## Current decision

Classification remains **Development Hardened**. PostgreSQL migration, schema, runtime,
pool, failure-recovery, local backup/restore, authenticated browser, and desktop/mobile
Playwright gates pass.

Release Candidate remains blocked by:

- real SMTP provider configuration plus delivery of test, invitation, update, cancellation,
  and reminder messages to a controlled external mailbox;
- resolving the current local System Health score of 90 (`degraded`) for storage/disk/memory
  thresholds and validating required production services in a production-like environment;
- container/Compose verification on a host with Docker available;
- the staging security, load, WebSocket soak, backup automation, TLS/domain/certificate, and
  regional recovery gates in the main readiness ledger.

Optional unconfigured providers are reported truthfully and are not treated as successful.
Production Ready remains out of scope until those external and environment-level gates pass.
