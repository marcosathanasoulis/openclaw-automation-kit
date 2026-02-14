#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-openclaw-demo-chat}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Set PROJECT_ID first. Example: PROJECT_ID=my-gcp-project $0"
  exit 1
fi

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud run deploy "${SERVICE}" \
  --source . \
  --region "${REGION}" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 2 \
  --port 8080 \
  --set-env-vars "OPENCLAW_AUTOMATION_ROOT=/app"
