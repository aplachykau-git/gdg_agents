# ==============================================================================
# Service Account & IAM Bindings
# ==============================================================================

resource "google_service_account" "studio_sa" {
  account_id   = var.service_account_id
  display_name = "Community AI Studio Runner"
  description  = "Service account for executing Community AI Studio Cloud Run agents"
  project      = var.project_id

  depends_on = [google_project_service.enabled_apis]
}

# Grant Vertex AI User role to service account
resource "google_project_iam_member" "sa_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}

# Grant Cloud Logging Log Writer role to service account
resource "google_project_iam_member" "sa_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}

# Grant Cloud Trace Agent role to service account
resource "google_project_iam_member" "sa_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}

# Grant Cloud Storage Object User role to service account for storage bucket
resource "google_storage_bucket_iam_member" "sa_storage_user" {
  bucket = locals.bucket_name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.studio_sa.email}"

  depends_on = [google_storage_bucket.assets_bucket]
}

# Allow Cloud Run Service Account to invoke private A2A services
resource "google_project_iam_member" "sa_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}
