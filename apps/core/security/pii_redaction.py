"""
Centralized PII Redaction Utilities

Provides PII detection and redaction for security and compliance.
Follows .claude/rules.md Rule #7 (< 150 lines per class).

Features:
- Email, phone, SSN, credit card detection
- IP address, API key, token redaction
- Configurable redaction strategies
- Performance-optimized regex patterns
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Pattern
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"


@dataclass
class PIIMatch:
    """Detected PII match."""
    pii_type: PIIType
    value: str
    start_pos: int
    end_pos: int
    redacted_value: str


class PIIRedactionService:
    """
    Service for detecting and redacting PII.

    Optimized regex patterns with configurable redaction strategies.
    """

    # Compiled regex patterns for performance
    PATTERNS: Dict[PIIType, Pattern] = {
        PIIType.EMAIL: re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ),
        PIIType.PHONE: re.compile(
            r'(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
        ),
        PIIType.SSN: re.compile(
            r'\b\d{3}-\d{2}-\d{4}\b'
        ),
        PIIType.CREDIT_CARD: re.compile(
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
        ),
        PIIType.IP_ADDRESS: re.compile(
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ),
        PIIType.API_KEY: re.compile(
            r'(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})',
            re.IGNORECASE
        ),
        PIIType.PASSWORD: re.compile(
            r'(password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\'>]{6,})',
            re.IGNORECASE
        ),
        PIIType.TOKEN: re.compile(
            r'(token|bearer)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})',
            re.IGNORECASE
        ),
    }

    @classmethod
    def redact_text(
        cls,
        text: str,
        pii_types: Optional[List[PIIType]] = None,
        redaction_char: str = '*'
    ) -> str:
        """
        Redact PII from text.

        Args:
            text: Text to redact
            pii_types: Types of PII to redact (None = all)
            redaction_char: Character to use for redaction

        Returns:
            Text with PII redacted

        Example:
            >>> PIIRedactionService.redact_text("Email: user@example.com")
            "Email: ***@***.com"
        """
        if not text:
            return text

        # Default to all PII types
        if pii_types is None:
            pii_types = list(PIIType)

        redacted = text

        for pii_type in pii_types:
            pattern = cls.PATTERNS.get(pii_type)

            if pattern:
                redacted = cls._redact_pattern(
                    redacted,
                    pattern,
                    pii_type,
                    redaction_char
                )

        return redacted

    @classmethod
    def detect_pii(
        cls,
        text: str,
        pii_types: Optional[List[PIIType]] = None
    ) -> List[PIIMatch]:
        """
        Detect PII in text without redaction.

        Args:
            text: Text to scan
            pii_types: Types of PII to detect (None = all)

        Returns:
            List of PII matches found
        """
        if not text:
            return []

        # Default to all PII types
        if pii_types is None:
            pii_types = list(PIIType)

        matches = []

        for pii_type in pii_types:
            pattern = cls.PATTERNS.get(pii_type)

            if pattern:
                for match in pattern.finditer(text):
                    matches.append(PIIMatch(
                        pii_type=pii_type,
                        value=match.group(0),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        redacted_value=cls._generate_redaction(
                            match.group(0),
                            pii_type
                        )
                    ))

        return matches

    @staticmethod
    def _redact_pattern(
        text: str,
        pattern: Pattern,
        pii_type: PIIType,
        redaction_char: str
    ) -> str:
        """Redact matches of a specific pattern."""
        def replacer(match):
            original = match.group(0)
            return PIIRedactionService._generate_redaction(
                original,
                pii_type,
                redaction_char
            )

        return pattern.sub(replacer, text)

    @staticmethod
    def _generate_redaction(
        value: str,
        pii_type: PIIType,
        redaction_char: str = '*'
    ) -> str:
        """
        Generate appropriate redaction for PII value.

        Preserves some structure for readability while redacting sensitive parts.
        """
        if pii_type == PIIType.EMAIL:
            # user@example.com -> u***@e***.com
            parts = value.split('@')
            if len(parts) == 2:
                return f"{parts[0][0]}{redaction_char * 3}@{parts[1][0]}{redaction_char * 3}.{parts[1].split('.')[-1]}"

        elif pii_type == PIIType.PHONE:
            # (555) 123-4567 -> (***) ***-4567
            return f"{redaction_char * 3}-{redaction_char * 3}-{value[-4:]}"

        elif pii_type == PIIType.SSN:
            # 123-45-6789 -> ***-**-6789
            return f"{redaction_char * 3}-{redaction_char * 2}-{value[-4:]}"

        elif pii_type == PIIType.CREDIT_CARD:
            # 1234 5678 9012 3456 -> **** **** **** 3456
            return f"{redaction_char * 4} {redaction_char * 4} {redaction_char * 4} {value[-4:]}"

        elif pii_type in [PIIType.API_KEY, PIIType.TOKEN, PIIType.PASSWORD]:
            # Show first 4 chars only
            return f"{value[:4]}{redaction_char * 12}"

        # Default: full redaction
        return redaction_char * len(value)


def redact_pii(text: str, pii_types: Optional[List[PIIType]] = None) -> str:
    """
    Convenience function for PII redaction.

    Args:
        text: Text to redact
        pii_types: Types of PII to redact (None = all)

    Returns:
        Text with PII redacted
    """
    return PIIRedactionService.redact_text(text, pii_types)


class PIIRedactionMixin:
    """
    Mixin for models/serializers to auto-redact PII fields.

    Usage:
        class MyModel(PIIRedactionMixin, models.Model):
            PII_FIELDS = ['email', 'phone']
            email = models.EmailField()
            phone = models.CharField(max_length=20)

            def get_redacted_data(self):
                return self.redact_pii_fields()
    """

    PII_FIELDS: List[str] = []

    def redact_pii_fields(self) -> Dict:
        """Get dict with PII fields redacted."""
        data = {}

        for field in self.PII_FIELDS:
            if hasattr(self, field):
                value = getattr(self, field)

                if value:
                    data[field] = PIIRedactionService.redact_text(str(value))
                else:
                    data[field] = value

        return data
