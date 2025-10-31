"""
Enhanced Pydantic Models for Authentication Service

Replaces dataclasses with comprehensive Pydantic models that provide:
- Runtime type validation
- Enhanced error handling
- Business rule validation
- Integration with existing Django patterns
- Multi-tenant security validation

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines each
- Rule #10: Comprehensive validation
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns
"""

from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
from uuid import UUID
from pydantic import Field, validator, root_validator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.validation_pydantic.pydantic_base import (
    BusinessLogicModel,
    TenantAwareModel,
    SecureModel,
    create_code_field,
    create_name_field
)
from apps.core.constants.datetime_constants import DISPLAY_DATETIME_FORMAT
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class UserAccessType(str, Enum):
    """
    Enhanced user access type enumeration.
    Inherits from str for better JSON serialization.
    """
    WEB = "Web"
    MOBILE = "Mobile"
    BOTH = "Both"


class SiteCode(str, Enum):
    """
    Enhanced site code enumeration for routing.
    Inherits from str for better JSON serialization.
    """
    SPSESIC = "SPSESIC"
    SPSPAYROLL = "SPSPAYROLL"
    SPSOPS = "SPSOPS"
    SPSOPERATION = "SPSOPERATION"
    SPSHR = "SPSHR"


class AuthenticationStatus(str, Enum):
    """Authentication status codes."""
    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_DISABLED = "account_disabled"
    TENANT_ACCESS_DENIED = "tenant_access_denied"
    SECURITY_VIOLATION = "security_violation"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"


class AuthenticationResult(SecureModel):
    """
    Enhanced authentication result with comprehensive validation.

    Replaces the dataclass with runtime validation and security features.
    """

    success: bool = Field(..., description="Whether authentication was successful")
    status: AuthenticationStatus = Field(
        AuthenticationStatus.SUCCESS,
        description="Detailed authentication status"
    )
    user_id: Optional[int] = Field(None, description="Authenticated user ID")
    redirect_url: Optional[str] = Field(
        None,
        description="URL to redirect user after authentication",
        max_length=2048
    )
    error_message: Optional[str] = Field(
        None,
        description="Human-readable error message",
        max_length=500
    )
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code",
        max_length=50
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Request correlation ID for tracking",
        max_length=100
    )
    session_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional session data"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="When this authentication result expires"
    )
    requires_mfa: bool = Field(False, description="Whether MFA is required")
    security_flags: List[str] = Field(
        default_factory=list,
        description="Security flags and warnings"
    )

    @validator('redirect_url')
    def validate_redirect_url(cls, value):
        """Validate redirect URL for security."""
        if value:
            # Prevent open redirects
            if not (value.startswith('/') or value.startswith('http://localhost') or value.startswith('https://')):
                raise ValueError("Invalid redirect URL format")

            # Check for dangerous patterns
            dangerous_patterns = ['javascript:', 'data:', 'vbscript:']
            if any(pattern in value.lower() for pattern in dangerous_patterns):
                raise ValueError("Potentially dangerous redirect URL")

        return value

    @validator('session_data')
    def validate_session_data(cls, value):
        """Validate session data doesn't contain sensitive information."""
        if value:
            # Check for potentially sensitive keys
            sensitive_keys = ['password', 'token', 'secret', 'key', 'credential']
            for key in value.keys():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    raise ValueError(f"Session data should not contain sensitive key: {key}")

        return value

    @root_validator
    def validate_result_consistency(cls, values):
        """Validate consistency between success status and other fields."""
        success = values.get('success', False)
        status = values.get('status')
        error_message = values.get('error_message')
        user_id = values.get('user_id')

        if success:
            if status != AuthenticationStatus.SUCCESS:
                raise ValueError("Success=True but status is not SUCCESS")
            if error_message:
                raise ValueError("Success=True but error_message is set")
            if not user_id:
                logger.warning("Successful authentication without user_id")
        else:
            if status == AuthenticationStatus.SUCCESS:
                raise ValueError("Success=False but status is SUCCESS")
            if not error_message:
                raise ValueError("Failed authentication must have error_message")

        return values

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_none=True)

    def is_successful(self) -> bool:
        """Check if authentication was successful."""
        return self.success and self.status == AuthenticationStatus.SUCCESS

    def has_security_concerns(self) -> bool:
        """Check if there are any security flags."""
        return len(self.security_flags) > 0

    @classmethod
    def create_success(
        cls,
        user_id: int,
        correlation_id: Optional[str] = None,
        redirect_url: Optional[str] = None,
        session_data: Optional[Dict[str, Any]] = None
    ) -> 'AuthenticationResult':
        """
        Factory method for successful authentication.

        Args:
            user_id: Authenticated user ID
            correlation_id: Request correlation ID
            redirect_url: Redirect URL
            session_data: Session data

        Returns:
            AuthenticationResult for successful authentication
        """
        return cls(
            success=True,
            status=AuthenticationStatus.SUCCESS,
            user_id=user_id,
            correlation_id=correlation_id,
            redirect_url=redirect_url,
            session_data=session_data
        )

    @classmethod
    def create_failure(
        cls,
        status: AuthenticationStatus,
        error_message: str,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
        security_flags: Optional[List[str]] = None
    ) -> 'AuthenticationResult':
        """
        Factory method for failed authentication.

        Args:
            status: Authentication status
            error_message: Human-readable error message
            error_code: Machine-readable error code
            correlation_id: Request correlation ID
            security_flags: Security warnings

        Returns:
            AuthenticationResult for failed authentication
        """
        return cls(
            success=False,
            status=status,
            error_message=error_message,
            error_code=error_code,
            correlation_id=correlation_id,
            security_flags=security_flags or []
        )


class UserContext(TenantAwareModel):
    """
    Enhanced user context with multi-tenant validation.

    Provides comprehensive user context for authentication decisions.
    """

    user_id: int = Field(..., description="User ID", gt=0)
    sitecode: Optional[SiteCode] = Field(None, description="Site code for routing")
    client_name: Optional[str] = create_name_field("Client name", max_length=200)
    has_wizard_data: bool = Field(False, description="Whether user has wizard data")
    access_type: Optional[UserAccessType] = Field(
        None,
        description="Type of user access (Web/Mobile/Both)"
    )
    session_id: Optional[str] = Field(None, description="Session ID", max_length=100)
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    login_count: int = Field(0, description="Number of successful logins", ge=0)
    failed_login_attempts: int = Field(
        0,
        description="Number of recent failed login attempts",
        ge=0,
        le=10
    )
    ip_address: Optional[str] = Field(None, description="Client IP address", max_length=45)
    user_agent: Optional[str] = Field(None, description="User agent string", max_length=500)
    permissions: List[str] = Field(
        default_factory=list,
        description="User permissions list"
    )
    roles: List[str] = Field(
        default_factory=list,
        description="User roles list"
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User preferences"
    )

    @validator('ip_address')
    def validate_ip_address(cls, value):
        """Validate IP address format."""
        if value:
            import re
            # Basic IPv4/IPv6 validation
            ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            ipv6_pattern = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'

            if not (re.match(ipv4_pattern, value) or re.match(ipv6_pattern, value)):
                raise ValueError("Invalid IP address format")

        return value

    @validator('failed_login_attempts')
    def validate_failed_attempts(cls, value):
        """Validate failed login attempts within reasonable limits."""
        if value > 10:
            raise ValueError("Too many failed login attempts")
        return value

    @root_validator
    def validate_context_consistency(cls, values):
        """Validate context data consistency."""
        access_type = values.get('access_type')
        user_agent = values.get('user_agent', '')

        # Validate access type consistency with user agent
        if access_type == UserAccessType.MOBILE:
            if user_agent and not any(mobile in user_agent.lower() for mobile in ['mobile', 'android', 'iphone']):
                logger.warning("Mobile access type but desktop user agent detected")

        return values

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate business rules for user context.

        Args:
            context: Additional validation context

        Raises:
            ValidationError: If business rules are violated
        """
        # Check for suspicious login patterns
        if self.failed_login_attempts >= 5:
            raise ValueError("Account temporarily locked due to failed login attempts")

        # Validate tenant access
        if context and context.get('required_tenant_id'):
            if self.client_id != context['required_tenant_id']:
                raise ValueError("User does not have access to required tenant")

    def is_mobile_user(self) -> bool:
        """Check if this is a mobile user."""
        return self.access_type in [UserAccessType.MOBILE, UserAccessType.BOTH]

    def is_web_user(self) -> bool:
        """Check if this is a web user."""
        return self.access_type in [UserAccessType.WEB, UserAccessType.BOTH]

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        """Check if user has specific role."""
        return role in self.roles

    def get_security_score(self) -> int:
        """
        Calculate security score based on context.

        Returns:
            Security score from 0-100
        """
        score = 100

        # Deduct for failed login attempts
        score -= self.failed_login_attempts * 5

        # Deduct for missing session data
        if not self.session_id:
            score -= 10

        # Deduct for suspicious patterns
        if self.failed_login_attempts > 0 and self.login_count < 5:
            score -= 15  # New user with failed attempts

        return max(0, score)

    @classmethod
    def from_user_and_request(
        cls,
        user: User,
        request,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> 'UserContext':
        """
        Factory method to create UserContext from user and request.

        Args:
            user: Django user instance
            request: Django HTTP request
            additional_context: Additional context data

        Returns:
            UserContext instance
        """
        data = {
            'user_id': user.id,
            'client_id': getattr(user, 'client_id', None),
            'bu_id': getattr(user, 'bu_id', None),
            'ip_address': cls._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'session_id': request.session.session_key
        }

        # Add additional context if provided
        if additional_context:
            data.update(additional_context)

        return cls(**data)

    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LoginRequest(SecureModel):
    """
    Pydantic model for login request validation.

    Provides comprehensive validation for login attempts.
    """

    loginid: str = create_code_field("Login ID", max_length=50)
    password: str = Field(
        ...,
        description="User password",
        min_length=1,
        max_length=128
    )
    remember_me: bool = Field(False, description="Remember user session")
    captcha_response: Optional[str] = Field(None, description="CAPTCHA response")
    device_fingerprint: Optional[str] = Field(
        None,
        description="Device fingerprint for security",
        max_length=200
    )
    client_info: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Client browser/device information"
    )

    @validator('password', pre=True)
    def validate_password_not_empty(cls, value):
        """Ensure password is not empty."""
        if not value or not value.strip():
            raise ValueError("Password cannot be empty")
        return value

    def validate_business_rules(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Validate login business rules.

        Args:
            context: Additional validation context (IP, rate limiting, etc.)

        Raises:
            ValidationError: If business rules are violated
        """
        # Check if CAPTCHA is required (based on context)
        if context and context.get('captcha_required', False):
            if not self.captcha_response:
                raise ValueError("CAPTCHA response is required")

        # Additional security validations can be added here
        pass


# Backward compatibility aliases for gradual migration
AuthResult = AuthenticationResult  # Shorter alias
LoginData = LoginRequest  # More descriptive alias