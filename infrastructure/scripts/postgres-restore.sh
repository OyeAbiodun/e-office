#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${MEETINGHQ_RESTORE_FILE:?MEETINGHQ_RESTORE_FILE is required}"
: "${MEETINGHQ_RESTORE_CONFIRM:?MEETINGHQ_RESTORE_CONFIRM is required}"

expected="RESTORE_${PGDATABASE}"
if [ "$MEETINGHQ_RESTORE_CONFIRM" != "$expected" ]; then
  printf '%s\n' "Restore refused: MEETINGHQ_RESTORE_CONFIRM must equal $expected" >&2
  exit 2
fi
if [ ! -f "$MEETINGHQ_RESTORE_FILE" ]; then
  printf '%s\n' "Restore refused: backup file does not exist" >&2
  exit 2
fi
if [ -f "$MEETINGHQ_RESTORE_FILE.sha256" ]; then
  sha256sum --check "$MEETINGHQ_RESTORE_FILE.sha256"
fi

pg_restore \
  --exit-on-error \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --dbname="$PGDATABASE" \
  "$MEETINGHQ_RESTORE_FILE"

printf '%s\n' "Restore completed. Run migrations and the recovery acceptance checklist."
