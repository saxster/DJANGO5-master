"""
DEPRECATED: Legacy monolithic settings file.

This file has been refactored into modular settings architecture.
All new development should use intelliwiz_config.settings which automatically
loads the appropriate environment-specific settings.

Migration Guide:
- Use intelliwiz_config.settings for all Django applications
- Environment is auto-detected from DJANGO_SETTINGS_MODULE
- Specialized settings are in intelliwiz_config.settings.* modules

For legacy compatibility, this file imports from the new modular structure.
"""

import warnings
import os

# Issue deprecation warning
warnings.warn(
    "intelliwiz_config.settings_legacy is deprecated. "
    "Use intelliwiz_config.settings instead. "
    "This will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

# Import from new modular structure based on environment
environment = os.environ.get('DJANGO_SETTINGS_MODULE', '').split('.')[-1]

if environment == 'production':
    from .settings.production import *
elif environment == 'development':
    from .settings.development import *
elif environment == 'test':
    from .settings.test import *
else:
    # Default to development
    from .settings.development import *
    print("Warning: Environment not specified, defaulting to development settings")

print(f"[LEGACY SETTINGS] Loaded via legacy import - environment: {environment}")
print(f"[LEGACY SETTINGS] Please migrate to use intelliwiz_config.settings instead")