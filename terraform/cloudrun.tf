# ==============================================================================
# Cloud Run Microservices (A2A Network & Root Orchestrator)
# ==============================================================================

# 1. Video Editor A2A Service
resource "google_cloud_run_v2_service" "video_editor" {
  name     = "video-editor-a2a"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.studio_sa.email
    timeout         = "600s"

    containers {
      image = "${locals.image_base}/video-editor-a2a:latest"

      resources {
        limits = {
          cpu    = "4"
          memory = "8Gi"
        }
      }

      env {
        name  = "VIDEO_AGENT_PROTOCOL"
        value = "https"
      }
      env {
        name  = "VIDEO_AGENT_PORT"
        value = "443"
      }
      env {
        name  = "COMMUNITY_NAME"
        value = var.community_name
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = locals.bucket_name
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.google_cloud_location
      }
      env {
        name  = "ENABLE_VIDEO_GENERATION"
        value = var.enable_video_generation
      }
      env {
        name  = "VIDEO_ENGINE"
        value = var.video_engine
      }
      env {
        name  = "RENDER_4K"
        value = "false"
      }
      env {
        name  = "RENDER_ORDINARY"
        value = "true"
      }
      env {
        name  = "RENDER_GIF"
        value = "true"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = var.use_vertex_ai
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_storage_bucket.assets_bucket,
    google_project_iam_member.sa_vertex_user,
    google_project_iam_member.sa_storage_admin
  ]
}

resource "google_cloud_run_v2_service_iam_member" "video_editor_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.video_editor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.studio_sa.email}"
}

# 2. Receipt Scanner A2A Service
resource "google_cloud_run_v2_service" "receipt_scanner" {
  name     = "receipt-scanner-a2a"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.studio_sa.email
    timeout         = "300s"

    containers {
      image = "${locals.image_base}/receipt-scanner-a2a:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "RECEIPT_AGENT_PROTOCOL"
        value = "https"
      }
      env {
        name  = "RECEIPT_AGENT_PORT"
        value = "443"
      }
      env {
        name  = "COMMUNITY_NAME"
        value = var.community_name
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = locals.bucket_name
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.google_cloud_location
      }
      env {
        name  = "GOOGLE_DRIVE_FOLDER_ID"
        value = var.google_drive_folder_id
      }
      env {
        name  = "GOOGLE_DOCS_TEMPLATE_ID"
        value = var.google_docs_template_id
      }
      env {
        name  = "GOOGLE_AUTH_METHOD"
        value = "adc"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = var.use_vertex_ai
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_storage_bucket.assets_bucket,
    google_project_iam_member.sa_vertex_user,
    google_storage_bucket_iam_member.sa_storage_user
  ]
}

resource "google_cloud_run_v2_service_iam_member" "receipt_scanner_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.receipt_scanner.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.studio_sa.email}"
}

# 3. Root Orchestrator Agent (community-root-agent)
resource "google_cloud_run_v2_service" "root_agent" {
  name     = "community-root-agent"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.studio_sa.email
    timeout         = "600s"

    containers {
      image = "${locals.image_base}/community-root-agent:latest"

      resources {
        limits = {
          cpu    = "4"
          memory = "8Gi"
        }
      }

      env {
        name  = "VIDEO_AGENT_A2A_URL"
        value = google_cloud_run_v2_service.video_editor.uri
      }
      env {
        name  = "RECEIPT_AGENT_A2A_URL"
        value = google_cloud_run_v2_service.receipt_scanner.uri
      }
      env {
        name  = "COMMUNITY_NAME"
        value = var.community_name
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = locals.bucket_name
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.google_cloud_location
      }
      env {
        name  = "ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS"
        value = "true"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = var.use_vertex_ai
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }
    }
  }

  depends_on = [
    google_cloud_run_v2_service.video_editor,
    google_cloud_run_v2_service.receipt_scanner,
    google_project_service.enabled_apis,
    google_storage_bucket.assets_bucket,
    google_project_iam_member.sa_vertex_user,
    google_storage_bucket_iam_member.sa_storage_user
  ]
}

resource "google_cloud_run_v2_service_iam_member" "root_agent_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.root_agent.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
