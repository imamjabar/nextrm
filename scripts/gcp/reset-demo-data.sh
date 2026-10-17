#!/usr/bin/env bash
# Restores the PUBLIC SYNTHETIC DEMO database to its pristine seeded state (for example before recording or judging).
# Destructive: drops every table owned by the application role, then migrates and seeds again. Synthetic data only.
set -euo pipefail
: "${GCP_PROJECT_ID:?Set the authorized project ID}"
: "${GCP_REGION:?Set the Cloud Run region}"
[[ "${1:-}" == "--yes" ]] || { echo 'Refusing to reset without --yes: all demo conversations, requests and choices are deleted.' >&2; exit 2; }
gcloud run jobs execute nextrm-db-setup --project="$GCP_PROJECT_ID" --region="$GCP_REGION" --args=--reset --wait
printf '%s\n' 'Demo database reset and reseeded.'
