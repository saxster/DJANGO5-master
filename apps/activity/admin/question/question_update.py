"""
Question UPDATE Resource for Django Admin Import/Export.

Handles updates to existing Question records.
Import template: ID*, Question Name, Answer Type, Client, Min, Max, etc.

Key Differences from CREATE:
- ID* field required (instead of uniqueness check)
- Conditional validation (only validates fields present in import)
- check_record_exists() instead of check_unique_record()

Extracted from: apps/activity/admin/question_admin.py (lines 1370-1633)
Date: 2025-10-10
"""

from math import isnan
from django.core.exceptions import ValidationError
from import_export import fields, resources
from import_export import widgets as wg
from apps.activity.models.question_model import Question
import apps.onboarding.models as om
from apps.core.widgets import EnabledTypeAssistWidget
from apps.core import utils
from apps.service.validators import clean_string

from .base import default_ta
from .validators import (
    NaNHandler,
    AnswerTypeValidator,
    NumericValidator,
)


class QuestionResourceUpdate(resources.ModelResource):
    """
    Django import-export resource for UPDATING existing Question records.

    Template fields:
    - ID* (required): Question ID to update
    - Question Name: Display name of question
    - Answer Type: Type of answer expected (NUMERIC, SINGLELINE, etc.)
    - Client: Client business unit code
    - Unit: Unit TypeAssist code
    - Category: Category TypeAssist code
    - Options: Comma-separated options for choice types
    - Min/Max: Numeric bounds for NUMERIC/RATING types
    - Alert On/Above/Below: Alert thresholds
    - Enable: Whether question is active (default: True)
    - Is AVPT: Whether attachments required (default: False)
    - AVPT Type: Type of attachment (BACKCAMPIC, FRONTCAMPIC, etc.)
    - Is WorkFlow: Whether question part of workflow (default: False)

    Validation differences from CREATE:
    - ID* field is required (identifies record to update)
    - Conditional validation: only validates fields present in import
    - check_record_exists() instead of check_unique_record()
    - Field names without asterisks (except ID*)
    """

    Unit = fields.Field(
        column_name="Unit",
        attribute="unit",
        widget=EnabledTypeAssistWidget(om.TypeAssist, "tacode"),
        saves_null_values=True,
        default=default_ta,
    )

    Category = fields.Field(
        column_name="Category",
        attribute="category",
        widget=EnabledTypeAssistWidget(om.TypeAssist, "tacode"),
        saves_null_values=True,
        default=default_ta,
    )

    Client = fields.Field(
        column_name="Client",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=lambda: om.Bt.objects.get_or_create(bucode="NONE")[0],
    )

    ID = fields.Field(attribute="id", column_name="ID*")
    AlertON = fields.Field(
        attribute="alerton", column_name="Alert On", saves_null_values=True
    )
    ALERTABOVE = fields.Field(column_name="Alert Above", saves_null_values=True)
    ALERTBELOW = fields.Field(column_name="Alert Below", saves_null_values=True)
    Options = fields.Field(
        attribute="options", column_name="Options", saves_null_values=True
    )
    Name = fields.Field(attribute="quesname", column_name="Question Name")
    Type = fields.Field(attribute="answertype", column_name="Answer Type")
    Min = fields.Field(attribute="min", column_name="Min", saves_null_values=True)
    Max = fields.Field(attribute="max", column_name="Max", saves_null_values=True)
    Enable = fields.Field(
        attribute="enable",
        column_name="Enable",
        default=True,
        widget=wg.BooleanWidget(),
    )
    IsAvpt = fields.Field(
        attribute="isavpt",
        column_name="Is AVPT",
        default=False,
        widget=wg.BooleanWidget(),
    )
    AttType = fields.Field(
        attribute="avpttype", column_name="AVPT Type", saves_null_values=True, default="NONE"
    )
    isworkflow = fields.Field(
        attribute="isworkflow", column_name="Is WorkFlow", default=False
    )

    class Meta:
        model = Question
        skip_unchanged = True
        report_skipped = True
        fields = [
            "Name",
            "Type",
            "Unit",
            "Options",
            "Enable",
            "IsAvpt",
            "AttType",
            "ID",
            "Client",
            "Min",
            "Max",
            "AlertON",
            "isworkflow",
            "Category",
            "ALERTABOVE",
            "ALERTBELOW",
        ]

    def __init__(self, *args, **kwargs):
        super(QuestionResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        """
        Pre-process and validate row data before importing.

        Validation pipeline (conditional - only for fields present):
        1. check_required_fields() - Ensure ID* and other required fields
        2. handle_nan_values() - Clean NaN values from pandas/Excel
        3. clean_question_name_and_answer_type() - Sanitize text fields
        4. clean_numeric_and_rating_fields() - Process numeric fields
        5. validate_numeric_values() - Ensure logical consistency
        6. check_answertype_fields() - Validate answer type is authorized
        7. validate_options_values() - Ensure options valid for choice types
        8. set_alert_on_value() - Auto-generate Alert On for NUMERIC types
        9. check_record_exists() - Ensure ID* exists in database
        """
        self.check_required_fields(row)
        self.handle_nan_values(row)
        self.clean_question_name_and_answer_type(row)
        self.clean_numeric_and_rating_fields(row)
        self.validate_numeric_values(row)
        self.check_answertype_fields(row)
        self.validate_options_values(row)
        self.set_alert_on_value(row)
        self.check_record_exists(row)
        super().before_import_row(row, **kwargs)

    def check_answertype_fields(self, row):
        """
        Validate answer type is in authorized list (conditional).

        Only validates if "Answer Type" field is present in row.
        Uses AnswerTypeValidator for centralized validation.
        """
        if "Answer Type" in row:
            AnswerTypeValidator.check_answertype_fields(row)

    def check_required_fields(self, row):
        """
        Validate required fields are present and non-empty.

        ID* is always required (identifies record to update).
        Other fields only validated if present in import.
        """
        # ID* always required for update
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})

        # Other required fields only validated if present
        required_fields = ["Answer Type", "Question Name", "Client"]
        for field in required_fields:
            if field in row:
                if row.get(field) in ["", None]:
                    raise ValidationError({field: f"{field} is a required field"})

    def clean_question_name_and_answer_type(self, row):
        """
        Sanitize text fields (conditional).

        Only cleans fields that are present in import.
        Uses clean_string() from apps/service/validators.
        """
        if "Question Name" in row:
            row["Question Name"] = clean_string(row.get("Question Name"))
        if "Answer Type" in row:
            row["Answer Type"] = clean_string(row.get("Answer Type"), code=True)

    def clean_numeric_and_rating_fields(self, row):
        """
        Process numeric fields for NUMERIC/RATING types (conditional).

        Only processes if "Answer Type" field present and is NUMERIC/RATING.
        Sets Options to None and converts Min/Max/Alert fields to float.
        """
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
        """
        Convert field value to float with validation.

        Args:
            row: Import row dictionary
            field: Field name to convert

        Raises:
            ValidationError: If Min/Max required but missing for NUMERIC/RATING
        """
        value = row.get(field)
        if value is not None and value != "NONE":
            row[field] = float(value)
        elif field in ["Min", "Max"]:
            raise ValidationError(
                {field: f"{field} is required when Answer Type is {row['Answer Type']}"}
            )

    def handle_nan_values(self, row):
        """
        Clean NaN values from pandas/Excel imports.

        Uses NaNHandler.handle_nan_values() for centralized handling.
        Converts NaN to None for numeric fields, None for text fields,
        and appropriate defaults for boolean fields.
        """
        values = ["Min", "Max", "Alert Below", "Alert Above"]
        for val in values:
            if val in row:
                if type(row.get(val)) == int:
                    continue
                elif row.get(val) == None:
                    continue
                elif row.get(val) == "NONE":
                    continue
                elif isnan(row.get(val)):
                    row[val] = None

    def validate_numeric_values(self, row):
        """
        Validate logical consistency of numeric fields (conditional).

        Only validates fields that are present in import.
        Ensures: Min < Alert Below < Alert Above < Max
        """
        if "Min" in row and "Alert Below" in row:
            min_value = row.get("Min")
            alert_below = row.get("Alert Below")
            if isinstance(alert_below, (int, float)) and isinstance(
                min_value, (int, float)
            ):
                if min_value and alert_below and float(min_value) > float(alert_below):
                    raise ValidationError("Alert Below should be greater than Min")

        if "Max" in row and "Alert Above" in row:
            max_value = row.get("Max")
            alert_above = row.get("Alert Above")
            if isinstance(alert_above, (int, float)) and isinstance(
                max_value, (int, float)
            ):
                if max_value and alert_above and float(max_value) < float(alert_above):
                    raise ValidationError("Alert Above should be smaller than Max")

        if "Alert Below" in row and "Alert Above" in row:
            alert_below = row.get("Alert Below")
            alert_above = row.get("Alert Above")
            if isinstance(alert_below, (int, float)) and isinstance(
                alert_above, (int, float)
            ):
                if (
                    alert_above
                    and alert_below
                    and float(alert_above) < float(alert_below)
                ):
                    raise ValidationError(
                        "Alert Above should be greater than Alert Below"
                    )

    def validate_options_values(self, row):
        """
        Validate Options field for choice types (conditional).

        Only validates if "Answer Type" present and is CHECKBOX/DROPDOWN.
        Ensures Options provided and Alert On values are in Options.
        """
        if "Answer Type" in row:
            if row["Answer Type"] in ["CHECKBOX", "DROPDOWN"]:
                if "Options" in row:
                    if row.get("Options") is None:
                        raise ValidationError(
                            "Options is required when Answer Type is in [DROPDOWN, CHECKBOX]"
                        )
                if "Alert On" in row and "Options" in row:
                    if row.get("Alert On") and row["Alert On"] not in row["Options"]:
                        raise ValidationError(
                            {"Alert On": "Alert On needs to be in Options"}
                        )

    def set_alert_on_value(self, row):
        """
        Auto-generate Alert On value for NUMERIC types (conditional).

        Only processes if "Answer Type" present and is NUMERIC.
        Format: "<{alert_below}, >{alert_above}"
        """
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
        """
        Verify that question with given ID* exists in database.

        Raises:
            ValidationError: If question with ID* not found
        """
        if not Question.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

    def before_save_instance(self, instance, row, **kwargs):
        """
        Apply system defaults before saving instance.

        Sets:
        - tenant_id = 1 (default tenant)
        - Common audit fields (cuser, muser, cdate, mdate)
        """
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        utils.save_common_stuff(self.request, instance, self.is_superuser)
