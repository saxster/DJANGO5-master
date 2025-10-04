"""
GraphQL Type Definitions for Question/QuestionSet Schema.

Provides complete GraphQL SDL (Schema Definition Language) types
for the enhanced Question schema with JSON fields.

Created: 2025-10-03
For Android/Kotlin Apollo GraphQL code generation.
"""

import graphene
from graphene_django.types import DjangoObjectType
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging


# ============================================================================
# NEW TYPES (Release N)
# ============================================================================

class NumericAlertType(graphene.ObjectType):
    """
    Numeric alert configuration for min/max thresholds.

    Used in AlertConfigType for NUMERIC, RATING, METERREADING answer types.
    """
    below = graphene.Float(
        description="Alert if value is below this threshold"
    )
    above = graphene.Float(
        description="Alert if value is above this threshold"
    )


class AlertConfigType(graphene.ObjectType):
    """
    Structured alert configuration replacing text-based 'alerton' field.

    Release N: Available alongside deprecated 'alerton' text field
    Release N+1, N+2: Both fields present (dual-write)
    Release N+3: Only this field available (alerton removed)
    """
    numeric = graphene.Field(
        NumericAlertType,
        description="Numeric alert thresholds (for NUMERIC/RATING types)"
    )
    choice = graphene.List(
        graphene.String,
        description="Choice values that trigger alerts (for DROPDOWN/CHECKBOX types)"
    )
    enabled = graphene.Boolean(
        required=True,
        default_value=False,
        description="Whether alerts are enabled for this question"
    )


class ValidationWarningType(graphene.ObjectType):
    """
    Validation warning for display_conditions issues.

    NEW in Release N - May appear in get_questionset_with_conditional_logic responses.
    Informs mobile app of data integrity issues (invalid dependencies, circular refs, etc.)
    """
    question_id = graphene.Int(
        required=True,
        description="QuestionSetBelonging ID with the issue"
    )
    warning = graphene.String(
        required=True,
        description="Human-readable warning message"
    )
    severity = graphene.String(
        required=True,
        description="Severity level: 'error', 'warning', or 'critical'"
    )


class DependencyInfoType(graphene.ObjectType):
    """
    Enhanced dependency information in dependency_map.

    NEW FIELDS in Release N:
    - cascade_hide: Automatically hide dependent questions
    - group: Grouping identifier for related questions
    """
    question_id = graphene.Int(
        required=True,
        description="ID of the dependent question (QuestionSetBelonging)"
    )
    question_seqno = graphene.Int(
        required=True,
        description="Sequence number of dependent question"
    )
    operator = graphene.String(
        required=True,
        description="Conditional operator (EQUALS, GT, IN, etc.)"
    )
    values = graphene.List(
        graphene.String,
        required=True,
        description="Values to compare against"
    )
    show_if = graphene.Boolean(
        required=True,
        description="True = show when condition met, False = hide when met"
    )
    cascade_hide = graphene.Boolean(
        required=True,
        default_value=False,
        description="NEW: If true, hide all dependent questions when this is hidden"
    )
    group = graphene.String(
        description="NEW: Optional grouping identifier for related questions"
    )


class ConditionalLogicResponseType(graphene.ObjectType):
    """
    Response type for get_questionset_with_conditional_logic query.

    Enhanced in Release N with validation_warnings field.
    """
    questions = graphene.List(
        graphene.String,  # JSON string of QuestionSetBelonging array
        required=True,
        description="Array of QuestionSetBelonging records"
    )
    dependency_map = graphene.JSONString(
        required=True,
        description="Map of parent question IDs to dependent question info"
    )
    has_conditional_logic = graphene.Boolean(
        required=True,
        description="Whether this question set has any conditional logic"
    )
    validation_warnings = graphene.List(
        ValidationWarningType,
        description="NEW: Validation warnings for dependency issues (may be null or empty)"
    )


# ============================================================================
# ENHANCED EXISTING TYPES (Release N)
# ============================================================================

class QuestionType(DjangoObjectType):
    """
    Enhanced Question type with new JSON fields.

    DEPRECATED FIELDS (Release N, N+1, N+2 only):
    - options (text) → Use optionsJson instead
    - alerton (text) → Use alertConfig instead

    These fields will be removed in Release N+3.
    """

    # NEW fields
    options_json = graphene.List(
        graphene.String,
        description="NEW: Structured options array (replaces 'options' text field)"
    )
    alert_config = graphene.Field(
        AlertConfigType,
        description="NEW: Structured alert configuration (replaces 'alerton' text field)"
    )

    class Meta:
        model = Question
        fields = "__all__"
        convert_choices_to_enum = False  # Keep as strings for Kotlin compatibility


class QuestionSetBelongingType(DjangoObjectType):
    """
    Enhanced QuestionSetBelonging type with new JSON fields.

    DEPRECATED FIELDS (Release N, N+1, N+2 only):
    - options (text) → Use optionsJson instead
    - alerton (text) → Use alertConfig instead

    These fields will be removed in Release N+3.
    """

    # NEW fields
    options_json = graphene.List(
        graphene.String,
        description="NEW: Structured options array (replaces 'options' text field)"
    )
    alert_config = graphene.Field(
        AlertConfigType,
        description="NEW: Structured alert configuration (replaces 'alerton' text field)"
    )

    class Meta:
        model = QuestionSetBelonging
        fields = "__all__"
        convert_choices_to_enum = False  # Keep as strings for Kotlin compatibility


class QuestionSetType(DjangoObjectType):
    """
    QuestionSet type - NO SCHEMA CHANGES in Release N.

    Only label improvements (internal, not affecting API).
    """

    class Meta:
        model = QuestionSet
        fields = "__all__"
        convert_choices_to_enum = False


# ============================================================================
# EXPORT ALL TYPES
# ============================================================================

__all__ = [
    'QuestionType',
    'QuestionSetType',
    'QuestionSetBelongingType',
    'AlertConfigType',
    'NumericAlertType',
    'ValidationWarningType',
    'DependencyInfoType',
    'ConditionalLogicResponseType',
]
