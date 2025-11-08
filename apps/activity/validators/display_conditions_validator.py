"""
Display Conditions Pydantic Validator.

Validates the conditional display logic for QuestionSetBelonging.
Fixes the misleading naming where 'question_id' actually holds QuestionSetBelonging ID.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #3: Self-documenting code patterns
- Rule #9: Validate and sanitize all user inputs

Created: 2025-10-03
Author: Claude Code
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from apps.activity.enums import ConditionalOperator
import logging

logger = logging.getLogger(__name__)


class DependencySchema(BaseModel):
    """
    Schema for question dependency configuration.

    IMPORTANT: The 'qsb_id' field holds a QuestionSetBelonging ID, NOT a Question ID.
    This clarifies the previous misleading naming where it was called 'question_id'.
    """

    qsb_id: int = Field(
        ...,
        description="QuestionSetBelonging ID this question depends on (NOT Question ID)",
        gt=0,
        alias="question_id"  # Accept old key for backward compatibility
    )

    operator: str = Field(
        default=ConditionalOperator.EQUALS,
        description="Comparison operator for conditional logic"
    )

    values: List[str] = Field(
        default_factory=list,
        description="Values to compare against for conditional display",
        max_length=50  # Prevent excessive arrays
    )

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """Validate operator is a valid ConditionalOperator."""
        try:
            # Check if it's a valid operator
            if v not in ConditionalOperator.values:
                raise ValueError(
                    f"Invalid operator '{v}'. Must be one of: {', '.join(ConditionalOperator.values)}"
                )
            return v
        except AttributeError:
            # If ConditionalOperator doesn't have .values, check choices
            valid_operators = [choice[0] for choice in ConditionalOperator.choices]
            if v not in valid_operators:
                raise ValueError(
                    f"Invalid operator '{v}'. Must be one of: {', '.join(valid_operators)}"
                )
            return v

    @field_validator('values')
    @classmethod
    def validate_values(cls, v: List[str]) -> List[str]:
        """Validate values array is not empty for most operators."""
        if not v:
            # Empty is only valid for IS_EMPTY/IS_NOT_EMPTY operators
            logger.warning("Dependency values list is empty - only valid for IS_EMPTY/IS_NOT_EMPTY operators")

        # Sanitize each value to prevent XSS
        sanitized_values = []
        for value in v:
            if not isinstance(value, str):
                value = str(value)
            # Basic XSS prevention - remove script tags and HTML
            import re
            cleaned = re.sub(r'<[^>]*>', '', value)
            cleaned = cleaned.strip()
            if cleaned:
                sanitized_values.append(cleaned[:500])  # Max 500 chars per value

        return sanitized_values

    class Config:
        populate_by_name = True  # Allow both qsb_id and question_id
        json_schema_extra = {
            "examples": [
                {
                    "qsb_id": 123,
                    "operator": "EQUALS",
                    "values": ["Yes"]
                },
                {
                    "qsb_id": 456,
                    "operator": "IN",
                    "values": ["Option1", "Option2", "Option3"]
                },
                {
                    "qsb_id": 789,
                    "operator": "GT",
                    "values": ["50"]
                }
            ]
        }


class DisplayConditionsSchema(BaseModel):
    """
    Complete schema for conditional display logic.

    This defines when a question should be shown or hidden based on
    answers to previous questions in the same question set.
    """

    depends_on: Optional[DependencySchema] = Field(
        default=None,
        description="Dependency configuration - question to depend on"
    )

    show_if: bool = Field(
        default=True,
        description="True = show when condition met, False = hide when condition met"
    )

    cascade_hide: bool = Field(
        default=False,
        description="If this question is hidden, hide all dependent questions too"
    )

    group: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional grouping identifier for related conditional questions"
    )

    @field_validator('group')
    @classmethod
    def validate_group(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize group name."""
        if v is None:
            return None

        # Remove special characters, allow only alphanumeric, underscore, hyphen
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '', v)
        return sanitized[:100] if sanitized else None

    @model_validator(mode='after')
    def validate_logic_consistency(self):
        """Validate logical consistency of the configuration."""
        # If depends_on is None, other fields should be defaults
        if self.depends_on is None:
            if not self.show_if or self.cascade_hide:
                logger.warning(
                    "Display conditions has no dependency but show_if=False or cascade_hide=True. "
                    "This configuration may not work as expected."
                )
        else:
            # If we have a dependency, validate values are provided for most operators
            if self.depends_on.operator not in [
                ConditionalOperator.IS_EMPTY,
                ConditionalOperator.IS_NOT_EMPTY
            ]:
                if not self.depends_on.values:
                    raise ValueError(
                        f"Operator '{self.depends_on.operator}' requires at least one value in 'values' array"
                    )

        return self

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "depends_on": {
                        "qsb_id": 123,
                        "operator": "EQUALS",
                        "values": ["Yes"]
                    },
                    "show_if": True,
                    "cascade_hide": False,
                    "group": "labour_work"
                },
                {
                    "depends_on": {
                        "qsb_id": 456,
                        "operator": "IN",
                        "values": ["Damage", "Broken", "Faulty"]
                    },
                    "show_if": True,
                    "cascade_hide": True,
                    "group": "incident_details"
                }
            ]
        }


class DisplayConditionsValidator:
    """
    Validator class for display_conditions field in QuestionSetBelonging.

    Provides validation methods for both creation and updates, with
    database-level validation for dependency ordering.
    """

    @staticmethod
    def validate_json_structure(data: Dict[str, Any]) -> DisplayConditionsSchema:
        """
        Validate display_conditions JSON structure using Pydantic.

        Args:
            data: Raw JSON data from display_conditions field

        Returns:
            Validated DisplayConditionsSchema instance

        Raises:
            ValueError: If validation fails with detailed error messages
        """
        try:
            # Handle None/empty case
            if not data:
                return DisplayConditionsSchema()

            # Validate using Pydantic
            validated = DisplayConditionsSchema(**data)
            return validated

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                f"Display conditions validation failed: {e}",
                extra={'data': data, 'error_type': type(e).__name__}
            )
            raise ValueError(f"Invalid display_conditions structure: {str(e)}") from e

    @staticmethod
    def validate_dependency_exists(
        qsb_id: int,
        dependency_qsb_id: int,
        qset_id: int
    ) -> Dict[str, Any]:
        """
        Validate that the dependency QuestionSetBelonging exists and is valid.

        Args:
            qsb_id: Current QuestionSetBelonging ID
            dependency_qsb_id: Dependency QuestionSetBelonging ID
            qset_id: Current question set ID

        Returns:
            Dict with validation results and dependency info

        Raises:
            ValueError: If dependency is invalid
        """
        from apps.activity.models.question_model import QuestionSetBelonging
        from django.core.exceptions import ObjectDoesNotExist

        try:
            # Get the dependency
            dependency = QuestionSetBelonging.objects.select_related('qset', 'question').get(
                pk=dependency_qsb_id
            )

            # Validate: Must be in the same question set
            if dependency.qset_id != qset_id:
                raise ValueError(
                    f"Dependency question (ID {dependency_qsb_id}) must be in the same question set. "
                    f"Expected qset_id={qset_id}, got qset_id={dependency.qset_id}"
                )

            # Validate: Cannot depend on itself
            if qsb_id and dependency_qsb_id == qsb_id:
                raise ValueError(
                    f"Question cannot depend on itself (ID {qsb_id})"
                )

            return {
                'valid': True,
                'dependency': dependency,
                'dependency_qsb_id': dependency_qsb_id,
                'dependency_seqno': dependency.seqno,
                'dependency_question': dependency.question.quesname if dependency.question else None
            }

        except ObjectDoesNotExist:
            raise ValueError(
                f"Dependency QuestionSetBelonging with ID {dependency_qsb_id} does not exist"
            ) from None

    @staticmethod
    def validate_dependency_ordering(
        current_seqno: int,
        dependency_seqno: int,
        dependency_qsb_id: int
    ) -> bool:
        """
        Validate that dependency question comes before this question.

        Args:
            current_seqno: Current question's sequence number
            dependency_seqno: Dependency question's sequence number
            dependency_qsb_id: Dependency QuestionSetBelonging ID

        Returns:
            True if ordering is valid

        Raises:
            ValueError: If dependency comes after current question
        """
        if dependency_seqno >= current_seqno:
            raise ValueError(
                f"Dependency question (seqno={dependency_seqno}, ID={dependency_qsb_id}) "
                f"must come BEFORE this question (seqno={current_seqno}). "
                f"Questions can only depend on previous questions in the same set."
            )
        return True

    @staticmethod
    def detect_circular_dependency(
        qsb_id: int,
        qset_id: int,
        visited: Optional[set] = None
    ) -> bool:
        """
        Detect circular dependencies in question conditional logic.

        Args:
            qsb_id: QuestionSetBelonging ID to check
            qset_id: Question set ID
            visited: Set of visited IDs (for recursion)

        Returns:
            True if no circular dependency detected

        Raises:
            ValueError: If circular dependency detected
        """
        from apps.activity.models.question_model import QuestionSetBelonging

        if visited is None:
            visited = set()

        if qsb_id in visited:
            raise ValueError(
                f"Circular dependency detected involving question ID {qsb_id}. "
                f"Dependency chain: {' → '.join(map(str, visited))} → {qsb_id}"
            )

        visited.add(qsb_id)

        # Get this question's dependencies
        try:
            qsb = QuestionSetBelonging.objects.get(pk=qsb_id)
            if qsb.display_conditions and qsb.display_conditions.get('depends_on'):
                parent_qsb_id = qsb.display_conditions['depends_on'].get('question_id')
                if parent_qsb_id:
                    # Recursively check parent
                    DisplayConditionsValidator.detect_circular_dependency(
                        parent_qsb_id,
                        qset_id,
                        visited.copy()
                    )
        except QuestionSetBelonging.DoesNotExist:
            # If question doesn't exist, no circular dependency
            pass

        return True


# Convenience functions for use in models and forms

def validate_display_conditions(
    data: Dict[str, Any],
    qsb_id: Optional[int] = None,
    qset_id: Optional[int] = None,
    seqno: Optional[int] = None
) -> DisplayConditionsSchema:
    """
    Complete validation of display_conditions with database checks.

    Args:
        data: Display conditions JSON data
        qsb_id: Current QuestionSetBelonging ID (None for creation)
        qset_id: Question set ID (required if data has dependencies)
        seqno: Current question sequence number (required if data has dependencies)

    Returns:
        Validated DisplayConditionsSchema

    Raises:
        ValueError: If validation fails
    """
    validator = DisplayConditionsValidator()

    # Step 1: Validate JSON structure
    validated = validator.validate_json_structure(data)

    # Step 2: If there's a dependency, validate database constraints
    if validated.depends_on and validated.depends_on.qsb_id:
        if qset_id is None:
            raise ValueError("qset_id is required when validating dependencies")
        if seqno is None:
            raise ValueError("seqno is required when validating dependencies")

        # Check dependency exists and is in same qset
        dep_info = validator.validate_dependency_exists(
            qsb_id=qsb_id,
            dependency_qsb_id=validated.depends_on.qsb_id,
            qset_id=qset_id
        )

        # Check ordering (dependency must come before)
        validator.validate_dependency_ordering(
            current_seqno=seqno,
            dependency_seqno=dep_info['dependency_seqno'],
            dependency_qsb_id=validated.depends_on.qsb_id
        )

        # Check for circular dependencies
        if qsb_id:  # Only check for updates, not creation
            validator.detect_circular_dependency(qsb_id, qset_id)

    return validated


def validate_dependency_ordering(
    current_seqno: int,
    dependency_seqno: int,
    dependency_qsb_id: int
) -> bool:
    """
    Shortcut function for dependency ordering validation.

    Args:
        current_seqno: Current question's sequence number
        dependency_seqno: Dependency question's sequence number
        dependency_qsb_id: Dependency QuestionSetBelonging ID

    Returns:
        True if valid

    Raises:
        ValueError: If invalid ordering
    """
    return DisplayConditionsValidator.validate_dependency_ordering(
        current_seqno, dependency_seqno, dependency_qsb_id
    )
