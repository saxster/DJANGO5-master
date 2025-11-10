"""
Legacy Security Intelligence App Shim
====================================

Old migrations referenced app label ``security_intelligence`` before the module
was moved under ``apps.noc.security_intelligence``. This package re-exposes the
same module so those migrations and imports continue to work.
"""

default_app_config = "apps.security_intelligence.apps.SecurityIntelligenceLegacyConfig"
