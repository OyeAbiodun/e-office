#!/bin/sh
set -eu

if [ "${MEETINGHQ_RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi
exec "$@"
