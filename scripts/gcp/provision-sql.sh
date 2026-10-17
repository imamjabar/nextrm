#!/usr/bin/env bash
# Repeat-safe Cloud SQL for PostgreSQL provisioning. Creates what is missing, validates what exists, never deletes.
# Cloud SQL bills every hour the instance exists, independent of traffic. Cost and teardown: docs/DEPLOY.md.
set -euo pipefail
: "${GCP_PROJECT_ID:?Set the authorized project ID}"
: "${GCP_REGION:?Set the region, e.g. asia-southeast1}"
P="$GCP_PROJECT_ID"; R="$GCP_REGION"
INSTANCE="${CLOUDSQL_INSTANCE:-nextrm-pg}"
TIER="${CLOUDSQL_TIER:-db-custom-1-3840}"
VERSION="${CLOUDSQL_VERSION:-POSTGRES_17}"
DB_NAME="${CLOUDSQL_DATABASE:-nextrm}"
DB_USER="${CLOUDSQL_USER:-nextrm_app}"
SECRET="${DATABASE_SECRET:-nextrm-database-url}"
API_SA="nextrm-api-sa@${P}.iam.gserviceaccount.com"
CONNECTION="${P}:${R}:${INSTANCE}"

gcloud services enable sqladmin.googleapis.com secretmanager.googleapis.com --project="$P"

instances="$(gcloud sql instances list --project="$P" --format='value(name)')"
if grep -qx "$INSTANCE" <<<"$instances"; then
  IFS=$'\t' read -r version region edition backups pitr protection state \
    < <(gcloud sql instances describe "$INSTANCE" --project="$P" --format='value(databaseVersion,region,settings.edition,settings.backupConfiguration.enabled,settings.backupConfiguration.pointInTimeRecoveryEnabled,settings.deletionProtectionEnabled,state)')
  [[ "$version" == "$VERSION" && "$region" == "$R" && "$edition" == ENTERPRISE && "$backups" == True && "$pitr" == True && "$protection" == True ]] \
    || { echo "Existing instance $INSTANCE is incompatible (version=$version region=$region edition=$edition backups=$backups pitr=$pitr deletion_protection=$protection). Fix it or choose another CLOUDSQL_INSTANCE." >&2; exit 1; }
  [[ "$state" == RUNNABLE ]] || { echo "Instance $INSTANCE is $state, not RUNNABLE." >&2; exit 1; }
else
  gcloud sql instances create "$INSTANCE" --project="$P" --region="$R" \
    --database-version="$VERSION" --edition=ENTERPRISE --tier="$TIER" \
    --storage-type=SSD --storage-size=10GB --storage-auto-increase --availability-type=ZONAL \
    --backup-start-time=18:00 --enable-point-in-time-recovery --retained-backups-count=7 --retained-transaction-log-days=7 \
    --maintenance-window-day=WED --maintenance-window-hour=18 --maintenance-release-channel=production \
    --ssl-mode=ENCRYPTED_ONLY --deletion-protection --database-flags=max_connections=100 --quiet
fi

databases="$(gcloud sql databases list --instance="$INSTANCE" --project="$P" --format='value(name)')"
grep -qx "$DB_NAME" <<<"$databases" || gcloud sql databases create "$DB_NAME" --instance="$INSTANCE" --project="$P"

users="$(gcloud sql users list --instance="$INSTANCE" --project="$P" --format='value(name)')"
secrets="$(gcloud secrets list --project="$P" --format='value(name)')"
if ! grep -qx "$DB_USER" <<<"$users" || ! grep -qx "$SECRET" <<<"$secrets"; then
  PASSWORD="$(openssl rand -hex 24)"
  if grep -qx "$DB_USER" <<<"$users"; then
    gcloud sql users set-password "$DB_USER" --instance="$INSTANCE" --project="$P" --password="$PASSWORD" >/dev/null
  else
    gcloud sql users create "$DB_USER" --instance="$INSTANCE" --project="$P" --password="$PASSWORD" >/dev/null
  fi
  grep -qx "$SECRET" <<<"$secrets" || gcloud secrets create "$SECRET" --project="$P" --replication-policy=automatic >/dev/null
  printf '%s' "postgresql+psycopg://${DB_USER}:${PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION}" \
    | gcloud secrets versions add "$SECRET" --project="$P" --data-file=- >/dev/null
  unset PASSWORD
fi

gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:${API_SA}" --role=roles/cloudsql.client --condition=None --quiet >/dev/null
gcloud secrets add-iam-policy-binding "$SECRET" --project="$P" --member="serviceAccount:${API_SA}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
printf 'Cloud SQL ready: %s (database %s, user %s)\nSecret: %s\n' "$CONNECTION" "$DB_NAME" "$DB_USER" "$SECRET"
