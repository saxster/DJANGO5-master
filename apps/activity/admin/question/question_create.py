"""
Question CREATE Resource for Django Admin Import/Export.

Handles creation of new Question records with full validation pipeline.
Import template: Question Name*, Answer Type*, Client*, Unit, Category, Min, Max, etc.

Validation Pipeline (before_import_row):
1. check_required_fields() - Client*, Question Name*, Answer Type*
2. NaNHandler.handle_nan_values() - Sanitize pandas NaN values
3. clean_question_name_and_answer_type() - String cleaning
4. AnswerTypeValidator.apply_answer_type_aware_defaults() - Type-specific defaults
5. OptionsValidator.clean_options_field() - Options validation
6. AVPTValidator.apply_avpt_conditional_logic() - AVPT logic
7. clean_numeric_and_rating_fields() - Numeric cleaning
8. NumericValidator.validate_numeric_values() - Min/Max/Alert validation
9. AnswerTypeValidator.check_answertype_fields() - Type authorization
10. OptionsValidator.validate_options_values() - Options required check
11. set_alert_on_value() - Auto-generate Alert On
12. check_unique_record() - Uniqueness validation

Extracted from: apps/activity/admin/question_admin.py (lines 34-629)
Date: 2025-10-10
"""

from django.core.exceptions import ValidationError
from import_export import fields, resources
from import_export import widgets as wg

from apps.activity.models.question_model import Question
import apps.onboarding.models as om
from apps.core.widgets import EnabledTypeAssistWidget
from apps.core import utils
from apps.core.utils_new.db_utils import get_or_create_none_typeassist, get_or_create_none_bv
from apps.service.validators import clean_string

from .base import default_ta
from .validators import (
    NaNHandler,
    AnswerTypeValidator,
    NumericValidator,
    OptionsValidator,
    AVPTValidator,
)


class QuestionResource(resources.ModelResource):
    """
    Resource for creating new Question records via Django Admin import/export.

    Field Definitions:
    - Question Name* (required): Name of the question
    - Answer Type* (required): Type of answer expected (NUMERIC, SINGLELINE, etc.)
    - Client* (required): Business unit (Bt) the question belongs to
    - Unit (optional): Unit of measurement (TypeAssist)
    - Category (optional): Question category (TypeAssist)
    - Min/Max: Numeric bounds for NUMERIC/RATING types
    - Options: Comma-separated choices for CHECKBOX/DROPDOWN/MULTISELECT
    - Alert On/Above/Below: Alerting thresholds
    - Is AVPT: Whether attachments are required
    - AVPT Type: Type of attachment (BACKCAMPIC, FRONTCAMPIC, AUDIO, VIDEO)
    - Enable: Whether question is active
    - Is WorkFlow: Whether question is part of workflow

    Validation:
    - Required fields: Question Name*, Answer Type*, Client*
    - Answer type must be in authorized list (14 types)
    - Numeric types must have valid Min/Max
    - Choice types must have valid Options
    - Uniqueness: (quesname, answertype, client) must be unique
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
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )

    id = fields.Field(attribute="id", column_name="ID")
    AlertON = fields.Field(
        attribute="alerton", column_name="Alert On", saves_null_values=True
    )
    ALERTABOVE = fields.Field(column_name="Alert Above", saves_null_values=True)
    ALERTBELOW = fields.Field(column_name="Alert Below", saves_null_values=True)
    Options = fields.Field(
        attribute="options", column_name="Options", saves_null_values=True
    )
    Name = fields.Field(attribute="quesname", column_name="Question Name*", default="Untitled Question")
    Type = fields.Field(attribute="answertype", column_name="Answer Type*", default="SINGLELINE")
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
            "id",
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
        """
        Initialize resource with request context.

        Args:
            is_superuser: Boolean indicating if user has superuser privileges
            request: Django request object for save_common_stuff
        """
        super(QuestionResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number=None, **kwargs):
        """
        Validate and transform row data before import.

        Validation pipeline (12 steps):
        1. Required fields check
        2. NaN value sanitization
        3. String cleaning
        4. Answer type defaults
        5. Options field cleaning
        6. AVPT conditional logic
        7. Numeric field cleaning
        8. Numeric value validation
        9. Answer type authorization
        10. Options validation
        11. Alert On auto-generation
        12. Uniqueness check

        Args:
            row: Dictionary containing import row data
            row_number: Row number in import file (for error reporting)
            **kwargs: Additional keyword arguments

        Raises:
            ValidationError: If any validation step fails
        """
        self.check_required_fields(row)
        NaNHandler.handle_nan_values(row)
        self.clean_question_name_and_answer_type(row)
        AnswerTypeValidator.apply_answer_type_aware_defaults(row)
        OptionsValidator.clean_options_field(row)
        AVPTValidator.apply_avpt_conditional_logic(row)
        self.clean_numeric_and_rating_fields(row)
        NumericValidator.validate_numeric_values(row)
        AnswerTypeValidator.check_answertype_fields(row)
        OptionsValidator.validate_options_values(row)
        self.set_alert_on_value(row)
        self.check_unique_record(row)
        super().before_import_row(row, **kwargs)

    def check_required_fields(self, row):
        """
        Validate that required fields are present and non-empty.

        Required fields:
        - Answer Type*: Type of answer expected
        - Question Name*: Name of the question
        - Client*: Business unit the question belongs to

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If any required field is missing or empty
        """
        required_fields = ["Answer Type*", "Question Name*", "Client*"]
        for field in required_fields:
            if row.get(field) in ["", None]:
                raise ValidationError({field: f"{field} is a required field"})

    def clean_question_name_and_answer_type(self, row):
        """
        Clean and normalize Question Name and Answer Type strings.

        - Question Name: Trims whitespace, removes special characters
        - Answer Type: Converts to uppercase code format

        Args:
            row: Dictionary containing import row data

        Modifies row in-place to clean string fields.
        """
        row["Question Name*"] = clean_string(row.get("Question Name*"))
        row["Answer Type*"] = clean_string(row.get("Answer Type*"), code=True)

    def clean_numeric_and_rating_fields(self, row):
        """
        Clean numeric fields for NUMERIC and RATING answer types.

        For NUMERIC/RATING types:
        - Options is set to None (not applicable)
        - Min/Max/Alert Below/Alert Above are converted to float

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If Min/Max conversion fails for NUMERIC/RATING
        """
        answer_type = row.get("Answer Type*")
        if answer_type in ["NUMERIC", "RATING"]:
            row["Options"] = None
            NumericValidator.convert_to_float(row, "Min")
            NumericValidator.convert_to_float(row, "Max")
            NumericValidator.convert_to_float(row, "Alert Below")
            NumericValidator.convert_to_float(row, "Alert Above")

    def set_alert_on_value(self, row):
        """
        Auto-generate Alert On value for NUMERIC types.

        For NUMERIC answer types with both Alert Below and Alert Above:
        - Alert On = "<{alert_below}, >{alert_above}"
        - Example: "<20, >80" means alert if value < 20 or > 80

        Args:
            row: Dictionary containing import row data

        Modifies row in-place to set Alert On field.
        """
        if row.get("Answer Type*") == "NUMERIC":
            alert_below = row.get("Alert Below")
            alert_above = row.get("Alert Above")
            if alert_above and alert_below:
                row["Alert On"] = f"<{alert_below}, >{alert_above}"

    def check_unique_record(self, row):
        """
        Validate uniqueness constraint for Question records.

        Uniqueness constraint: (quesname, answertype, client) must be unique.
        Prevents duplicate questions with same name and type for same client.

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If record with same (quesname, answertype, client) exists
        """
        if (
            Question.objects.select_related()
            .filter(
                quesname=row["Question Name*"],
                answertype=row["Answer Type*"],
                client__bucode=row["Client*"],
            )
            .exists()
        ):
            values = [str(value) if value is not None else "" for value in row.values()]
            raise ValidationError(
                f"Record with these values already exists: {', '.join(values)}"
            )

    def before_save_instance(self, instance, row, **kwargs):
        """
        Apply instance-level defaults and system values before saving.

        System defaults:
        - tenant_id: Default to 1 if not set
        - category_id: Default to NONE TypeAssist (ID 1) if not set
        - unit_id: Default to NONE TypeAssist (ID 1) if not set
        - avpttype: Default to "NONE" if not set

        Answer-Type-Specific Defaults:
        - Non-Numeric Types (SINGLELINE, MULTILINE, DATE, TIME, etc.):
          - options: "NONE"
          - alerton: "NONE"
          - min: -1 (not applicable)
          - max: -1 (not applicable)
        - Numeric Types (NUMERIC, RATING):
          - options: "NONE"
          - min/max: Keep validated values
        - Choice Types (CHECKBOX, DROPDOWN, MULTISELECT):
          - min: -1 (not applicable)
          - max: -1 (not applicable)
          - alerton: "NONE"

        Args:
            instance: Question model instance to be saved
            row: Dictionary containing import row data
            **kwargs: Additional keyword arguments
        """
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        utils.save_common_stuff(self.request, instance, self.is_superuser)

        # Category/Unit defaults to NONE TypeAssist or ID = 1
        if not instance.category_id:
            try:
                none_typeassist = get_or_create_none_typeassist()[0]
                instance.category_id = none_typeassist.id if none_typeassist else 1
            except (ValueError, TypeError, AttributeError):
                instance.category_id = 1

        if not instance.unit_id:
            try:
                none_typeassist = get_or_create_none_typeassist()[0]
                instance.unit_id = none_typeassist.id if none_typeassist else 1
            except (ValueError, TypeError, AttributeError):
                instance.unit_id = 1

        # AVPT Type system default
        if not instance.avpttype or instance.avpttype == "":
            instance.avpttype = "NONE"

        # Answer-Type-Specific Instance Defaults
        answer_type = instance.answertype

        # Non-Numeric Types
        if answer_type in ["SINGLELINE", "MULTILINE", "DATE", "TIME", "SIGNATURE", "EMAILID", "PEOPLELIST", "SITELIST", "METERREADING"]:
            if not instance.options or instance.options == "":
                instance.options = "NONE"
            if not instance.alerton or instance.alerton == "":
                instance.alerton = "NONE"
            if instance.min is None:
                instance.min = -1
            if instance.max is None:
                instance.max = -1

        # Numeric Types
        elif answer_type in ["NUMERIC", "RATING"]:
            if not instance.options or instance.options == "":
                instance.options = "NONE"
            # Keep valid Min/Max values from validation

        # Choice Types
        elif answer_type in ["CHECKBOX", "DROPDOWN", "MULTISELECT"]:
            if instance.min is None:
                instance.min = -1
            if instance.max is None:
                instance.max = -1
            if not instance.alerton or instance.alerton == "":
                instance.alerton = "NONE"
