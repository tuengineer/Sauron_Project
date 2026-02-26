import os

# Carpeta raíz (ya es el repo clonado)
ROOT_DIR = "."

# Estructura de carpetas y archivos
structure = {
    "risk": ["manager.py"],
    "terraform": ["main.tf", "variables.tf"],
    "scripts": ["deploy.sh"],
    ".github/workflows": ["deploy.yml"]
}

# Contenido de los archivos
files_content = {
    "risk/manager.py": """from google.cloud import firestore
import os

class FirestoreWrapper:
    def __init__(self, project_id=None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.db = firestore.Client(project=self.project_id)

    def set_document(self, collection_name, doc_id, data):
        self.db.collection(collection_name).document(doc_id).set(data)
        return True

    def get_document(self, collection_name, doc_id):
        doc = self.db.collection(collection_name).document(doc_id).get()
        return doc.to_dict() if doc.exists else None

    def delete_document(self, collection_name, doc_id):
        self.db.collection(collection_name).document(doc_id).delete()
        return True

    def list_documents(self, collection_name):
        return [doc.to_dict() for doc in self.db.collection(collection_name).stream()]

if __name__ == "__main__":
    fs = FirestoreWrapper()
    fs.set_document("risk_logs", "test_doc", {"status": "ok"})
    print(fs.get_document("risk_logs", "test_doc"))
""",
    "scripts/deploy.sh": """#!/bin/bash
set -e

export PROJECT_ID=${PROJECT_ID:-"sauron-prod"}
export REGION=${REGION:-"europe-west1"}

echo "Desplegando Sauron Risk Manager..."

cd ../terraform
terraform init
terraform apply -auto-approve

echo "Despliegue completado."
""",
    "terraform/main.tf": """provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "risk_bucket" {
  name          = "${var.project_id}-risk-data"
  location      = var.region
  force_destroy = true
}

resource "google_firestore_database" "risk_db" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}
""",
    "terraform/variables.tf": """variable "project_id" {
  description = "ID del proyecto de Google Cloud"
  type        = string
}

variable "region" {
  description = "Región de despliegue"
  type        = string
  default     = "europe-west1"
}
""",
    ".github/workflows/deploy.yml": """name: Deploy Sauron Risk Manager

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.7.5

      - name: Authenticate GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}

      - name: Run deploy script
        run: bash scripts/deploy.sh
        env:
          PROJECT_ID: ${{ secrets.GCP_PROJECT }}
          REGION: europe-west1
"""
}

# Función para crear carpetas y archivos
def create_structure():
    for folder, files in structure.items():
        dir_path = os.path.join(ROOT_DIR, folder)
        os.makedirs(dir_path, exist_ok=True)
        for file in files:
            file_path = os.path.join(dir_path, file)
            if not os.path.exists(file_path):  # no sobreescribe archivos existentes
                with open(file_path, "w", encoding="utf-8") as f:
                    key = os.path.join(folder, file)
                    f.write(files_content.get(key, ""))
    print("Estructura y archivos generados correctamente en el repo.")

if __name__ == "__main__":
    create_structure()