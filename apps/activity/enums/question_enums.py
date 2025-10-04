"""
Centralized Question/QuestionSet Enumerations.

This module consolidates all enums previously scattered across Question and
QuestionSetBelonging models, providing a single source of truth and helper methods.

Following .claude/rules.md:
- Rule #7: Avoid code duplication
- Rule #4: Use small functions
- Rule #3: Self-documenting code patterns

Created: 2025-10-03
Author: Claude Code
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from typing import Set, List


class AnswerType(models.TextChoices):
    """
    Unified answer type enumeration for Questions and QuestionSetBelonging.

    Consolidates previously duplicated enums from both models.
    Covers all input types supported by the mobile and web frontends.
    """

    # Text input types
    SINGLELINE = "SINGLELINE", _("Single Line")
    MULTILINE = "MULTILINE", _("Multiline")
    EMAILID = "EMAILID", _("Email ID")

    # Numeric types
    NUMERIC = "NUMERIC", _("Numeric")
    RATING = "RATING", _("Rating")
    METERREADING = "METERREADING", _("Meter Reading")

    # Choice types
    CHECKBOX = "CHECKBOX", _("Checkbox")
    DROPDOWN = "DROPDOWN", _("Dropdown")
    MULTISELECT = "MULTISELECT", _("Multi Select")

    # Date/Time types
    DATE = "DATE", _("Date")
    TIME = "TIME", _("Time")

    # Special types
    SIGNATURE = "SIGNATURE", _("Signature")
    PEOPLELIST = "PEOPLELIST", _("People List")
    SITELIST = "SITELIST", _("Site List")
    GPSLOCATION = "GPSLOCATION", _("GPS Location")

    # DEPRECATED: Camera types (now handled by AvptType)
    # Kept for backward compatibility with existing QuestionSetBelonging records
    BACKCAMERA = "BACKCAMERA", _("Back Camera (Deprecated - use AVPT)")
    FRONTCAMERA = "FRONTCAMERA", _("Front Camera (Deprecated - use AVPT)")

    # Special value for none/unknown
    NONE = "NONE", _("None")

    @classmethod
    def requires_options(cls) -> Set[str]:
        """
        Answer types that require options to be defined.

        Returns:
            Set of answer type values that must have options
        """
        return {
            cls.CHECKBOX,
            cls.DROPDOWN,
            cls.MULTISELECT,
        }

    @classmethod
    def requires_min_max(cls) -> Set[str]:
        """
        Answer types that require min/max values.

        Returns:
            Set of answer type values that must have min/max
        """
        return {
            cls.NUMERIC,
            cls.RATING,
            cls.METERREADING,
        }

    @classmethod
    def is_numeric_type(cls, value: str) -> bool:
        """
        Check if answer type is numeric.

        Args:
            value: Answer type value to check

        Returns:
            True if numeric type requiring min/max
        """
        return value in cls.requires_min_max()

    @classmethod
    def is_choice_type(cls, value: str) -> bool:
        """
        Check if answer type requires choice options.

        Args:
            value: Answer type value to check

        Returns:
            True if choice type requiring options
        """
        return value in cls.requires_options()

    @classmethod
    def is_deprecated(cls, value: str) -> bool:
        """
        Check if answer type is deprecated.

        Args:
            value: Answer type value to check

        Returns:
            True if deprecated (camera types)
        """
        return value in {cls.BACKCAMERA, cls.FRONTCAMERA}

    @classmethod
    def supports_alerts(cls) -> Set[str]:
        """
        Answer types that support alert configuration.

        Returns:
            Set of answer types supporting alerts
        """
        return {
            cls.NUMERIC,
            cls.RATING,
            cls.METERREADING,
            cls.CHECKBOX,
            cls.DROPDOWN,
            cls.MULTISELECT,
        }

    @classmethod
    def mobile_supported_types(cls) -> List[str]:
        """
        Answer types supported by Android/Kotlin mobile app.

        Returns:
            List of mobile-compatible answer types
        """
        return [
            cls.SINGLELINE,
            cls.MULTILINE,
            cls.EMAILID,
            cls.NUMERIC,
            cls.RATING,
            cls.CHECKBOX,
            cls.DROPDOWN,
            cls.MULTISELECT,
            cls.DATE,
            cls.TIME,
            cls.SIGNATURE,
            cls.PEOPLELIST,
            cls.SITELIST,
            cls.GPSLOCATION,
            cls.METERREADING,
        ]


class AvptType(models.TextChoices):
    """
    Attachment/Verification/Photo/Text (AVPT) type enumeration.

    Defines types of media attachments that can be required for questions.
    Used by both Question and QuestionSetBelonging models.
    """

    # Camera types
    BACKCAMPIC = "BACKCAMPIC", _("Back Camera Pic")
    FRONTCAMPIC = "FRONTCAMPIC", _("Front Camera Pic")

    # Media types
    AUDIO = "AUDIO", _("Audio")
    VIDEO = "VIDEO", _("Video")

    # No attachment required
    NONE = "NONE", _("None")

    @classmethod
    def is_camera_type(cls, value: str) -> bool:
        """Check if AVPT type is a camera type."""
        return value in {cls.BACKCAMPIC, cls.FRONTCAMPIC}

    @classmethod
    def is_media_type(cls, value: str) -> bool:
        """Check if AVPT type is audio/video media."""
        return value in {cls.AUDIO, cls.VIDEO}

    @classmethod
    def requires_device_permission(cls, value: str) -> bool:
        """Check if AVPT type requires device permissions on mobile."""
        return value != cls.NONE


class ConditionalOperator(models.TextChoices):
    """
    Operators for conditional display logic in QuestionSetBelonging.

    Used in display_conditions field to determine when to show/hide questions
    based on answers to previous questions.
    """

    # Equality operators
    EQUALS = "EQUALS", _("Equals")
    NOT_EQUALS = "NOT_EQUALS", _("Not Equals")

    # Containment operators
    CONTAINS = "CONTAINS", _("Contains")
    NOT_CONTAINS = "NOT_CONTAINS", _("Does Not Contain")
    IN = "IN", _("In List")
    NOT_IN = "NOT_IN", _("Not In List")

    # Comparison operators (for numeric types)
    GREATER_THAN = "GT", _("Greater Than")
    GREATER_THAN_OR_EQUAL = "GTE", _("Greater Than or Equal")
    LESS_THAN = "LT", _("Less Than")
    LESS_THAN_OR_EQUAL = "LTE", _("Less Than or Equal")

    # Special operators
    IS_EMPTY = "IS_EMPTY", _("Is Empty")
    IS_NOT_EMPTY = "IS_NOT_EMPTY", _("Is Not Empty")

    @classmethod
    def numeric_operators(cls) -> Set[str]:
        """Operators valid for numeric question types."""
        return {
            cls.EQUALS,
            cls.NOT_EQUALS,
            cls.GREATER_THAN,
            cls.GREATER_THAN_OR_EQUAL,
            cls.LESS_THAN,
            cls.LESS_THAN_OR_EQUAL,
            cls.IS_EMPTY,
            cls.IS_NOT_EMPTY,
        }

    @classmethod
    def text_operators(cls) -> Set[str]:
        """Operators valid for text question types."""
        return {
            cls.EQUALS,
            cls.NOT_EQUALS,
            cls.CONTAINS,
            cls.NOT_CONTAINS,
            cls.IS_EMPTY,
            cls.IS_NOT_EMPTY,
        }

    @classmethod
    def choice_operators(cls) -> Set[str]:
        """Operators valid for choice question types (dropdown, checkbox)."""
        return {
            cls.EQUALS,
            cls.NOT_EQUALS,
            cls.IN,
            cls.NOT_IN,
            cls.IS_EMPTY,
            cls.IS_NOT_EMPTY,
        }

    @classmethod
    def validate_for_answer_type(cls, operator: str, answer_type: str) -> bool:
        """
        Validate if operator is compatible with answer type.

        Args:
            operator: Conditional operator value
            answer_type: Answer type value

        Returns:
            True if operator is valid for this answer type
        """
        if AnswerType.is_numeric_type(answer_type):
            return operator in cls.numeric_operators()
        elif AnswerType.is_choice_type(answer_type):
            return operator in cls.choice_operators()
        else:
            return operator in cls.text_operators()


class QuestionSetType(models.TextChoices):
    """
    Types of question sets supported by the system.

    Standardized casing and labels for better consistency.
    """

    # Asset management
    ASSET = "ASSET", _("Asset")
    CHECKPOINT = "CHECKPOINT", _("Checkpoint")
    ASSETAUDIT = "ASSETAUDIT", _("Asset Audit")
    ASSETMAINTENANCE = "ASSETMAINTENANCE", _("Asset Maintenance")

    # Checklists
    CHECKLIST = "CHECKLIST", _("Checklist")
    RPCHECKLIST = "RPCHECKLIST", _("RP Checklist")
    QUESTIONSET = "QUESTIONSET", _("Question Set")

    # Reports
    INCIDENTREPORT = "INCIDENTREPORT", _("Incident Report")
    SITEREPORT = "SITEREPORT", _("Site Report")

    # Work management
    WORKPERMIT = "WORKPERMIT", _("Work Permit")
    RETURN_WORK_PERMIT = "RETURN_WORK_PERMIT", _("Return Work Permit")
    WORK_ORDER = "WORK_ORDER", _("Work Order")

    # Other
    KPI_TEMPLATE = "KPITEMPLATE", _("KPI Template")  # Standardized label
    SCRAPPEDTEMPLATE = "SCRAPPEDTEMPLATE", _("Scrapped Template")
    SLA_TEMPLATE = "SLA_TEMPLATE", _("Service Level Agreement")
    POSTING_ORDER = "POSTING_ORDER", _("Posting Order")
    SITESURVEY = "SITESURVEY", _("Site Survey")

    @classmethod
    def requires_asset_association(cls) -> Set[str]:
        """Question set types that require asset/checkpoint association."""
        return {
            cls.ASSET,
            cls.CHECKPOINT,
            cls.ASSETAUDIT,
            cls.ASSETMAINTENANCE,
        }

    @classmethod
    def supports_scheduling(cls) -> Set[str]:
        """Question set types that can be scheduled."""
        return {
            cls.CHECKLIST,
            cls.RPCHECKLIST,
            cls.ASSETAUDIT,
            cls.ASSETMAINTENANCE,
            cls.WORK_ORDER,
        }


# Utility functions for validation

def validate_options_for_answer_type(answer_type: str, options: str = None) -> bool:
    """
    Validate that options are provided when required.

    Args:
        answer_type: AnswerType value
        options: Options string/JSON

    Returns:
        True if valid, False otherwise
    """
    if AnswerType.is_choice_type(answer_type):
        return options is not None and len(str(options).strip()) > 0
    return True


def validate_min_max_for_answer_type(
    answer_type: str,
    min_val: float = None,
    max_val: float = None
) -> bool:
    """
    Validate that min/max are provided when required.

    Args:
        answer_type: AnswerType value
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        True if valid, False otherwise
    """
    if AnswerType.is_numeric_type(answer_type):
        return (
            min_val is not None
            and max_val is not None
            and min_val < max_val
        )
    return True


# Backward compatibility helpers

def get_legacy_answer_type_display(value: str) -> str:
    """
    Get display name for legacy camera answer types.

    Args:
        value: Answer type value

    Returns:
        Display name with deprecation warning if applicable
    """
    if value == AnswerType.BACKCAMERA:
        return "Back Camera (Deprecated - use AVPT with BACKCAMPIC)"
    elif value == AnswerType.FRONTCAMERA:
        return "Front Camera (Deprecated - use AVPT with FRONTCAMPIC)"
    else:
        return AnswerType(value).label
