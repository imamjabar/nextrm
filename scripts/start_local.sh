#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"
API_PORT="${NEXTRM_API_PORT:-8000}"
WEB_PORT="${NEXTRM_WEB_PORT:-3000}"
for port in "$API_PORT" "$WEB_PORT"; do
  if command -v lsof >/dev/null && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop your previous server or set NEXTRM_API_PORT / NEXTRM_WEB_PORT." >&2
    exit 1
  fi
done
if [[ ! -x .venv/bin/python || ! -d apps/web/node_modules/next ]]; then
  echo 'Install Python/Node dependencies using README before startup.' >&2; exit 1
fi
./scripts/dev_db.sh start
export DATABASE_URL="$(./scripts/dev_db.sh url)"
export ENVIRONMENT=development
export NEXTRM_SEED_CUSTOMER_ACTIVITY=true
export AUTH_PROVIDER=synthetic_demo
export NEXTRM_AUTH_PROVIDER=synthetic_demo
export NEXTRM_AI_PROVIDER="${NEXTRM_AI_PROVIDER:-vertex}"
if [[ "$NEXTRM_AI_PROVIDER" == "vertex" ]]; then
  export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}}"
  export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-asia-southeast1}"
  export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}"
  export GEMINI_THINKING_LEVEL="${GEMINI_THINKING_LEVEL:-minimal}"
  export GEMINI_THINKING_LEVEL_FALLBACK="${GEMINI_THINKING_LEVEL_FALLBACK:-low}"
  if [[ -z "$GOOGLE_CLOUD_PROJECT" ]]; then
    echo 'Live Gemini needs GOOGLE_CLOUD_PROJECT (or gcloud config project) and `gcloud auth application-default login`. For an offline SIMULATED run, set NEXTRM_AI_PROVIDER=local explicitly.' >&2; exit 1
  fi
fi
export PYTHONPATH="$PROJECT_ROOT/services/api"
mkdir -p runtime/backups
./scripts/dev_db.sh backup "runtime/backups/before-start-$(date +%Y%m%d-%H%M%S).dump"
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_demo.py
.venv/bin/python scripts/generate_rm_types.py
WEB_MODE="${NEXTRM_WEB_MODE:-production}"
DEV_BUNDLER="${NEXTRM_DEV_BUNDLER:-webpack}"
if [[ "$WEB_MODE" != "production" && "$DEV_BUNDLER" != "webpack" && "$DEV_BUNDLER" != "turbo" ]]; then
  echo 'NEXTRM_DEV_BUNDLER must be webpack or turbo.' >&2; exit 1
fi
if [[ "$WEB_MODE" == "production" ]]; then
  if [[ ! -f apps/web/.next/BUILD_ID ]] || find apps/web/src apps/web/next.config.mjs apps/web/package.json -type f -newer apps/web/.next/BUILD_ID -print -quit 2>/dev/null | read -r _; then
    echo 'Building the current frontend once for fast local page navigation…'
    NEXTRM_BUILD_DIR=.next npm --prefix apps/web run build
  fi
  mkdir -p apps/web/.next/standalone/.next
  cp -R apps/web/.next/static apps/web/.next/standalone/.next/
  cp -R apps/web/public apps/web/.next/standalone/
fi
PIDS=()
cleanup(){
 trap - EXIT INT TERM
 for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
 # Bound shutdown even when an HTTP keep-alive delays Next.js termination.
 for attempt in {1..20}; do
  running=false
  for pid in "${PIDS[@]}"; do if kill -0 "$pid" 2>/dev/null; then running=true; fi; done
  if [[ "$running" == false ]]; then break; fi
  sleep 0.1
 done
 for pid in "${PIDS[@]}"; do if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi; done
 wait || true
}
trap cleanup EXIT INT TERM
API_ARGS=(app.main:app --host 127.0.0.1 --port "$API_PORT")
if [[ "$WEB_MODE" != "production" && "${NEXTRM_API_RELOAD:-false}" == "true" ]]; then
  API_ARGS+=(--reload --reload-delay 0.3 --reload-dir services/api/app)
fi
.venv/bin/uvicorn "${API_ARGS[@]}" >runtime/api.log 2>&1 & PIDS+=("$!")
.venv/bin/python services/worker/main.py >runtime/worker.log 2>&1 & PIDS+=("$!")
if [[ "$WEB_MODE" == "production" ]]; then
 (cd apps/web && exec env PORT="$WEB_PORT" HOSTNAME=127.0.0.1 NEXTRM_DEMO_MODE=true API_INTERNAL_URL="http://127.0.0.1:$API_PORT" node .next/standalone/server.js) >runtime/web.log 2>&1 & PIDS+=("$!")
else
 DEV_ARGS=(dev -H 127.0.0.1 -p "$WEB_PORT")
 DEV_BUILD_DIR=.next-local
 if [[ "$DEV_BUNDLER" == "turbo" ]]; then DEV_ARGS+=(--turbo); DEV_BUILD_DIR=.next-turbo; fi
 (cd apps/web && exec env NEXTRM_BUILD_DIR="$DEV_BUILD_DIR" NEXTRM_DEMO_MODE=true API_INTERNAL_URL="http://127.0.0.1:$API_PORT" ./node_modules/.bin/next "${DEV_ARGS[@]}") >runtime/web.log 2>&1 & PIDS+=("$!")
fi
echo 'Starting the API, worker and frontend; checking readiness…'
NEXTRM_READY_API="$API_PORT" NEXTRM_READY_WEB="$WEB_PORT" .venv/bin/python - <<'PYREADY'
import json,os,time,urllib.request
urls=[f"http://127.0.0.1:{os.environ['NEXTRM_READY_API']}/health",f"http://127.0.0.1:{os.environ['NEXTRM_READY_WEB']}/api/config"]
deadline=time.monotonic()+45
while time.monotonic()<deadline:
 try:
  for url in urls:
   with urllib.request.urlopen(url,timeout=2) as response: json.load(response)
  break
 except (OSError,ValueError):time.sleep(.25)
else:raise SystemExit('Local startup readiness timed out. Inspect runtime logs; no successful fallback is assumed.')
PYREADY
echo "NextRM demo accounts: http://localhost:$WEB_PORT/demo"
echo "RM workspace: http://localhost:$WEB_PORT/workspace"
echo "Customer app: http://localhost:$WEB_PORT/customer/chat"
echo "Logs: runtime/api.log, runtime/worker.log, runtime/web.log"
echo "Selected provider: $NEXTRM_AI_PROVIDER. Local is SIMULATED; Google modes never fall back silently. Ctrl+C stops all three processes."
if [[ "$WEB_MODE" != "production" ]]; then
  echo "Development: $DEV_BUNDLER bundler; API reload ${NEXTRM_API_RELOAD:-false}. Edits do not rerun migrations, seeding or production builds."
fi
while true; do
 for pid in "${PIDS[@]}"; do if ! kill -0 "$pid" 2>/dev/null; then echo 'A local process stopped. Inspect runtime logs; no successful fallback is assumed.' >&2; exit 1; fi; done
 sleep 1
done
