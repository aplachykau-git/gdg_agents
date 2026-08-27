#!/usr/bin/env bash

# ==============================================================================
# 🚀 Community Studio - Cloud Run & Firebase A2A Multi-Service Deployer
# ==============================================================================

set -e

# Always run from the repository root directory
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Source .env if exists to load API keys and configs
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Resolve gcloud binary
GCLOUD_BIN="$(which gcloud || echo gcloud)"

# Configuration
REGION="${GCP_REGION:-europe-central2}"
PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$($GCLOUD_BIN config get-value project 2>/dev/null)}}"
BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-storage}"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: GCP Project ID is not set. Run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

echo "================================================================"
echo "🎯 Target GCP Project: $PROJECT_ID"
echo "🌍 Target Region:      $REGION"
echo "🪣 Target GCS Bucket:  $BUCKET_NAME"
echo "📂 Workspace Root:     $REPO_ROOT"
echo "================================================================"

# Enable required Google Cloud APIs
echo "🔧 [1/6] Enabling required Cloud APIs (Cloud Run, Cloud Build, Artifact Registry, Storage)..."
"$GCLOUD_BIN" services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com \
    --project "$PROJECT_ID"

# Helper function to build and deploy a service
build_and_deploy() {
    local SERVICE_NAME="$1"
    local DOCKERFILE="$2"
    local ENV_VARS="$3"
    local MEMORY="${4:-4Gi}"
    local CPU="${5:-2}"
    local TIMEOUT="${6:-300}"
    local IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

    echo "🔨 Building container image for ${SERVICE_NAME} using ${DOCKERFILE}..."
    local TMP_CONFIG
    TMP_CONFIG=$(mktemp)
    cat <<EOF > "$TMP_CONFIG"
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '${IMAGE_TAG}', '-f', '${DOCKERFILE}', '.']
images:
- '${IMAGE_TAG}'
EOF

    "$GCLOUD_BIN" builds submit --project "$PROJECT_ID" --config="$TMP_CONFIG" .
    rm -f "$TMP_CONFIG"

    echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run with ${MEMORY} RAM and ${CPU} CPUs..."
    "$GCLOUD_BIN" run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --platform managed \
        --allow-unauthenticated \
        --memory "$MEMORY" \
        --cpu "$CPU" \
        --timeout "$TIMEOUT" \
        --set-env-vars "$ENV_VARS"
}

# 1. Deploy Video Editor A2A Microservice
echo ""
echo "🎬 [2/6] Building & Deploying Video Editor A2A Microservice..."
build_and_deploy "video-editor-a2a" "deploy/Dockerfile.video_editor" \
    "VIDEO_AGENT_PROTOCOL=https,VIDEO_AGENT_PORT=443,COMMUNITY_NAME=${COMMUNITY_NAME:-Krakow},GCS_BUCKET_NAME=${BUCKET_NAME},GEMINI_API_KEY=${GEMINI_API_KEY:-},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},ENABLE_VIDEO_GENERATION=false,RENDER_4K=${RENDER_4K:-false},RENDER_ORDINARY=true,RENDER_GIF=true" \
    "8Gi" "4" "600"

VIDEO_A2A_URL=$("$GCLOUD_BIN" run services describe video-editor-a2a --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
echo "✅ Video Editor A2A deployed at: $VIDEO_A2A_URL"

# 2. Deploy Receipt Scanner A2A Microservice
echo ""
echo "🧾 [3/6] Building & Deploying Receipt Scanner A2A Microservice..."
build_and_deploy "receipt-scanner-a2a" "deploy/Dockerfile.receipt_scanner" \
    "RECEIPT_AGENT_PROTOCOL=https,RECEIPT_AGENT_PORT=443,COMMUNITY_NAME=${COMMUNITY_NAME:-Krakow},GCS_BUCKET_NAME=${BUCKET_NAME},GEMINI_API_KEY=${GEMINI_API_KEY:-},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},GOOGLE_DRIVE_FOLDER_ID=${GOOGLE_DRIVE_FOLDER_ID:-}"

RECEIPT_A2A_URL=$("$GCLOUD_BIN" run services describe receipt-scanner-a2a --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
echo "✅ Receipt Scanner A2A deployed at: ${RECEIPT_A2A_URL}"

# 3. Deploy Root Orchestrator Agent
echo ""
echo "🧠 [4/6] Building & Deploying Root Orchestrator Agent (community-root-agent)..."
build_and_deploy "community-root-agent" "deploy/Dockerfile.root" \
    "VIDEO_AGENT_A2A_URL=${VIDEO_A2A_URL},RECEIPT_AGENT_A2A_URL=${RECEIPT_A2A_URL},COMMUNITY_NAME=${COMMUNITY_NAME:-Community},GCS_BUCKET_NAME=${BUCKET_NAME},GEMINI_API_KEY=${GEMINI_API_KEY:-},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS=true" \
    "8Gi" "4" "600"

ROOT_AGENT_URL=$("$GCLOUD_BIN" run services describe community-root-agent --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
echo "✅ Root Orchestrator deployed at: ${ROOT_AGENT_URL}"

# 4. Build Frontend
echo ""
echo "💻 [5/6] Building Svelte 5 Production Frontend..."
npm run build --prefix frontend

# 5. Deploy to Firebase Hosting
echo ""
echo "🔥 [6/6] Deploying Frontend & Cloud Run rewrites to Firebase Hosting..."
npx -y firebase-tools deploy --only hosting --project "$PROJECT_ID"

echo ""
echo "================================================================"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "   ├─ 🧠 Root Orchestrator Cloud Run: $ROOT_AGENT_URL"
echo "   ├─ 🎬 Video Editor A2A Cloud Run:  $VIDEO_A2A_URL"
echo "   ├─ 🧾 Receipt Scanner A2A Cloud Run: $RECEIPT_A2A_URL"
echo "   └─ 🔥 Check your Firebase Hosting URL in the summary above!"
echo "================================================================"
