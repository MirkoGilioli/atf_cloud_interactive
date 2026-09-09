#!/bin/bash
# catchup_intervention_agent.sh — Deploys the intervention agent solution.
#
# This script:
#   1. Derives project and environment variables from gcloud
#   2. Copies the completed agent.py from agents_solution/intervention_agent/
#   3. Generates .env from .env.example
#   4. Generates agent_card.json from template with correct Cloud Run URL
#   5. Deploys the intervention agent to Cloud Run
#   6. Verifies deployment by inspecting the Cloud Run service and agent card
#
# Prerequisites:
#   - gcloud CLI authenticated and configured with the lab project
#   - setup.sh has already been run (infrastructure is provisioned)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${SCRIPT_DIR}/intervention_agent" ]]; then
  AGENT_DIR="${SCRIPT_DIR}/intervention_agent"
  SOLUTION_DIR="$(cd "${SCRIPT_DIR}/../agents_solution/intervention_agent" 2>/dev/null && pwd || true)"
else
  AGENT_DIR="${SCRIPT_DIR}"
  SOLUTION_DIR="$(cd "${SCRIPT_DIR}/../../agents_solution/intervention_agent" 2>/dev/null && pwd || true)"
fi

# --- Derive environment variables ---
GOOGLE_CLOUD_PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ -z "${GOOGLE_CLOUD_PROJECT}" ]]; then
  echo "ERROR: No active gcloud project. Run: gcloud config set project <PROJECT_ID>"
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "${GOOGLE_CLOUD_PROJECT}" \
  --format='value(projectNumber)' 2>/dev/null)"
if [[ -z "${PROJECT_NUMBER}" ]]; then
  echo "ERROR: Could not retrieve project number for ${GOOGLE_CLOUD_PROJECT}."
  exit 1
fi

export GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION="us-central1"
export AGENT_SA="cymbal-agent@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
export AGENT_SERVICE_NAME="intervention-agent"
export VS_DATASTORE_ID="projects/${PROJECT_NUMBER}/locations/global/collections/default_collection/dataStores/cymbal-meet-docs"
export GCS_MCP_ENDPOINT="https://gcs-mcp-server-${PROJECT_NUMBER}.${GOOGLE_CLOUD_LOCATION}.run.app/mcp"
export INTERVENTIONS_BUCKET="gs://${GOOGLE_CLOUD_PROJECT}-cymbal-meet-interventions"

SERVICE_URL="https://${AGENT_SERVICE_NAME}-${PROJECT_NUMBER}.${GOOGLE_CLOUD_LOCATION}.run.app"

echo "============================================"
echo "Intervention Agent Catchup Deployment"
echo "============================================"
echo "Project:             ${GOOGLE_CLOUD_PROJECT}"
echo "Project Number:      ${PROJECT_NUMBER}"
echo "Region:              ${GOOGLE_CLOUD_LOCATION}"
echo "Service Account:     ${AGENT_SA}"
echo "Service Name:        ${AGENT_SERVICE_NAME}"
echo "Service URL:         ${SERVICE_URL}"
echo "Vertex AI Datastore: ${VS_DATASTORE_ID}"
echo "GCS MCP Endpoint:    ${GCS_MCP_ENDPOINT}"
echo "Interventions Bucket:${INTERVENTIONS_BUCKET}"
echo "============================================"

# --- Step 1: Copy solution agent.py ---
echo ""
echo "Step 1: Checking agent.py ..."
if [[ -n "${SOLUTION_DIR}" && -f "${SOLUTION_DIR}/agent.py" ]]; then
  echo "  Copying completed agent.py from ${SOLUTION_DIR} ..."
  cp "${SOLUTION_DIR}/agent.py" "${AGENT_DIR}/agent.py"
  echo "  Done."
else
  echo "  Solution directory not found; using existing agent.py in ${AGENT_DIR}."
fi

# --- Step 2: Generate .env from .env.example ---
echo ""
echo "Step 2: Generating .env file ..."
if [[ -f "${AGENT_DIR}/.env.example" ]]; then
  sed -e "s|<YOUR_PROJECT_ID>|${GOOGLE_CLOUD_PROJECT}|g" \
      -e "s|<YOUR_PROJECT_NUMBER>|${PROJECT_NUMBER}|g" \
      -e "s|<YOUR_VERTEX_AI_SEARCH_DATASTORE_ID>|${VS_DATASTORE_ID}|g" \
    "${AGENT_DIR}/.env.example" > "${AGENT_DIR}/.env"
  echo "  Done."
fi

# --- Step 3: Generate agent_card.json from template ---
echo ""
echo "Step 3: Generating agent_card.json with service URL ..."
if [[ -f "${AGENT_DIR}/agent_card.json.template" ]]; then
  sed "s|http://localhost:8080|${SERVICE_URL}|" \
    "${AGENT_DIR}/agent_card.json.template" > "${AGENT_DIR}/agent_card.json"
  echo "  Done."
fi

# --- Step 4: Deploy to Cloud Run ---
echo ""
echo "Step 4: Deploying intervention agent to Cloud Run ..."
cd "${AGENT_DIR}"
bash deploy_to_run.sh

echo ""
echo "============================================"
echo "Catchup complete! Intervention agent deployed to:"
echo "  ${SERVICE_URL}"
echo "Agent card URL:"
echo "  ${SERVICE_URL}/.well-known/agent.json"
echo "============================================"
