provider "google" {
  project = var.project_id
  region  = var.region
}

# -------------------------------
# Firestore (modo nativo)
# -------------------------------
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

# -------------------------------
# Service Account
# -------------------------------
resource "google_service_account" "sauron_sa" {
  account_id   = var.service_account_name
  display_name = "Sauron Executor Service Account"
}

# Roles mínimos
resource "google_project_iam_member" "datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.sauron_sa.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sauron_sa.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sauron_sa.email}"
}

# -------------------------------
# Secret Manager
# -------------------------------
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(var.secrets)
  secret_id = each.key
  replication {
    automatic = true
  }
}

# -------------------------------
# Cloud Run Service
# -------------------------------
resource "google_cloud_run_service" "sauron" {
  name     = "sauron-risk-manager"
  location = var.region

  metadata {
    annotations = {
      "autoscaling.knative.dev/minScale" = "0"
      "autoscaling.knative.dev/maxScale" = "1"
    }
  }

  template {
    spec {
      service_account_name = google_service_account.sauron_sa.email
      containers {
        image = var.cloud_run_image

        dynamic "env" {
          for_each = google_secret_manager_secret.secrets
          content {
            name = env.key
            value_from {
              secret_key_ref {
                secret = env.value.id
                version = "latest"
              }
            }
          }
        }

        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
          }
        }
      }
      container_concurrency = 1
      timeout_seconds       = 300
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Permitir invocación solo desde Scheduler
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  service  = google_cloud_run_service.sauron.name
  location = google_cloud_run_service.sauron.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sauron_sa.email}"
}

# -------------------------------
# Cloud Scheduler Jobs
# -------------------------------
# TODO: Migrar a Cloud Tasks si requerimos sub-30s
resource "google_cloud_scheduler_job" "scan_job" {
  name        = "scan-opportunities"
  description = "Invoca endpoint /scan cada 1 minuto"
  schedule    = "*/1 * * * *" 
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${google_cloud_run_service.sauron.status[0].url}/scan"
    oidc_token {
      service_account_email = google_service_account.sauron_sa.email
    }
  }
}

resource "google_cloud_scheduler_job" "reset_job" {
  name        = "reset-daily-budget"
  description = "Resetea presupuesto diario y estado a las 00:00 UTC"
  schedule    = "0 0 * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${google_cloud_run_service.sauron.status[0].url}/reset"
    oidc_token {
      service_account_email = google_service_account.sauron_sa.email
    }
  }
}

# -------------------------------
# Outputs
# -------------------------------
output "service_url" {
  description = "URL del Cloud Run para webhooks"
  value       = google_cloud_run_service.sauron.status[0].url
}

output "discord_webhook_secret" {
  description = "Nombre del secret para Discord"
  value       = google_secret_manager_secret.secrets["discord_webhook_url"].id
}
