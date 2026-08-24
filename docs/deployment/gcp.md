# MeetingHQ deployment on Google Cloud Platform

This guide describes the supported path from local development to staging and production.
It intentionally uses infrastructure compatible with MeetingHQ's current shared-filesystem
storage adapter and separates migrations, HTTP serving, and scheduled reminder delivery.

## Production architecture

```text
Internet
  -> Cloud DNS
  -> Global HTTPS Load Balancer + Google-managed certificate + Cloud Armor
       -> web Service (GKE Autopilot, Nginx static React build)
       -> api Service (GKE Autopilot, FastAPI; embedded worker disabled)
            -> Cloud SQL for PostgreSQL (private IP, HA)
            -> Memorystore for Redis (private IP)
            -> Filestore Enterprise shared volume (attachments and generated mail)
       -> reminder CronJob (same API image, `python -m meetinghq_api.worker`)

Artifact Registry <- Cloud Build / CI
Secret Manager -> Workload Identity -> GKE workloads
Cloud Logging / Monitoring / Error Reporting <- application and platform telemetry
```

GKE Autopilot is used rather than Cloud Run because the current storage adapter requires a
shared POSIX filesystem. Cloud Run's writable filesystem is ephemeral and must not be used
for production attachments, avatars, mail, or calendar artifacts. A future GCS storage
adapter can make Cloud Run a viable runtime without changing business modules.

## Required GCP services

- One GCP project per environment (recommended: `meetinghq-staging` and
  `meetinghq-production`).
- Artifact Registry for immutable API and web container images.
- GKE Autopilot regional cluster with Workload Identity.
- Cloud SQL for PostgreSQL 17 using private IP, regional high availability, automated
  backups, point-in-time recovery, deletion protection, and SSL-required connections.
- Memorystore for Redis with private service access.
- Filestore Enterprise mounted read/write by API and worker workloads.
- Secret Manager for database credentials, JWT signing secret, SMTP credentials, and
  bootstrap credentials.
- Cloud DNS, global external Application Load Balancer, Google-managed certificate, and
  Cloud Armor.
- Cloud Logging, Cloud Monitoring, Error Reporting, alert policies, and uptime checks.

## Environment separation

Never share databases, Redis instances, buckets/volumes, secrets, service accounts, or
domains between staging and production. Build a container once, address it by digest, test
that digest in staging, and promote the same digest to production.

Suggested domains:

- Staging: `staging.meetinghq.example`
- Production: `meetinghq.example`

## Identity and secrets

Use Workload Identity; do not distribute service-account key files. Create separate least-
privilege Kubernetes service accounts for migrations, API, worker, and web. Mount secrets
through the Secret Manager CSI driver or synchronize them to namespaced Kubernetes Secrets.

Required production secrets include:

- `MEETINGHQ_DATABASE_URL`
- `MEETINGHQ_REDIS_URL`
- `MEETINGHQ_JWT_SECRET` (random, at least 32 bytes; rotate through a planned session reset)
- `MEETINGHQ_SMTP_USERNAME` and `MEETINGHQ_SMTP_PASSWORD`
- `INITIAL_SUPER_ADMIN_*` values for the first installation only

Never put a secret in `VITE_*`; Vite values are embedded in public browser assets.

## Production configuration

For the first isolated **staging** acceptance environment, set at minimum:

```dotenv
MEETINGHQ_ENVIRONMENT=staging
MEETINGHQ_LOG_LEVEL=INFO
MEETINGHQ_API_CORS_ORIGINS=["https://meetinghq.example"]
MEETINGHQ_TRUSTED_HOSTS=["meetinghq.example"]
MEETINGHQ_WEB_APP_URL=https://meetinghq.example
MEETINGHQ_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/meetinghq?ssl=require
MEETINGHQ_REDIS_URL=redis://REDIS_PRIVATE_IP:6379/0
MEETINGHQ_JWT_SECRET=<secret-manager-reference>
MEETINGHQ_SECURE_COOKIES=true
MEETINGHQ_AUTH_RATE_LIMIT_FAIL_CLOSED=true
MEETINGHQ_STORAGE_PROVIDER=local
MEETINGHQ_LOCAL_STORAGE_PATH=/var/lib/meetinghq/storage
MEETINGHQ_PUBLIC_STORAGE_URL=/api/v1/storage
MEETINGHQ_EMBEDDED_REMINDER_WORKER=false
MEETINGHQ_RUN_MIGRATIONS=false
MEETINGHQ_SMTP_HOST=<transactional-mail-host>
MEETINGHQ_SMTP_PORT=587
MEETINGHQ_SMTP_STARTTLS=true
MEETINGHQ_SMTP_FROM_EMAIL=meetings@meetinghq.example
MEETINGHQ_EMAIL_OUTBOX_PATH=/var/lib/meetinghq/storage/outbox
VITE_API_URL=https://meetinghq.example/api/v1
```

The current local adapter over a shared Filestore mount is acceptable only for isolated
staging acceptance. `MEETINGHQ_ENVIRONMENT=production` intentionally refuses the local
storage provider. A production object-storage adapter (recommended: private GCS with signed,
tenant-scoped retrieval) remains a release blocker and must replace this staging bridge.

The API and worker must mount the same Filestore path at
`/var/lib/meetinghq/storage`. The web workload does not need this mount.

## Container build and registry

Build from the repository root and tag with the immutable commit SHA. Enable vulnerability
scanning in Artifact Registry. Do not deploy mutable `latest` tags.

```bash
docker build -f apps/api/Dockerfile -t REGION-docker.pkg.dev/PROJECT/meetinghq/api:COMMIT .
docker build --build-arg VITE_API_URL=https://meetinghq.example/api/v1 \
  -f apps/web/Dockerfile -t REGION-docker.pkg.dev/PROJECT/meetinghq/web:COMMIT .
```

In production, run a single Kubernetes Job with `MEETINGHQ_RUN_MIGRATIONS=true` before
rolling out API pods. API and worker workloads must set it to `false`; do not start multiple
new API replicas against an unapplied migration.

## Database migration

1. Take an on-demand Cloud SQL backup.
2. Start a Kubernetes Job using the new API image and command `alembic upgrade head`.
3. Wait for success and record the Alembic revision.
4. Run `/api/v1/ready` from the private network.
5. Roll out worker and API workloads only after the migration Job succeeds.

Schema downgrades are not the default rollback strategy. Prefer application rollback with a
backward-compatible migration, then apply a reviewed corrective migration.

## API deployment

- Set `MEETINGHQ_EMBEDDED_REMINDER_WORKER=false`.
- Use a rolling update with `maxUnavailable: 0` and a PodDisruptionBudget.
- Use `/api/v1/health` for liveness and `/api/v1/ready` for readiness.
- Set CPU/memory requests and limits from measured staging load.
- Start with two replicas across zones; use Horizontal Pod Autoscaling on CPU and request
  latency.
- Configure a termination grace period long enough for Uvicorn to finish in-flight requests.
- Keep refresh cookies HTTPS-only and route `/api` and the web origin through the same public
  hostname.

## Reminder worker and scheduler

Production API pods must not run the embedded loop. Create a Kubernetes CronJob that runs:

```bash
python -m meetinghq_api.worker
```

Schedule it every minute, set `concurrencyPolicy: Forbid`, a bounded execution deadline, and
retain failed Job history. Reminder claims use database row locks with `SKIP LOCKED`, so
PostgreSQL workers do not process the same due reminder concurrently. Alert on Job failures
and on reminders remaining in `pending` or `failed` state.

## Networking and HTTPS

- Use private IP for Cloud SQL, Memorystore, and Filestore.
- Permit database and cache traffic only from the GKE workload network.
- Terminate TLS at the global load balancer and redirect HTTP to HTTPS.
- Use a Google-managed certificate and alert before expiration.
- Apply Cloud Armor managed WAF rules and rate limits to authentication endpoints.
- Restrict API documentation in production at the edge if it is not intended for customers.

## SMTP and external delivery

Configure a production transactional email provider, SPF, DKIM, and DMARC. Verify the
sending domain and monitor bounces and complaint rates. A local outbox is a development
transport only: System Health reports unconfigured SMTP as a production recommendation, and
external invitees will not receive mail until SMTP passes a real connection test.

## Monitoring and logging

- Ingest structured JSON application logs into Cloud Logging.
- Create log-based metrics for authentication failures, account lockouts, HTTP 5xx,
  invitation failures, reminder failures, worker exceptions, and migration failures.
- Monitor API latency/error rate/saturation, Cloud SQL connections/CPU/storage/replication,
  Redis memory/evictions, Filestore capacity/latency, pod restarts, CronJob age, and load
  balancer health.
- Create external uptime checks for `/api/v1/health`, `/api/v1/ready`, and the login page.
- Route critical alerts to an owned on-call channel and document acknowledgement/escalation.

## Backup and restore

Enable Cloud SQL automated backups and point-in-time recovery. Schedule Filestore snapshots
and export critical snapshots to a separate protected project or region. Retain backups
according to organization policy.

At least quarterly, restore Cloud SQL and Filestore into an isolated recovery environment,
apply the exact production image digest, run migrations if required, verify login and a full
meeting/invitation/RSVP flow, and record recovery point and recovery time evidence. A backup
that has not been restored is not considered verified.

## Scaling

- Scale API replicas horizontally only after the database connection budget is configured.
- Keep one scheduled reminder execution at a time initially; increase concurrency only after
  delivery idempotency and provider rate limits are validated under load.
- Monitor N+1 queries and pagination before increasing replica counts.
- Filestore is shared state; monitor inode/capacity growth and migrate to a dedicated GCS
  adapter before storage throughput becomes the limiting resource.

## Rollback

1. Stop the rollout when health or smoke tests fail.
2. Route workloads back to the last verified image digest.
3. Do not automatically downgrade the database.
4. Disable newly introduced feature flags when that safely isolates the change.
5. Restore data only for confirmed corruption, using the documented recovery procedure.
6. Preserve logs, audit records, release digest, migration revision, and incident timeline.

## Release checklist

- [ ] Ruff, Black, MyPy, backend tests, ESLint, TypeScript, Vitest, Playwright, and production
      builds pass for the promoted commit.
- [ ] Container vulnerability scan has no unaccepted critical findings.
- [ ] Staging uses the exact production image digests.
- [ ] Migration Job succeeds and the Alembic revision is recorded.
- [ ] API liveness/readiness, login, refresh, direct URL refresh, and logout pass.
- [ ] Create/edit/reschedule/cancel meeting, participant invitation, email+ICS delivery, RSVP,
      calendar visibility, and reminders pass.
- [ ] Super Admin and normal Member authorization/tenant-isolation tests pass.
- [ ] SMTP, Cloud SQL, Redis, worker, scheduler, and Filestore report healthy.
- [ ] HTTPS, secure cookies, CORS, Cloud Armor, DNS, and certificates are verified.
- [ ] Backup and restore evidence is current.
- [ ] Dashboards, alerts, runbooks, rollback owner, and on-call contacts are confirmed.

## Known production blockers

This document is a deployment path, not a production-readiness claim. Before the first live
deployment, MeetingHQ still requires a rehearsed GCP deployment, external SMTP delivery
evidence, load/performance results, restored-backup evidence, automated accessibility and
browser regression results, and an independent security review.
