"""
Unified Task Failure Taxonomy System

Provides intelligent failure classification, automatic remediation suggestions,
and context-aware retry policies for all Celery tasks.

Features:
- Automatic failure type detection from exception patterns
- Remediation action recommendations
- Integration with DLQ and monitoring systems
- Extensible taxonomy for custom failure types

Usage:
    from apps.core.tasks.failure_taxonomy import FailureTaxonomy
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS


    try:
        task_logic()
    except CELERY_EXCEPTIONS as exc:
        failure_info = FailureTaxonomy.classify(exc, task_context)
        # Use failure_info for intelligent retry/alerting

Related Files:
- apps/core/models/task_failure_record.py - DLQ model
- background_tasks/dead_letter_queue.py - DLQ service
- apps/core/tasks/base.py - Base task classes
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from django.db import (
    IntegrityError, OperationalError, DataError, DatabaseError,
    InterfaceError, ProgrammingError
)
from django.core.exceptions import ValidationError, ObjectDoesNotExist

logger = logging.getLogger('celery.taxonomy')


# ============================================================================
# Failure Type Enumeration
# ============================================================================

class FailureType(Enum):
    """
    Comprehensive failure type classification for task execution.

    Each type has specific retry behavior and remediation strategies.
    """

    # Transient failures (auto-retry with backoff)
    TRANSIENT_DATABASE = "TRANSIENT_DATABASE"         # Deadlocks, connection pool exhausted
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"           # Timeouts, connection refused
    TRANSIENT_RESOURCE = "TRANSIENT_RESOURCE"         # Memory, CPU, disk space
    TRANSIENT_RATE_LIMIT = "TRANSIENT_RATE_LIMIT"     # API rate limiting

    # Permanent failures (no auto-retry, requires fix)
    PERMANENT_VALIDATION = "PERMANENT_VALIDATION"     # Invalid input data
    PERMANENT_NOT_FOUND = "PERMANENT_NOT_FOUND"       # Missing required data
    PERMANENT_PERMISSION = "PERMANENT_PERMISSION"     # Access denied
    PERMANENT_LOGIC = "PERMANENT_LOGIC"               # Business logic error

    # Configuration failures (requires config change)
    CONFIG_MISSING_SETTING = "CONFIG_MISSING_SETTING" # Missing environment variable
    CONFIG_INVALID_SETTING = "CONFIG_INVALID_SETTING" # Malformed configuration
    CONFIG_MISSING_SERVICE = "CONFIG_MISSING_SERVICE" # Service not configured

    # External service failures (retry with longer backoff)
    EXTERNAL_API_DOWN = "EXTERNAL_API_DOWN"           # 3rd party API unavailable
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"         # 3rd party API error response
    EXTERNAL_TIMEOUT = "EXTERNAL_TIMEOUT"             # External service timeout

    # System failures (requires immediate attention)
    SYSTEM_OUT_OF_MEMORY = "SYSTEM_OUT_OF_MEMORY"     # OOM killer
    SYSTEM_DISK_FULL = "SYSTEM_DISK_FULL"             # Disk space exhausted
    SYSTEM_WORKER_CRASH = "SYSTEM_WORKER_CRASH"       # Worker process crash

    # Unknown (default fallback)
    UNKNOWN = "UNKNOWN"


class RemediationAction(Enum):
    """Recommended remediation actions for each failure type."""

    AUTO_RETRY = "AUTO_RETRY"                         # Automatic retry with backoff
    MANUAL_RETRY = "MANUAL_RETRY"                     # Manual intervention needed
    FIX_DATA = "FIX_DATA"                             # Data correction required
    FIX_CONFIG = "FIX_CONFIG"                         # Configuration change needed
    SCALE_RESOURCES = "SCALE_RESOURCES"               # Add workers/resources
    ALERT_TEAM = "ALERT_TEAM"                         # Immediate team notification
    CHECK_EXTERNAL = "CHECK_EXTERNAL"                 # Check external service status
    INVESTIGATE = "INVESTIGATE"                       # Requires investigation


# ============================================================================
# Failure Classification Result
# ============================================================================

@dataclass
class FailureClassification:
    """
    Complete classification result for a task failure.

    Attributes:
        failure_type: Classified failure type
        confidence: Classification confidence (0.0-1.0)
        remediation_action: Recommended action
        remediation_details: Specific remediation instructions
        retry_recommended: Whether automatic retry is recommended
        retry_delay_seconds: Recommended retry delay
        alert_level: Alert severity (info, warning, critical)
        context: Additional context for debugging
    """
    failure_type: FailureType
    confidence: float
    remediation_action: RemediationAction
    remediation_details: str
    retry_recommended: bool
    retry_delay_seconds: int
    alert_level: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['failure_type'] = self.failure_type.value
        result['remediation_action'] = self.remediation_action.value
        return result


# ============================================================================
# Failure Taxonomy Classifier
# ============================================================================

class FailureTaxonomy:
    """
    Intelligent failure classification system for Celery tasks.

    Analyzes exceptions and task context to provide:
    - Failure type classification
    - Remediation recommendations
    - Retry policy suggestions
    - Alert severity determination
    """

    # Exception pattern matching rules
    EXCEPTION_PATTERNS = {
        # Database failures
        IntegrityError: (FailureType.PERMANENT_VALIDATION, 0.9),
        OperationalError: (FailureType.TRANSIENT_DATABASE, 0.8),
        DataError: (FailureType.PERMANENT_VALIDATION, 0.9),
        ProgrammingError: (FailureType.PERMANENT_LOGIC, 0.9),
        InterfaceError: (FailureType.TRANSIENT_DATABASE, 0.7),

        # Validation failures
        ValidationError: (FailureType.PERMANENT_VALIDATION, 0.95),
        ValueError: (FailureType.PERMANENT_VALIDATION, 0.8),
        TypeError: (FailureType.PERMANENT_LOGIC, 0.8),
        KeyError: (FailureType.PERMANENT_LOGIC, 0.7),

        # Resource failures
        ObjectDoesNotExist: (FailureType.PERMANENT_NOT_FOUND, 0.9),
        FileNotFoundError: (FailureType.PERMANENT_NOT_FOUND, 0.9),
        PermissionError: (FailureType.PERMANENT_PERMISSION, 0.95),

        # Network failures
        ConnectionError: (FailureType.TRANSIENT_NETWORK, 0.8),
        TimeoutError: (FailureType.TRANSIENT_NETWORK, 0.8),
        OSError: (FailureType.TRANSIENT_RESOURCE, 0.6),

        # Memory failures
        MemoryError: (FailureType.SYSTEM_OUT_OF_MEMORY, 1.0),
    }

    # Error message pattern matching
    MESSAGE_PATTERNS = [
        # Database patterns
        (r'deadlock detected', FailureType.TRANSIENT_DATABASE, 0.95),
        (r'connection pool exhausted', FailureType.TRANSIENT_DATABASE, 0.9),
        (r'too many connections', FailureType.TRANSIENT_DATABASE, 0.9),
        (r'database is locked', FailureType.TRANSIENT_DATABASE, 0.85),

        # Network patterns
        (r'connection refused', FailureType.TRANSIENT_NETWORK, 0.9),
        (r'connection timeout', FailureType.EXTERNAL_TIMEOUT, 0.9),
        (r'network is unreachable', FailureType.TRANSIENT_NETWORK, 0.9),
        (r'name resolution failed', FailureType.CONFIG_MISSING_SERVICE, 0.8),

        # Rate limiting patterns
        (r'rate limit exceeded', FailureType.TRANSIENT_RATE_LIMIT, 0.95),
        (r'too many requests', FailureType.TRANSIENT_RATE_LIMIT, 0.9),
        (r'429', FailureType.TRANSIENT_RATE_LIMIT, 0.85),

        # Resource patterns
        (r'out of memory', FailureType.SYSTEM_OUT_OF_MEMORY, 1.0),
        (r'disk quota exceeded', FailureType.SYSTEM_DISK_FULL, 0.95),
        (r'no space left', FailureType.SYSTEM_DISK_FULL, 0.95),

        # Configuration patterns
        (r'environment variable .* not set', FailureType.CONFIG_MISSING_SETTING, 0.9),
        (r'setting .* is required', FailureType.CONFIG_MISSING_SETTING, 0.9),
        (r'invalid configuration', FailureType.CONFIG_INVALID_SETTING, 0.85),

        # External API patterns
        (r'service unavailable', FailureType.EXTERNAL_API_DOWN, 0.85),
        (r'502 bad gateway', FailureType.EXTERNAL_API_DOWN, 0.9),
        (r'503 service unavailable', FailureType.EXTERNAL_API_DOWN, 0.9),
        (r'504 gateway timeout', FailureType.EXTERNAL_TIMEOUT, 0.9),
    ]

    # Remediation mapping
    REMEDIATION_MAP = {
        FailureType.TRANSIENT_DATABASE: (
            RemediationAction.AUTO_RETRY,
            "Database deadlock or connection issue - will retry automatically",
            True, 60, "warning"
        ),
        FailureType.TRANSIENT_NETWORK: (
            RemediationAction.AUTO_RETRY,
            "Network connectivity issue - will retry automatically",
            True, 120, "warning"
        ),
        FailureType.TRANSIENT_RATE_LIMIT: (
            RemediationAction.AUTO_RETRY,
            "Rate limit exceeded - will retry after backoff period",
            True, 300, "info"
        ),
        FailureType.PERMANENT_VALIDATION: (
            RemediationAction.FIX_DATA,
            "Invalid input data - requires data correction before retry",
            False, 0, "error"
        ),
        FailureType.PERMANENT_NOT_FOUND: (
            RemediationAction.FIX_DATA,
            "Required data not found - verify data exists and retry",
            False, 0, "error"
        ),
        FailureType.PERMANENT_PERMISSION: (
            RemediationAction.FIX_CONFIG,
            "Permission denied - check service account permissions",
            False, 0, "critical"
        ),
        FailureType.CONFIG_MISSING_SETTING: (
            RemediationAction.FIX_CONFIG,
            "Missing configuration - add required environment variable",
            False, 0, "critical"
        ),
        FailureType.EXTERNAL_API_DOWN: (
            RemediationAction.CHECK_EXTERNAL,
            "External service unavailable - check service status and retry",
            True, 1800, "warning"
        ),
        FailureType.SYSTEM_OUT_OF_MEMORY: (
            RemediationAction.SCALE_RESOURCES,
            "Out of memory - increase worker memory or reduce batch size",
            False, 0, "critical"
        ),
        FailureType.UNKNOWN: (
            RemediationAction.INVESTIGATE,
            "Unknown failure type - requires investigation",
            False, 0, "error"
        ),
    }

    @classmethod
    def classify(
        cls,
        exception: Exception,
        task_context: Optional[Dict[str, Any]] = None
    ) -> FailureClassification:
        """
        Classify task failure and provide remediation guidance.

        Args:
            exception: The exception that caused failure
            task_context: Optional task execution context
                - task_name: Name of the failed task
                - task_args: Task arguments
                - retry_count: Number of retries attempted
                - execution_time: Task execution duration

        Returns:
            FailureClassification with complete analysis

        Example:
            try:
                result = risky_operation()
            except (ValueError, TypeError, AttributeError) as exc:
                classification = FailureTaxonomy.classify(
                    exc,
                    {'task_name': 'process_data', 'retry_count': 2}
                )
                logger.error(f"Task failed: {classification.remediation_details}")
        """
        task_context = task_context or {}

        # Step 1: Exception type matching
        failure_type, confidence = cls._classify_by_exception_type(exception)

        # Step 2: Message pattern matching (can override type matching)
        message_type, message_confidence = cls._classify_by_message(str(exception))

        # Use message pattern if higher confidence
        if message_confidence > confidence:
            failure_type = message_type
            confidence = message_confidence

        # Step 3: Context-based refinement
        failure_type, confidence = cls._refine_with_context(
            failure_type, confidence, exception, task_context
        )

        # Step 4: Get remediation details
        remediation = cls._get_remediation(failure_type)

        # Step 5: Build classification result
        classification = FailureClassification(
            failure_type=failure_type,
            confidence=confidence,
            remediation_action=remediation[0],
            remediation_details=remediation[1],
            retry_recommended=remediation[2],
            retry_delay_seconds=remediation[3],
            alert_level=remediation[4],
            context={
                'exception_type': type(exception).__name__,
                'exception_message': str(exception)[:500],
                'task_name': task_context.get('task_name'),
                'retry_count': task_context.get('retry_count', 0),
            }
        )

        # Log classification
        logger.info(
            f"Classified failure: {failure_type.value} (confidence: {confidence:.2f})",
            extra={
                'failure_type': failure_type.value,
                'confidence': confidence,
                'remediation_action': remediation[0].value,
                'task_name': task_context.get('task_name'),
            }
        )

        return classification

    @classmethod
    def _classify_by_exception_type(cls, exception: Exception) -> Tuple[FailureType, float]:
        """Classify failure by exception type."""
        exc_type = type(exception)

        # Direct match
        if exc_type in cls.EXCEPTION_PATTERNS:
            return cls.EXCEPTION_PATTERNS[exc_type]

        # Check inheritance
        for pattern_type, (failure_type, confidence) in cls.EXCEPTION_PATTERNS.items():
            if isinstance(exception, pattern_type):
                return failure_type, confidence * 0.8  # Lower confidence for inherited match

        return FailureType.UNKNOWN, 0.5

    @classmethod
    def _classify_by_message(cls, message: str) -> Tuple[FailureType, float]:
        """Classify failure by error message patterns."""
        message_lower = message.lower()

        best_match = (FailureType.UNKNOWN, 0.0)

        for pattern, failure_type, confidence in cls.MESSAGE_PATTERNS:
            if re.search(pattern, message_lower):
                if confidence > best_match[1]:
                    best_match = (failure_type, confidence)

        return best_match

    @classmethod
    def _refine_with_context(
        cls,
        failure_type: FailureType,
        confidence: float,
        exception: Exception,
        task_context: Dict[str, Any]
    ) -> Tuple[FailureType, float]:
        """Refine classification using task execution context."""

        # If retry count is high and still transient, increase confidence in permanent
        retry_count = task_context.get('retry_count', 0)
        if retry_count >= 3 and failure_type.value.startswith('TRANSIENT'):
            # After 3 retries, less confident it's transient
            confidence *= 0.7

        # Check for database-related task names
        task_name = task_context.get('task_name', '')
        if 'database' in task_name.lower() or 'migration' in task_name.lower():
            if isinstance(exception, (DatabaseError, OperationalError)):
                confidence = min(confidence * 1.2, 1.0)

        # Check execution time for timeout classification
        execution_time = task_context.get('execution_time', 0)
        if execution_time > 300 and isinstance(exception, (TimeoutError, ConnectionError)):
            failure_type = FailureType.EXTERNAL_TIMEOUT
            confidence = 0.9

        return failure_type, min(confidence, 1.0)

    @classmethod
    def _get_remediation(cls, failure_type: FailureType) -> Tuple:
        """Get remediation details for failure type."""
        return cls.REMEDIATION_MAP.get(
            failure_type,
            cls.REMEDIATION_MAP[FailureType.UNKNOWN]
        )

    @classmethod
    def get_retry_policy(cls, failure_type: FailureType) -> Dict[str, Any]:
        """
        Get recommended retry policy for failure type.

        Returns:
            Policy dict with max_retries, initial_delay, backoff_factor, max_delay
        """
        policies = {
            FailureType.TRANSIENT_DATABASE: {
                'max_retries': 5,
                'initial_delay': 30,
                'backoff_factor': 2.0,
                'max_delay': 3600,
            },
            FailureType.TRANSIENT_NETWORK: {
                'max_retries': 3,
                'initial_delay': 60,
                'backoff_factor': 2.0,
                'max_delay': 1800,
            },
            FailureType.TRANSIENT_RATE_LIMIT: {
                'max_retries': 3,
                'initial_delay': 300,
                'backoff_factor': 3.0,
                'max_delay': 3600,
            },
            FailureType.EXTERNAL_API_DOWN: {
                'max_retries': 2,
                'initial_delay': 900,
                'backoff_factor': 2.0,
                'max_delay': 7200,
            },
        }

        return policies.get(failure_type, {
            'max_retries': 0,
            'initial_delay': 0,
            'backoff_factor': 1.0,
            'max_delay': 0,
        })

    @classmethod
    def should_alert(cls, classification: FailureClassification) -> bool:
        """Determine if failure requires immediate alerting."""
        critical_types = {
            FailureType.SYSTEM_OUT_OF_MEMORY,
            FailureType.SYSTEM_DISK_FULL,
            FailureType.SYSTEM_WORKER_CRASH,
            FailureType.PERMANENT_PERMISSION,
        }

        return (
            classification.failure_type in critical_types or
            classification.alert_level == 'critical' or
            (classification.context.get('retry_count', 0) >= 5)
        )
