# MeetingHQ

**Schedule. Meet. Collaborate.**

MeetingHQ is an AI-powered digital workplace. This repository contains its production
foundation: an asynchronous FastAPI API, a React application, tenant-aware
authentication, calendars, meeting lifecycle, collaboration, Internal Mail,
administration centers, infrastructure, quality gates, and CI.

This repository is under release-candidate hardening. Passing local checks is not a
production-readiness claim; promotion requires the staging, SMTP, PostgreSQL migration,
backup-restore, performance, and security evidence in the
[GCP release checklist](docs/deployment/gcp.md#release-checklist).

## Architecture

```text
apps/api   FastAPI composition root, module boundaries, and infrastructure adapters
apps/web   React shell, route tree, providers, layout, and feature folders
packages   Future independently versioned shared packages
infrastructure   Runtime entry points and edge proxy configuration
docs       Operational and developer documentation
```

The backend is a modular monolith. Each feature will own its domain model, use cases,
transport adapters, and persistence adapters. Cross-module interactions should use
explicit application contracts or domain events rather than importing another module's
internals. This preserves clean boundaries while avoiding distributed-system overhead
before scale or team topology requires it.

The web application mirrors those feature boundaries. Global code is limited to the
composition root, layout, provider configuration, and tightly scoped primitives.

Calendar architecture is documented in [docs/calendar.md](docs/calendar.md) and
[docs/scheduling-engine.md](docs/scheduling-engine.md).

## Prerequisites

- Docker Desktop with Compose v2 (recommended)
- Or Python 3.13, Node.js 22+, PostgreSQL 17, and Redis 8 for native development

## Quick start

```bash
cd meetinghq
cp .env.example .env
docker compose up --build
```

## First-run bootstrap

After migrations, API startup checks whether any organization exists. On a completely
empty installation it atomically creates the initial organization, default workspace,
verified Super Admin, explicit organization ownership, and owner access to the default
workspace. The Super Admin role receives the complete permission catalog.

Configure these required variables before the first startup:

```dotenv
INITIAL_SUPER_ADMIN_EMAIL=textabi12@gmail.com
INITIAL_SUPER_ADMIN_PASSWORD=ChangeMe123!
INITIAL_SUPER_ADMIN_FIRST_NAME=Abiodun
INITIAL_SUPER_ADMIN_LAST_NAME=
INITIAL_ORGANIZATION_NAME=MeetingHQ
INITIAL_WORKSPACE_NAME=Main Workspace
```

Log in with the configured email and password. MeetingHQ resolves the account's
organization, workspace, roles, and permissions automatically; users never enter an
organization slug.

The initializer is permanent infrastructure, not demo data. Once any organization exists,
subsequent startups perform no bootstrap writes and never overwrite organizations, users,
roles, or workspaces.

Open:

- Web application: http://localhost:5173
- API health: http://localhost:8000/api/v1/health
- API documentation: http://localhost:8000/api/docs
- Optional unified gateway: `docker compose --profile gateway up --build`, then
  http://localhost:8080

The default credentials in `.env.example` are for local development only.

Meeting invitations, password resets, and temporary credentials use SMTP when
`MEETINGHQ_SMTP_HOST` is configured. Without SMTP, development installs write real
RFC-compliant `.eml` messages to `apps/api/storage/outbox`; meeting invitations include
an ICS calendar attachment. The reminder worker delivers the configured 15-minute,
30-minute, 1-hour, and 24-hour reminders while the API is running.

Internal Mail is available at `/mail`. Organization-to-organization-user messages
are delivered directly into tenant-isolated mailboxes. External delivery is enabled
only after an administrator configures SMTP in Integration Center. Provider
credentials are encrypted before persistence, never returned by the API, and can be
validated with the provider's Test Connection workflow. See
[Internal Mail](docs/internal-mail.md).

## Developer commands

```bash
make install
make lint
make test
make build
```

On Windows, run the equivalent commands from the `Makefile` directly if `make` is not
installed.

## Health model

- `GET /api/v1/health` is a liveness probe and has no external dependencies.
- `GET /api/v1/ready` checks PostgreSQL and Redis and returns `503` when either is
  unavailable.

## Authentication

Milestone 02 provides organization registration, password authentication, rotating
refresh sessions, password recovery, email verification, session management, audit
logging, and permission-based endpoint protection. See
[Authentication and identity](docs/authentication.md) for security and API details.

## Organization management

Organizations own workspaces; workspaces own teams; teams own explicit memberships.
All management APIs enforce tenant filters and centralized RBAC permissions. Important
state transitions publish durable activity events used by the real dashboard.

- [Organizations and users](docs/organizations.md)
- [Workspaces and teams](docs/workspaces.md)

## Documentation

- [Local development](docs/local-development.md)
- [GCP deployment](docs/deployment/gcp.md)
- [Backup, restore, and disaster recovery](docs/disaster-recovery.md)
- [Production-readiness audit](docs/production-readiness-audit.md)
- [Environment variables](docs/environment.md)
- [Administration Centers](docs/administration-centers.md)
- [Internal Mail](docs/internal-mail.md)
- [Meeting architecture](docs/meeting-architecture.md)
- [Meeting lifecycle](docs/meeting-lifecycle.md)
- [Meeting API](docs/meeting-api.md)
- [Chat architecture](docs/chat-architecture.md)
- [Realtime architecture](docs/realtime-architecture.md)
- [WebSocket events](docs/websocket-events.md)
- [Chat API](docs/chat-api.md)
- Interactive API documentation is generated from FastAPI at `/api/docs`.

## Product boundary

Identity, organization management, calendar scheduling, meetings, collaboration,
notifications, Internal Mail, and administration foundations are implemented.
Provider-specific OAuth synchronization, AI, billing, and reports remain gated until
their corresponding production implementation is complete.
