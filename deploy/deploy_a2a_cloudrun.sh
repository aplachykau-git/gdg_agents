#!/usr/bin/env bash

# ==============================================================================
# 🚀 Community AI Studio - Cloud Run & Firebase A2A Multi-Service Deployer
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

# Configure Dedicated Service Account with Least Privilege
SA_NAME="community-studio-runtime"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔐 [1.5/6] Configuring dedicated Service Account: $SA_EMAIL..."
if ! "$GCLOUD_BIN" iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating Service Account $SA_NAME..."
    "$GCLOUD_BIN" iam service-accounts create "$SA_NAME" \
        --description="Runtime identity for Community AI Studio Cloud Run services" \
        --display-name="Community Studio Runtime SA" \
        --project="$PROJECT_ID"
fi

# Grant minimal IAM roles
for role in roles/logging.logWriter roles/cloudtrace.agent roles/aiplatform.user; do
    "$GCLOUD_BIN" projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet >/dev/null 2>&1 || true
done

# Grant storage permissions to deliverables bucket
"$GCLOUD_BIN" storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectUser" \
    --quiet >/dev/null 2>&1 || true

# Helper function to build and deploy a service
build_and_deploy() {
    local SERVICE_NAME="$1"
    local DOCKERFILE="$2"
    local ENV_VARS="$3"
    local MEMORY="${4:-4Gi}"
    local CPU="${5:-2}"
    local TIMEOUT="${6:-300}"
    local AUTH_MODE="${7:---allow-unauthenticated}"
    local INGRESS_MODE="${8:---ingress=all}"
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

    echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run ($AUTH_MODE, $INGRESS_MODE) with SA ${SA_EMAIL}..."
    "$GCLOUD_BIN" run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --platform managed \
        --service-account "$SA_EMAIL" \
        $AUTH_MODE \
        $INGRESS_MODE \
        --memory "$MEMORY" \
        --cpu "$CPU" \
        --timeout "$TIMEOUT" \
        --set-env-vars "$ENV_VARS"
}

GEMINI_KEY="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"

# 1. Deploy Video Editor A2A Microservice (Private)
echo ""
echo "🎬 [2/6] Building & Deploying Video Editor A2A Microservice (Private Auth)..."
build_and_deploy "video-editor-a2a" "deploy/Dockerfile.video_editor" \
    "VIDEO_AGENT_PROTOCOL=https,VIDEO_AGENT_PORT=443,COMMUNITY_NAME=${COMMUNITY_NAME:-Krakow},GCS_BUCKET_NAME=${BUCKET_NAME},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},VIDEO_ENGINE=${VIDEO_ENGINE:-omni},ENABLE_VIDEO_GENERATION=${ENABLE_VIDEO_GENERATION:-true},RENDER_4K=${RENDER_4K:-false},RENDER_ORDINARY=${RENDER_ORDINARY:-true},RENDER_GIF=${RENDER_GIF:-false},GEMINI_API_KEY=${GEMINI_KEY},GOOGLE_API_KEY=${GEMINI_KEY},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI:-0}" \
    "8Gi" "4" "600" "--no-allow-unauthenticated"

"$GCLOUD_BIN" run services add-iam-policy-binding video-editor-a2a \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker" \
    --quiet >/dev/null 2>&1 || true

VIDEO_A2A_URL=$("$GCLOUD_BIN" run services describe video-editor-a2a --region "$REGION" --project "$PROJECT_ID" --format="value(status.url)")
echo "✅ Video Editor A2A deployed (Private) at: $VIDEO_A2A_URL"

# 2. Deploy Receipt Scanner A2A Microservice (Private)
echo ""
echo "🧾 [3/6] Building & Deploying Receipt Scanner A2A Microservice (Private Auth)..."
build_and_deploy "receipt-scanner-a2a" "deploy/Dockerfile.receipt_scanner" \
    "RECEIPT_AGENT_PROTOCOL=https,RECEIPT_AGENT_PORT=443,COMMUNITY_NAME=${COMMUNITY_NAME:-Krakow},GCS_BUCKET_NAME=${BUCKET_NAME},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},GOOGLE_DRIVE_FOLDER_ID=${GOOGLE_DRIVE_FOLDER_ID:-},GOOGLE_DOCS_TEMPLATE_ID=${GOOGLE_DOCS_TEMPLATE_ID:-},GOOGLE_AUTH_METHOD=adc,GEMINI_API_KEY=${GEMINI_KEY},GOOGLE_API_KEY=${GEMINI_KEY},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI:-0}" \
    "4Gi" "2" "300" "--no-allow-unauthenticated"

"$GCLOUD_BIN" run services add-iam-policy-binding receipt-scanner-a2a \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker" \
    --quiet >/dev/null 2>&1 || true

RECEIPT_A2A_URL=$("$GCLOUD_BIN" run services describe receipt-scanner-a2a --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
echo "✅ Receipt Scanner A2A deployed (Private) at: ${RECEIPT_A2A_URL}"

# 3. Deploy Root Orchestrator Agent (Protected Ingress: reachable only via Firebase Hosting rewrites)
echo ""
echo "🧠 [4/6] Building & Deploying Root Orchestrator Agent (community-root-agent)..."
build_and_deploy "community-root-agent" "deploy/Dockerfile.root" \
    "VIDEO_AGENT_A2A_URL=${VIDEO_A2A_URL},RECEIPT_AGENT_A2A_URL=${RECEIPT_A2A_URL},COMMUNITY_NAME=${COMMUNITY_NAME:-Community},GCS_BUCKET_NAME=${BUCKET_NAME},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS=true,ENABLE_VIDEO_GENERATION=${ENABLE_VIDEO_GENERATION:-true},VIDEO_ENGINE=${VIDEO_ENGINE:-omni},RENDER_ORDINARY=${RENDER_ORDINARY:-true},RENDER_4K=${RENDER_4K:-false},RENDER_GIF=${RENDER_GIF:-false},GEMINI_API_KEY=${GEMINI_KEY},GOOGLE_API_KEY=${GEMINI_KEY},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI:-0}" \
    "8Gi" "4" "600" "--allow-unauthenticated" "--ingress=all"

ROOT_AGENT_URL=$("$GCLOUD_BIN" run services describe community-root-agent --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
echo "✅ Root Orchestrator deployed at: ${ROOT_AGENT_URL}"

# 4. Build Frontend
echo ""
echo "💻 [5/6] Building Svelte 5 Production Frontend..."
VITE_API_URL="$ROOT_AGENT_URL" VITE_STUDIO_SA_EMAIL="$SA_EMAIL" npm run build --prefix frontend

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
