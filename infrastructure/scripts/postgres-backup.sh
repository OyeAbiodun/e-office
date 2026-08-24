#!/bin/sh
set -eu

umask 077
: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${MEETINGHQ_BACKUP_DIRECTORY:?MEETINGHQ_BACKUP_DIRECTORY is required}"

mkdir -p "$MEETINGHQ_BACKUP_DIRECTORY"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$MEETINGHQ_BACKUP_DIRECTORY/meetinghq-${PGDATABASE}-${timestamp}.dump"

pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="$target" \
  "$PGDATABASE"
pg_restore --list "$target" >/dev/null
sha256sum "$target" >"$target.sha256"

printf '%s\n' "Backup created and structurally verified: $target"
