"""
Settings module for intelliwiz_config project.
Automatically loads the appropriate settings based on DJANGO_SETTINGS_MODULE.
"""

import os

# Get the environment from DJANGO_SETTINGS_MODULE
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')

if 'production' in settings_module:
    from .production import *
elif 'development' in settings_module:
    from .development import *
elif 'test' in settings_module:
    from .test import *
else:
    # Default to development if not specified
    from .development import *
    print("Warning: No specific settings module specified, defaulting to development settings")