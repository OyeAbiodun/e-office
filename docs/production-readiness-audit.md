# Production Readiness Audit

Last verified: 2026-08-24

The SMTP/PostgreSQL production-target checkpoint, including isolated PostgreSQL 17.6,
migration head `0029`, backup/restore evidence, current quality gates, and the truthful external
SMTP blocker, is recorded in [smtp-postgresql-readiness.md](./smtp-postgresql-readiness.md).

This document is the release evidence ledger for the Profile Center completion and production-readiness pass. `Green` means the behavior has direct local automated or browser evidence. `Yellow` means the implementation works locally but still needs deployment, operational, or broader acceptance evidence. `Red` means the required external production environment has not yet been provisioned or rehearsed.

## Executive status

| Area | Status | Evidence | Remaining work |
| --- | --- | --- | --- |
| Authentication and session continuity | Yellow | Email/password login, protected navigation, hard refresh, and a second authenticated tab were verified locally. | Re-run the same journey in staging behind the production ingress, domain, cookies, and TLS termination. |
| Profile Center | Yellow | Profile navigation, personal data, avatar controls, security history, password flow, MFA enrollment UI, sessions, preferences, connected accounts, organization context, breadcrumbs, and pagination are implemented and locally verified. | Validate MFA with a real authenticator in staging and complete screen-reader acceptance testing. |
| Notifications | Yellow | Notification inbox, unread count, live WebSocket updates, preferences, and route access are implemented. A connection-pool exhaustion defect was fixed and the reconnect/accessibility paths pass E2E. | Prove long-duration reconnect behavior and external browser notification delivery in staging. |
| Provider and integration truthfulness | Yellow | Provider registry, official UI branding, configured-versus-validated status, connection testing, audit metadata, and health integration are implemented. | Configure and validate production credentials for each enabled provider. |
| System Health | Yellow | Required, recommended, optional, configured, unavailable, and healthy semantics are separated; history and recommendations are exposed. | Connect production observability and prove alerts, history retention, and incident operations. |
| Automated quality gates | Green | Ruff, Black, strict MyPy, 67 backend tests, ESLint, TypeScript, 25 frontend tests, production build, 10 Playwright journeys, and npm audit pass. | Resolve the documented Python 3.14/aiosqlite cleanup warnings and standardize local Node on 22. |
| GCP deployment readiness | Red | A concrete deployment, migration, backup, restore, scaling, monitoring, and rollback runbook exists. | Provision a staging project and execute deployment, restore, failover, rollback, load, and security rehearsals. |

## Browser acceptance evidence

The local application was verified with the bootstrap Super Admin account. Credentials are intentionally not repeated in this document.

- Login succeeded and returned the expected Super Admin identity.
- Dashboard loaded live widgets and activity data.
- The global account menu exposed Profile, Security & MFA, Notification Preferences, and Account Preferences.
- `/profile/security` rendered the hierarchical breadcrumb `MeetingHQ / Profile Center / Security & MFA`.
- A hard refresh retained the authenticated session.
- A second browser tab opened `/profile/notifications` without requiring another login.
- Session pagination rendered `Showing 1–8 of 189 active sessions` and limited row actions to the current page.
- The authenticated route sweep covered Dashboard, Calendar, Meetings, Chat, Mail, Notifications, Users, Members, Roles, Platform Management, System Health, Integration Center, Help Center, Profile, and Administration.
- A live API probe confirmed the bootstrap user has the Super Admin role and the dashboard returned 10 widgets and 10 recent activity records.

Screenshots:

- [Profile Center verification](./profile-center-verification.png)
- [System Health verification](./system-health-verification.png)

## Defect corrected during verification

Repeated authenticated navigation originally exhausted the SQLAlchemy connection pool. The notification WebSocket kept one database session open for its entire lifetime, and closed browser tabs could leave polling loops alive because the server never consumed a receive event. The API then failed with `QueuePool limit of size 5 overflow 10 reached` and protected pages appeared to stall.

The WebSocket now authenticates in a short-lived session, opens a fresh short-lived session only for each unread-count query, consumes incoming frames with a bounded timeout so disconnects are observed, and exits cleanly on disconnect. The complete desktop/mobile Playwright suite passed after this correction.

## Quality-gate evidence

| Gate | Result |
| --- | --- |
| Ruff | Passed |
| Black check | Passed; 198 files unchanged |
| MyPy strict | Passed; 157 source files checked |
| Pytest | Passed; 67 tests, 78% measured coverage |
| ESLint | Passed |
| TypeScript | Passed |
| Vitest | Passed; 25 tests |
| Frontend production build | Passed; 5,765 modules transformed |
| Playwright | Passed; 10 desktop/mobile journeys |
| npm audit | Passed; 0 vulnerabilities |

The Playwright suite covers desktop and mobile command navigation, calendar create/edit/delete, internal mail sending, login shell behavior, and serious axe accessibility checks for Dashboard and Chat.

## Health-score interpretation

The local health score is currently **80**, not 100. Thirteen of fifteen required components pass. The two truthful local failures are disk pressure (93.7% used) and low remaining storage (6.3% free). SMTP is recommended but unconfigured. Optional unconfigured services—including external integrations, SSL/domain/certificate checks, backups, cron, search, AI, calendar providers, and file providers—do not lower the score.

A score of 100 is therefore possible only when every required component passes; optional unconfigured services no longer create a permanent penalty.

## Remaining release blockers and risks

1. Provision the documented GCP staging architecture and run the complete deployment runbook.
2. Configure a real SMTP provider and verify invitation, reset, notification, retry, bounce, and failure workflows end to end.
3. Execute Cloud SQL backup/restore, migration rollback, application rollback, worker retry, WebSocket reconnect, and regional failure rehearsals.
4. Run load and soak tests for API, WebSocket, database pool, Redis, scheduler, and notification worker behavior.
5. Complete penetration testing, dependency/container scanning, IAM review, secret-rotation rehearsal, and tenant-isolation review across all modules.
6. Complete manual acceptance for a non-admin member, denied permissions, cross-tenant access attempts, keyboard-only use, screen readers, high contrast, tablet, and supported mobile browsers.
7. Resolve four non-failing Python 3.14/aiosqlite SQLAlchemy cleanup warnings observed after the backend test run.
8. Standardize developer and CI Node.js on version 22; the current local machine uses 20.19.2 and emits an engine warning even though all frontend gates pass.

## Release decision

The Profile Center completion pass and all local quality gates are complete. MeetingHQ must **not** be presented as fully production-ready yet: the external staging deployment, real provider delivery, recovery rehearsals, load/security evidence, and broader manual acceptance above remain required release gates.
