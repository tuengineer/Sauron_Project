#!/bin/bash
set -e

echo "🧙 Sauron v2 Deploy"

# 1. Validar prerequisitos
command -v gcloud >/dev/null 2>&1 || { echo "❌ gcloud no instalado"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ terraform no instalado"; exit 1; }

# 2. Variables
read -p "GCP Project ID: " PROJECT_ID
read -p "Region [us-central1]: " REGION
REGION=${REGION:-us-central1}

export GOOGLE_CLOUD_PROJECT=$PROJECT_ID

# 3. Terraform
cd terraform
terraform init
terraform apply -var="project_id=$PROJECT_ID" -var="region=$REGION" -auto-approve

# 4. Cargar secrets (interactivo, no loggeado)
echo "🔐 Configurar secrets (se ocultan al escribir)"
read -s -p "Polymarket API Key: " POLY_KEY
echo
read -s -p "Private Key (wallet): " PRIV_KEY
echo
read -s -p "Discord Webhook URL: " DISCORD_URL
echo

echo "$POLY_KEY" | gcloud secrets versions add polymarket_api_key --data-file=-
echo "$PRIV_KEY" | gcloud secrets versions add private_key --data-file=-
echo "$DISCORD_URL" | gcloud secrets versions add discord_webhook_url --data-file=-

# 5. Deploy Cloud Run (build y push de imagen)
cd ..
gcloud builds submit --tag gcr.io/$PROJECT_ID/sauron:v1
gcloud run deploy sauron-risk-manager \
  --image gcr.io/$PROJECT_ID/sauron:v1 \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated

# 6. Verificar health
SERVICE_URL=$(gcloud run services describe sauron-risk-manager --region $REGION --format 'value(status.url)')
echo "⏳ Esperando servicio..."
sleep 10

if curl -s "$SERVICE_URL/health" | grep -q "ok"; then
  echo "✅ Deploy exitoso"
else
  echo "⚠️ Health check falló, revisar logs: gcloud logging tail"
fi

echo ""
echo "📊 Dashboard: $SERVICE_URL"
echo "📋 Comandos útiles:"
echo "  gcloud logging tail --service=sauron-risk-manager"
echo "  curl -X POST $SERVICE_URL/reset  # Reset manual"
