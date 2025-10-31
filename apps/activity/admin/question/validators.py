"""
Shared Validation Logic for Question Resources.

Contains reusable validation methods extracted from all resource classes.
All validators are stateless classes with static methods.

Extracted from: apps/activity/admin/question_admin.py (validation methods)
Date: 2025-10-10
"""

from math import isnan
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

# Import dependencies
from apps.service.validators import clean_string

# Constants
AUTHORIZED_ANSWER_TYPES = [
    "DATE",
    "CHECKBOX",
    "MULTISELECT",
    "DROPDOWN",
    "EMAILID",
    "MULTILINE",
    "NUMERIC",
    "SIGNATURE",
    "SINGLELINE",
    "TIME",
    "RATING",
    "PEOPLELIST",
    "SITELIST",
    "METERREADING",
]


class NaNHandler:
    """
    Handles NaN (Not-a-Number) values from Excel/CSV imports.

    Converts NaN values to appropriate defaults based on field type:
    - Numeric fields: None
    - Text fields: None
    - Boolean fields: True/False based on field semantics
    """

    @staticmethod
    def handle_nan_values(row):
        """
        Clean NaN values from all fields in the row.

        Args:
            row: Dictionary containing import row data

        Modifies row in-place by replacing NaN values with appropriate defaults.
        """
        # Handle numeric fields
        numeric_fields = ["Min", "Max", "Alert Below", "Alert Above"]
        for field in numeric_fields:
            value = row.get(field)
            if value is None or value == "NONE" or value == "":
                row[field] = None
                continue
            try:
                # Check for NaN values from pandas
                if hasattr(value, '__iter__') and str(value).lower() == 'nan':
                    row[field] = None
                    continue
                if isinstance(value, float) and isnan(value):
                    row[field] = None
                    continue
                row[field] = float(value)  # Convert valid numbers
            except (ValueError, TypeError):
                row[field] = None  # Replace invalid values with None

        # Handle text fields that might have NaN values
        text_fields = ["Options", "Alert On", "AVPT Type", "Category", "Unit"]
        for field in text_fields:
            value = row.get(field)
            if value is None or value == "" or str(value).lower() == 'nan':
                row[field] = None
                continue
            try:
                if isinstance(value, float) and isnan(value):
                    row[field] = None
                    continue
            except (ValueError, TypeError):
                pass  # Keep the original value if it's not a problematic float

        # Handle boolean fields
        boolean_fields = ["Enable", "Is AVPT", "Is WorkFlow", "Is Mandatory"]
        for field in boolean_fields:
            value = row.get(field)
            if value is None or value == "" or str(value).lower() == 'nan':
                if field == "Enable":
                    row[field] = True  # Default enabled
                elif field == "Is AVPT":
                    row[field] = False  # Default not AVPT
                elif field == "Is WorkFlow":
                    row[field] = False  # Default not workflow
                elif field == "Is Mandatory":
                    row[field] = True  # Default mandatory
                continue
            try:
                if isinstance(value, float) and isnan(value):
                    if field == "Enable":
                        row[field] = True
                    elif field == "Is Mandatory":
                        row[field] = True
                    else:
                        row[field] = False
                    continue
            except (ValueError, TypeError):
                pass


class AnswerTypeValidator:
    """
    Validates answer types and applies type-specific defaults.

    Answer types determine what kind of data a question expects:
    - NUMERIC/RATING: Require Min/Max, Options set to "NONE"
    - SINGLELINE/MULTILINE: Text fields, Min/Max = -1
    - DATE/TIME/etc: Special types, Min/Max = -1
    - CHECKBOX/DROPDOWN/MULTISELECT: Choice types, require Options
    """

    @staticmethod
    def check_answertype_fields(row):
        """
        Validate that answer type is in the authorized list.

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If answer type is not authorized
        """
        # Handle both create and update field names
        answer_type_key = "Answer Type*" if "Answer Type*" in row else "Answer Type"
        answer_type_val = row.get(answer_type_key)

        if answer_type_val and answer_type_val not in AUTHORIZED_ANSWER_TYPES:
            raise ValidationError(
                {
                    answer_type_val: f"{answer_type_val} is not a valid AnswerType. Please select a valid AnswerType."
                }
            )

    @staticmethod
    def apply_answer_type_aware_defaults(row):
        """
        Apply defaults based on answer type according to documentation.

        Args:
            row: Dictionary containing import row data

        Default logic:
        - NUMERIC/RATING: Options="NONE", Min=0.0, Max=100.0
        - Text types: Options="NONE", Alert On="NONE", Min=-1, Max=-1
        - Special types: Options="NONE", Alert On="NONE", Min=-1, Max=-1
        - Choice types: Handled in clean_options_field
        """
        answer_type = row.get("Answer Type*", row.get("Answer Type", "SINGLELINE"))

        # Category 1: Numeric/Rating Types
        if answer_type in ["NUMERIC", "RATING"]:
            # Options: Always "NONE"
            if not row.get("Options") or row.get("Options") == "" or row.get("Options") is None:
                row["Options"] = "NONE"
            # Min/Max: Provide defaults if completely empty
            if not row.get("Min") or row.get("Min") == "" or row.get("Min") is None or str(row.get("Min")).lower() == 'nan':
                row["Min"] = 0.0  # Default minimum for numeric types
            if not row.get("Max") or row.get("Max") == "" or row.get("Max") is None or str(row.get("Max")).lower() == 'nan':
                row["Max"] = 100.0  # Default maximum for numeric types

        # Category 2: Text Input Types
        elif answer_type in ["SINGLELINE", "MULTILINE"]:
            if not row.get("Options") or row.get("Options") == "" or row.get("Options") is None:
                row["Options"] = "NONE"
            if not row.get("Alert On") or row.get("Alert On") == "" or row.get("Alert On") is None:
                row["Alert On"] = "NONE"
            # Min/Max: -1 for not applicable
            if not row.get("Min") or row.get("Min") == "" or row.get("Min") is None or row.get("Min") == "NONE":
                row["Min"] = -1
            if not row.get("Max") or row.get("Max") == "" or row.get("Max") is None or row.get("Max") == "NONE":
                row["Max"] = -1

        # Category 3: Special Input Types
        elif answer_type in ["DATE", "TIME", "SIGNATURE", "EMAILID", "PEOPLELIST", "SITELIST", "METERREADING"]:
            if not row.get("Options") or row.get("Options") == "" or row.get("Options") is None:
                row["Options"] = "NONE"
            if not row.get("Alert On") or row.get("Alert On") == "" or row.get("Alert On") is None:
                row["Alert On"] = "NONE"
            # Min/Max: -1 for not applicable
            if not row.get("Min") or row.get("Min") == "" or row.get("Min") is None or row.get("Min") == "NONE":
                row["Min"] = -1
            if not row.get("Max") or row.get("Max") == "" or row.get("Max") is None or row.get("Max") == "NONE":
                row["Max"] = -1

        # Category 4: Choice-Based Types (handled in clean_options_field)
        # CHECKBOX, DROPDOWN, MULTISELECT


class NumericValidator:
    """
    Validates numeric fields and ensures logical consistency.

    Validation rules:
    - Min < Alert Below < Alert Above < Max
    - NUMERIC/RATING types must have Min and Max
    - Alert thresholds are optional but must be logical if present
    """

    @staticmethod
    def validate_numeric_values(row):
        """
        Validate logical consistency of numeric fields.

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If numeric values are not logically consistent
        """
        min_value = NumericValidator.parse_float(row.get("Min"))
        max_value = NumericValidator.parse_float(row.get("Max"))
        alert_below = NumericValidator.parse_float(row.get("Alert Below"))
        alert_above = NumericValidator.parse_float(row.get("Alert Above"))

        # Enforce Min/Max if NUMERIC or RATING
        answer_type_key = "Answer Type*" if "Answer Type*" in row else "Answer Type"
        answer_type = str(row.get(answer_type_key, "")).strip().upper()

        if answer_type in ["NUMERIC", "RATING"]:
            if min_value is None or max_value is None:
                raise ValidationError("NUMERIC/RATING type must have both Min and Max values")

        # Logical consistency checks (only if values are present)
        if min_value is not None and alert_below is not None:
            if min_value > alert_below:
                raise ValidationError("Alert Below should be greater than Min")

        if max_value is not None and alert_above is not None:
            if max_value < alert_above:
                raise ValidationError("Alert Above should be smaller than Max")

        if alert_above is not None and alert_below is not None:
            if alert_above < alert_below:
                raise ValidationError("Alert Above should be greater than Alert Below")

    @staticmethod
    def convert_to_float(row, field):
        """
        Convert a field to float, handling None and validation.

        Args:
            row: Dictionary containing import row data
            field: Name of field to convert

        Raises:
            ValidationError: If Min/Max is required but missing for NUMERIC/RATING
        """
        value = row.get(field)

        # Handle None, empty string, "NONE", and nan values
        if value is None or value == "" or str(value).strip().upper() == "NONE":
            value = None
        else:
            try:
                # Check if it's a nan float
                if isinstance(value, float) and isnan(value):
                    value = None
                elif str(value).strip().lower() == 'nan':
                    value = None
                else:
                    value = float(value)
            except (ValueError, TypeError):
                value = None

        if value is not None:
            row[field] = float(value)
        else:
            row[field] = None
            # Only raise error for Min/Max if they're required for NUMERIC/RATING
            answer_type_key = "Answer Type*" if "Answer Type*" in row else "Answer Type"
            if field in ["Min", "Max"] and row.get(answer_type_key) in ["NUMERIC", "RATING"]:
                raise ValidationError(
                    f"{field} is required when Answer Type is {row.get(answer_type_key)}"
                )

    @staticmethod
    def parse_float(value):
        """
        Parse a value to float, returning None for invalid values.

        Args:
            value: Value to parse

        Returns:
            float or None
        """
        if value is None or value == "" or str(value).strip().upper() == "NONE":
            return None
        try:
            if isinstance(value, float) and isnan(value):
                return None
            elif str(value).strip().lower() == 'nan':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None


class OptionsValidator:
    """
    Validates and cleans the Options field for choice-based answer types.

    For CHECKBOX/DROPDOWN/MULTISELECT types:
    - Options must be provided (default: "Option1,Option2")
    - Duplicates are removed (case-insensitive)
    - Invalid characters are stripped
    - Minimum 2 options required
    - Maximum 100 characters per option
    """

    @staticmethod
    def clean_options_field(row):
        """
        Clean and validate options field based on answer type.

        Args:
            row: Dictionary containing import row data

        Modifies row in-place to clean and normalize options.
        """
        answer_type = row.get("Answer Type*", row.get("Answer Type", "SINGLELINE"))

        if answer_type in ["CHECKBOX", "DROPDOWN", "MULTISELECT"]:
            options = row.get("Options", "")

            # If empty, generate default options
            if not options or options == "" or options is None or str(options).lower() == 'nan':
                row["Options"] = "Option1,Option2"
            else:
                # Clean and validate provided options
                options_str = str(options).strip()
                if options_str:
                    # Split by comma and clean each option
                    option_list = [opt.strip() for opt in options_str.split(",") if opt.strip()]

                    # Remove duplicates (case-insensitive) while preserving order
                    seen = set()
                    cleaned_options = []
                    for opt in option_list:
                        opt_lower = opt.lower()
                        if opt_lower not in seen and opt:
                            seen.add(opt_lower)
                            # Validate characters - remove invalid ones
                            cleaned_opt = opt.replace("|", "").replace(";", "").replace("\n", "").replace("\r", "").replace("\t", "")
                            if len(cleaned_opt) <= 100:  # Max 100 chars per option
                                cleaned_options.append(cleaned_opt)

                    # Ensure minimum 2 options
                    if len(cleaned_options) < 2:
                        cleaned_options.extend(["Option1", "Option2"])
                        cleaned_options = cleaned_options[:2]  # Take first 2

                    row["Options"] = ",".join(cleaned_options)
                else:
                    row["Options"] = "Option1,Option2"

            # Min/Max: -1 for choice types (not applicable)
            if not row.get("Min") or row.get("Min") == "" or row.get("Min") is None or row.get("Min") == "NONE":
                row["Min"] = -1
            if not row.get("Max") or row.get("Max") == "" or row.get("Max") is None or row.get("Max") == "NONE":
                row["Max"] = -1

    @staticmethod
    def validate_options_values(row):
        """
        Validate that Options are provided for choice types and Alert On is valid.

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If Options missing for choice types or Alert On not in Options
        """
        answer_type_key = "Answer Type*" if "Answer Type*" in row else "Answer Type"
        answer_type = row.get(answer_type_key)

        if answer_type in ["CHECKBOX", "DROPDOWN"]:
            if row.get("Options") is None:
                raise ValidationError(
                    "Options is required when Answer Type is in [DROPDOWN, CHECKBOX]"
                )
            if row.get("Alert On"):
                # Convert comma-separated strings to lists for comparison
                alert_on_value = row["Alert On"]
                options_value = row["Options"]

                # Handle both string and list formats
                if isinstance(alert_on_value, str):
                    alert_on_list = [item.strip() for item in alert_on_value.split(",") if item.strip()]
                else:
                    alert_on_list = [alert_on_value] if alert_on_value else []

                if isinstance(options_value, str):
                    options_list = [item.strip() for item in options_value.split(",") if item.strip()]
                else:
                    options_list = [options_value] if options_value else []

                # Check if all alert_on items are in options
                invalid_items = [item for item in alert_on_list if item not in options_list]
                if invalid_items:
                    raise ValidationError(
                        {"Alert On": f"The following items are not in Options: {', '.join(invalid_items)}"}
                    )


class AVPTValidator:
    """
    Validates AVPT (Attachment/Photo/Video Type) fields.

    AVPT logic:
    - If Is AVPT = False, AVPT Type = "NONE"
    - If Is AVPT = True, AVPT Type must be valid (BACKCAMPIC, FRONTCAMPIC, AUDIO, VIDEO)
    - Default AVPT Type when Is AVPT = True: "BACKCAMPIC"
    """

    VALID_AVPT_TYPES = ["BACKCAMPIC", "FRONTCAMPIC", "AUDIO", "VIDEO", "NONE"]

    @staticmethod
    def apply_avpt_conditional_logic(row):
        """
        Apply AVPT (attachment) field conditional logic.

        Args:
            row: Dictionary containing import row data

        Modifies row in-place to apply AVPT business rules.
        """
        is_avpt = row.get("Is AVPT")
        avpt_type = row.get("AVPT Type")

        # Convert string representations to boolean
        if isinstance(is_avpt, str):
            is_avpt = is_avpt.lower() in ["true", "1", "yes", "on"]
        elif is_avpt is None or is_avpt == "":
            is_avpt = False

        row["Is AVPT"] = is_avpt

        # AVPT Type logic
        if not is_avpt:
            # If Is AVPT = False, AVPT Type defaults to "NONE"
            row["AVPT Type"] = "NONE"
        else:
            # If Is AVPT = True, AVPT Type is required and cannot be "NONE"
            if not avpt_type or avpt_type == "" or avpt_type is None or avpt_type == "NONE" or str(avpt_type).lower() == 'nan':
                # Default to BACKCAMPIC if AVPT is required but type not specified
                row["AVPT Type"] = "BACKCAMPIC"
            else:
                # Validate AVPT type
                if avpt_type not in AVPTValidator.VALID_AVPT_TYPES:
                    row["AVPT Type"] = "BACKCAMPIC"  # Default to valid type

    @staticmethod
    def check_AVPT_fields(row):
        """
        Validate that AVPT Type is in the valid list.

        Args:
            row: Dictionary containing import row data

        Raises:
            ValidationError: If AVPT Type is not valid
        """
        avpt_type = row.get("AVPT Type")
        if avpt_type and avpt_type != "NONE":
            if avpt_type not in AVPTValidator.VALID_AVPT_TYPES:
                raise ValidationError(
                    {
                        avpt_type: f"{avpt_type} is not a valid AVPT Type. Please select a valid AVPT Type from {AVPTValidator.VALID_AVPT_TYPES}"
                    }
                )
