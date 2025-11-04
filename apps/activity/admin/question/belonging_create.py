"""
QuestionSetBelonging CREATE Resource for Django Admin Import/Export.

Handles creation of new QuestionSetBelonging records (Question-QuestionSet mappings).
Import template: Question Name*, Question Set*, Client*, Site*, Answer Type*, etc.

Special Features:
- Complex foreign key relationships (Question + QuestionSet)
- AVPT field validation with conditional logic
- Uniqueness across 4 fields (qset + question + client + site)
- Answer type-specific defaults

Extracted from: apps/activity/admin/question_admin.py (lines 1012-1368)
Date: 2025-10-10
"""

import logging
from django.core.exceptions import ValidationError
from import_export import fields, resources
from import_export import widgets as wg

from apps.activity.models.question_model import QuestionSetBelonging, QuestionSet, Question
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from apps.core import utils
from apps.service.validators import clean_string

from .base import default_ta, get_or_create_none_qset, get_or_create_none_question, get_or_create_none_bv, AUTHORIZED_ANSWER_TYPES, VALID_AVPT_TYPES
from .widgets import QsetFKW, QuesFKW

logger = logging.getLogger(__name__)


class QuestionSetBelongingResource(resources.ModelResource):
    """
    Import/Export Resource for QuestionSetBelonging CREATE operations.

    Handles:
    - Foreign key validation for Question, QuestionSet, Client, Site
    - NaN value handling for all field types (text, numeric, boolean)
    - Answer type-specific field defaults (Options, Min/Max, Alert On)
    - AVPT field validation (5 valid types)
    - Uniqueness validation (qset + question + client + site)
    - Numeric field validation (Min < Alert Below < Alert Above < Max)

    Import Template Columns (9 required, 10 optional):
    Required:
    - Question Name* (Foreign Key to Question)
    - Question Set* (Foreign Key to QuestionSet)
    - Client* (Foreign Key to Bt)
    - Site* (Foreign Key to Bt)
    - Answer Type* (14 valid types from AUTHORIZED_ANSWER_TYPES)
    - Seq No* (Integer, sequence order)

    Optional:
    - Is AVPT (Boolean, default False)
    - AVPT Type (Text, default "NONE", validated against VALID_AVPT_TYPES)
    - Is Mandatory (Boolean, default True)
    - Min (Float, for NUMERIC/RATING types)
    - Max (Float, for NUMERIC/RATING types)
    - Alert Below (Float, for NUMERIC types)
    - Alert Above (Float, for NUMERIC types)
    - Alert On (Text, auto-generated for NUMERIC or manual for CHECKBOX/DROPDOWN)
    - Options (Text, comma-separated, required for CHECKBOX/DROPDOWN)
    """

    Name = fields.Field(
        column_name="Question Name*",
        attribute="question",
        widget=QuesFKW(Question, "quesname"),
        saves_null_values=True,
        default=get_or_create_none_question,
    )
    QSET = fields.Field(
        column_name="Question Set*",
        attribute="qset",
        widget=QsetFKW(QuestionSet, "qsetname"),
        saves_null_values=True,
        default=get_or_create_none_qset,
    )

    CLIENT = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )

    BV = fields.Field(
        column_name="Site*",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )

    ANSTYPE = fields.Field(attribute="answertype", column_name="Answer Type*")
    id = fields.Field(attribute="id", column_name="ID")
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No*")
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
        super(QuestionSetBelongingResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        """
        Main validation pipeline executed before each row import.

        Processing Order:
        1. check_required_fields() - Validate all required fields present
        2. handle_nan_values() - Convert NaN to None for all field types
        3. set_default_values() - Apply system defaults (AVPT Type, Is AVPT, Is Mandatory)
        4. clean_question_name_and_answer_type() - Clean text fields
        5. clean_numeric_and_rating_fields() - Clean and convert numeric fields
        6. validate_numeric_values() - Logical consistency checks
        7. validate_options_values() - Options validation for CHECKBOX/DROPDOWN
        8. set_alert_on_value() - Auto-generate Alert On for NUMERIC types
        9. check_unique_record() - Uniqueness validation
        10. check_AVPT_fields() - AVPT type validation
        11. check_answertype_fields() - Answer type validation
        """
        self.check_required_fields(row)
        self.handle_nan_values(row)  # Add nan handling
        self.set_default_values(row)  # Set defaults per documentation
        self.clean_question_name_and_answer_type(row)
        self.clean_numeric_and_rating_fields(row)
        self.validate_numeric_values(row)
        self.validate_options_values(row)
        self.set_alert_on_value(row)
        self.check_unique_record(row)
        self.check_AVPT_fields(row)
        self.check_answertype_fields(row)
        super().before_import_row(row, **kwargs)

    def handle_nan_values(self, row):
        """
        Handle nan values in all fields.

        Processes three categories of fields:
        1. Text fields: Options, Alert On, AVPT Type → None
        2. Numeric fields: Min, Max, Alert Below, Alert Above → None
        3. Boolean fields: Is AVPT (→False), Is Mandatory (→True)
        """
        import math

        # Handle text fields that might have nan
        text_fields = ["Options", "Alert On", "AVPT Type"]
        for field in text_fields:
            value = row.get(field)
            if value is None or value == "":
                continue
            try:
                if isinstance(value, float) and math.isnan(value):
                    row[field] = None
                elif str(value).strip().lower() == 'nan':
                    row[field] = None
            except (ValueError, TypeError):
                pass

        # Handle numeric fields
        numeric_fields = ["Min", "Max", "Alert Below", "Alert Above"]
        for field in numeric_fields:
            value = row.get(field)
            if value is None or value == "":
                continue
            try:
                if isinstance(value, float) and math.isnan(value):
                    row[field] = None
                elif str(value).strip().lower() == 'nan':
                    row[field] = None
            except (ValueError, TypeError):
                pass

        # Handle boolean fields
        boolean_fields = ["Is AVPT", "Is Mandatory"]
        for field in boolean_fields:
            value = row.get(field)
            if value is None or value == "":
                continue
            try:
                if isinstance(value, float) and math.isnan(value):
                    if field == "Is Mandatory":
                        row[field] = True  # Default to mandatory
                    else:
                        row[field] = False  # Default to not AVPT
                elif str(value).strip().lower() == 'nan':
                    if field == "Is Mandatory":
                        row[field] = True
                    else:
                        row[field] = False
            except (ValueError, TypeError):
                pass

    def set_default_values(self, row):
        """
        Set default values according to documentation.

        System Defaults:
        - AVPT Type: "NONE" if empty
        - Is AVPT: False if empty
        - Is Mandatory: True if empty
        - Options: "NONE" for non-numeric types if empty
        - Alert On: "NONE" for non-numeric types if empty
        """
        # AVPT Type: Default to "NONE" if empty
        if not row.get("AVPT Type") or row.get("AVPT Type") is None:
            row["AVPT Type"] = "NONE"

        # Is AVPT: Default to False
        if row.get("Is AVPT") is None or row.get("Is AVPT") == "":
            row["Is AVPT"] = False

        # Is Mandatory: Default to True
        if row.get("Is Mandatory") is None or row.get("Is Mandatory") == "":
            row["Is Mandatory"] = True

        # Handle Options and Alert On based on Answer Type (will be refined in other methods)
        answer_type = row.get("Answer Type*")
        if answer_type not in ["NUMERIC", "RATING"]:
            # Options: Default to "NONE" for non-numeric types if empty
            if not row.get("Options") or row.get("Options") is None:
                row["Options"] = "NONE"
            # Alert On: Default to "NONE" for non-numeric types if empty
            if not row.get("Alert On") or row.get("Alert On") is None:
                row["Alert On"] = "NONE"

    def check_AVPT_fields(self, row):
        """
        Validate AVPT Type field against VALID_AVPT_TYPES.

        Valid Values: BACKCAMPIC, FRONTCAMPIC, AUDIO, VIDEO, NONE
        Raises: ValidationError if invalid AVPT Type
        """
        avpt_type = row.get("AVPT Type")
        if avpt_type and avpt_type != "NONE":
            if avpt_type not in VALID_AVPT_TYPES:
                raise ValidationError(
                    {
                        avpt_type: "%(type)s is not a valid AVPT Type. Please select a valid AVPT Type from %(valid)s"
                        % {"type": avpt_type, "valid": VALID_AVPT_TYPES}
                    }
                )

    def check_required_fields(self, row):
        """
        Validate presence of all required fields.

        Required Fields:
        - Answer Type*
        - Question Name*
        - Question Set*
        - Client*
        - Site*
        """
        required_fields = [
            "Answer Type*",
            "Question Name*",
            "Question Set*",
            "Client*",
            "Site*",
        ]
        for field in required_fields:
            if row.get(field) in ["", None]:
                raise ValidationError(f"{field} is a required field")

    def clean_question_name_and_answer_type(self, row):
        """
        Clean text fields using service layer validators.

        - Question Name: Standard string cleaning
        - Answer Type: Code-style cleaning (uppercase)
        """
        row["Question Name*"] = clean_string(row.get("Question Name*"))
        row["Answer Type*"] = clean_string(row.get("Answer Type*"), code=True)

    def clean_numeric_and_rating_fields(self, row):
        """
        Process numeric fields for NUMERIC and RATING answer types.

        For NUMERIC/RATING:
        - Options → None
        - Min → float (required)
        - Max → float (required)
        - Alert Below → float (optional)
        - Alert Above → float (optional)
        """
        answer_type = row.get("Answer Type*")
        if answer_type in ["NUMERIC", "RATING"]:
            row["Options"] = None
            self.convert_to_float(row, "Min")
            self.convert_to_float(row, "Max")
            self.convert_to_float(row, "Alert Below")
            self.convert_to_float(row, "Alert Above")

    def convert_to_float(self, row, field):
        """
        Convert field value to float with comprehensive NaN handling.

        Conversion Rules:
        - None/empty/"NONE" → None
        - NaN float → None
        - "nan" string → None
        - Valid number → float

        Raises: ValidationError if Min/Max required but missing
        """
        import math
        value = row.get(field)

        # Handle None, empty string, "NONE", and nan values
        if value is None or value == "" or str(value).strip().upper() == "NONE":
            value = None
        else:
            try:
                # Check if it's a nan float
                if isinstance(value, float) and math.isnan(value):
                    value = None
                elif str(value).strip().lower() == 'nan':
                    value = None
                else:
                    value = float(value)
            except (ValueError, TypeError):
                value = None

        logger.debug("Value: %s %s", value, type(value))
        if value is not None:
            row[field] = float(value)
        else:
            row[field] = None
            # Only raise error for Min/Max if they're required for NUMERIC/RATING
            if field in ["Min", "Max"] and row.get("Answer Type*") in ["NUMERIC", "RATING"]:
                raise ValidationError(
                    f"{field} is required when Answer Type* is {row.get('Answer Type*')}"
                )

    def parse_float(self, value):
        """
        Helper to safely parse float values with NaN handling.

        Returns:
            float or None: Parsed value or None if invalid/NaN
        """
        import math
        if value is None or value == "" or str(value).strip().upper() == "NONE":
            return None
        try:
            if isinstance(value, float) and math.isnan(value):
                return None
            elif str(value).strip().lower() == 'nan':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def validate_numeric_values(self, row):
        """
        Validate logical consistency of numeric fields.

        Validation Rules:
        1. NUMERIC/RATING types MUST have both Min and Max
        2. Min < Alert Below (if Alert Below present)
        3. Alert Above < Max (if Alert Above present)
        4. Alert Below < Alert Above (if both present)

        Raises: ValidationError on any violation
        """
        answer_type = str(row.get("Answer Type*")).strip().upper()

        min_value = self.parse_float(row.get("Min"))
        max_value = self.parse_float(row.get("Max"))
        alert_below = self.parse_float(row.get("Alert Below"))
        alert_above = self.parse_float(row.get("Alert Above"))

        # Enforce Min/Max if NUMERIC
        if answer_type == "NUMERIC" or answer_type == "RATING":
            if min_value is None or max_value is None:
                raise ValidationError("NUMERIC type must have both Min and Max values")

        # Logical consistency checks (only if values are present)
        if (
            min_value is not None
            and alert_below is not None
            and min_value > alert_below
        ):
            raise ValidationError("Min should be smaller than Alert Below")
        if (
            max_value is not None
            and alert_above is not None
            and max_value < alert_above
        ):
            raise ValidationError("Max should be greater than Alert Above")
        if (
            alert_above is not None
            and alert_below is not None
            and alert_above < alert_below
        ):
            raise ValidationError("Alert Above should be greater than Alert Below")

    def set_alert_on_value(self, row):
        """
        Auto-generate Alert On field for NUMERIC answer types.

        Format: "<{alert_below}, >{alert_above}"
        Example: "<10, >90" means alert if value < 10 or > 90

        Only applies when both Alert Below and Alert Above are present.
        """
        if row.get("Answer Type*") == "NUMERIC":
            alert_below = row.get("Alert Below")
            alert_above = row.get("Alert Above")
            if alert_above and alert_below:
                row["Alert On"] = f"<{alert_below}, >{alert_above}"

    def check_unique_record(self, row):
        """
        Validate uniqueness across 4-field composite key.

        Uniqueness Constraint:
        - Question Set (qset)
        - Question Name (question)
        - Client
        - Site

        Raises: ValidationError if duplicate found
        """
        if (
            QuestionSetBelonging.objects.select_related()
            .filter(
                qset__qsetname=row["Question Set*"],
                question__quesname=row["Question Name*"],
                client__bucode=row["Client*"],
                bu__bucode=row["Site*"],
            )
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exists: {row.values()}"
            )

    def check_answertype_fields(self, row):
        """
        Validate Answer Type against AUTHORIZED_ANSWER_TYPES.

        Valid Types (14):
        DATE, CHECKBOX, MULTISELECT, DROPDOWN, EMAILID, MULTILINE,
        NUMERIC, SIGNATURE, SINGLELINE, TIME, RATING, PEOPLELIST,
        SITELIST, METERREADING

        Raises: ValidationError if invalid Answer Type
        """
        Answer_type_val = row.get("Answer Type*")
        if Answer_type_val not in AUTHORIZED_ANSWER_TYPES:
            raise ValidationError(
                {
                    Answer_type_val: f"{Answer_type_val} is a not a valid Answertype.Please select a valid AnswerType."
                }
            )

    def validate_options_values(self, row):
        """
        Validate Options field for choice-based answer types.

        For CHECKBOX/DROPDOWN:
        - Options is REQUIRED
        - Alert On (if present) must be in Options

        Raises: ValidationError if validation fails
        """
        if row["Answer Type*"] in ["CHECKBOX", "DROPDOWN"]:
            if row.get("Options") is None:
                raise ValidationError(
                    "Options is required when Answer Type* is in [DROPDOWN, CHECKBOX]"
                )
            if row.get("Alert On") and row["Alert On"] not in row["Options"]:
                raise ValidationError("Alert On needs to be in Options")

    def before_save_instance(self, instance, row, **kwargs):
        """
        Apply instance-level defaults before saving.

        System Defaults Applied:
        - tenant_id: 1 (default tenant)
        - AVPT Type: "NONE" if empty
        - Options: "NONE" for non-numeric types if empty
        - Alert On: "NONE" for non-numeric types if empty

        Also calls: utils.save_common_stuff() for audit fields
        """
        # Set tenant_id to 1 as default if not already set
        if not hasattr(instance, 'tenant_id') or instance.tenant_id is None:
            instance.tenant_id = 1

        # Set system defaults according to documentation
        # AVPT Type: Default to "NONE" if empty
        if not instance.avpttype or instance.avpttype == "":
            instance.avpttype = "NONE"

        # Options: Default to "NONE" if empty (for non-numeric types)
        if instance.answertype not in ["NUMERIC", "RATING"]:
            if not instance.options or instance.options == "":
                instance.options = "NONE"

        # Alert On: Default to "NONE" if empty (for non-numeric types)
        if instance.answertype not in ["NUMERIC", "RATING"]:
            if not instance.alerton or instance.alerton == "":
                instance.alerton = "NONE"

        utils.save_common_stuff(self.request, instance, self.is_superuser)
