# ==============================================================================
# Google Cloud Platform Service APIs
# ==============================================================================

locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "docs.googleapis.com",
    "drive.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(locals.required_apis)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}
