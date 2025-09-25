#!/usr/bin/env python
"""
Fix report paths for local development
Run with: python manage.py shell < fix_report_paths.py
"""

import os
from django.conf import settings

print("Checking current report paths...")
print(f"ONDEMAND_REPORTS_GENERATED: {getattr(settings, 'ONDEMAND_REPORTS_GENERATED', 'Not set')}")
print(f"TEMP_REPORTS_GENERATED: {getattr(settings, 'TEMP_REPORTS_GENERATED', 'Not set')}")

# Create local directories if they don't exist
local_ondemand = os.path.join(settings.BASE_DIR, 'ondemand_reports')
local_temp = os.path.join(settings.BASE_DIR, 'tmp_reports')

print(f"\nCreating local directories...")
os.makedirs(local_ondemand, exist_ok=True)
os.makedirs(local_temp, exist_ok=True)

print(f"✅ Created: {local_ondemand}")
print(f"✅ Created: {local_temp}")

print("\nTo fix this permanently, add these to your .env file or local settings:")
print(f"ONDEMAND_REPORTS_GENERATED={local_ondemand}")
print(f"TEMP_REPORTS_GENERATED={local_temp}")

# Check if we can write to the directories
import tempfile
try:
    with tempfile.NamedTemporaryFile(dir=local_ondemand, delete=True) as f:
        f.write(b'test')
    print(f"\n✅ Write test successful for {local_ondemand}")
except Exception as e:
    print(f"\n❌ Write test failed for {local_ondemand}: {e}")

try:
    with tempfile.NamedTemporaryFile(dir=local_temp, delete=True) as f:
        f.write(b'test')
    print(f"✅ Write test successful for {local_temp}")
except Exception as e:
    print(f"❌ Write test failed for {local_temp}: {e}")