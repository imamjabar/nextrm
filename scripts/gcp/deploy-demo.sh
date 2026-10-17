#!/usr/bin/env bash
# Deploys the PUBLIC SYNTHETIC DEMO: public web + private API on Cloud Run, Gemini on Vertex AI, data in Cloud SQL for PostgreSQL.
# Images are tagged by content hash: unchanged services are neither rebuilt nor re-migrated, and the API and web
# pipelines (build, then deploy) run in parallel.
# Usage: scripts/gcp/deploy-demo.sh [--build-only] [--setup] [--db-setup] [--remote-web-build]
#   --build-only        build and push changed images, deploy nothing
#   --setup             re-apply APIs, registry, service accounts, IAM and Cloud SQL validation (automatic on the first deploy)
#   --db-setup          force the migrate + seed job (otherwise it runs only when migrations, models or seed inputs changed)
#   --remote-web-build  compile the web app inside Cloud Build instead of locally (slower; the local build output is
#                       otherwise packaged by Cloud Build into the same Node image)
# API_MIN_INSTANCES (default 0) keeps that many API instances warm. At 0 the API scales to zero when idle, so the first
# request after about 15 idle minutes waits for a container start; 1 keeps one instance billed around the clock.
# Production (Firebase identity, demo disabled) uses scripts/gcp/deploy.sh instead.
set -euo pipefail
: "${GCP_PROJECT_ID:?Set the authorized project ID}"
: "${GCP_REGION:?Set the Cloud Run region, e.g. asia-southeast1}"
: "${GEMINI_MODEL:?Set a Gemini model ID available in Vertex AI}"
BUILD_ONLY=0; SETUP=0; REMOTE_WEB=0; FORCE_DB=0
for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=1 ;;
    --setup) SETUP=1 ;;
    --db-setup) FORCE_DB=1 ;;
    --remote-web-build) REMOTE_WEB=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
GEMINI_LOCATION="${GEMINI_LOCATION:-$GCP_REGION}"
# Google Maps Platform (optional). Server key lives in Secret Manager; the browser key is public by design
# and must be restricted to the web URL (HTTP referrer) and the Maps JavaScript API in the Cloud console.
MAPS_SERVER_KEY_SECRET="${MAPS_SERVER_KEY_SECRET:-}"
GOOGLE_MAPS_BROWSER_KEY="${GOOGLE_MAPS_BROWSER_KEY:-}"
GOOGLE_MAPS_MAP_ID="${GOOGLE_MAPS_MAP_ID:-}"
P="$GCP_PROJECT_ID"; R="$GCP_REGION"
PREFIX="${R}-docker.pkg.dev/${P}/nextrm-repo"
API_SA="nextrm-api-sa@${P}.iam.gserviceaccount.com"
WEB_SA="nextrm-web-sa@${P}.iam.gserviceaccount.com"
DATABASE_SECRET="${DATABASE_SECRET:-nextrm-database-url}"
CONNECTION="${P}:${R}:${CLOUDSQL_INSTANCE:-nextrm-pg}"
cd "$(dirname "$0")/../.."
LOGS="$(mktemp -d)"
START=$SECONDS
SETUP_RAN=0

stage() { printf '[%3ss] %s\n' "$((SECONDS - START))" "$*"; }
hash_tree() {
  find "$@" -type f -not -path '*/node_modules/*' -not -path '*/.next*' -not -path '*/__pycache__/*' -not -path 'services/api/tests/*' \
    -not -name '*.pyc' -not -name '.DS_Store' -not -name '*.tsbuildinfo' -print0 \
    | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12
}
bg() {
  local name="$1"; shift
  ( trap 'echo $? >"$LOGS/$name.rc"' EXIT; "$@" >"$LOGS/$name.log" 2>&1 ) &
}
join() {
  local failed=0 rc name
  wait
  for rc in "$LOGS"/*.rc; do
    [[ -e "$rc" ]] || continue
    name="$(basename "$rc" .rc)"
    if [[ "$(cat "$rc")" != 0 ]]; then failed=1; echo "FAILED: $name" >&2; tail -40 "$LOGS/$name.log" >&2; fi
    rm -f "$rc"
  done
  return "$failed"
}
image_exists() { gcloud artifacts docker images describe "$1" --project="$P" >/dev/null 2>&1; }
secret_version() {
  gcloud secrets versions list "$DATABASE_SECRET" --project="$P" --filter='state=ENABLED' --sort-by='~createTime' --limit=1 --format='value(name)' | sed 's#.*/##'
}
service_field() {
  gcloud run services describe "$1" --project="$P" --region="$R" --format="value($2)" 2>/dev/null || true
}
build_api() {
  gcloud builds submit . --project="$P" --config=infra/cloudbuild-api.yaml \
    --substitutions="_IMAGE=${API_IMAGE},_CACHE=${PREFIX}/api:cache" --quiet
}
build_web() {
  if [[ "$REMOTE_WEB" == 1 ]]; then
    gcloud builds submit . --project="$P" --config=infra/cloudbuild-web.yaml \
      --substitutions="_IMAGE=${WEB_IMAGE},_CACHE=${PREFIX}/web:cache" --quiet
    return
  fi
  local context
  context="$(mktemp -d)"
  npm --prefix apps/web run build
  mkdir -p "$context/app/.next"
  cp -R apps/web/.next/standalone/. "$context/app/"
  cp -R apps/web/.next/static "$context/app/.next/static"
  cp -R apps/web/public "$context/app/public"
  cp infra/Dockerfile.web-prebuilt "$context/Dockerfile"
  gcloud builds submit "$context" --project="$P" --tag="$WEB_IMAGE" --quiet
  rm -rf "$context"
}

deploy_api() {
  local version secrets env
  version="$(secret_version)"
  if [[ -z "$version" ]]; then echo "Secret ${DATABASE_SECRET} has no enabled version; run scripts/gcp/provision-sql.sh" >&2; return 1; fi
  secrets="DATABASE_URL=${DATABASE_SECRET}:${version}"
  if [[ "$FORCE_DB" == 1 || "$(service_field nextrm-api 'metadata.labels.nextrm_db')" != "$DB_TAG" ]]; then
    gcloud run jobs deploy nextrm-db-setup --project="$P" --region="$R" --image="$API_IMAGE" --service-account="$API_SA" \
      --set-cloudsql-instances="$CONNECTION" --set-secrets="$secrets" \
      --set-env-vars="ENVIRONMENT=development,NEXTRM_SEED_CUSTOMER_ACTIVITY=true" \
      --command=/app/scripts/gcp/db-setup.sh --tasks=1 --max-retries=0 --task-timeout=600 --execute-now --wait
  fi
  env="ENVIRONMENT=development,DEBUG=false,AUTH_PROVIDER=synthetic_demo,NEXTRM_SEED_CUSTOMER_ACTIVITY=true,NEXTRM_WORKER_HEALTH_FILE=/tmp/worker-health.json,NEXTRM_AI_PROVIDER=vertex,GOOGLE_CLOUD_PROJECT=${P},GOOGLE_CLOUD_LOCATION=${GEMINI_LOCATION},GEMINI_MODEL=${GEMINI_MODEL}"
  if [[ -n "${GEMINI_THINKING_LEVEL:-}" ]]; then env="${env},GEMINI_THINKING_LEVEL=${GEMINI_THINKING_LEVEL}"; fi
  if [[ -n "${GEMINI_THINKING_BUDGET:-}" ]]; then env="${env},GEMINI_THINKING_BUDGET=${GEMINI_THINKING_BUDGET}"; fi
  if [[ -n "$MAPS_SERVER_KEY_SECRET" ]]; then
    env="${env},NEXTRM_POI_PROVIDER=google"; secrets="${secrets},GOOGLE_MAPS_SERVER_KEY=${MAPS_SERVER_KEY_SECRET}:latest"
  else
    env="${env},NEXTRM_POI_PROVIDER=synthetic"
  fi
  gcloud run deploy nextrm-api --project="$P" --region="$R" --image="$API_IMAGE" \
    --service-account="$API_SA" --no-allow-unauthenticated --ingress=all \
    --command=/app/scripts/gcp/demo-api-entrypoint.sh --set-cloudsql-instances="$CONNECTION" \
    --set-env-vars="$env" --set-secrets="$secrets" --port=8000 --cpu=1 --memory=1Gi --cpu-boost \
    --min-instances="${API_MIN_INSTANCES:-0}" --max-instances=3 --no-cpu-throttling --concurrency=20 --timeout=60 --update-labels="nextrm_db=${DB_TAG}" --quiet
  if [[ "$SETUP_RAN" == 1 ]]; then
    gcloud run services add-iam-policy-binding nextrm-api --project="$P" --region="$R" --member="serviceAccount:${WEB_SA}" --role=roles/run.invoker --quiet >/dev/null
  fi
}
deploy_web() {
  gcloud run deploy nextrm-web --project="$P" --region="$R" --image="$WEB_IMAGE" \
    --service-account="$WEB_SA" --allow-unauthenticated \
    --set-env-vars="API_INTERNAL_URL=$1,NEXTRM_DEMO_MODE=true,NEXTRM_AUTH_PROVIDER=synthetic_demo,GOOGLE_MAPS_BROWSER_KEY=${GOOGLE_MAPS_BROWSER_KEY},GOOGLE_MAPS_MAP_ID=${GOOGLE_MAPS_MAP_ID}" \
    --port=3000 --cpu=1 --memory=512Mi --min-instances=0 --max-instances=3 --quiet
}
api_pipeline() { if [[ "$NEED_API" == 1 ]]; then build_api; fi; deploy_api; }
web_pipeline() { if [[ "$NEED_WEB" == 1 ]]; then build_web; fi; deploy_web "$API_URL"; }

stage 'hashing sources'
API_TAG="$(hash_tree requirements.txt requirements-google.txt alembic.ini infra/Dockerfile.api services data scripts/seed_demo.py scripts/gcp/demo-api-entrypoint.sh scripts/gcp/db-setup.sh)"
DB_TAG="$(hash_tree alembic.ini services/api/migrations services/api/app/models services/api/app/core/seeder.py services/api/app/services/rm_seed.py services/api/app/services/bank_seed.py data scripts/seed_demo.py scripts/gcp/db-setup.sh)"
WEB_TAG="$(hash_tree apps/web infra/Dockerfile.web infra/Dockerfile.web-prebuilt)"
API_IMAGE="${PREFIX}/api:${API_TAG}"; WEB_IMAGE="${PREFIX}/web:${WEB_TAG}"

if [[ "$BUILD_ONLY" == 0 ]] && { [[ "$SETUP" == 1 ]] || [[ -z "$(service_field nextrm-api status.url)" ]]; }; then
  SETUP_RAN=1
  stage 'setup: APIs, registry, service accounts, IAM, Cloud SQL'
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com iam.googleapis.com --project="$P"
  GCP_PROJECT_ID="$P" GCP_REGION="$R" ./scripts/gcp/bootstrap.sh
  GCP_PROJECT_ID="$P" GCP_REGION="$R" ./scripts/gcp/provision-sql.sh
  gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:${API_SA}" --role=roles/aiplatform.user --condition=None --quiet >/dev/null
  BUILD_SA="$(gcloud projects describe "$P" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
  gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:${BUILD_SA}" --role=roles/cloudbuild.builds.builder --condition=None --quiet >/dev/null
  if [[ -n "$MAPS_SERVER_KEY_SECRET" ]]; then
    gcloud services enable places.googleapis.com secretmanager.googleapis.com --project="$P"
    gcloud secrets add-iam-policy-binding "$MAPS_SERVER_KEY_SECRET" --project="$P" --member="serviceAccount:${API_SA}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
  fi
  if [[ -n "$GOOGLE_MAPS_BROWSER_KEY" ]]; then gcloud services enable maps-backend.googleapis.com --project="$P"; fi
fi

NEED_API=1; NEED_WEB=1
if image_exists "$API_IMAGE"; then NEED_API=0; stage "api ${API_TAG}: image exists, build skipped"; else stage "api ${API_TAG}: build needed"; fi
if image_exists "$WEB_IMAGE"; then NEED_WEB=0; stage "web ${WEB_TAG}: image exists, build skipped"; else stage "web ${WEB_TAG}: build needed"; fi

if [[ "$BUILD_ONLY" == 1 ]]; then
  if [[ "$NEED_API" == 1 ]]; then bg build-api build_api; fi
  if [[ "$NEED_WEB" == 1 ]]; then bg build-web build_web; fi
  join
  stage "images ready: api:${API_TAG} web:${WEB_TAG}"; exit 0
fi

API_URL="$(service_field nextrm-api status.url)"
if [[ -n "$API_URL" ]]; then
  stage 'api and web pipelines running in parallel'
  bg api api_pipeline
  bg web web_pipeline
  join
else
  stage 'first deploy: build both, then api, then web'
  if [[ "$NEED_API" == 1 ]]; then bg build-api build_api; fi
  if [[ "$NEED_WEB" == 1 ]]; then bg build-web build_web; fi
  join
  deploy_api
  API_URL="$(service_field nextrm-api status.url)"
  deploy_web "$API_URL"
fi
WEB_URL="$(service_field nextrm-web status.url)"
stage 'done'
printf 'API (private): %s\nWeb (public):  %s/demo\nImages:        api:%s web:%s\nDatabase:      Cloud SQL %s\n' "$API_URL" "$WEB_URL" "$API_TAG" "$WEB_TAG" "$CONNECTION"
