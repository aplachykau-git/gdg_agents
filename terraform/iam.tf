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

# Grant Cloud Storage Object Admin role to service account
resource "google_project_iam_member" "sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}

# Allow Cloud Run to invoke other Cloud Run services (A2A Network)
resource "google_project_iam_member" "sa_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}
