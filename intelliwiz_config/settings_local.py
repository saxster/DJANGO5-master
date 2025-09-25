"""
Local development settings override
"""
import os
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Override report generation paths for local development
ONDEMAND_REPORTS_GENERATED = os.path.join(BASE_DIR, 'ondemand_reports')
TEMP_REPORTS_GENERATED = os.path.join(BASE_DIR, 'tmp_reports')

# Ensure directories exist
os.makedirs(ONDEMAND_REPORTS_GENERATED, exist_ok=True)
os.makedirs(TEMP_REPORTS_GENERATED, exist_ok=True)

# Fix Celery warning in development
CELERY_TASK_STORE_EAGER_RESULT = True

print(f"[LOCAL SETTINGS] Report paths configured:")
print(f"  ONDEMAND_REPORTS_GENERATED: {ONDEMAND_REPORTS_GENERATED}")
print(f"  TEMP_REPORTS_GENERATED: {TEMP_REPORTS_GENERATED}")
print(f"[LOCAL SETTINGS] Celery eager result storage enabled")