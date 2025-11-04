"""
Base Admin Classes and Utilities

Foundation classes and helper functions for onboarding admin functionality.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from django.contrib import admin
from import_export import resources, fields
from import_export import widgets as wg
from import_export.admin import ImportExportModelAdmin
import apps.tenants.models as tm
from apps.service.validators import clean_point_field, clean_string
from apps.peoples import models as pm
from apps.client_onboarding.forms import (
    BtForm,
    ShiftForm,
)
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.core.utils_new.db_utils import (
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_people,
)
from apps.core import utils
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError, DatabaseError
import re
from math import isnan
from apps.core.widgets import EnabledTypeAssistWidget
from apps.client_onboarding.utils import bulk_create_geofence
from apps.activity.models.job_model import Job


class BaseResource(resources.ModelResource):
    """Base resource class for import/export functionality"""
    CLIENT = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default="NONE",
    )
    BV = fields.Field(
        column_name="BV*",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        saves_null_values=True,
        default="NONE",
    )

    def __init__(self, *args, **kwargs):
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def before_save_instance(self, instance, using_transactions, dry_run):
        utils.save_common_stuff(self.request, instance, self.is_superuser)
        super().before_save_instance(instance, using_transactions, dry_run)


def default_ta():
    """Get or create default TypeAssist instance"""
    return get_or_create_none_typeassist()[0]


class BaseFieldSet2:
    """Base field set for common model fields"""
    client = fields.Field(
        column_name="client",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default="NONE",
    )
    bu = fields.Field(
        column_name="bu",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        saves_null_values=True,
        default="NONE",
    )
    tenant = fields.Field(
        column_name="tenant",
        attribute="tenant",
        widget=wg.ForeignKeyWidget(tm.TenantAwareModel, "tenantname"),
        saves_null_values=True,
    )
