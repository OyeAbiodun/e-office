# OfficeFlow Incident Response Guide

## Purpose

Use this runbook for security, availability, data-integrity, privacy, finance, payroll, or tenant
isolation incidents. Never include credentials, tokens, salary details, medical documents, or raw
provider secrets in incident tickets or chat.

## First response

1. Declare an incident owner, severity, start time, affected environment, and communication channel.
2. Preserve logs, request correlation IDs, audit records, deployment revision, migration revision,
   and provider status before changing state.
3. Contain the smallest affected surface. Disable a feature/provider through supported configuration
   instead of deleting data or stopping unrelated services.
4. For suspected tenant leakage, financial duplication, payroll exposure, or credential compromise,
   suspend the affected workflow and escalate immediately.
5. Do not rotate credentials, roll back migrations, restore databases, or issue compensating finance
   entries without an approved recovery plan and a verified recovery point.

## Diagnosis

- Review `/api/v1/health`, System Health, structured application logs, failed job counts, integration
  audit history, immutable Audit Center events, database/Redis availability, and storage capacity.
- Correlate by timestamp, organization, request ID, resource ID, deployment SHA, and actor. Keep
  tenant data segregated in all evidence.
- Distinguish application failure, provider rejection, invalid configuration, capacity pressure,
  security event, and user error.

## Recovery

- Follow [disaster-recovery.md](disaster-recovery.md) for backup, restore, and rollback.
- Verify migrations before application traffic resumes.
- Re-run the affected workflow, authorization negatives, idempotency checks, audit checks, and health
  probes. For finance/payroll, reconcile ledgers before reopening writes.
- Record every manual remediation and compensating action in the incident timeline.

## Closure

Document impact, root cause, containment, recovery evidence, data/privacy assessment, notifications,
follow-up owner, and due date. Add regression coverage for application-controlled defects. Close only
after monitoring is stable and affected owners approve recovery.
