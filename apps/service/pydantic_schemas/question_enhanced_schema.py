"""
Enhanced Pydantic Schemas for Question/QuestionSet Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/activity/serializers.py QuestionSerializer patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

from apps.core.validation_pydantic.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# ENUMS FOR TYPE SAFETY
# ============================================================================

class AnswerType(str):
    """Question answer types (for Kotlin enum generation)."""
    TEXT = "TEXT"
    NUMERIC = "NUMERIC"
    CHECKBOX = "CHECKBOX"
    DROPDOWN = "DROPDOWN"
    DATE = "DATE"
    TIME = "TIME"
    DATETIME = "DATETIME"
    RATING = "RATING"
    SIGNATURE = "SIGNATURE"
    IMAGE = "IMAGE"
    MULTISELECT = "MULTISELECT"
    METERREADING = "METERREADING"


# ============================================================================
# QUESTION MODELS
# ============================================================================

class QuestionDetailSchema(BusinessLogicModel):
    """
    Complete Question schema for mobile operations.

    Mirrors apps/activity/models/question_model.py Question model.
    Maps to Kotlin data class: QuestionDetail
    """
    # Identity
    id: Optional[int] = Field(None, description="Server-assigned ID")
    quesname: str = Field(..., min_length=3, max_length=200, description="Question text")

    # Answer configuration
    answertype: AnswerType = Field(..., description="Answer type (TEXT, NUMERIC, CHECKBOX, etc.)")
    options: Optional[List[str]] = Field(None, description="Options for DROPDOWN/CHECKBOX/MULTISELECT")
    min: Optional[float] = Field(None, description="Minimum value (for NUMERIC/RATING)")
    max: Optional[float] = Field(None, description="Maximum value (for NUMERIC/RATING)")

    # Alert configuration
    alerton: Optional[str] = Field(None, max_length=200, description="Alert condition (legacy)")
    alert_config: Optional[Dict[str, Any]] = Field(None, description="Structured alert configuration (NEW)")

    # Advanced features
    isworkflow: bool = Field(default=False, description="Whether question triggers workflow")
    isavpt: bool = Field(default=False, description="Whether this is an AVPT question")
    avpttype: Optional[str] = Field(None, max_length=50, description="AVPT type if isavpt=True")
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement (for NUMERIC)")

    # Classification
    category: Optional[str] = Field(None, max_length=100, description="Question category")

    # Multi-tenant
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")

    # Audit
    ctzoffset: Optional[int] = Field(None, description="Client timezone offset (minutes)")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('quesname')
    @classmethod
    def validate_quesname_content(cls, v: str) -> str:
        """Validate question name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Question name must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("Question name cannot exceed 200 characters")
        return v

    @field_validator('min', 'max')
    @classmethod
    def validate_numeric_range(cls, v: Optional[float]) -> Optional[float]:
        """Validate min/max values are not negative."""
        if v is not None and v < 0:
            raise ValueError("Min/max values cannot be negative")
        return v

    def validate_business_rules(self, context=None):
        """Validate business rules for questions."""
        from pydantic import ValidationError

        errors = []

        # Validate min < max
        if self.min is not None and self.max is not None:
            if self.min >= self.max:
                errors.append({
                    'loc': ['max'],
                    'msg': 'Max value must be greater than min value',
                    'type': 'business_rule_violation'
                })

        # Validate options required for certain answer types
        if self.answertype in [AnswerType.CHECKBOX, AnswerType.DROPDOWN, AnswerType.MULTISELECT]:
            if not self.options or len(self.options) == 0:
                errors.append({
                    'loc': ['options'],
                    'msg': f'Options are required for {self.answertype} questions',
                    'type': 'business_rule_violation'
                })

        if errors:
            raise ValidationError(errors, self.__class__)


class QuestionSetDetailSchema(BusinessLogicModel):
    """
    Complete QuestionSet schema.

    Mirrors apps/activity/models/question_model.py QuestionSet model.
    Maps to Kotlin data class: QuestionSetDetail
    """
    # Identity
    id: Optional[int] = Field(None, description="Server-assigned ID")
    qsetname: str = Field(..., min_length=3, max_length=200, description="Question set name")

    # Classification
    type: Optional[str] = Field(None, max_length=50, description="Question set type")
    parent_id: Optional[int] = Field(None, description="Parent question set ID")

    # Configuration
    enable: bool = Field(default=True, description="Whether question set is active")
    assetincludes: Optional[List[int]] = Field(None, description="Included asset IDs")
    site_type_includes: Optional[List[str]] = Field(None, description="Included site types")
    buincludes: Optional[List[int]] = Field(None, description="Included business unit IDs")
    show_to_all_sites: bool = Field(default=False, description="Whether visible to all sites")

    # Multi-tenant
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")

    # Audit
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('qsetname')
    @classmethod
    def validate_qsetname_content(cls, v: str) -> str:
        """Validate question set name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Question set name must be at least 3 characters")
        return v


__all__ = [
    'AnswerType',
    'QuestionDetailSchema',
    'QuestionSetDetailSchema',
]
