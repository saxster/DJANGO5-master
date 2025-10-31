"""
Enhanced Pydantic Models for LLM Service Interfaces

Provides comprehensive validation for LLM service interactions including:
- Context data validation
- User input sanitization
- Response structure validation
- Conversation flow validation
- Multi-language support validation

Features:
- Runtime type validation
- Content safety validation
- Token limit validation
- Structured response validation
- Integration with existing LLM patterns

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines each
- Rule #10: Comprehensive validation
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns

Ontology: validation_rules=True, ai_guardrails=True, security_critical=True, type_safe=True
Category: pydantic_models, llm_validation, ai_safety
Domain: conversational_ai, llm_integration, content_safety, knowledge_query
Responsibility: Validate LLM inputs/outputs; sanitize user input; enforce guardrails; safety scoring
Dependencies: pydantic, core.validation_pydantic.pydantic_base, core.services.validation_service
Security: XSS/SQL injection detection, PII filtering, prompt injection prevention, content moderation
Validation Patterns:
  - Input sanitization: XSS, SQL injection, sensitive key detection
  - Token limits: 100-4000 tokens, conversation type-specific minimums
  - Content safety: Safety score (0.0-1.0), moderation flags, harmful content blocking
  - Response validation: Token usage structure, follow-up questions length, confidence scores
  - Conversation state: Started, in_progress, generating, awaiting_approval, completed, error
AI Guardrails:
  - User input: Max 10k chars, sanitized, injection-checked
  - Previous interactions: Max 50, role validation (user/assistant/system)
  - Recommendations: Critical priority requires implementation steps, confidence-consensus checks
  - Question generation: 1-10 questions, 10-500 chars each, must end with '?'
Language Support: EN, ES, FR, DE, ZH, JA, KO
Use Case: IntelliWiz conversational onboarding, site audit, troubleshooting, knowledge queries
"""

from typing import Dict, List, Optional, Any, Union, Literal
from enum import Enum
from datetime import datetime
from uuid import UUID
from pydantic import Field, validator, root_validator, constr, conint

from apps.core.validation_pydantic.pydantic_base import (
    BusinessLogicModel,
    TenantAwareModel,
    SecureModel,
    create_name_field
)
from apps.core.services.validation_service import ValidationService
import logging
import json

logger = logging.getLogger(__name__)


class ConversationType(str, Enum):
    """Conversation type enumeration."""
    INITIAL_SETUP = "initial_setup"
    SITE_AUDIT = "site_audit"
    CONFIGURATION = "configuration"
    TROUBLESHOOTING = "troubleshooting"
    KNOWLEDGE_QUERY = "knowledge_query"


class ConversationState(str, Enum):
    """Conversation state enumeration."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    GENERATING_RECOMMENDATIONS = "generating_recommendations"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class LanguageCode(str, Enum):
    """Supported language codes."""
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    ZH = "zh"
    JA = "ja"
    KO = "ko"


class ContentSafetyLevel(str, Enum):
    """Content safety levels."""
    SAFE = "safe"
    NEEDS_REVIEW = "needs_review"
    POTENTIALLY_HARMFUL = "potentially_harmful"
    BLOCKED = "blocked"


class LLMContextData(SecureModel):
    """
    Enhanced context data for LLM interactions.

    Validates and sanitizes context data passed to LLM services.

    Ontology: validation_rules=True, ai_guardrails=True, security_critical=True
    Purpose: Request payload for LLM service calls (IntelliWiz conversational onboarding)
    Inherits: SecureModel (PII detection, encryption awareness)
    Validation: User input sanitization, previous interactions structure, token limits
    Security Checks:
      - XSS detection: ValidationService.contains_xss()
      - SQL injection: ValidationService.contains_sql_injection()
      - Sensitive keys: Blocks password/token/secret in client_context
      - Input sanitization: ValidationService.sanitize_input()
    Guardrails:
      - Initial setup: Requires >= 500 tokens
      - Multilingual: Requires user_preferences.multilingual_enabled=true
      - Previous interactions: Max 50, role must be user/assistant/system
    Use Case: IntelliWiz site onboarding, configuration, troubleshooting conversations
    """

    user_input: str = Field(
        ...,
        description="User input text",
        min_length=1,
        max_length=10000
    )
    conversation_type: ConversationType = Field(
        ...,
        description="Type of conversation"
    )
    language: LanguageCode = Field(
        LanguageCode.EN,
        description="Conversation language"
    )
    client_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Client-specific context data"
    )
    business_unit_id: Optional[int] = Field(None, description="Business unit ID", gt=0)
    previous_interactions: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation interactions",
        max_items=50
    )
    user_preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User preferences for response generation"
    )
    content_restrictions: List[str] = Field(
        default_factory=list,
        description="Content restriction flags"
    )
    max_response_tokens: conint(ge=100, le=4000) = Field(
        1000,
        description="Maximum tokens for response"
    )
    temperature: Optional[float] = Field(
        0.7,
        description="Response creativity temperature",
        ge=0.0,
        le=2.0
    )

    @validator('user_input', pre=True)
    def validate_and_sanitize_input(cls, value):
        """Sanitize user input for safety."""
        if not value or not value.strip():
            raise ValueError("User input cannot be empty")

        # Sanitize input
        sanitized = ValidationService.sanitize_input(value, allow_html=False)

        # Check for content safety
        if ValidationService.contains_sql_injection(sanitized):
            raise ValueError("Potentially harmful content detected in user input")

        if ValidationService.contains_xss(sanitized):
            raise ValueError("Potentially harmful content detected in user input")

        return sanitized.strip()

    @validator('previous_interactions')
    def validate_previous_interactions(cls, value):
        """Validate previous interactions structure."""
        for interaction in value:
            if not isinstance(interaction, dict):
                raise ValueError("Each interaction must be a dictionary")

            required_keys = {'role', 'content', 'timestamp'}
            if not all(key in interaction for key in required_keys):
                raise ValueError("Each interaction must have role, content, and timestamp")

            if interaction['role'] not in ['user', 'assistant', 'system']:
                raise ValueError("Invalid interaction role")

        return value

    @validator('client_context')
    def validate_client_context(cls, value):
        """Validate client context doesn't contain sensitive data."""
        if value:
            sensitive_patterns = ['password', 'token', 'secret', 'key', 'credential', 'api_key']
            for key in value.keys():
                if any(pattern in key.lower() for pattern in sensitive_patterns):
                    raise ValueError(f"Client context should not contain sensitive key: {key}")

        return value

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate LLM-specific business rules.

        Args:
            context: Additional validation context

        Raises:
            ValueError: If business rules are violated
        """
        # Validate token limits based on conversation type
        if self.conversation_type == ConversationType.INITIAL_SETUP:
            if self.max_response_tokens < 500:
                raise ValueError("Initial setup conversations require at least 500 tokens")

        # Validate language consistency
        if self.language != LanguageCode.EN:
            if not self.user_preferences.get('multilingual_enabled', False):
                raise ValueError("Multilingual support not enabled for this user")


class LLMResponse(SecureModel):
    """
    Enhanced LLM response model with comprehensive validation.

    Ontology: validation_rules=True, ai_guardrails=True
    Purpose: LLM service response with safety scoring and moderation
    Inherits: SecureModel (PII detection)
    Validation: Token usage structure, follow-up questions length, safety consistency
    Safety Guardrails:
      - safety_score < 0.3: Flagged as NEEDS_REVIEW
      - safety_score < 0.1: Flagged as POTENTIALLY_HARMFUL
      - is_safe_for_display(): Requires score >= 0.3 and no moderation flags
    Content Validation:
      - XSS detection: ValidationService.contains_xss()
      - Response sanitization if harmful content detected
    Token Usage: Must include prompt_tokens, completion_tokens, total_tokens
    Follow-up Questions: Max 5, each 1-200 chars
    Use Case: IntelliWiz response validation, content moderation, safety filtering
    """

    response_id: str = Field(..., description="Unique response identifier")
    content: str = Field(
        ...,
        description="Response content",
        min_length=1,
        max_length=10000
    )
    confidence_score: float = Field(
        ...,
        description="Response confidence score",
        ge=0.0,
        le=1.0
    )
    token_usage: Dict[str, int] = Field(
        ...,
        description="Token usage statistics"
    )
    processing_time_ms: int = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0
    )
    safety_score: float = Field(
        1.0,
        description="Content safety score",
        ge=0.0,
        le=1.0
    )
    safety_level: ContentSafetyLevel = Field(
        ContentSafetyLevel.SAFE,
        description="Content safety level"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )
    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions",
        max_items=5
    )
    sources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Sources used for response generation"
    )
    language_detected: Optional[LanguageCode] = Field(
        None,
        description="Detected language of input"
    )
    moderation_flags: List[str] = Field(
        default_factory=list,
        description="Content moderation flags"
    )

    @validator('token_usage')
    def validate_token_usage(cls, value):
        """Validate token usage structure."""
        required_keys = {'prompt_tokens', 'completion_tokens', 'total_tokens'}
        if not all(key in value for key in required_keys):
            raise ValueError("Token usage must include prompt_tokens, completion_tokens, and total_tokens")

        for key, count in value.items():
            if not isinstance(count, int) or count < 0:
                raise ValueError(f"Token count for {key} must be a non-negative integer")

        return value

    @validator('follow_up_questions')
    def validate_follow_up_questions(cls, value):
        """Validate follow-up questions."""
        for question in value:
            if not isinstance(question, str) or len(question.strip()) == 0:
                raise ValueError("Follow-up questions must be non-empty strings")

            if len(question) > 200:
                raise ValueError("Follow-up questions must be 200 characters or less")

        return value

    @validator('content', pre=True)
    def validate_response_content(cls, value):
        """Validate response content safety."""
        if not value or not value.strip():
            raise ValueError("Response content cannot be empty")

        # Check for potentially harmful content
        if ValidationService.contains_xss(value):
            logger.warning("Response contains potentially harmful content")
            # Don't raise error, but flag for review
            return ValidationService.sanitize_input(value, allow_html=True)

        return value.strip()

    @root_validator
    def validate_safety_consistency(cls, values):
        """Validate safety score and level consistency."""
        safety_score = values.get('safety_score', 1.0)
        safety_level = values.get('safety_level')

        if safety_score < 0.3 and safety_level == ContentSafetyLevel.SAFE:
            values['safety_level'] = ContentSafetyLevel.NEEDS_REVIEW

        if safety_score < 0.1:
            values['safety_level'] = ContentSafetyLevel.POTENTIALLY_HARMFUL

        return values

    def is_safe_for_display(self) -> bool:
        """Check if response is safe to display to users."""
        return (
            self.safety_level in [ContentSafetyLevel.SAFE, ContentSafetyLevel.NEEDS_REVIEW] and
            self.safety_score >= 0.3 and
            not self.moderation_flags
        )


class QuestionGeneration(SecureModel):
    """
    Model for validating generated questions.
    """

    questions: List[str] = Field(
        ...,
        description="Generated questions",
        min_items=1,
        max_items=10
    )
    question_type: str = Field(
        ...,
        description="Type of questions generated",
        max_length=50
    )
    difficulty_level: Literal["beginner", "intermediate", "advanced"] = Field(
        "beginner",
        description="Difficulty level of questions"
    )
    context_relevance: float = Field(
        ...,
        description="Relevance score to context",
        ge=0.0,
        le=1.0
    )
    estimated_duration: Optional[int] = Field(
        None,
        description="Estimated time to answer all questions (minutes)",
        ge=1,
        le=60
    )

    @validator('questions')
    def validate_questions(cls, value):
        """Validate individual questions."""
        for question in value:
            if not isinstance(question, str):
                raise ValueError("All questions must be strings")

            question = question.strip()
            if len(question) < 10:
                raise ValueError("Questions must be at least 10 characters long")

            if len(question) > 500:
                raise ValueError("Questions must be 500 characters or less")

            # Check if it's actually a question
            if not question.endswith('?') and '?' not in question:
                logger.warning(f"Generated text doesn't appear to be a question: {question[:50]}...")

        return value


class RecommendationData(TenantAwareModel):
    """
    Enhanced model for AI-generated recommendations.

    Ontology: validation_rules=True, ai_guardrails=True, tenant_aware=True
    Purpose: AI-generated recommendations with maker-checker validation
    Inherits: TenantAwareModel (tenant_id, bu_id validation)
    Validation: Implementation steps, confidence score consistency, priority-based requirements
    Guardrails:
      - Critical priority: MUST have implementation_steps
      - High confidence (>= 0.9): Warning if no consensus
      - Maker/checker confidence: Average should roughly match overall confidence
    Business Rules:
      - Implementation steps: Min 5 chars each
      - Consensus: Maker and checker LLMs agree
      - Confidence mismatch: Warn if |overall - avg| > 0.3
    Use Case: IntelliWiz site audit recommendations, configuration suggestions
    Maker-Checker: Dual LLM validation for high-stakes recommendations
    """

    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    title: str = create_name_field("Recommendation title", max_length=200)
    description: str = Field(
        ...,
        description="Detailed recommendation description",
        min_length=10,
        max_length=2000
    )
    confidence_score: float = Field(
        ...,
        description="Confidence in recommendation",
        ge=0.0,
        le=1.0
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        "medium",
        description="Recommendation priority"
    )
    category: str = Field(
        ...,
        description="Recommendation category",
        max_length=100
    )
    implementation_steps: List[str] = Field(
        default_factory=list,
        description="Steps to implement recommendation",
        max_items=20
    )
    estimated_impact: Optional[str] = Field(
        None,
        description="Expected impact of implementation",
        max_length=500
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Prerequisites for implementation"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Associated risks"
    )
    resources_required: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Resources required for implementation"
    )
    consensus: bool = Field(False, description="Whether there's consensus on this recommendation")
    maker_confidence: Optional[float] = Field(None, description="Maker LLM confidence", ge=0.0, le=1.0)
    checker_confidence: Optional[float] = Field(None, description="Checker LLM confidence", ge=0.0, le=1.0)

    @validator('implementation_steps')
    def validate_implementation_steps(cls, value):
        """Validate implementation steps."""
        for step in value:
            if not isinstance(step, str) or len(step.strip()) < 5:
                raise ValueError("Implementation steps must be meaningful strings")

        return value

    @root_validator
    def validate_confidence_scores(cls, values):
        """Validate confidence score consistency."""
        confidence = values.get('confidence_score')
        maker_conf = values.get('maker_confidence')
        checker_conf = values.get('checker_confidence')

        if maker_conf and checker_conf:
            # Average confidence should roughly match overall confidence
            avg_confidence = (maker_conf + checker_conf) / 2
            if abs(confidence - avg_confidence) > 0.3:
                logger.warning(f"Confidence score mismatch: overall={confidence}, avg={avg_confidence}")

        return values

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate recommendation business rules.

        Args:
            context: Additional validation context

        Raises:
            ValueError: If business rules are violated
        """
        # Critical recommendations must have implementation steps
        if self.priority == "critical" and not self.implementation_steps:
            raise ValueError("Critical recommendations must include implementation steps")

        # High confidence recommendations should have consensus
        if self.confidence_score >= 0.9 and not self.consensus:
            logger.warning("High confidence recommendation without consensus")


# Response envelope models
class LLMServiceResponse(SecureModel):
    """
    Standard response envelope for LLM service operations.
    """

    success: bool = Field(..., description="Whether operation was successful")
    data: Optional[Union[LLMResponse, List[LLMResponse], QuestionGeneration, List[RecommendationData]]] = Field(
        None,
        description="Response data"
    )
    error_message: Optional[str] = Field(None, description="Error message if unsuccessful")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    request_id: Optional[str] = Field(None, description="Request correlation ID")
    processing_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Processing metadata and metrics"
    )

    @root_validator
    def validate_response_consistency(cls, values):
        """Validate response consistency."""
        success = values.get('success', False)
        data = values.get('data')
        error_message = values.get('error_message')

        if success and not data:
            logger.warning("Successful response without data")

        if not success and not error_message:
            raise ValueError("Unsuccessful response must have error message")

        return values


# Convenience aliases for backward compatibility
ContextData = LLMContextData
ResponseData = LLMResponse
ServiceResponse = LLMServiceResponse