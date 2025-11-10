"""
QuestionSet UPDATE Resource for Django Admin Import/Export.

Handles updates to existing QuestionSet records.
Import template: ID*, Question Set Name, QuestionSet Type, Client, Site, etc.

Key Differences from CREATE:
- ID* field required
- Conditional validation (only if field present)
- check_record_exists() instead of unique_record_check()

Extracted from: apps/activity/admin/question_admin.py (lines 1889-2048)
Date: 2025-10-10
"""

from math import isnan
from django.core.exceptions import ValidationError
from django.apps import apps
from import_export import fields, resources
from import_export import widgets as wg

from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.core import utils

from .base import (
    default_ta,
    AUTHORIZED_QUESTIONSET_TYPES,
    get_or_create_none_bv,
    get_or_create_none_qset,
)


class QuestionSetResourceUpdate(resources.ModelResource):
    CLIENT = fields.Field(
        column_name="Client",
        attribute="client",
        widget=wg.ForeignKeyWidget(Bt, "bucode"),
        default=get_or_create_none_bv,
    )

    BV = fields.Field(
        column_name="Site",
        attribute="bu",
        widget=wg.ForeignKeyWidget(Bt, "bucode"),
        default=get_or_create_none_bv,
    )

    BelongsTo = fields.Field(
        column_name="Belongs To",
        default=get_or_create_none_qset,
        attribute="parent",
        widget=wg.ForeignKeyWidget(QuestionSet, "qsetname"),
    )

    ID = fields.Field(attribute="id", column_name="ID*")
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No", default=-1)
    QSETNAME = fields.Field(attribute="qsetname", column_name="Question Set Name")
    Type = fields.Field(attribute="type", column_name="QuestionSet Type")
    ASSETINCLUDES = fields.Field(
        attribute="assetincludes", column_name="Asset Includes", default=[]
    )
    SITEINCLUDES = fields.Field(
        attribute="buincludes", column_name="Site Includes", default=[]
    )
    SITEGRPINCLUDES = fields.Field(
        attribute="site_grp_includes", column_name="Site Group Includes", default=[]
    )
    SITETYPEINCLUDES = fields.Field(
        attribute="site_type_includes", column_name="Site Type Includes", default=[]
    )
    SHOWTOALLSITES = fields.Field(
        attribute="show_to_all_sites", column_name="Show To All Sites", default=False
    )
    URL = fields.Field(attribute="url", column_name="URL", default="NONE")

    class Meta:
        model = QuestionSet
        skip_unchanged = True
        report_skipped = True
        fields = [
            "ID",
            "Question Set Name",
            "ASSETINCLUDES",
            "SITEINCLUDES",
            "SITEGRPINCLUDES",
            "SITETYPEINCLUDES",
            "SHOWTOALLSITES",
            "URL",
            "BV",
            "CLIENT",
            "Type",
            "BelongsTo",
            "SEQNO",
        ]

    def __init__(self, *args, **kwargs):
        super(QuestionSetResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.check_record_exists(row)
        self.verify_valid_questionset_type(row)
        super().before_import_row(row, **kwargs)

    def verify_valid_questionset_type(self, row):
        if "QuestionSet Type" in row:
            questionset_type = row.get("QuestionSet Type")
            if questionset_type not in AUTHORIZED_QUESTIONSET_TYPES:
                raise ValidationError(
                    {
                        questionset_type: f"{questionset_type} is not a valid Questionset Type. Please select a valid QuestionSet."
                    }
                )

    def check_required_fields(self, row):
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})
        required_fields = ["QuestionSet Type", "Question Set Name", "Seq No"]
        for field in required_fields:
            if field in row:
                if not row.get(field):
                    raise ValidationError({field: f"{field} is a required field"})

        """ optional_fields = ['Site Group Includes', 'Site Includes', 'Asset Includes', 'Site Type Includes']
        if all(not row.get(field) for field in optional_fields):
            raise ValidationError("You should provide a value for at least one field from the following: "
                                "'Site Group Includes', 'Site Includes', 'Asset Includes', 'Site Type Includes'") """

    def validate_row(self, row):
        models_mapping = {
            "Site Group Includes": ("peoples", "Pgroup", "id", "groupname"),
            "Site Includes": ("onboarding", "Bt", "id", "bucode"),
            "Asset Includes": ("activity", "Asset", "id", "assetcode"),
            "Site Type Includes": ("onboarding", "TypeAssist", "id", "tacode"),
        }

        for field, (
            app_name,
            model_name,
            lookup_field,
            model_field,
        ) in models_mapping.items():
            if field_value := row.get(field):
                model = apps.get_model(app_name, model_name)
                values = field_value.split(",")
                list_value = []
                for val in values:
                    get_value = list(
                        model.objects.filter(**{f"{model_field}": val}).values()
                    )
                    list_value.append(str(get_value[0]["id"]))
                count = model.objects.filter(
                    **{f"{lookup_field}__in": list_value}
                ).count()
                if len(values) != count:
                    raise ValidationError(
                        {
                            field: f"Some of the values specified in {field} do not exist in the system"
                        }
                    )
                row[field] = list_value

    def check_record_exists(self, row):
        if not QuestionSet.objects.select_related().filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

    def before_save_instance(self, instance, row, **kwargs):
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        utils.save_common_stuff(self.request, instance, self.is_superuser)
