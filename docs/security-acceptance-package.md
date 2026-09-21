# OfficeFlow security acceptance package

This package makes the internal security verification reproducible. It supports the canonical
[production-readiness audit](production-readiness-audit.md); it is not an independent assessment,
penetration-test report, or release approval.

## Scope and environment

- Record the branch and immutable commit before execution.
- Supported release runtimes are Python 3.13 and Node 22; CI/staging results are authoritative.
- Use an isolated database, Redis namespace, storage root, and test tenants. Disable or redirect
  outbound email. Never use production credentials or business data.
- Retain sanitized command results, Playwright JSON, dependency reports, and reviewer sign-off.

## Reproducible internal verification

Run from the repository root:

```powershell
cd apps/api
..\..\.venv\Scripts\python.exe -m ruff check src tests
..\..\.venv\Scripts\python.exe -m black --check src tests
..\..\.venv\Scripts\python.exe -m mypy --strict src
..\..\.venv\Scripts\python.exe -m pytest
..\..\.venv\Scripts\python.exe -m pip_audit

cd ..\web
npm run format:check
npm run lint
npx tsc -b --pretty false
npm run test -- --run
npm run build
npm audit --omit=dev
npx playwright test --reporter=list,json
```

The authenticated suite must include `voucher-lifecycle.spec.ts`, `payroll-management.spec.ts`,
`tasks-daily-activities.spec.ts`, and `project-management.spec.ts`. Review evidence for:

| Control | Required evidence |
| --- | --- |
| Tenant isolation | Cross-tenant resources and attachments return 404; lists contain no foreign rows |
| RBAC and segregation | Staff, manager, accountant, auditor and payroll roles plus unauthorized-role negatives |
| Authentication/session | Login, refresh/replay, password change, direct navigation, logout/expiry and production fail-closed tests |
| Finance/payroll confidentiality | Lifecycle, ledger, idempotency, payslip ownership and cross-tenant denials |
| Attachment authorization | Authorized download, unrelated/foreign denial and filename/MIME/path validation |
| API configuration | CORS, trusted hosts, HTTPS URL, Redis/rate-limit, signing-key and storage validation |
| Dependencies | Current `pip-audit` and production `npm audit` output or a signed exception |

## Independent acceptance handoff

Provide the assessor with the final commit SHA, architecture/data-flow diagram, API schema, role and
permission matrix, staging URL, isolated test tenants, non-production accounts, dependency/SBOM
output, configuration checklist, log access, and rules of engagement. At minimum the independent
party should test OWASP ASVS/API risks, tenant boundary bypass, IDOR/BOLA, privilege escalation,
session/token replay and revocation, upload/download abuse, finance/payroll disclosure, rate-limit
bypass, WebSocket authorization, SSRF/injection, security headers, and secret exposure.

The independent gate remains **BLOCKED** until an authorized assessor supplies a dated report,
severity-ranked findings, retest evidence for release-blocking findings, and explicit acceptance by
the product/security owner. Internal tests must never be described as independent certification.
