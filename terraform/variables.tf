# -------------------------------
# Variables de entrada
# -------------------------------

variable "project_id" {
  description = "GCP Project ID donde se desplegarán los recursos"
  type        = string
}

variable "region" {
  description = "Región para Cloud Run, Firestore y Scheduler"
  type        = string
  default     = "us-central1"
}

variable "cloud_run_image" {
  description = "Imagen Docker para Cloud Run"
  type        = string
}

variable "service_account_name" {
  description = "Nombre de la Service Account de Sauron"
  type        = string
  default     = "sauron-executor"
}

variable "secrets" {
  description = "Lista de secretos a crear en Secret Manager"
  type        = list(string)
  default     = ["polymarket_api_key", "private_key", "discord_webhook_url"]
}
