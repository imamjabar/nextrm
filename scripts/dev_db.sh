#!/usr/bin/env bash
# Project-local PostgreSQL for development, tests and validation scripts.
# Listens on 127.0.0.1 only with trust auth; durability is off so seeding and test cloning stay fast.
# Usage: scripts/dev_db.sh start|stop|status|url|reset|gc
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${NEXTRM_PGDATA:-$ROOT/runtime/postgres}"
PORT="${NEXTRM_PGPORT:-54417}"
DB="${NEXTRM_PGDATABASE:-nextrm}"

find_bin() {
  local configured="${NEXTRM_PG_BIN:-}" on_path="" dir
  on_path="$(command -v pg_ctl 2>/dev/null || true)"
  [[ -n "$on_path" ]] && on_path="$(dirname "$on_path")"
  for dir in "$configured" "$on_path" \
    /Applications/Postgres.app/Contents/Versions/latest/bin \
    /opt/homebrew/opt/postgresql@17/bin /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@17/bin \
    /usr/lib/postgresql/17/bin /usr/lib/postgresql/16/bin; do
    if [[ -n "$dir" && -x "$dir/pg_ctl" ]]; then echo "$dir"; return; fi
  done
  echo 'PostgreSQL binaries not found. Install Postgres.app or `brew install postgresql@17`, or set NEXTRM_PG_BIN.' >&2
  exit 1
}
BIN="$(find_bin)"
psql_admin() { "$BIN/psql" -X -q -h 127.0.0.1 -p "$PORT" -d postgres -v ON_ERROR_STOP=1 "$@"; }
accepting() { "$BIN/pg_isready" -q -h 127.0.0.1 -p "$PORT"; }
owned_running() { "$BIN/pg_ctl" -D "$DATA" status >/dev/null 2>&1; }

start() {
  if [[ ! -f "$DATA/PG_VERSION" ]]; then
    mkdir -p "$DATA"
    "$BIN/initdb" -D "$DATA" -U "$(id -un)" --auth=trust --encoding=UTF8 --locale=en_US.UTF-8 >/dev/null
    cat >>"$DATA/postgresql.conf" <<CONF
listen_addresses = '127.0.0.1'
unix_socket_directories = ''
timezone = 'UTC'
max_connections = 200
shared_buffers = 256MB
fsync = off
synchronous_commit = off
full_page_writes = off
CONF
  fi
  if ! owned_running; then
    if accepting; then
      echo "Port $PORT is used by another PostgreSQL server; set NEXTRM_PGPORT to a free port." >&2
      exit 1
    fi
    mkdir -p "$ROOT/runtime"
    "$BIN/pg_ctl" -D "$DATA" -o "-p $PORT" -l "$ROOT/runtime/postgres.log" -w -t 60 start >/dev/null
  fi
  if [[ "$(psql_admin -tAc "select 1 from pg_database where datname='$DB'")" != 1 ]]; then
    psql_admin -c "create database \"$DB\""
  fi
}

case "${1:-}" in
  start) start ;;
  stop) "$BIN/pg_ctl" -D "$DATA" -m fast -w stop >/dev/null ;;
  status) owned_running && echo "running on 127.0.0.1:$PORT" || { echo 'stopped'; exit 1; } ;;
  url) echo "postgresql+psycopg://127.0.0.1:$PORT/$DB" ;;
  reset) start; psql_admin -c "drop database if exists \"$DB\" with (force)" -c "create database \"$DB\"" ;;
  backup)
    start
    if [[ "$(psql_admin -d "$DB" -tAc "select count(*) from information_schema.tables where table_schema='public'")" -gt 0 ]]; then
      "$BIN/pg_dump" -Fc -h 127.0.0.1 -p "$PORT" -f "$2" "$DB" && echo "Existing local database backed up to $2 before explicit additive migration."
    fi ;;
  gc)
    start
    psql_admin -tAc "select datname from pg_database where datname ~ '^nextrm_(t|tpl|v)_'" | while read -r name; do
      [[ -n "$name" ]] && psql_admin -c "drop database if exists \"$name\" with (force)"
    done ;;
  *) echo 'Usage: scripts/dev_db.sh start|stop|status|url|reset|backup <file>|gc' >&2; exit 2 ;;
esac
