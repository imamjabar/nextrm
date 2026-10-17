#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export NEXTRM_WEB_MODE=dev
export NEXTRM_DEV_BUNDLER="${NEXTRM_DEV_BUNDLER:-turbo}"
export NEXTRM_API_RELOAD=true
exec "$PROJECT_ROOT/scripts/start_local.sh"
