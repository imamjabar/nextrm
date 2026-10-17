#!/usr/bin/env sh
# Cloud Run Job entrypoint: explicit schema migration, then the repeat-safe synthetic seed. Never run at API startup.
# --reset first drops every object owned by the application role: synthetic demo data only, see reset-demo-data.sh.
set -eu
: "${DATABASE_URL:?Set DATABASE_URL}"
[ "${ENVIRONMENT:-}" = "development" ] || { echo 'synthetic seeding requires the development environment' >&2; exit 1; }
cd /app
if [ "${1:-}" = "--reset" ]; then
  python - <<'PY'
import os
from sqlalchemy import create_engine, text
with create_engine(os.environ['DATABASE_URL']).begin() as connection:
    connection.execute(text('DROP OWNED BY CURRENT_USER CASCADE'))
print('Dropped every object owned by the application role.')
PY
fi
alembic upgrade head
python scripts/seed_demo.py
