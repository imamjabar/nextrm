#!/usr/bin/env bash
set -euo pipefail
: "${WEB_URL:?Set deployed web URL}"
: "${FIREBASE_ID_TOKEN:?Set an authorized short-lived end-user token}"
: "${TENANT_ID:?Set authorized membership tenant}"
curl --fail --silent --show-error "$WEB_URL/api/v1/auth/me" --header "Authorization: Bearer $FIREBASE_ID_TOKEN" --header "X-Tenant-Id: $TENANT_ID"
printf '\n%s\n' 'Authenticated proxy/membership smoke passed. Full workflow and negative tenancy tests remain separate gates.'
