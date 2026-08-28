output "root_agent_url" {
  description = "Public URL of the Root Orchestrator Cloud Run service"
  value       = google_cloud_run_v2_service.root_agent.uri
}

output "video_editor_a2a_url" {
  description = "Public URL of the Video Editor A2A Cloud Run service"
  value       = google_cloud_run_v2_service.video_editor.uri
}

output "receipt_scanner_a2a_url" {
  description = "Public URL of the Receipt Scanner A2A Cloud Run service"
  value       = google_cloud_run_v2_service.receipt_scanner.uri
}

output "gcs_bucket_name" {
  description = "Name of the Google Cloud Storage bucket created for assets and reports"
  value       = google_storage_bucket.assets_bucket.name
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.studio_repo.repository_id}"
}

output "service_account_email" {
  description = "Service account email running the Cloud Run microservices"
  value       = google_service_account.studio_sa.email
}
