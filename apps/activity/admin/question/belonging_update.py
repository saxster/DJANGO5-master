"""
QuestionSetBelonging UPDATE Resource for Django Admin Import/Export.

Handles updates to existing QuestionSetBelonging records.
Import template: ID*, Question Name, Question Set, Client, Site, etc.

Key Differences from CREATE:
- ID* field required
- Conditional validation
- check_record_exists() validation
- Supports Alert On list validation for CHECKBOX/DROPDOWN

Extracted from: apps/activity/admin/question_admin.py (lines 1635-1887)
Date: 2025-10-10
"""

from math import isnan
from django.core.exceptions import ValidationError
from import_export import fields, resources
from import_export import widgets as wg
from apps.activity.models.question_model import QuestionSetBelonging, QuestionSet, Question
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.core import utils
from apps.service.validators import clean_string

from .base import (
    default_ta,
    get_or_create_none_bv,
    get_or_create_none_qset,
    get_or_create_none_question,
)
from .validators import (
    NaNHandler,
    AnswerTypeValidator,
    NumericValidator,
    AVPTValidator,
)
from .widgets import QsetFKWUpdate, QuesFKWUpdate


class QuestionSetBelongingResourceUpdate(resources.ModelResource):
    Name = fields.Field(
        column_name="Question Name",
        attribute="question",
        widget=QuesFKWUpdate(Question, "quesname"),
        saves_null_values=True,
        default=get_or_create_none_question,
    )

    QSET = fields.Field(
        column_name="Question Set",
        attribute="qset",
        widget=QsetFKWUpdate(QuestionSet, "qsetname"),
        saves_null_values=True,
        default=get_or_create_none_qset,
    )

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

    ANSTYPE = fields.Field(attribute="answertype", column_name="Answer Type")
    ID = fields.Field(attribute="id", column_name="ID*")
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No")
    ISAVPT = fields.Field(attribute="isavpt", column_name="Is AVPT", default=False)
    AVPTType = fields.Field(
        attribute="avpttype", column_name="AVPT Type", saves_null_values=True
    )
    MIN = fields.Field(attribute="min", column_name="Min")
    ALERTON = fields.Field(attribute="alerton", column_name="Alert On")
    ALERTABOVE = fields.Field(column_name="Alert Above", saves_null_values=True)
    ALERTBELOW = fields.Field(column_name="Alert Below", saves_null_values=True)
    MAX = fields.Field(attribute="max", column_name="Max")
    OPTIONS = fields.Field(attribute="options", column_name="Options")
    ISMANDATORY = fields.Field(
        attribute="ismandatory", column_name="Is Mandatory", default=True
    )

    class Meta:
        model = QuestionSetBelonging
        skip_unchanged = True
        report_skipped = True
        fields = [
            "NAME",
            "QSET",
            "CLIENT",
            "BV",
            "OPTIONS",
            "ISAVPT",
            "AVPTType",
            "ID",
            "MIN",
            "MAX",
            "ISMANDATORY",
            "SEQNO",
            "ANSTYPE",
            "ALERTON",
            "Name",
            "ALERTABOVE",
            "ALERTBELOW",
        ]

    def __init__(self, *args, **kwargs):
        super(QuestionSetBelongingResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.clean_question_name_and_answer_type(row)
        self.clean_numeric_and_rating_fields(row)
        self.validate_numeric_values(row)
        self.validate_options_values(row)
        self.set_alert_on_value(row)
        self.check_record_exists(row)
        self.check_AVPT_fields(row)
        super().before_import_row(row, **kwargs)

    def check_AVPT_fields(self, row):
        if "AVPT Type" in row:
            valid_avpt = ["BACKCAMPIC", "FRONTCAMPIC", "AUDIO", "VIDEO", "NONE"]
            avpt_type = row.get("AVPT Type")
            if avpt_type and avpt_type != "NONE":
                if avpt_type not in valid_avpt:
                    raise ValidationError(
                        {
                            avpt_type: "%(type)s is not a valid AVPT Type. Please select a valid AVPT Type from %(valid)s"
                            % {"type": avpt_type, "valid": valid_avpt}
                        }
                    )

    def check_required_fields(self, row):
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})
        required_fields = [
            "Answer Type",
            "Question Name",
            "Question Set",
            "Client",
            "Site",
        ]
        for field in required_fields:
            if field in row:
                if row.get(field) in ["", None]:
                    raise ValidationError(f"{field} is a required field")

    def clean_question_name_and_answer_type(self, row):
        if "Question Name" in row:
            row["Question Name"] = clean_string(row.get("Question Name"))
        if "Answer Type" in row:
            row["Answer Type"] = clean_string(row.get("Answer Type"), code=True)

    def clean_numeric_and_rating_fields(self, row):
        if "Answer Type" in row:
            answer_type = row.get("Answer Type")
            if answer_type in ["NUMERIC", "RATING"]:
                if "Options" in row:
                    row["Options"] = None
                if "Min" in row:
                    self.convert_to_float(row, "Min")
                if "Max" in row:
                    self.convert_to_float(row, "Max")
                if "Alert Below" in row:
                    self.convert_to_float(row, "Alert Below")
                if "Alert Above" in row:
                    self.convert_to_float(row, "Alert Above")

    def convert_to_float(self, row, field):
        value = row.get(field)
        if value is not None and value != "NONE":
            row[field] = float(value)
        elif field in ["Min", "Max"]:
            raise ValidationError(
                f"{field} is required when Answer Type is {row['Answer Type']}"
            )

    def validate_numeric_values(self, row):
        if "Min" in row and "Alert Below" in row:
            min_value = row.get("Min")
            alert_below = row.get("Alert Below")
            if isinstance(alert_below, (int, float)) and isinstance(
                alert_below, (int, float)
            ):
                if min_value and alert_below and float(min_value) > float(alert_below):
                    raise ValidationError("Alert Below should be greater than Min")
        if "Max" in row and "Alert Above" in row:
            max_value = row.get("Max")
            alert_above = row.get("Alert Above")
            if isinstance(alert_below, (int, float)) and isinstance(
                alert_below, (int, float)
            ):
                if max_value and alert_above and float(max_value) < float(alert_above):
                    raise ValidationError("Alert Above should be smaller than Max")
        if "Alert Below" in row and "Alert Above" in row:
            alert_below = row.get("Alert Below")
            alert_above = row.get("Alert Above")
            if isinstance(alert_below, (int, float)) and isinstance(
                alert_below, (int, float)
            ):
                if (
                    alert_above
                    and alert_below
                    and float(alert_above) < float(alert_below)
                ):
                    raise ValidationError(
                        "Alert Above should be greater than Alert Below"
                    )

    def set_alert_on_value(self, row):
        if "Answer Type" in row:
            if row.get("Answer Type") == "NUMERIC":
                if "Alert Below" in row and "Alert Above" in row and "Alert On" in row:
                    alert_below = row.get("Alert Below")
                    alert_above = row.get("Alert Above")
                    alert_below_str = (
                        "null"
                        if alert_below is None
                        or alert_below == ""
                        or (isinstance(alert_below, float) and isnan(alert_below))
                        else alert_below
                    )
                    alert_above_str = (
                        "null"
                        if alert_above is None
                        or alert_above == ""
                        or (isinstance(alert_above, float) and isnan(alert_above))
                        else alert_above
                    )
                    if alert_above_str != "null" and alert_below_str != "null":
                        row["Alert On"] = f"<{alert_below_str}, >{alert_above_str}"
                    else:
                        row["Alert On"] = None
                else:
                    raise ValidationError(
                        "Alert Above, Alert Below and Alert On Field is required"
                    )

    def check_record_exists(self, row):
        if not QuestionSetBelonging.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

    def validate_options_values(self, row):
        if "Answer Type" in row:
            if row["Answer Type"] in ["CHECKBOX", "DROPDOWN"]:
                if "Options" in row:
                    if row.get("Options") is None:
                        raise ValidationError(
                            "Options is required when Answer Type is in [DROPDOWN, CHECKBOX]"
                        )
                if "Alert On" in row and "Options" in row:
                    if row.get("Alert On"):
                        # Convert comma-separated strings to lists
                        alert_on_list = [
                            item.strip()
                            for item in row["Alert On"].split(",")
                            if item.strip()
                        ]
                        options_list = [
                            item.strip()
                            for item in row["Options"].split(",")
                            if item.strip()
                        ]
                        invalid_items = [
                            item for item in alert_on_list if item not in options_list
                        ]
                        if invalid_items:
                            raise ValidationError(
                                {
                                    "Alert On": f"The following items are not in Options: {', '.join(invalid_items)}"
                                }
                            )

    def before_save_instance(self, instance, row, **kwargs):
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        utils.save_common_stuff(self.request, instance, self.is_superuser)
