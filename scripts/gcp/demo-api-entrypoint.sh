#!/usr/bin/env sh
# Public synthetic demo only: the API and the evaluation worker share one container.
# Schema and synthetic data come from the nextrm-db-setup job (scripts/gcp/db-setup.sh), never from startup.
set -eu
: "${DATABASE_URL:?Set DATABASE_URL}"
case "$DATABASE_URL" in postgresql*) ;; *) echo 'DATABASE_URL must be a PostgreSQL URL' >&2; exit 1 ;; esac
[ "${ENVIRONMENT:-}" = "development" ] || { echo 'demo entrypoint requires the synthetic development environment' >&2; exit 1; }
cd /app
DB_POOL_SIZE=2 DB_MAX_OVERFLOW=0 python services/worker/main.py &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
