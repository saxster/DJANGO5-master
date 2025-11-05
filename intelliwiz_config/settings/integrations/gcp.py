"""
Google Cloud Platform Integration Configuration

GCP services:
- Google Cloud Storage (GCS) for media uploads
- Google Maps API
- Google Drive API for bulk imports
- Gemini LLM provider (primary AI service)
"""

import os
import json
from pathlib import Path
import environ

env = environ.Env()

# ============================================================================
# GOOGLE CLOUD STORAGE CONFIGURATION
# ============================================================================
# Security compliance: Rule #4 (Secure Secret Management)
# Configuration-based credentials prevent hardcoded paths and enable
# environment-specific deployment

# GCS Bucket for media uploads (move_media_to_cloud_storage task)
GCS_BUCKET_NAME = env("GCS_BUCKET_NAME", default="")  # Must be set if GCS_ENABLED

# GCS Project ID (optional - inferred from credentials if not set)
GCS_PROJECT_ID = env("GCS_PROJECT_ID", default="")

# GCS Credentials Path - MUST be absolute path to service account JSON file
# Default location: <project_root>/credentials/gcs-service-account.json
# Production: Set via GOOGLE_APPLICATION_CREDENTIALS environment variable
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # intelliwiz_config/settings/integrations/.. -> project root
GCS_CREDENTIALS_PATH = env(
    "GOOGLE_APPLICATION_CREDENTIALS",
    default=str(_BASE_DIR / "credentials" / "gcs-service-account.json")
)

# GCS Configuration Validation (fail fast at startup)
GCS_ENABLED = env.bool("GCS_ENABLED", default=False)  # Explicit opt-in for GCS usage

if GCS_ENABLED:
    # Validate GCS configuration if explicitly enabled
    if not GCS_BUCKET_NAME:
        raise ValueError(
            "GCS_ENABLED is True but GCS_BUCKET_NAME is not set. "
            "Please set GCS_BUCKET_NAME environment variable."
        )

    if not GCS_CREDENTIALS_PATH:
        raise ValueError(
            "GCS_ENABLED is True but GOOGLE_APPLICATION_CREDENTIALS is not set. "
            "Please set GOOGLE_APPLICATION_CREDENTIALS environment variable."
        )

    # Verify credentials file exists
    if not os.path.exists(GCS_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"GCS credentials file not found at: {GCS_CREDENTIALS_PATH}\n"
            f"Please ensure the service account JSON file exists at this path.\n"
            f"Set GOOGLE_APPLICATION_CREDENTIALS environment variable to override."
        )

    # Verify credentials file is readable and valid JSON
    try:
        with open(GCS_CREDENTIALS_PATH, 'r') as f:
            creds_data = json.load(f)
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in creds_data]
            if missing_fields:
                raise ValueError(
                    f"GCS credentials file is missing required fields: {', '.join(missing_fields)}"
                )
    except json.JSONDecodeError as e:
        raise ValueError(
            f"GCS credentials file is not valid JSON: {GCS_CREDENTIALS_PATH}\n"
            f"Error: {e}"
        )
    except PermissionError:
        raise PermissionError(
            f"Cannot read GCS credentials file: {GCS_CREDENTIALS_PATH}\n"
            f"Please check file permissions."
        )

# ============================================================================
# GOOGLE EXTERNAL APIs
# ============================================================================

GOOGLE_MAP_SECRET_KEY = env("GOOGLE_MAP_SECRET_KEY", default="")
BULK_IMPORT_GOOGLE_DRIVE_API_KEY = env("BULK_IMPORT_GOOGLE_DRIVE_API_KEY", default="")

# ============================================================================
# GOOGLE GEMINI LLM CONFIGURATION (Primary AI Provider)
# ============================================================================

GOOGLE_API_KEY = env("GOOGLE_API_KEY", default="")
GEMINI_MODEL_MAKER = env("GEMINI_MODEL_MAKER", default="gemini-1.5-pro-latest")
GEMINI_MODEL_CHECKER = env("GEMINI_MODEL_CHECKER", default="gemini-1.5-flash-latest")

# Validate Gemini configuration if enabled
if GOOGLE_API_KEY:
    # Configuration is valid, no warning needed
    pass
else:
    # Warn if Gemini is not configured (optional)
    import warnings
    warnings.warn(
        "GOOGLE_API_KEY is not set. "
        "Gemini AI provider will be unavailable. "
        "Dashboard agent intelligence will fall back to Claude or be disabled. "
        "Set GOOGLE_API_KEY environment variable to enable Gemini.",
        RuntimeWarning
    )

__all__ = [
    'GCS_BUCKET_NAME',
    'GCS_PROJECT_ID',
    'GCS_CREDENTIALS_PATH',
    'GCS_ENABLED',
    'GOOGLE_MAP_SECRET_KEY',
    'BULK_IMPORT_GOOGLE_DRIVE_API_KEY',
    'GOOGLE_API_KEY',
    'GEMINI_MODEL_MAKER',
    'GEMINI_MODEL_CHECKER',
]
