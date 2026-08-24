# Backup, restore, and disaster recovery

This is the operational procedure for MeetingHQ data recovery. It is a preparation
artifact, not evidence that recovery has been rehearsed. A release cannot be called
production-ready until a restore has succeeded in an isolated environment and its RPO/RTO
evidence is recorded.

## Protected data sets

- PostgreSQL is the system of record for tenants, identities, meetings, RSVP state,
  notifications, configuration, and audit records.
- The configured object-storage volume contains avatars, attachments, mail objects, and
  meeting artifacts. Database and object snapshots must be taken from a consistent recovery
  window.
- Redis is disposable coordination/cache state and is rebuilt; it is not restored as a
  source of record.
- Secret Manager values, image digests, migration revision, DNS/TLS configuration, and
  infrastructure definitions require separately protected version history.

## PostgreSQL backup

The reference script is
[`infrastructure/scripts/postgres-backup.sh`](../infrastructure/scripts/postgres-backup.sh).
Supply `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGPASSWORD` through the deployment secret
boundary and an encrypted `MEETINGHQ_BACKUP_DIRECTORY`. The script creates a custom-format
dump, validates its catalog, creates a SHA-256 checksum, and uses restrictive file
permissions. Never upload an unencrypted dump to a public or shared location.

For GCP, Cloud SQL automated backups and point-in-time recovery are primary. Retain regular
logical exports in a separate protected project/region according to the approved retention
policy. Alert on missed backups and verify restore eligibility, not only job completion.

## Object storage

Snapshot the production volume/bucket with versioning and retention lock where policy
requires it. Preserve object keys and metadata. Encrypt at rest and in transit; restrict
restore and delete permissions to the recovery role. Align the snapshot timestamp with the
database recovery point and record both identifiers.

## Isolated restore rehearsal

1. Open a recovery record with owner, target RPO/RTO, source backup IDs, application image
   digest, and Alembic revision.
2. Provision a new isolated database, Redis instance, storage volume, secrets, and hostname.
   Never restore over staging or production for a rehearsal.
3. Set `MEETINGHQ_RESTORE_FILE` and the explicit destructive confirmation
   `MEETINGHQ_RESTORE_CONFIRM=RESTORE_<database>`, then run
   [`infrastructure/scripts/postgres-restore.sh`](../infrastructure/scripts/postgres-restore.sh).
4. Restore the matching object snapshot and verify object counts/checksums.
5. Run `alembic current`, apply reviewed forward migrations, and start the exact recorded
   image digest with outbound email disabled or redirected to a recovery sink.
6. Verify organization/user counts, tenant isolation, login, avatar retrieval, attachments,
   meeting creation, invitation/ICS generation, RSVP, reschedule, cancellation, calendars,
   reminders, mail, and audit history.
7. Record achieved RPO/RTO, discrepancies, logs, and approver sign-off; then destroy the
   isolated recovery environment under change control.

## Rollback

Prefer application rollback to the previous immutable image when the new schema remains
backward compatible. Do not automatically run Alembic downgrades in production. For an
incompatible or corrupting change, stop writes, preserve evidence, and choose a reviewed
forward corrective migration or point-in-time recovery. Data restore is a last-resort
incident action and requires an explicit recovery point and business approval.

## Initial policy targets

- Daily backups retained 35 days, monthly copies retained 13 months, subject to the final
  organization compliance policy.
- Quarterly isolated restore rehearsal and after every material storage/migration change.
- Target RPO: 15 minutes with PITR. Target RTO: 4 hours. These are objectives until measured
  during rehearsal.
