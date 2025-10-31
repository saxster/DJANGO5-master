"""
Custom admin app configuration to enable the IntelliWiz admin site.

Replacing Django's default admin config allows us to use the
IntelliWizAdminSite defined in ``apps.core.admin.admin_site`` as the
project-wide admin site while keeping all default admin behaviour.
"""
from django.contrib.admin.apps import AdminConfig


class IntelliWizAdminConfig(AdminConfig):
    """Configure Django admin to use the IntelliWiz admin site."""

    default_site = "apps.core.admin.admin_site.IntelliWizAdminSite"
