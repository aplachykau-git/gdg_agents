#!/usr/bin/env bash
# ==============================================================================
# One-time setup of the persistent ADK session store (Cloud SQL for PostgreSQL).
#
# Creates (idempotently):
#   * Cloud SQL Postgres instance  $SESSION_DB_INSTANCE  (db-f1-micro, ~10 USD/month)
#   * database $SESSION_DB_NAME and user $SESSION_DB_USER with a random password
#   * Secret Manager secret  $SESSION_SECRET_NAME  holding the SQLAlchemy URI
#   * IAM for the runtime service account (cloudsql.client, secretAccessor)
#
# deploy_a2a_cloudrun.sh picks the secret up automatically on the next deploy.
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
if [ -f ".env" ]; then set -a; source .env; set +a; fi

GCLOUD_BIN="$(which gcloud || echo gcloud)"
REGION="${GCP_REGION:-europe-central2}"
PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$($GCLOUD_BIN config get-value project 2>/dev/null)}}"
SESSION_DB_INSTANCE="${SESSION_DB_INSTANCE:-community-sessions}"
SESSION_DB_TIER="${SESSION_DB_TIER:-db-f1-micro}"
SESSION_DB_NAME="${SESSION_DB_NAME:-adk_sessions}"
SESSION_DB_USER="${SESSION_DB_USER:-adk}"
SESSION_SECRET_NAME="${SESSION_SECRET_NAME:-session-service-uri}"
SA_EMAIL="community-studio-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🗄️  Session DB: ${SESSION_DB_INSTANCE} (${SESSION_DB_TIER}) in ${PROJECT_ID}/${REGION}"
"$GCLOUD_BIN" services enable sqladmin.googleapis.com secretmanager.googleapis.com --project "$PROJECT_ID"

if ! "$GCLOUD_BIN" sql instances describe "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" >/dev/null 2>&1; then
    "$GCLOUD_BIN" sql instances create "$SESSION_DB_INSTANCE" \
        --project "$PROJECT_ID" --region "$REGION" \
        --database-version POSTGRES_16 --edition ENTERPRISE --tier "$SESSION_DB_TIER" \
        --storage-size 10 --storage-auto-increase --backup-start-time 03:00
fi

if ! "$GCLOUD_BIN" sql databases describe "$SESSION_DB_NAME" --instance "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" >/dev/null 2>&1; then
    "$GCLOUD_BIN" sql databases create "$SESSION_DB_NAME" --instance "$SESSION_DB_INSTANCE" --project "$PROJECT_ID"
fi

if "$GCLOUD_BIN" secrets describe "$SESSION_SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "🔑 Secret ${SESSION_SECRET_NAME} already exists; keeping the current password."
else
    DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    if "$GCLOUD_BIN" sql users describe "$SESSION_DB_USER" --instance "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" >/dev/null 2>&1; then
        "$GCLOUD_BIN" sql users set-password "$SESSION_DB_USER" --instance "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" --password "$DB_PASSWORD"
    else
        "$GCLOUD_BIN" sql users create "$SESSION_DB_USER" --instance "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" --password "$DB_PASSWORD"
    fi
    CONNECTION_NAME="$("$GCLOUD_BIN" sql instances describe "$SESSION_DB_INSTANCE" --project "$PROJECT_ID" --format='value(connectionName)')"
    URI="postgresql+asyncpg://${SESSION_DB_USER}:${DB_PASSWORD}@/${SESSION_DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
    printf '%s' "$URI" | "$GCLOUD_BIN" secrets create "$SESSION_SECRET_NAME" --project "$PROJECT_ID" --replication-policy automatic --data-file=-
fi

for role in roles/cloudsql.client roles/secretmanager.secretAccessor; do
    "$GCLOUD_BIN" projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" --role="$role" --condition=None --quiet >/dev/null
done

echo "✅ Session store ready. Run deploy/deploy_a2a_cloudrun.sh to attach it to the services."
