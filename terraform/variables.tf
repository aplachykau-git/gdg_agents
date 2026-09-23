variable "project_id" {
  description = "Target Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Default Google Cloud region for services, storage, and Artifact Registry"
  type        = string
  default     = "europe-central2"
}

variable "community_name" {
  description = "Name of the developer/organizer community (e.g. GDG Krakow)"
  type        = string
  default     = "GDG Krakow"
}

variable "gcs_bucket_name" {
  description = "Custom Google Cloud Storage bucket name for assets and reports (defaults to <project_id>-storage)"
  type        = string
  default     = ""
}

variable "gemini_api_key" {
  description = "Google AI Studio API Key (optional if using Vertex AI)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "use_vertex_ai" {
  description = "Whether to use Google Vertex AI (1) or AI Studio API Key (0)"
  type        = string
  default     = "0"
}

variable "google_cloud_location" {
  description = "Vertex AI location (e.g. global or europe-central2)"
  type        = string
  default     = "global"
}

variable "google_drive_folder_id" {
  description = "Target Google Drive Folder ID for automated expense reports"
  type        = string
  default     = ""
}

variable "google_docs_template_id" {
  description = "Google Docs template ID for expense reimbursement formatting"
  type        = string
  default     = ""
}

variable "enable_video_generation" {
  description = "Enable generative AI video rendering (Gemini Omni Flash). Set to false to conserve credits."
  type        = string
  default     = "false"
}

variable "video_engine" {
  description = "Video generation engine (omni)"
  type        = string
  default     = "omni"
}

variable "artifact_registry_repo_name" {
  description = "Artifact Registry Docker repository name"
  type        = string
  default     = "community-studio-containers"
}

variable "service_account_id" {
  description = "Custom service account ID for running Cloud Run microservices"
  type        = string
  default     = "community-studio-runtime"
}

variable "enable_persistent_sessions" {
  description = "Store ADK sessions in Cloud SQL Postgres (survives restarts, allows scaling). ~10 USD/month for db-f1-micro."
  type        = bool
  default     = true
}

variable "session_db_tier" {
  description = "Cloud SQL machine tier for the session database"
  type        = string
  default     = "db-f1-micro"
}

variable "max_instances" {
  description = "Max Cloud Run instances per service when persistent sessions are enabled"
  type        = number
  default     = 5
}
