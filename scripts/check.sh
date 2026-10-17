#!/usr/bin/env bash
# Runs only the checks affected by edits since the last passing run (stamp: runtime/.check-stamp), in parallel.
# Usage: scripts/check.sh [--all]    --all runs everything, including the production build and the real HTTP validation.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runtime
STAMP=runtime/.check-stamp
MARK=runtime/.check-start
LOGS="$(mktemp -d)"
ALL=0
[[ "${1:-}" == "--all" ]] && ALL=1
touch "$MARK"
START=$SECONDS

changed() {
  [[ "$ALL" == 1 || ! -f "$STAMP" ]] && return 0
  [[ -n "$(find "$@" -type f -newer "$STAMP" -not -path '*/node_modules/*' -not -path '*/.next*' -not -path '*/__pycache__/*' -not -name '*.pyc' 2>/dev/null | head -n 1)" ]]
}
bg() {
  local name="$1"; shift
  ( trap 'echo $? >"$LOGS/$name.rc"' EXIT; "$@" >"$LOGS/$name.log" 2>&1 ) &
}
report() {
  local failed=0 rc name
  for rc in "$LOGS"/*.rc; do
    [[ -e "$rc" ]] || continue
    name="$(basename "$rc" .rc)"
    if [[ "$(cat "$rc")" == 0 ]]; then echo "pass  $name"; else failed=1; echo "FAIL  $name"; tail -40 "$LOGS/$name.log"; fi
    rm -f "$rc"
  done
  return "$failed"
}
api_checks() { ./.venv/bin/pytest -q --no-header -p no:warnings; }
web_checks() {
  if changed services/api/app; then ./.venv/bin/python scripts/generate_rm_types.py >/dev/null; fi
  npm --prefix apps/web run typecheck
  for test in scripts/test_*.mjs; do [[ "$test" == *proxy_smoke* ]] || node "$test"; done
}

ran=0
if changed services/api data requirements.txt requirements-dev.txt alembic.ini pytest.ini scripts/devdb.py scripts/dev_db.sh; then ran=1; bg api-tests api_checks; fi
if changed services/api/app apps/web/src apps/web/package.json apps/web/package-lock.json apps/web/tsconfig.json apps/web/next.config.mjs scripts; then ran=1; bg web-checks web_checks; fi
wait
if ! report; then rm -f "$MARK"; echo "checks failed after $((SECONDS - START))s" >&2; exit 1; fi
if [[ "$ALL" == 1 ]]; then
  npm --prefix apps/web run build >"$LOGS/build.log" 2>&1 || { tail -40 "$LOGS/build.log"; rm -f "$MARK"; exit 1; }
  echo "pass  production build"
  ./.venv/bin/python scripts/validate_account_http.py
fi
mv "$MARK" "$STAMP"
if [[ "$ran" == 0 ]]; then echo "nothing changed since the last passing run (--all forces a full run)"; fi
echo "all selected checks passed in $((SECONDS - START))s"
