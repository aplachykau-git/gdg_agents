# 🌍 Community AI Studio — Terraform Multi-Project Deployment Guide

This Terraform module provides **Infrastructure as Code (IaC)** to deploy the full **Community AI Studio** multi-agent architecture to any Google Cloud Platform (GCP) project in minutes.

---

## 🏗️ What Terraform Provisions

1. **Google Cloud APIs**: Automatically enables Cloud Run, Cloud Build, Artifact Registry, Storage, Vertex AI, Docs, and Drive APIs.
2. **Artifact Registry**: Docker container repository (`community-studio-containers`).
3. **Google Cloud Storage**: Dedicated asset bucket (`${project_id}-storage`) with CORS configuration for frontend asset downloads and report storage.
4. **Service Account & Least Privilege IAM**: Dedicated `community-studio-runtime` service account with scoped roles:
   - `roles/aiplatform.user` (Vertex AI / Gemini models)
   - `roles/logging.logWriter` (Cloud Logging)
   - `roles/cloudtrace.agent` (Cloud Trace telemetry)
   - `roles/storage.objectUser` (scoped specifically to the deliverables GCS bucket)
   - `roles/run.invoker` (service-to-service invocation for private A2A services)
5. **Cloud Run Microservices**:
   - `video-editor-a2a` (8Gi RAM, 4 vCPU, 600s timeout, **Private IAM Auth**)
   - `receipt-scanner-a2a` (4Gi RAM, 2 vCPU, 300s timeout, **Private IAM Auth**)
   - `community-root-agent` (8Gi RAM, 4 vCPU, 600s timeout, Headless `adk api_server` with automatic service URL wiring)

---

## 🚀 Quickstart: Deploy to a New GCP Project

### Step 1: Authenticate with Google Cloud
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_TARGET_GCP_PROJECT_ID
```

### Step 2: Configure Terraform Variables
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```
Edit `terraform.tfvars` with your project ID:
```hcl
project_id     = "your-target-gcp-project-id"
region         = "europe-central2"
community_name = "Your Community"
gemini_api_key = "AIzaSy..." # or set use_vertex_ai = "1"
```

### Step 3: Run Automated One-Click Deployment
From the repository root:
```bash
make tf-deploy
# OR:
bash deploy/deploy_terraform.sh
```

---

## 🛠️ Manual Terraform Step-by-Step Workflow

If you prefer running Terraform commands manually:

### 1. Build and Push Container Images
```bash
PROJECT_ID="your-target-gcp-project-id"
REGION="europe-central2"
REPO="community-studio-containers"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# Create repo if not existing yet
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || true

# Build & Push containers via Cloud Build
gcloud builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/video-editor-a2a:latest" -f deploy/Dockerfile.video_editor .
gcloud builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/receipt-scanner-a2a:latest" -f deploy/Dockerfile.receipt_scanner .
gcloud builds submit --project "$PROJECT_ID" --tag "${IMAGE_BASE}/community-root-agent:latest" -f deploy/Dockerfile.root .
```

### 2. Initialize & Apply Terraform
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 3. Deploy Frontend (Firebase Hosting)
```bash
cd ..
npm run build --prefix frontend
npx -y firebase-tools deploy --only hosting --project YOUR_TARGET_GCP_PROJECT_ID
```

---

## 🧹 Destroying Resources

To clean up all provisioned infrastructure in the project:
```bash
cd terraform
terraform destroy
```
