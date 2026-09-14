# Reporting & Management Intelligence

MeetingHQ reporting creates tenant-scoped, historically stable report snapshots from canonical
work data. It does not copy tasks, activities, projects, meetings, leave, finance, vouchers, or
payroll into a second operational system.

## Workflow

The default employee workflow is `Generated Draft → Draft → Submitted → Final`. Employees can
edit narrative context while authoritative source metrics remain locked. A manager may return a
submitted report with a required reason; the employee can correct, version, and resubmit it.

Organization policy defaults to review-before-send enabled and automatic submission disabled.
When automatic submission is explicitly enabled, the shared worker submits scheduled drafts after
the configured deadline. Automated actions have no impersonated user actor and are recorded in
report history, activity events, and the immutable audit trail.

Final reports retain the source snapshot, source references, policy snapshot, narrative version,
submission mode, reviewer, and workflow timestamps. Later changes to canonical records do not
silently rewrite final reports.

## Sources and privacy

One batched source adapter combines, as applicable:

- tasks and daily activities;
- projects, updates, milestones, risks, and issues;
- meetings, decisions, and action items;
- aggregated leave context;
- aggregated voucher, finance, and payroll indicators.

Every source query is organization-scoped. Employee, team, department, project, and management
visibility is enforced by the API. Sensitive management indicators are included only when the
requesting user also holds the corresponding source permission. Report permissions never override
leave, voucher, finance, payroll, project, or tenant privacy.

## Scheduling

The existing application worker processes report generation, deadline reminders, and automatic
submission. Scheduling uses the organization's configured IANA timezone and a durable generation
key made from organization, subject, report type, and reporting period. Repeated worker runs reuse
the existing scheduled report.

Daily, weekly, and monthly schedules can be enabled independently. Manual report generation also
supports custom periods up to 366 days.

## API

All endpoints are under `/api/v1/reports`:

- `GET/PUT /policy` — read or update organization reporting policy;
- `GET /dashboard` — permission-aware operational intelligence;
- `GET /source-preview` — preview the signed-in employee's canonical work sources;
- `POST /` — generate an employee, team, department, project, or management report;
- `GET /` — server-side search, filters, and pagination;
- `GET/PATCH /{id}` — read a report or edit permitted narrative fields;
- `POST /{id}/submit` — owner submission;
- `POST /{id}/review` — manager acceptance or return for correction;
- `GET /{id}/export?format=pdf|csv|xlsx` — authorized export;
- `POST /scheduler/run` — administrator-only idempotent manual scheduler trigger.

The UI is available at `/reports`, is generated from the database-driven navigation registry, and
includes My Reports, manager review, report generation, management intelligence, policy controls,
print styling, and PDF/CSV/XLSX exports.

## Permissions

Reporting permissions appear in Role Management under **Reporting & Intelligence**:

- `reports.view_own`, `reports.create_own`, `reports.submit_own`;
- `reports.view_team`, `reports.review_team`;
- `reports.view_department`, `reports.view_management`;
- `reports.generate`, `reports.export`, `reports.manage_policy`.

Project reports continue to require project visibility and `projects.generate_reports` where
appropriate.
