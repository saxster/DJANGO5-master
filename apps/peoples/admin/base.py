"""
Base utilities and helper functions for peoples admin.

Provides:
    - Helper functions for data cleaning and password management
    - Shared widget classes for foreign key relationships
    - Common utilities used across admin modules
"""

import math
import re
from apps.core.utils_new.db_utils import (
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_people,
    get_or_create_none_pgroup,
)
from django.db.models import Q
from import_export import widgets as wg
from apps.client_onboarding import models as om_client
from apps.core_onboarding import models as om_core
from apps.peoples import models as pm


def save_people_passwd(user):
    """
    Set user password based on loginid if not already set.

    Args:
        user: People instance

    Security:
        - Uses Django's set_password for proper hashing
        - Falls back to loginid if no password provided
    """
    paswd = f"{user.loginid}" if not user.password else user.password
    user.set_password(paswd)


def clean_value(value):
    """
    Clean import-export values by converting 'NONE' strings and NaN to None.

    Args:
        value: Value from import row

    Returns:
        Cleaned value or None
    """
    if isinstance(value, str) and value.strip().upper() == "NONE":
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def default_ta():
    """
    Get or create default TypeAssist instance for NONE value.

    Returns:
        TypeAssist instance
    """
    return get_or_create_none_typeassist()[0]


# =============================================================================
# CUSTOM WIDGETS FOR FOREIGN KEY RELATIONSHIPS
# =============================================================================


class PgroupFKW(wg.ForeignKeyWidget):
    """
    Foreign key widget for Pgroup with client filtering.

    Filters queryset based on client in import row.
    """

    def get_queryset(self, value, row, *args, **kwargs):
        """Filter by client from import row."""
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]),
        )


class PeopleFKW(wg.ForeignKeyWidget):
    """
    Foreign key widget for People with client filtering.

    Filters queryset based on client in import row.
    """

    def get_queryset(self, value, row, *args, **kwargs):
        """Filter by client from import row."""
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]),
        )


class SiteFKW(wg.ForeignKeyWidget):
    """
    Foreign key widget for Site/BV with client filtering.

    Filters queryset based on client in import row.
    """

    def get_queryset(self, value, row, *args, **kwargs):
        """Filter by client from import row."""
        return self.model.objects.select_related().filter(
            Q(client__bucode__exact=row["Client*"]),
        )
