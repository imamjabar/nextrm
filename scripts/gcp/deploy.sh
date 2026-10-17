#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set authorized project ID}"
: "${GCP_REGION:?Set deployment region}"
: "${CLOUD_SQL_CONNECTION_NAME:?Set provisioned Cloud SQL instance connection name}"
: "${DATABASE_SECRET_VERSION:?Set database Secret Manager secret:version}"
: "${FIREBASE_WEB_API_KEY:?Set Firebase public web configuration key}"
: "${IMAGE_TAG:?Set immutable deployment image tag}"
REGION="$GCP_REGION"
PREFIX="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/nextrm-repo"
gcloud builds submit . --project="$GCP_PROJECT_ID" --config=infra/cloudbuild-api.yaml --substitutions="_IMAGE=${PREFIX}/api:${IMAGE_TAG},_CACHE=${PREFIX}/api:cache"
# Run migrations once, explicitly, before routing application traffic. Schema downgrade is not traffic rollback.
gcloud run jobs deploy nextrm-migrate --project="$GCP_PROJECT_ID" --region="$REGION" --image="${PREFIX}/api:${IMAGE_TAG}" --service-account="nextrm-api-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --set-cloudsql-instances="$CLOUD_SQL_CONNECTION_NAME" --set-secrets="DATABASE_URL=${DATABASE_SECRET_VERSION}" --command=alembic --args=upgrade,head --tasks=1 --max-retries=0
gcloud run jobs execute nextrm-migrate --project="$GCP_PROJECT_ID" --region="$REGION" --wait
gcloud run deploy nextrm-api --project="$GCP_PROJECT_ID" --region="$REGION" --image="${PREFIX}/api:${IMAGE_TAG}" --service-account="nextrm-api-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --no-allow-unauthenticated --add-cloudsql-instances="$CLOUD_SQL_CONNECTION_NAME" --set-secrets="DATABASE_URL=${DATABASE_SECRET_VERSION}" --set-env-vars="ENVIRONMENT=production,AUTH_PROVIDER=firebase,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},DEBUG=false" --port=8000 --max-instances=3 --concurrency=10
API_URL="$(gcloud run services describe nextrm-api --project="$GCP_PROJECT_ID" --region="$REGION" --format='value(status.url)')"
gcloud run services add-iam-policy-binding nextrm-api --project="$GCP_PROJECT_ID" --region="$REGION" --member="serviceAccount:nextrm-web-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --role=roles/run.invoker
gcloud builds submit . --project="$GCP_PROJECT_ID" --config=infra/cloudbuild-web.yaml --substitutions="_IMAGE=${PREFIX}/web:${IMAGE_TAG},_CACHE=${PREFIX}/web:cache"
gcloud run deploy nextrm-web --project="$GCP_PROJECT_ID" --region="$REGION" --image="${PREFIX}/web:${IMAGE_TAG}" --service-account="nextrm-web-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --allow-unauthenticated --set-env-vars="API_INTERNAL_URL=${API_URL},NEXTRM_DEMO_MODE=false,FIREBASE_WEB_API_KEY=${FIREBASE_WEB_API_KEY}" --port=3000 --max-instances=3
printf '%s\n' 'Deployment commands completed. Run authenticated smoke tests; this output is not submission certification.'
