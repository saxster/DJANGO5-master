"""
PII Detection Service for User-Generated Content.

Detects and optionally sanitizes PII in user-generated content:
- Journal entries
- Comments and notes
- Ticket descriptions
- Form submissions
- Any user-provided text

CRITICAL: Prevents accidental PII exposure in logs when user content is logged.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from django.conf import settings

from apps.core.services.base_service import BaseService, monitor_service_performance
from apps.core.middleware.logging_sanitization import LogSanitizationService

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    DATE_OF_BIRTH = "date_of_birth"


@dataclass
class PIIDetectionResult:
    """Result of PII detection in content."""
    contains_pii: bool
    pii_types_found: List[str]
    pii_count: int
    sanitized_content: Optional[str] = None
    detection_confidence: float = 1.0


class PIIDetectionService(BaseService):
    """
    Service for detecting PII in user-generated content.

    Features:
    1. Multi-pattern PII detection
    2. Content sanitization
    3. Detection confidence scoring
    4. Safe logging of user content
    5. Compliance with data protection regulations
    """

    def __init__(self):
        super().__init__()
        self.detection_patterns = self._initialize_patterns()
        self.enable_auto_sanitization = True


    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "PIIDetectionService"
    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize PII detection patterns."""
        return {
            PIIType.EMAIL.value: LogSanitizationService.EMAIL_PATTERN,
            PIIType.PHONE.value: LogSanitizationService.PHONE_PATTERN,
            PIIType.CREDIT_CARD.value: LogSanitizationService.CREDIT_CARD_PATTERN,
            PIIType.SSN.value: re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            PIIType.IP_ADDRESS.value: re.compile(
                r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ),
            PIIType.DATE_OF_BIRTH.value: re.compile(
                r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12][0-9]|3[01])[/-](?:19|20)\d{2}\b'
            ),
            PIIType.PASSPORT.value: re.compile(
                r'\b[A-Z]{1,2}\d{6,9}\b'
            ),
        }

    @monitor_service_performance("detect_pii")
    def detect_pii(
        self,
        content: str,
        sanitize: bool = False
    ) -> PIIDetectionResult:
        """
        Detect PII in user-generated content.

        Args:
            content: Text content to analyze
            sanitize: Whether to return sanitized version

        Returns:
            PIIDetectionResult with detection and optionally sanitized content
        """
        if not content or not isinstance(content, str):
            return PIIDetectionResult(
                contains_pii=False,
                pii_types_found=[],
                pii_count=0
            )

        pii_types_found = set()
        total_matches = 0

        for pii_type, pattern in self.detection_patterns.items():
            matches = pattern.findall(content)
            if matches:
                pii_types_found.add(pii_type)
                total_matches += len(matches)

        contains_pii = len(pii_types_found) > 0

        result = PIIDetectionResult(
            contains_pii=contains_pii,
            pii_types_found=list(pii_types_found),
            pii_count=total_matches,
            detection_confidence=self._calculate_confidence(content, pii_types_found)
        )

        if sanitize and contains_pii:
            result.sanitized_content = LogSanitizationService.sanitize_message(content)

        return result

    def _calculate_confidence(
        self,
        content: str,
        pii_types: Set[str]
    ) -> float:
        """Calculate confidence score for PII detection."""
        if not pii_types:
            return 1.0

        confidence = 1.0

        if PIIType.EMAIL.value in pii_types:
            email_count = len(LogSanitizationService.EMAIL_PATTERN.findall(content))
            if email_count > 5:
                confidence *= 0.9

        if PIIType.PHONE.value in pii_types:
            phone_context = re.search(r'(call|phone|mobile|contact)', content, re.IGNORECASE)
            if phone_context:
                confidence *= 1.0
            else:
                confidence *= 0.8

        return round(confidence, 2)

    @monitor_service_performance("safe_log_user_content")
    def safe_log_user_content(
        self,
        content: str,
        max_length: int = 200,
        detect_pii: bool = True
    ) -> str:
        """
        Create a safe version of user content for logging.

        Args:
            content: User-generated content
            max_length: Maximum length to include
            detect_pii: Whether to detect and sanitize PII

        Returns:
            str: Safe version of content for logging
        """
        if not content:
            return "[empty]"

        truncated = content[:max_length] + "..." if len(content) > max_length else content

        if detect_pii:
            detection = self.detect_pii(truncated, sanitize=True)
            if detection.contains_pii:
                self.logger.info(
                    "PII detected in user content",
                    extra={
                        'pii_types': detection.pii_types_found,
                        'pii_count': detection.pii_count,
                        'content_length': len(content)
                    }
                )
                return detection.sanitized_content or "[PII_REDACTED]"

        return truncated

    @monitor_service_performance("analyze_content_for_logging")
    def analyze_content_for_logging(
        self,
        content_dict: Dict[str, any]
    ) -> Dict[str, any]:
        """
        Analyze and sanitize a dictionary of content for safe logging.

        Args:
            content_dict: Dictionary with user-generated content

        Returns:
            Dict: Sanitized version safe for logging
        """
        safe_dict = {}

        for key, value in content_dict.items():
            if isinstance(value, str):
                detection = self.detect_pii(value)

                if detection.contains_pii:
                    safe_dict[key] = f"[CONTAINS_PII: {', '.join(detection.pii_types_found)}]"
                else:
                    safe_dict[key] = value[:100] + "..." if len(value) > 100 else value

            elif isinstance(value, dict):
                safe_dict[key] = self.analyze_content_for_logging(value)

            elif isinstance(value, (list, tuple)):
                safe_dict[key] = [
                    self.safe_log_user_content(str(item)) if isinstance(item, str) else item
                    for item in value
                ]

            else:
                safe_dict[key] = value

        return safe_dict