#!/usr/bin/env python3
"""create_model_armor.py — Create Cloud DLP templates and Model Armor template.

Creates:
1. DLP Inspect Template (inspect_email) for detecting EMAIL_ADDRESS.
2. DLP Deidentify Template (redact_emails) for redacting EMAIL_ADDRESS.
3. Model Armor Template (mask_emails) linking the DLP templates with RAI filters.

Idempotent — safe to re-run.

Usage:
  python setup/create_model_armor.py
  PROJECT_ID=my-project MODEL_ARMOR_LOCATION=us python setup/create_model_armor.py
"""

import os
import subprocess
import sys
import requests
import google.auth
from google.auth.transport.requests import Request

LOCATION = os.environ.get("MODEL_ARMOR_LOCATION", "us")
TEMPLATE_ID = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "mask_emails")
INSPECT_TEMPLATE_ID = os.environ.get("DLP_INSPECT_TEMPLATE_ID", "inspect_email")
DEIDENTIFY_TEMPLATE_ID = os.environ.get("DLP_DEIDENTIFY_TEMPLATE_ID", "redact_emails")


def get_project_id() -> str:
    project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True,
        )
        project_id = result.stdout.strip()
    if not project_id:
        print("ERROR: No project set. Run 'gcloud config set project <id>' or export PROJECT_ID.")
        sys.exit(1)
    return project_id


def get_authenticated_headers(project_id: str) -> dict:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return {
        "Authorization": f"Bearer {credentials.token}",
        "X-Goog-User-Project": project_id,
        "Content-Type": "application/json",
    }


def get_or_create_inspect_template(headers: dict, project_id: str) -> str:
    """Ensure DLP Inspect Template exists and return its full resource name."""
    url = f"https://dlp.googleapis.com/v2/projects/{project_id}/locations/{LOCATION}/inspectTemplates/{INSPECT_TEMPLATE_ID}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        print(f"    DLP inspect template '{INSPECT_TEMPLATE_ID}' already exists.")
        return r.json()["name"]

    # Check if there is an existing inspect template with displayName == "inspect_email"
    list_url = f"https://dlp.googleapis.com/v2/projects/{project_id}/locations/{LOCATION}/inspectTemplates"
    list_r = requests.get(list_url, headers=headers)
    if list_r.status_code == 200:
        templates = list_r.json().get("inspectTemplates", [])
        for t in templates:
            if t.get("displayName") == "inspect_email":
                print(f"    Found existing DLP inspect template: {t['name']}")
                return t["name"]

    print(f"    Creating DLP inspect template '{INSPECT_TEMPLATE_ID}'...")
    body = {
        "inspectTemplate": {
            "displayName": "inspect_email",
            "description": "Template to inspect email addresses for Model Armor",
            "inspectConfig": {
                "infoTypes": [{"name": "EMAIL_ADDRESS"}],
                "minLikelihood": "POSSIBLE",
            },
        },
        "templateId": INSPECT_TEMPLATE_ID,
    }
    create_r = requests.post(list_url, json=body, headers=headers)
    if create_r.status_code in (200, 201):
        created_name = create_r.json()["name"]
        print(f"    Created DLP inspect template: {created_name}")
        return created_name
    else:
        print(f"ERROR creating DLP inspect template: {create_r.status_code} - {create_r.text}")
        sys.exit(1)


def get_or_create_deidentify_template(headers: dict, project_id: str) -> str:
    """Ensure DLP Deidentify Template exists and return its full resource name."""
    url = f"https://dlp.googleapis.com/v2/projects/{project_id}/locations/{LOCATION}/deidentifyTemplates/{DEIDENTIFY_TEMPLATE_ID}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        print(f"    DLP deidentify template '{DEIDENTIFY_TEMPLATE_ID}' already exists.")
        return r.json()["name"]

    list_url = f"https://dlp.googleapis.com/v2/projects/{project_id}/locations/{LOCATION}/deidentifyTemplates"
    print(f"    Creating DLP deidentify template '{DEIDENTIFY_TEMPLATE_ID}'...")
    body = {
        "deidentifyTemplate": {
            "displayName": "redact_emails",
            "description": "Template to redact email addresses for Model Armor",
            "deidentifyConfig": {
                "infoTypeTransformations": {
                    "transformations": [
                        {
                            "infoTypes": [{"name": "EMAIL_ADDRESS"}],
                            "primitiveTransformation": {
                                "redactConfig": {}
                            },
                        }
                    ]
                },
                "transformationErrorHandling": {
                    "throwError": {}
                },
            },
        },
        "templateId": DEIDENTIFY_TEMPLATE_ID,
    }
    create_r = requests.post(list_url, json=body, headers=headers)
    if create_r.status_code in (200, 201):
        created_name = create_r.json()["name"]
        print(f"    Created DLP deidentify template: {created_name}")
        return created_name
    else:
        print(f"ERROR creating DLP deidentify template: {create_r.status_code} - {create_r.text}")
        sys.exit(1)


def get_or_create_model_armor_template(
    headers: dict, project_id: str, inspect_template_name: str, deidentify_template_name: str
) -> str:
    """Ensure Model Armor Template exists and return its full resource name."""
    endpoint = f"https://modelarmor.{LOCATION}.rep.googleapis.com"
    template_url = f"{endpoint}/v1/projects/{project_id}/locations/{LOCATION}/templates/{TEMPLATE_ID}"
    r = requests.get(template_url, headers=headers)
    if r.status_code == 200:
        print(f"    Model Armor template '{TEMPLATE_ID}' already exists.")
        return r.json()["name"]

    print(f"    Creating Model Armor template '{TEMPLATE_ID}'...")
    create_url = f"{endpoint}/v1/projects/{project_id}/locations/{LOCATION}/templates?templateId={TEMPLATE_ID}"
    body = {
        "filterConfig": {
            "raiSettings": {
                "raiFilters": [
                    {"filterType": "HATE_SPEECH", "confidenceLevel": "HIGH"},
                    {"filterType": "DANGEROUS", "confidenceLevel": "HIGH"},
                    {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "HIGH"},
                    {"filterType": "HARASSMENT", "confidenceLevel": "HIGH"},
                ]
            },
            "sdpSettings": {
                "advancedConfig": {
                    "inspectTemplate": inspect_template_name,
                    "deidentifyTemplate": deidentify_template_name,
                }
            },
        },
        "templateMetadata": {
            "enforcementType": "INSPECT_AND_BLOCK",
            "filterVersionSelector": {
                "alias": "FILTER_VERSION_ALIAS_STABLE"
            },
            "modalities": [
                "MODALITY_TEXT",
                "MODALITY_IMAGE",
            ],
            "multiLanguageDetection": {},
            "dataResidencyCompliant": True,
        },
    }
    create_r = requests.post(create_url, json=body, headers=headers)
    if create_r.status_code in (200, 201):
        created_name = create_r.json()["name"]
        print(f"    Created Model Armor template: {created_name}")
        return created_name
    else:
        print(f"ERROR creating Model Armor template: {create_r.status_code} - {create_r.text}")
        sys.exit(1)


def main():
    project_id = get_project_id()
    print(f"    Project: {project_id}")
    print(f"    Location: {LOCATION}")

    headers = get_authenticated_headers(project_id)

    inspect_name = get_or_create_inspect_template(headers, project_id)
    deidentify_name = get_or_create_deidentify_template(headers, project_id)
    ma_name = get_or_create_model_armor_template(headers, project_id, inspect_name, deidentify_name)

    print(f"\n    Model Armor setup complete: {ma_name}")


if __name__ == "__main__":
    main()
