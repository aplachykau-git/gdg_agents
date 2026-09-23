# ==============================================================================
# Persistent ADK session store: Cloud SQL for PostgreSQL + Secret Manager URI
# ==============================================================================

locals {
  session_db_enabled = var.enable_persistent_sessions
}

resource "google_sql_database_instance" "sessions" {
  count            = local.session_db_enabled ? 1 : 0
  name             = "community-sessions"
  project          = var.project_id
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    tier              = var.session_db_tier
    edition           = "ENTERPRISE"
    disk_size         = 10
    disk_autoresize   = true
    availability_type = "ZONAL"

    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }
  }

  deletion_protection = true
  depends_on          = [google_project_service.enabled_apis]
}

resource "google_sql_database" "sessions" {
  count    = local.session_db_enabled ? 1 : 0
  name     = "adk_sessions"
  project  = var.project_id
  instance = google_sql_database_instance.sessions[0].name
}

resource "random_password" "session_db" {
  count   = local.session_db_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "google_sql_user" "sessions" {
  count    = local.session_db_enabled ? 1 : 0
  name     = "adk"
  project  = var.project_id
  instance = google_sql_database_instance.sessions[0].name
  password = random_password.session_db[0].result
}

resource "google_secret_manager_secret" "session_uri" {
  count     = local.session_db_enabled ? 1 : 0
  secret_id = "session-service-uri"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "session_uri" {
  count  = local.session_db_enabled ? 1 : 0
  secret = google_secret_manager_secret.session_uri[0].id
  secret_data = format(
    "postgresql+asyncpg://%s:%s@/%s?host=/cloudsql/%s",
    google_sql_user.sessions[0].name,
    random_password.session_db[0].result,
    google_sql_database.sessions[0].name,
    google_sql_database_instance.sessions[0].connection_name,
  )
}

resource "google_project_iam_member" "sa_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}

resource "google_project_iam_member" "sa_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.studio_sa.email}"
}
