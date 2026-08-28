# ==============================================================================
# Google Cloud Storage Bucket & Artifact Registry
# ==============================================================================

resource "google_storage_bucket" "assets_bucket" {
  name                        = locals.bucket_name
  location                    = var.region
  project                     = var.project_id
  force_destroy               = false
  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "OPTIONS"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.enabled_apis]
}

# Grant public read access to storage objects for previewing generated reports/media in UI
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.assets_bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Artifact Registry Repository for Docker container images
resource "google_artifact_registry_repository" "studio_repo" {
  location      = var.region
  repository_id = var.artifact_registry_repo_name
  description   = "Docker container images repository for Community AI Studio microservices"
  format        = "DOCKER"
  project       = var.project_id

  depends_on = [google_project_service.enabled_apis]
}
