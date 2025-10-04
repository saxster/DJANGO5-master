"""
Pydantic Models for JSON Field Validation

Provides comprehensive validation for JSON fields used throughout the Django application.
These models can be used to validate complex nested data structures stored in JSONField.

Common JSON fields validated:
- people_extras (user capabilities and preferences)
- context_data (conversation and session context)
- collected_data (form and workflow data)
- configuration_data (system configurations)
- metadata fields (various entity metadata)

Features:
- Nested data structure validation
- Type safety for complex objects
- Business rule validation
- Security sanitization
- Multi-tenant data validation

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines each
- Rule #10: Comprehensive validation
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns
"""

from typing import Dict, List, Optional, Any, Union, Literal
from enum import Enum
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from pydantic import Field, validator, root_validator, constr, conint, confloat

from apps.core.validation.pydantic_base import (
    BusinessLogicModel,
    TenantAwareModel,
    SecureModel,
    create_code_field,
    create_name_field,
    create_email_field
)
from apps.core.services.validation_service import ValidationService
import logging
import json

logger = logging.getLogger(__name__)


class CapabilityLevel(str, Enum):
    """Capability level enumeration."""
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SystemPreference(str, Enum):
    """System preference enumeration."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    AUTO = "auto"


class NotificationChannel(str, Enum):
    """Notification channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class PeopleExtrasData(SecureModel):
    """
    Validation model for people_extras JSON field.

    Validates user capabilities, preferences, and extended attributes.
    """

    # AI Capabilities
    ai_enabled: bool = Field(False, description="Whether AI features are enabled")
    ai_model_preference: Optional[str] = Field(
        None,
        description="Preferred AI model",
        max_length=50
    )
    ai_capability_level: CapabilityLevel = Field(
        CapabilityLevel.NONE,
        description="User's AI capability level"
    )

    # System Capabilities
    system_capabilities: Dict[str, CapabilityLevel] = Field(
        default_factory=dict,
        description="System capability levels by module"
    )

    # Preferences
    language_preference: str = Field(
        "en",
        description="Preferred language code",
        max_length=10
    )
    timezone_preference: str = Field(
        "UTC",
        description="Preferred timezone",
        max_length=50
    )
    theme_preference: Literal["light", "dark", "auto"] = Field(
        "auto",
        description="UI theme preference"
    )

    # Notification Settings
    notification_preferences: Dict[str, SystemPreference] = Field(
        default_factory=dict,
        description="Notification preferences by type"
    )
    notification_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Enabled notification channels"
    )

    # Dashboard Settings
    dashboard_layout: Optional[Dict[str, Any]] = Field(
        None,
        description="Dashboard layout configuration"
    )
    widget_preferences: Dict[str, bool] = Field(
        default_factory=dict,
        description="Widget visibility preferences"
    )

    # Security Settings
    two_factor_enabled: bool = Field(False, description="Whether 2FA is enabled")
    session_timeout: Optional[int] = Field(
        None,
        description="Session timeout in minutes",
        ge=5,
        le=1440  # Max 24 hours
    )
    ip_whitelist: List[str] = Field(
        default_factory=list,
        description="Whitelisted IP addresses",
        max_items=10
    )

    # Integration Settings
    external_integrations: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="External integration configurations"
    )
    api_access_enabled: bool = Field(False, description="Whether API access is enabled")

    # Custom Fields
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom user fields"
    )

    # Metadata
    profile_completion_score: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None,
        description="Profile completion score"
    )
    last_preferences_update: Optional[datetime] = Field(
        None,
        description="When preferences were last updated"
    )
    migration_version: int = Field(
        1,
        description="Data migration version",
        ge=1
    )

    @validator('system_capabilities')
    def validate_system_capabilities(cls, value):
        """Validate system capabilities structure."""
        allowed_modules = [
            'task_management', 'reporting', 'scheduling', 'helpdesk',
            'attendance', 'asset_management', 'maintenance', 'security',
            'analytics', 'mobile_app', 'api_access'
        ]

        for module in value.keys():
            if module not in allowed_modules:
                logger.warning(f"Unknown system module in capabilities: {module}")

        return value

    @validator('ip_whitelist')
    def validate_ip_whitelist(cls, value):
        """Validate IP addresses in whitelist."""
        import re
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'

        for ip in value:
            if not re.match(ipv4_pattern, ip):
                raise ValueError(f"Invalid IP address format: {ip}")

        return value

    @validator('external_integrations')
    def validate_external_integrations(cls, value):
        """Validate external integrations don't contain sensitive data."""
        sensitive_keys = ['password', 'secret', 'token', 'key', 'credential']

        for integration_name, config in value.items():
            if isinstance(config, dict):
                for key in config.keys():
                    if any(sensitive in key.lower() for sensitive in sensitive_keys):
                        raise ValueError(f"External integration config should not contain sensitive key: {key}")

        return value

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate people extras business rules.

        Args:
            context: Additional validation context

        Raises:
            ValueError: If business rules are violated
        """
        # AI features require minimum capability level
        if self.ai_enabled and self.ai_capability_level == CapabilityLevel.NONE:
            raise ValueError("AI features require capability level above 'none'")

        # Session timeout validation
        if self.session_timeout and self.session_timeout < 5:
            raise ValueError("Session timeout must be at least 5 minutes")


class ConversationContextData(TenantAwareModel):
    """
    Validation model for conversation context_data JSON field.

    Validates conversation and session context information.
    """

    # Session Information
    session_id: Optional[str] = Field(None, description="Session identifier")
    user_id: int = Field(..., description="User ID", gt=0)
    conversation_type: str = Field(..., description="Type of conversation")
    language: str = Field("en", description="Conversation language", max_length=10)

    # Context Data
    current_step: Optional[str] = Field(None, description="Current conversation step")
    completed_steps: List[str] = Field(
        default_factory=list,
        description="List of completed steps"
    )
    pending_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pending actions in conversation"
    )

    # User State
    user_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences relevant to conversation"
    )
    historical_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Historical conversation context"
    )

    # Environmental Context
    device_type: Optional[Literal["web", "mobile", "tablet", "api"]] = Field(
        None,
        description="Device type used for conversation"
    )
    browser_info: Optional[Dict[str, str]] = Field(
        None,
        description="Browser information"
    )
    location_context: Optional[Dict[str, str]] = Field(
        None,
        description="Location context if available"
    )

    # Conversation Metadata
    started_at: datetime = Field(..., description="When conversation started")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    total_interactions: conint(ge=0) = Field(0, description="Total number of interactions")
    error_count: conint(ge=0) = Field(0, description="Number of errors encountered")

    # Flow Control
    max_steps: Optional[conint(gt=0)] = Field(None, description="Maximum allowed steps")
    timeout_minutes: conint(ge=1, le=60) = Field(30, description="Conversation timeout in minutes")
    requires_approval: bool = Field(False, description="Whether conversation requires approval")

    # Quality Metrics
    user_satisfaction_score: Optional[confloat(ge=1.0, le=5.0)] = Field(
        None,
        description="User satisfaction score (1-5)"
    )
    conversation_quality_score: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None,
        description="Computed conversation quality score"
    )

    @validator('completed_steps', 'pending_actions')
    def validate_steps_and_actions(cls, value):
        """Validate steps and actions don't contain sensitive data."""
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for key in item.keys():
                        if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret']):
                            raise ValueError("Steps and actions should not contain sensitive data")
        return value

    @root_validator
    def validate_conversation_consistency(cls, values):
        """Validate conversation data consistency."""
        started_at = values.get('started_at')
        last_activity = values.get('last_activity')

        if started_at and last_activity:
            if last_activity < started_at:
                raise ValueError("Last activity cannot be before conversation start")

        return values


class CollectedFormData(SecureModel):
    """
    Validation model for collected_data JSON field.

    Validates form and workflow collected data.
    """

    # Form Metadata
    form_id: str = Field(..., description="Form identifier")
    form_version: str = Field(..., description="Form version")
    collection_timestamp: datetime = Field(..., description="When data was collected")
    completion_status: Literal["partial", "complete", "validated"] = Field(
        "partial",
        description="Form completion status"
    )

    # Form Fields
    field_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Form field data"
    )
    field_metadata: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadata about form fields"
    )

    # Validation Information
    validation_errors: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Validation errors by field"
    )
    validation_warnings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Validation warnings by field"
    )

    # Workflow Context
    workflow_step: Optional[str] = Field(None, description="Current workflow step")
    workflow_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Workflow step history"
    )

    # File Attachments
    file_attachments: List[Dict[str, str]] = Field(
        default_factory=list,
        description="File attachment references"
    )

    # Submission Tracking
    submission_attempts: conint(ge=0) = Field(0, description="Number of submission attempts")
    last_submission_error: Optional[str] = Field(
        None,
        description="Last submission error message"
    )

    # Data Quality
    completeness_score: confloat(ge=0.0, le=1.0) = Field(
        0.0,
        description="Data completeness score"
    )
    quality_score: confloat(ge=0.0, le=1.0) = Field(
        0.0,
        description="Data quality score"
    )

    @validator('field_data')
    def validate_field_data(cls, value):
        """Validate form field data."""
        for field_name, field_value in value.items():
            # Sanitize string values
            if isinstance(field_value, str):
                # Check for potentially harmful content
                if ValidationService.contains_xss(field_value):
                    raise ValueError(f"Field '{field_name}' contains potentially harmful content")

                if ValidationService.contains_sql_injection(field_value):
                    raise ValueError(f"Field '{field_name}' contains potentially harmful content")

        return value

    @validator('file_attachments')
    def validate_file_attachments(cls, value):
        """Validate file attachment references."""
        required_keys = ['filename', 'file_path', 'file_size', 'content_type']

        for attachment in value:
            if not all(key in attachment for key in required_keys):
                raise ValueError("File attachments must include filename, file_path, file_size, and content_type")

            # Validate file size
            try:
                file_size = int(attachment['file_size'])
                if file_size < 0 or file_size > 100 * 1024 * 1024:  # 100MB limit
                    raise ValueError("File size must be between 0 and 100MB")
            except (ValueError, TypeError):
                raise ValueError("Invalid file size format")

        return value


class SystemConfigurationData(TenantAwareModel):
    """
    Validation model for system configuration JSON fields.
    """

    # Configuration Metadata
    config_version: str = Field(..., description="Configuration version")
    config_type: str = Field(..., description="Type of configuration")
    last_updated: datetime = Field(..., description="Last update timestamp")
    updated_by: int = Field(..., description="User ID who last updated", gt=0)

    # Feature Flags
    feature_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Feature flag settings"
    )

    # System Parameters
    system_parameters: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict,
        description="System parameter values"
    )

    # Integration Settings
    integration_settings: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Integration configuration settings"
    )

    # Security Settings
    security_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Security configuration settings"
    )

    # Environment Settings
    environment: Literal["development", "staging", "production"] = Field(
        "production",
        description="Environment type"
    )
    debug_enabled: bool = Field(False, description="Whether debug mode is enabled")

    # Validation Rules
    validation_rules: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Custom validation rules"
    )

    @validator('security_settings')
    def validate_security_settings(cls, value):
        """Validate security settings don't expose sensitive information."""
        sensitive_keys = ['password', 'secret_key', 'private_key', 'token']

        for key in value.keys():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Security settings should not contain plaintext sensitive key: {key}")

        return value

    @root_validator
    def validate_environment_consistency(cls, values):
        """Validate environment and debug settings consistency."""
        environment = values.get('environment')
        debug_enabled = values.get('debug_enabled', False)

        if environment == 'production' and debug_enabled:
            logger.warning("Debug mode enabled in production environment")

        return values


class MetadataModel(SecureModel):
    """
    Generic validation model for entity metadata JSON fields.
    """

    # Entity Information
    entity_type: str = Field(..., description="Type of entity")
    entity_id: int = Field(..., description="Entity ID", gt=0)

    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        description="Entity tags",
        max_items=20
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Entity labels"
    )
    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Entity annotations"
    )

    # Relationships
    related_entities: List[Dict[str, Union[str, int]]] = Field(
        default_factory=list,
        description="Related entities"
    )

    # Tracking Information
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: int = Field(..., description="Creator user ID", gt=0)
    version: conint(ge=1) = Field(1, description="Metadata version")

    # Custom Properties
    custom_properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom entity properties"
    )

    @validator('tags')
    def validate_tags(cls, value):
        """Validate entity tags."""
        for tag in value:
            if not isinstance(tag, str) or len(tag.strip()) == 0:
                raise ValueError("Tags must be non-empty strings")

            if len(tag) > 50:
                raise ValueError("Tags must be 50 characters or less")

        return value

    @validator('related_entities')
    def validate_related_entities(cls, value):
        """Validate related entities structure."""
        required_keys = {'entity_type', 'entity_id'}

        for entity in value:
            if not isinstance(entity, dict):
                raise ValueError("Related entities must be dictionaries")

            if not all(key in entity for key in required_keys):
                raise ValueError("Related entities must have entity_type and entity_id")

        return value


# Utility functions for JSON field validation
def validate_json_field(
    json_data: Any,
    model_class: type,
    partial: bool = False
) -> Union[Dict[str, Any], Any]:
    """
    Validate JSON field data using Pydantic model.

    Args:
        json_data: JSON data to validate
        model_class: Pydantic model class
        partial: Whether to allow partial validation

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    if json_data is None:
        return None

    if isinstance(json_data, str):
        try:
            json_data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    if partial:
        # For partial validation, only validate provided fields
        if isinstance(json_data, dict):
            provided_fields = {
                field: value for field, value in json_data.items()
                if field in model_class.model_fields
            }
            validated = model_class.model_validate(provided_fields)
        else:
            validated = model_class.model_validate(json_data)
    else:
        validated = model_class.model_validate(json_data)

    return validated.model_dump()


def create_json_field_validator(model_class: type, partial: bool = False):
    """
    Create a validator function for Django JSONField.

    Args:
        model_class: Pydantic model class
        partial: Whether to allow partial validation

    Returns:
        Validator function for Django JSONField
    """
    def validator_function(value):
        """Django JSONField validator function."""
        return validate_json_field(value, model_class, partial)

    return validator_function


# Convenience exports
__all__ = [
    'PeopleExtrasData',
    'ConversationContextData',
    'CollectedFormData',
    'SystemConfigurationData',
    'MetadataModel',
    'validate_json_field',
    'create_json_field_validator'
]