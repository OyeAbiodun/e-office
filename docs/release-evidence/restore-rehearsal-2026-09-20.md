# Database restore rehearsal attempt — 2026-09-20

- Source: verified PostgreSQL custom-format backup
  `officeflow-pre-release-20260919221426.dump` (2,015,610 bytes), stored outside the repository.
- Backup catalog: readable; 1,310 TOC entries; gzip custom-format archive; source database
  `meetinghq`.
- Intended target: a uniquely named `officeflow_restore_gate_<timestamp>` database, never the
  active acceptance database.
- Result: **BLOCKED before restore**. The live PostgreSQL service is on port 5432, while the ignored
  local `.env` still names retired port 5433. After selecting the verified live port, the only
  supplied application role (`meetinghq`) reported `rolcreatedb=false` and `rolsuper=false`, and
  PostgreSQL rejected isolated database creation with `permission denied to create database`.
- Data changed: none. No target database was created, no restore was started, and the active
  acceptance database was not modified.
- Exact prerequisite: a database-administrator-approved temporary database created for the
  rehearsal, or temporary `CREATEDB` capability/administrator execution limited to the isolated
  restore operation. Host-wide database privileges were not changed without authorization.
- Prior evidence: the canonical readiness ledger retains the earlier successful isolated restore
  (revision `a4f5d6e7c801`, 37 organizations, 241 users, 48 Help articles) as historical PASS
  evidence. This attempt does not replace it with a new PASS.
