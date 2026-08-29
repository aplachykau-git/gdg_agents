#!/usr/bin/env bash

# ==============================================================================
# 🚀 Community AI Studio — Terraform One-Click Deployment Automation
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Source .env if exists to load API keys and configs
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

GCLOUD_BIN="$(which gcloud || echo gcloud)"
TERRAFORM_BIN="$(which terraform || echo terraform)"

REGION="${GCP_REGION:-europe-central2}"
PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$($GCLOUD_BIN config get-value project 2>/dev/null)}}"
REPO_NAME="community-studio-containers"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: GCP Project ID is not set. Run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

echo "================================================================"
echo "🎯 Target GCP Project: $PROJECT_ID"
echo "🌍 Target Region:      $REGION"
echo "📦 Artifact Registry:  $IMAGE_BASE"
echo "================================================================"

# 1. Enable foundational APIs required to push images and run Terraform
echo ""
echo "🔧 [1/5] Enabling Artifact Registry and Cloud Build APIs..."
"$GCLOUD_BIN" services enable \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    storage.googleapis.com \
    --project "$PROJECT_ID"

# 2. Ensure Artifact Registry repository exists for image push
echo ""
echo "📦 [2/5] Setting up Artifact Registry repository..."
"$GCLOUD_BIN" artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Community AI Studio containers" \
    --project="$PROJECT_ID" 2>/dev/null || true

# 3. Build & push container images via Cloud Build
echo ""
echo "🔨 [3/5] Building container images with Cloud Build..."
echo "  -> Building video-editor-a2a..."
"$GCLOUD_BIN" builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/video-editor-a2a:latest" -f deploy/Dockerfile.video_editor .

echo "  -> Building receipt-scanner-a2a..."
"$GCLOUD_BIN" builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/receipt-scanner-a2a:latest" -f deploy/Dockerfile.receipt_scanner .

echo "  -> Building community-root-agent..."
"$GCLOUD_BIN" builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/community-root-agent:latest" -f deploy/Dockerfile.root .

# 4. Generate terraform.tfvars dynamically if not present
if [ ! -f "terraform/terraform.tfvars" ]; then
    echo "⚙️ Creating terraform/terraform.tfvars from active environment..."
    cat <<EOF > terraform/terraform.tfvars
project_id              = "${PROJECT_ID}"
region                  = "${REGION}"
community_name          = "${COMMUNITY_NAME:-GDG Krakow}"
gemini_api_key          = "${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
use_vertex_ai           = "${GOOGLE_GENAI_USE_VERTEXAI:-0}"
google_cloud_location   = "${GOOGLE_CLOUD_LOCATION:-global}"
google_drive_folder_id  = "${GOOGLE_DRIVE_FOLDER_ID:-}"
google_docs_template_id = "${GOOGLE_DOCS_TEMPLATE_ID:-}"
enable_video_generation = "${ENABLE_VIDEO_GENERATION:-false}"
video_engine            = "${VIDEO_ENGINE:-omni}"
EOF
fi

# 5. Apply Terraform
echo ""
echo "🚀 [4/5] Running Terraform Apply..."
cd terraform
"$TERRAFORM_BIN" init
"$TERRAFORM_BIN" apply -auto-approve
cd "$REPO_ROOT"

# 6. Build & Deploy Frontend
echo ""
echo "💻 [5/5] Building & Deploying Frontend..."
STUDIO_SA_EMAIL=$(cd terraform && "$TERRAFORM_BIN" output -raw service_account_email 2>/dev/null || echo "")
VITE_STUDIO_SA_EMAIL="$STUDIO_SA_EMAIL" npm run build --prefix frontend
npx -y firebase-tools deploy --only hosting --project "$PROJECT_ID"

echo ""
echo "================================================================"
echo "🎉 TERRAFORM DEPLOYMENT COMPLETE!"
echo "================================================================"
