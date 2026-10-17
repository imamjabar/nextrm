#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set the authorized Google Cloud project explicitly}"
: "${GCP_REGION:?Set the supported target region explicitly}"
command -v gcloud >/dev/null || { echo 'Google Cloud CLI is not installed'; exit 1; }
gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectId)'
failed=0
for api in run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com identitytoolkit.googleapis.com aiplatform.googleapis.com; do
 enabled="$(gcloud services list --project="$GCP_PROJECT_ID" --enabled --filter="config.name=$api" --format='value(config.name)')"
 if [[ "$enabled" != "$api" ]]; then echo "Missing API: $api"; failed=1; fi
done
exit "$failed"
