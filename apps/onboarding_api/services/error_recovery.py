"""
Error Recovery Service

Proactive error categorization, contextual messaging, and automatic recovery.

Architecture:
- Error categorization with severity levels
- Automatic retry strategies based on error type
- Contextual user-facing error messages
- Fallback workflows for common failure scenarios

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization

Author: Claude Code
Date: 2025-10-01
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"  # System-wide impact, immediate attention
    HIGH = "high"          # Blocks user progress, needs urgent fix
    MEDIUM = "medium"      # Impacts experience, should be fixed soon
    LOW = "low"            # Minor issue, can be worked around
    INFO = "info"          # Informational, no action needed


class ErrorCategory(str, Enum):
    """Error categories for classification"""
    # Infrastructure
    DATABASE = "database"
    NETWORK = "network"
    CACHE = "cache"
    STORAGE = "storage"

    # External Services
    LLM_API = "llm_api"
    TRANSLATION_API = "translation_api"
    EXTERNAL_API = "external_api"

    # User Input
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"

    # Business Logic
    STATE_TRANSITION = "state_transition"
    DATA_INTEGRITY = "data_integrity"
    CONFIGURATION = "configuration"

    # Unknown
    UNKNOWN = "unknown"


class ErrorRecoveryService:
    """
    Service for error categorization and automated recovery

    Provides:
    - Intelligent error categorization
    - Automatic retry strategies
    - Contextual user-facing error messages
    - Fallback workflow orchestration
    """

    def __init__(self):
        self.retry_strategies = self._initialize_retry_strategies()
        self.error_patterns = self._initialize_error_patterns()
        self.fallback_workflows = self._initialize_fallback_workflows()

    # ==========================================================================
    # ERROR CATEGORIZATION
    # ==========================================================================

    def categorize_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Categorize error with severity and suggested recovery

        Args:
            exception: The exception that occurred
            context: Additional context (session_id, user_id, etc.)

        Returns:
            Error classification with recovery suggestions
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)

        # Determine category
        category = self._determine_error_category(exception_type, exception_message)

        # Determine severity
        severity = self._determine_error_severity(category, exception, context)

        # Get recovery strategy
        recovery_strategy = self._get_recovery_strategy(category, severity)

        # Check if retryable
        is_retryable = self._is_retryable(category, exception)

        # Get contextual message
        user_message = self._generate_user_facing_message(
            category=category,
            severity=severity,
            exception_message=exception_message,
            context=context
        )

        return {
            'error_id': self._generate_error_id(exception, context),
            'category': category.value,
            'severity': severity.value,
            'exception_type': exception_type,
            'exception_message': exception_message,
            'is_retryable': is_retryable,
            'recovery_strategy': recovery_strategy,
            'user_message': user_message,
            'technical_details': self._sanitize_technical_details(exception, context),
            'occurred_at': timezone.now().isoformat()
        }

    def _determine_error_category(
        self,
        exception_type: str,
        exception_message: str
    ) -> ErrorCategory:
        """Determine error category from exception type and message"""
        # Check patterns
        for pattern, category in self.error_patterns.items():
            if re.search(pattern, exception_type, re.IGNORECASE):
                return category
            if re.search(pattern, exception_message, re.IGNORECASE):
                return category

        # Default categorization
        if 'Database' in exception_type or 'Integrity' in exception_type:
            return ErrorCategory.DATABASE
        elif 'Connection' in exception_type or 'Timeout' in exception_type:
            return ErrorCategory.NETWORK
        elif 'Validation' in exception_type or 'Invalid' in exception_message:
            return ErrorCategory.VALIDATION
        elif 'Permission' in exception_type or 'Forbidden' in exception_message:
            return ErrorCategory.AUTHORIZATION
        elif 'LLM' in exception_type or 'AI' in exception_type:
            return ErrorCategory.LLM_API
        else:
            return ErrorCategory.UNKNOWN

    def _determine_error_severity(
        self,
        category: ErrorCategory,
        exception: Exception,
        context: Optional[Dict[str, Any]]
    ) -> ErrorSeverity:
        """Determine error severity based on category and context"""
        # Critical severity conditions
        if category in [ErrorCategory.DATABASE, ErrorCategory.DATA_INTEGRITY]:
            return ErrorSeverity.CRITICAL

        # High severity conditions
        if category in [ErrorCategory.LLM_API, ErrorCategory.AUTHENTICATION]:
            return ErrorSeverity.HIGH

        # Medium severity
        if category in [ErrorCategory.NETWORK, ErrorCategory.EXTERNAL_API]:
            return ErrorSeverity.MEDIUM

        # Low severity
        if category in [ErrorCategory.VALIDATION, ErrorCategory.CACHE]:
            return ErrorSeverity.LOW

        # Check context for session importance
        if context and context.get('is_critical_session'):
            return ErrorSeverity.HIGH

        return ErrorSeverity.MEDIUM

    def _is_retryable(self, category: ErrorCategory, exception: Exception) -> bool:
        """Determine if error is retryable"""
        # Non-retryable categories
        non_retryable = [
            ErrorCategory.VALIDATION,
            ErrorCategory.AUTHORIZATION,
            ErrorCategory.DATA_INTEGRITY
        ]

        if category in non_retryable:
            return False

        # Retryable categories
        retryable = [
            ErrorCategory.NETWORK,
            ErrorCategory.DATABASE,
            ErrorCategory.LLM_API,
            ErrorCategory.CACHE
        ]

        return category in retryable

    # ==========================================================================
    # RETRY STRATEGIES
    # ==========================================================================

    def get_retry_configuration(
        self,
        error_categorization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get retry configuration for error

        Args:
            error_categorization: Result from categorize_error()

        Returns:
            Retry configuration (delay, max_attempts, backoff)
        """
        category = error_categorization['category']
        severity = error_categorization['severity']

        strategy = self.retry_strategies.get(category, self.retry_strategies['default'])

        # Adjust for severity
        if severity == ErrorSeverity.CRITICAL.value:
            strategy['max_attempts'] = max(strategy['max_attempts'], 5)
            strategy['initial_delay_seconds'] = 1  # Retry faster for critical
        elif severity == ErrorSeverity.LOW.value:
            strategy['max_attempts'] = min(strategy['max_attempts'], 2)

        return strategy

    def calculate_retry_delay(
        self,
        attempt: int,
        strategy: Dict[str, Any]
    ) -> float:
        """
        Calculate delay before next retry attempt

        Args:
            attempt: Current retry attempt (1-indexed)
            strategy: Retry strategy configuration

        Returns:
            Delay in seconds
        """
        initial_delay = strategy['initial_delay_seconds']
        backoff_factor = strategy['backoff_factor']
        max_delay = strategy['max_delay_seconds']

        if strategy['backoff_type'] == 'exponential':
            delay = initial_delay * (backoff_factor ** (attempt - 1))
        elif strategy['backoff_type'] == 'linear':
            delay = initial_delay * attempt
        else:  # fixed
            delay = initial_delay

        # Apply jitter (±20%)
        import random
        jitter = delay * 0.2 * (random.random() - 0.5) * 2
        delay = delay + jitter

        return min(delay, max_delay)

    # ==========================================================================
    # USER-FACING MESSAGES
    # ==========================================================================

    def _generate_user_facing_message(
        self,
        category: ErrorCategory,
        severity: ErrorSeverity,
        exception_message: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Generate contextual, user-friendly error message

        Returns:
            Dict with 'title', 'message', 'action_button', 'help_link'
        """
        # Category-specific messages
        messages = {
            ErrorCategory.DATABASE: {
                'title': 'Temporary Service Issue',
                'message': 'We\'re experiencing a temporary issue saving your progress. Your data is safe, and we\'re working to resolve this.',
                'action_button': 'Try Again',
                'help_link': '/help/service-issues'
            },
            ErrorCategory.NETWORK: {
                'title': 'Connection Issue',
                'message': 'We\'re having trouble connecting to our services. Please check your internet connection and try again.',
                'action_button': 'Retry',
                'help_link': '/help/connection-issues'
            },
            ErrorCategory.LLM_API: {
                'title': 'AI Service Temporarily Unavailable',
                'message': 'Our AI service is temporarily unavailable. We\'re working to restore it. You can continue manually or try again shortly.',
                'action_button': 'Continue Manually',
                'help_link': '/help/ai-service'
            },
            ErrorCategory.VALIDATION: {
                'title': 'Invalid Input',
                'message': self._extract_validation_message(exception_message),
                'action_button': 'Review Input',
                'help_link': '/help/input-validation'
            },
            ErrorCategory.AUTHORIZATION: {
                'title': 'Access Denied',
                'message': 'You don\'t have permission to perform this action. Please contact your administrator if you believe this is an error.',
                'action_button': 'Go Back',
                'help_link': '/help/permissions'
            },
            ErrorCategory.STATE_TRANSITION: {
                'title': 'Invalid Action',
                'message': 'This action cannot be performed at this time. Please complete the previous steps first.',
                'action_button': 'Continue',
                'help_link': '/help/workflow'
            }
        }

        default_message = {
            'title': 'Something Went Wrong',
            'message': 'We encountered an unexpected issue. Our team has been notified, and we\'re working to fix it.',
            'action_button': 'Try Again',
            'help_link': '/help/general-errors'
        }

        message = messages.get(category, default_message)

        # Add severity indicator for critical errors
        if severity == ErrorSeverity.CRITICAL:
            message['severity_indicator'] = 'This is a critical issue affecting service availability.'

        # Add session recovery suggestion if available
        if context and context.get('has_checkpoint'):
            message['recovery_hint'] = 'Your progress has been saved. You can resume from where you left off.'

        return message

    def _extract_validation_message(self, exception_message: str) -> str:
        """Extract user-friendly validation message"""
        # Remove technical jargon
        cleaned = exception_message.replace('ValidationError:', '').strip()
        cleaned = re.sub(r'\[.*?\]', '', cleaned)  # Remove field names in brackets

        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return cleaned or 'Please review your input and try again.'

    # ==========================================================================
    # FALLBACK WORKFLOWS
    # ==========================================================================

    def get_fallback_workflow(
        self,
        error_categorization: Dict[str, Any],
        session_state: str
    ) -> Dict[str, Any]:
        """
        Get fallback workflow for error

        Args:
            error_categorization: Result from categorize_error()
            session_state: Current session state

        Returns:
            Fallback workflow steps
        """
        category = error_categorization['category']

        # Get base fallback for category
        fallback = self.fallback_workflows.get(category, self.fallback_workflows['default'])

        # Customize based on session state
        if session_state == 'GENERATING_RECOMMENDATIONS':
            if category == ErrorCategory.LLM_API.value:
                fallback['steps'] = [
                    {
                        'action': 'use_template_recommendations',
                        'description': 'Use pre-configured templates instead of AI',
                        'automated': True
                    },
                    {
                        'action': 'notify_user',
                        'description': 'Inform user of fallback mode',
                        'automated': True
                    }
                ]

        return fallback

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _generate_error_id(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate unique error ID for tracking"""
        import hashlib
        error_string = f"{type(exception).__name__}:{str(exception)}:{timezone.now().isoformat()}"
        if context and context.get('session_id'):
            error_string += f":{context['session_id']}"

        return hashlib.sha256(error_string.encode()).hexdigest()[:12]

    def _sanitize_technical_details(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sanitize technical details for logging (Rule #15)"""
        import traceback

        # Sanitize context
        safe_context = {}
        if context:
            # Remove sensitive data
            safe_keys = ['session_id', 'user_id', 'action', 'state']
            safe_context = {k: v for k, v in context.items() if k in safe_keys}

        return {
            'exception_type': type(exception).__name__,
            'traceback_lines': traceback.format_exc().split('\n')[-5:],  # Last 5 lines
            'context': safe_context
        }

    def _initialize_retry_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize retry strategies for different error categories"""
        return {
            ErrorCategory.DATABASE.value: {
                'max_attempts': 3,
                'initial_delay_seconds': 1,
                'backoff_factor': 2,
                'backoff_type': 'exponential',
                'max_delay_seconds': 30
            },
            ErrorCategory.NETWORK.value: {
                'max_attempts': 5,
                'initial_delay_seconds': 2,
                'backoff_factor': 2,
                'backoff_type': 'exponential',
                'max_delay_seconds': 60
            },
            ErrorCategory.LLM_API.value: {
                'max_attempts': 4,
                'initial_delay_seconds': 3,
                'backoff_factor': 2.5,
                'backoff_type': 'exponential',
                'max_delay_seconds': 120
            },
            ErrorCategory.EXTERNAL_API.value: {
                'max_attempts': 3,
                'initial_delay_seconds': 5,
                'backoff_factor': 2,
                'backoff_type': 'exponential',
                'max_delay_seconds': 90
            },
            'default': {
                'max_attempts': 2,
                'initial_delay_seconds': 2,
                'backoff_factor': 2,
                'backoff_type': 'exponential',
                'max_delay_seconds': 30
            }
        }

    def _initialize_error_patterns(self) -> Dict[str, ErrorCategory]:
        """Initialize regex patterns for error categorization"""
        return {
            r'database|postgres|mysql|sql': ErrorCategory.DATABASE,
            r'connection|timeout|network': ErrorCategory.NETWORK,
            r'cache|redis|memcache': ErrorCategory.CACHE,
            r'llm|openai|anthropic|gpt': ErrorCategory.LLM_API,
            r'translation|translate': ErrorCategory.TRANSLATION_API,
            r'validation|invalid|required': ErrorCategory.VALIDATION,
            r'permission|forbidden|unauthorized': ErrorCategory.AUTHORIZATION,
            r'state|transition|workflow': ErrorCategory.STATE_TRANSITION,
            r'integrity|constraint|duplicate': ErrorCategory.DATA_INTEGRITY
        }

    def _initialize_fallback_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Initialize fallback workflows for different error categories"""
        return {
            ErrorCategory.LLM_API.value: {
                'name': 'LLM Service Fallback',
                'steps': [
                    {
                        'action': 'use_cached_response',
                        'description': 'Check for cached similar response',
                        'automated': True
                    },
                    {
                        'action': 'use_template_response',
                        'description': 'Use pre-configured template',
                        'automated': True
                    },
                    {
                        'action': 'manual_fallback',
                        'description': 'Allow user to proceed manually',
                        'automated': False
                    }
                ]
            },
            ErrorCategory.DATABASE.value: {
                'name': 'Database Failure Fallback',
                'steps': [
                    {
                        'action': 'save_to_cache',
                        'description': 'Temporarily save to cache',
                        'automated': True
                    },
                    {
                        'action': 'background_sync',
                        'description': 'Queue for background sync when DB recovers',
                        'automated': True
                    }
                ]
            },
            'default': {
                'name': 'Generic Error Fallback',
                'steps': [
                    {
                        'action': 'log_error',
                        'description': 'Log error for investigation',
                        'automated': True
                    },
                    {
                        'action': 'notify_user',
                        'description': 'Show friendly error message',
                        'automated': True
                    },
                    {
                        'action': 'provide_support_link',
                        'description': 'Offer support contact',
                        'automated': True
                    }
                ]
            }
        }


# Service factory function
def get_error_recovery_service() -> ErrorRecoveryService:
    """Get error recovery service instance"""
    return ErrorRecoveryService()


__all__ = [
    'ErrorRecoveryService',
    'ErrorSeverity',
    'ErrorCategory',
    'get_error_recovery_service',
]
