"""
Shared Base Classes and Helpers for Question Admin.

Constants and utilities used across all question resource classes.
Extracted from: apps/activity/admin/question_admin.py (lines 30-32, constants)
Date: 2025-10-10

This module provides:
- Authorized answer types constant (14 types)
- Authorized questionset types constant (11 types)
- Valid AVPT types constant (5 types)
- Helper function for default TypeAssist values
"""

from apps.core.utils_new.db_utils import (
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_qset,
    get_or_create_none_question,
)


# Authorized Answer Types (14 types)
# Used in: QuestionResource, QuestionSetBelongingResource, QuestionResourceUpdate
# Used for validation in check_answertype_fields() methods
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


# Authorized QuestionSet Types (11 types)
# Used in: QuestionSetResource, QuestionSetResourceUpdate
# Used for validation in verify_valid_questionset_type() methods
AUTHORIZED_QUESTIONSET_TYPES = [
    "CHECKLIST",
    "RPCHECKLIST",
    "INCIDENTREPORT",
    "SITEREPORT",
    "WORKPERMIT",
    "RETURN_WORK_PERMIT",
    "KPITEMPLATE",
    "SCRAPPEDTEMPLATE",
    "ASSETAUDIT",
    "ASSETMAINTENANCE",
    "WORK_ORDER",
]


# Valid AVPT (Audio/Video/Photo Attachment) Types (5 types)
# Used in: QuestionSetBelongingResource
# Used for validation in check_AVPT_fields() method
VALID_AVPT_TYPES = ["BACKCAMPIC", "FRONTCAMPIC", "AUDIO", "VIDEO", "NONE"]


def default_ta():
    """
    Get or create NONE TypeAssist default.

    Used as default value for Unit and Category fields in Question resources.
    This function returns the TypeAssist instance with tacode='NONE', creating
    it if it doesn't exist in the database.

    Returns:
        TypeAssist: The first element of the tuple (TypeAssist instance with tacode='NONE').

    Usage:
        Unit = fields.Field(
            column_name="Unit",
            attribute="unit",
            widget=EnabledTypeAssistWidget(TypeAssist, "tacode"),
            saves_null_values=True,
            default=default_ta,  # Uses this function
        )
    """
    return get_or_create_none_typeassist()[0]
