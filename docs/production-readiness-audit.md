# OfficeFlow Production Readiness Audit

Last verified: 2026-09-20

Branch: `feature/pre-release-hardening`
Baseline: `71d86804b8421d2b2f55800604fb98bae827998e`

This is the canonical release-evidence ledger. Credentials, tokens, personal data, salary data,
and provider secrets are intentionally excluded.

## Release decision

**Classification: DEVELOPMENT HARDENED**

Application-controlled static gates, unit/integration tests, database restore, authenticated
desktop/mobile journeys, a bounded API load probe, and a bounded WebSocket soak pass. OfficeFlow
is not a Release Candidate because container execution, authorized GCP staging, production TLS and
domain configuration, automated staging recovery, full security acceptance, real-device push, and
a production-like multi-user load test remain blocked or untested.

## Verified baseline

| Item | Result |
| --- | --- |
| Product | OfficeFlow (MeetingHQ compatibility identifiers retained internally) |
| Alembic | One head/current revision: `a4f5d6e7c801`; `alembic check` reports no drift |
| Local runtimes | Python 3.14.6; Node 20.19.2; PostgreSQL 17.6 |
| Supported build runtimes | Python 3.13 and Node 22 in CI/project metadata |
| Final acceptance services | Web 5174, API 8001, PostgreSQL 5432, Redis 6379; Office Platform ports 5173/8000 were not touched |
| Backend | 168 passed; 83% measured coverage |
| Frontend | 24 files, 81 tests passed |
| Browser | 48 cases exercised in one aggregate run (41 passed initially); all 7 failures were corrected and passed in focused desktop/mobile reruns |
| Dependencies | `pip-audit`: no known vulnerabilities after upgrading local pip tooling to 26.2.1; `npm audit --omit=dev`: 0 |
| SMTP | Disabled and unconfigured in the final restored acceptance database; no external message was sent |
| System Health | Degraded, score 80: storage/disk pressure and four delivery jobs require attention |

The developer host does not match supported production toolchains. Passing local results under
Python 3.14 and Node 20 are useful evidence, but CI/staging must remain authoritative for Python
3.13 and Node 22.

## Release-readiness matrix

| Area | Classification | Evidence / reason |
| --- | --- | --- |
| Repository, migration chain, schema drift | PASS | Clean baseline audited; one migration head; current DB and models agree |
| Backend lint, format, typing, tests | PASS | Ruff, Black, strict MyPy (198 source files), 168 Pytest tests, 83% coverage |
| Frontend lint, format, typing, tests, build | PASS | Prettier, ESLint, TypeScript, 81 Vitest tests, Vite production build |
| Authentication/session/RBAC | PASS | Automated replay/refresh/permission tests plus authenticated direct navigation and refresh journeys |
| Employees, departments, tasks, projects | PASS | Backend suite and role-separated desktop/mobile acceptance; tenant-negative task/project paths pass |
| Meetings, calendar, chat | PASS | Full meeting lifecycle, RSVP, reminder, reschedule, cancel, calendar, action-item link; authenticated WebSocket tests |
| Leave | PASS | Entitlement, approval/rejection, insufficient balance, admin adjustment, calendar and mobile acceptance |
| Payroll confidentiality and lifecycle | PASS | Preparer/reviewer/approver/accountant/employee separation, posting, payslip security, mobile and tenant isolation |
| Reporting and Help Centre | PASS | Review workflow, automation controls, project reports, exports, content/search/support/admin browser flows |
| Voucher/Finance backend integrity | PASS | Full backend suite covers lifecycle, SoD, idempotency, ledger, reversal and tenant boundaries |
| Voucher full role-separated browser rerun | NOT TESTED | Current Playwright inventory has finance navigation but no complete Staff/Manager/Accountant/Auditor voucher spec |
| Tenant isolation | PASS | Explicit automated negatives across major modules and runtime browser negatives for tasks, projects, attachments and payroll |
| File authorization | PASS | MIME/filename/path/tenant tests plus authenticated task/project download browser proofs |
| Database backup and restore | PASS | Custom-format backup restored to a separate temporary DB; revision and representative counts verified |
| API bounded load | PASS | 10 concurrent workers, 200 authenticated reads, 0 failures; p50 411.8 ms, p95 1,024.1 ms, max 2,552.3 ms |
| WebSocket bounded soak | PASS | 10 authenticated sockets held 60 seconds and reconnect verified, on desktop and mobile projects |
| Production-like multi-user mixed load | NOT TESTED | The bounded probe used one authenticated identity and read-only requests |
| SMTP connection | PASS | Provider handshake/authentication succeeded; no external message was sent in this sprint |
| Email deliverability | BLOCKED | Previously accepted Gmail delivery landed in Spam; DNS/reputation/provider remediation remains external work |
| Browser push real device | BLOCKED | Local VAPID keys, HTTPS and device/browser permission prerequisites are absent |
| System Health | FAIL | Required application services are reachable, but storage is 93.5% used (6.5% free) and four delivery jobs need attention |
| Docker execution | BLOCKED | Docker is not installed on this host; Compose was reviewed but not executed |
| GCP staging | BLOCKED | No deployment authorization or staging credentials were supplied |
| TLS/domain/certificate monitoring | BLOCKED | Production ingress and domain are not provisioned in this environment |
| Production secrets/configuration | BLOCKED | Fail-closed validation exists; real production secrets and managed services require staging provisioning |

## Defects corrected in this pass

1. Daily Activity rejected/accepted future dates using UTC day boundaries instead of the user's
   local calendar day. The service now uses the local application date consistently.
2. A Leave integration test used fixed dates that became historical; fixtures now remain valid
   relative to the execution date.
3. Meeting reminders coupled in-app notification creation to SMTP success. In-app and browser-push
   routing now occur independently on the first attempt; SMTP retries cannot duplicate them.
4. Browser acceptance had stale MeetingHQ branding, heading, tab-role, report-action, and balance
   expectations. Tests now target current OfficeFlow accessible semantics and actual ledger math.
5. Frontend Prettier drift across 57 files was normalized.
6. Chat/WebSocket acceptance assumed pre-existing conversation data. The tests now provision a
   tenant-scoped workspace conversation when the authenticated tenant is empty.
7. Reports, Help, and direct-navigation checks used empty-state-incompatible or ambiguous selectors
   and a short lazy-route wait. They now assert accessible, deterministic page semantics.

## Performance and resilience evidence

Representative single-request local probes before the bounded run ranged from 51 ms (Help search)
to 254 ms (Dashboard). The bounded run used 10 concurrent workers and 200 authenticated, read-only
requests across Dashboard, Tasks, Projects, Users, Finance, Payroll, Leave, Reports, and Help. It
completed in 10.679 seconds with no HTTP failures. These are development-host measurements, not an
SLA or production capacity claim.

The real-time soak opened 10 authenticated chat sockets concurrently, held them for 60 seconds,
verified all remained open, closed them, and verified a fresh reconnect. It passed in both desktop
and 390px mobile Playwright projects. Longer token-expiry, worker-restart, and production-ingress
soaks remain staging gates.

## Database recovery evidence

A PostgreSQL custom-format backup (2,015,610 bytes) was created outside the repository, restored to
a unique temporary database, and removed after verification. The restored database contained
migration `a4f5d6e7c801`, 37 organizations, 241 users, and 48 Help articles. The active database was
not overwritten during that rehearsal. For final browser acceptance, the available local database
was backed up (274,295 bytes) and upgraded forward from `0028_postgres_alignment` to
`a4f5d6e7c801`; its existing organization and user remained intact and `alembic check` reported no
drift. Object-storage recovery and automated scheduled backups remain untested.

## Security and operations notes

- Production configuration fails closed for default signing keys, insecure cookies, missing Redis,
  fail-open rate limiting, non-HTTPS public URLs/CORS, wildcard trusted hosts, and local production
  storage.
- Security middleware supplies CSP, clickjacking protection, MIME sniffing protection, referrer and
  permissions policies, and production/staging HSTS.
- Repository scans found no private keys or AWS access-key patterns. Provider secrets remain
  encrypted/write-only and were not printed.
- The final backend suite emitted 45 non-failing warnings from the existing structlog
  `format_exc_info` configuration. CI's supported Python 3.13 remains the release authority;
  the warning should be removed in a later logging-maintenance change.
- Low host disk capacity must be remediated before container builds, extended load tests, or local
  backup retention. Do not delete user data merely to improve the score.

## Operational documentation

- [GCP deployment guide](deployment/gcp.md)
- [Environment configuration](environment.md)
- [Migration and operator runbook](meetinghq-runbook.md)
- [Backup, restore, and rollback](disaster-recovery.md)
- [Incident response](incident-response.md)
- [Known SMTP/PostgreSQL operational history](smtp-postgresql-readiness.md)

## Gates required before promotion

1. Add and pass the full role-separated Voucher browser lifecycle in the current suite.
2. Run CI with Python 3.13 and Node 22 on the final commit.
3. Execute Docker image/Compose validation on a Docker-capable host.
4. Deploy to an authorized GCP staging environment and verify managed PostgreSQL, Redis, storage,
   worker, scheduler, HTTPS, domain, certificates, logs, metrics, alerts, and secret rotation.
5. Run a production-like multi-user mixed read/write load test and longer WebSocket/token-expiry soak.
6. Complete independent security/tenant-isolation acceptance and penetration testing.
7. Configure automated staging backups and prove database plus object-storage recovery and rollback.
8. Resolve host storage pressure and investigate the four queued delivery failures.
9. Configure VAPID and prove real-device browser push over HTTPS.
10. Remediate email deliverability (SPF/DKIM/DMARC/reputation as applicable) and reconfirm Inbox placement.

OfficeFlow is **not ready to merge into `MHQ`** until the product owner accepts the documented
external gates and the Voucher browser gap is closed.
