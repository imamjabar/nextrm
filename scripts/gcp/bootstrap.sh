#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set authorized project}"
: "${GCP_REGION:?Set authorized region}"
# Fail on permission errors; an unsuccessful describe is not permission to create a duplicate resource.
repos="$(gcloud artifacts repositories list --project="$GCP_PROJECT_ID" --location="$GCP_REGION" --format='value(name)')"
if grep -qE '(^|/)nextrm-repo$' <<<"$repos"; then
 format="$(gcloud artifacts repositories describe nextrm-repo --project="$GCP_PROJECT_ID" --location="$GCP_REGION" --format='value(format)')"
 [[ "$format" == 'DOCKER' ]] || { echo 'Existing registry has incompatible format'; exit 1; }
else
 gcloud artifacts repositories create nextrm-repo --project="$GCP_PROJECT_ID" --location="$GCP_REGION" --repository-format=docker
fi
accounts="$(gcloud iam service-accounts list --project="$GCP_PROJECT_ID" --format='value(email)')"
for name in nextrm-web-sa nextrm-api-sa; do
 if [[ "$accounts" != *"${name}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"* ]]; then
  gcloud iam service-accounts create "$name" --project="$GCP_PROJECT_ID" --display-name="$name"
 fi
done
printf '%s\n' 'Registry and service accounts validated. Run scripts/gcp/provision-sql.sh for Cloud SQL and the database secret; Firebase and AI configuration are provisioned separately. No application is deployed by bootstrap.'
