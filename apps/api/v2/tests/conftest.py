"""Pytest configuration for API V2 tests."""

import os
import django
from django.conf import settings

# Ensure Django settings are configured for tests in this directory
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings_test")

# Initialize Django if not already done
if not settings.configured:
    django.setup()
