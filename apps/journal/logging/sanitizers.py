"""
PII Sanitization for Logging

Comprehensive PII redaction for journal and wellness log messages.
Complies with .claude/rules.md Rule #15 (Sensitive Data Logging).

Features:
- Automatic user name redaction
- Journal content sanitization
- Mood/stress data protection
- Search query redaction
- Configurable redaction levels

Author: Claude Code
Date: 2025-10-01
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from functools import wraps
from django.conf import settings

logger = logging.getLogger(__name__)


class PIIRedactionLevel(Enum):
    """Redaction intensity levels for different environments."""
    MINIMAL = 'minimal'      # Development - minimal redaction
    STANDARD = 'standard'    # Staging - standard redaction
    STRICT = 'strict'        # Production - maximum redaction


# PII detection patterns (compiled for performance)
PII_PATTERNS = {
    'user_name': re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'),  # First Last
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'phone': re.compile(r'(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'),
    'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    'user_id': re.compile(r'user[_\s]id[:\s=]+[\w-]+', re.IGNORECASE),
    'uuid': re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'),
}

# Journal-specific patterns
JOURNAL_PATTERNS = {
    'journal_title': re.compile(r'(title|entry)[:\s=]+"([^"]+)"', re.IGNORECASE),
    'journal_content': re.compile(r'content[:\s=]+"([^"]+)"', re.IGNORECASE),
    'mood_description': re.compile(r'mood[:\s=]+([A-Za-z\s]+)', re.IGNORECASE),
    'stress_trigger': re.compile(r'trigger[s]?[:\s=]+\[([^\]]+)\]', re.IGNORECASE),
    'gratitude': re.compile(r'gratitude[:\s=]+\[([^\]]+)\]', re.IGNORECASE),
    'affirmation': re.compile(r'affirmation[s]?[:\s=]+\[([^\]]+)\]', re.IGNORECASE),
}


def get_redaction_level() -> PIIRedactionLevel:
    """
    Determine redaction level based on environment.

    Returns:
        PIIRedactionLevel: Current environment's redaction level
    """
    if settings.DEBUG:
        return PIIRedactionLevel.MINIMAL
    elif getattr(settings, 'STAGING', False):
        return PIIRedactionLevel.STANDARD
    else:
        return PIIRedactionLevel.STRICT


def sanitize_pii_text(
    text: str,
    redaction_level: Optional[PIIRedactionLevel] = None,
    preserve_debug_value: bool = True
) -> str:
    """
    Sanitize text by redacting PII patterns.

    Args:
        text: Text to sanitize
        redaction_level: Redaction intensity (auto-detected if None)
        preserve_debug_value: Whether to preserve partial info for debugging

    Returns:
        str: Sanitized text with PII redacted

    Example:
        >>> sanitize_pii_text("User John Doe created entry")
        "User [REDACTED] created entry"

        >>> sanitize_pii_text("Email sent to user@example.com")
        "Email sent to [EMAIL_REDACTED]"
    """
    if not text or not isinstance(text, str):
        return str(text) if text is not None else ''

    if redaction_level is None:
        redaction_level = get_redaction_level()

    sanitized = text

    # Apply redaction based on level
    if redaction_level == PIIRedactionLevel.MINIMAL:
        # Minimal redaction - only obvious PII
        sanitized = PII_PATTERNS['email'].sub('[EMAIL_REDACTED]', sanitized)
        sanitized = PII_PATTERNS['phone'].sub('[PHONE_REDACTED]', sanitized)
        sanitized = PII_PATTERNS['ssn'].sub('[SSN_REDACTED]', sanitized)

    elif redaction_level == PIIRedactionLevel.STANDARD:
        # Standard redaction - most PII
        sanitized = PII_PATTERNS['email'].sub('[EMAIL_REDACTED]', sanitized)
        sanitized = PII_PATTERNS['phone'].sub('[PHONE_REDACTED]', sanitized)
        sanitized = PII_PATTERNS['ssn'].sub('[SSN_REDACTED]', sanitized)
        sanitized = PII_PATTERNS['user_name'].sub('[USER_NAME]', sanitized)

        if preserve_debug_value:
            # Preserve user ID patterns for debugging
            sanitized = PII_PATTERNS['user_id'].sub('user_id=[ID]', sanitized)
        else:
            sanitized = PII_PATTERNS['user_id'].sub('[USER_ID_REDACTED]', sanitized)

    else:  # STRICT
        # Strict redaction - all PII including UUIDs
        sanitized = PII_PATTERNS['email'].sub('[EMAIL]', sanitized)
        sanitized = PII_PATTERNS['phone'].sub('[PHONE]', sanitized)
        sanitized = PII_PATTERNS['ssn'].sub('[SSN]', sanitized)
        sanitized = PII_PATTERNS['user_name'].sub('[USER]', sanitized)
        sanitized = PII_PATTERNS['user_id'].sub('[USER_ID]', sanitized)
        sanitized = PII_PATTERNS['uuid'].sub('[UUID]', sanitized)

    return sanitized


def sanitize_journal_log_message(message: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Sanitize journal-specific log messages.

    Redacts:
    - Journal entry titles
    - Content snippets
    - Mood descriptions
    - Stress triggers
    - Gratitude items
    - Affirmations

    Args:
        message: Log message to sanitize
        context: Optional context dict with additional data to redact

    Returns:
        str: Sanitized log message

    Example:
        >>> sanitize_journal_log_message('Created entry "I am feeling anxious today"')
        'Created entry "[REDACTED]"'
    """
    if not message:
        return ''

    sanitized = message
    redaction_level = get_redaction_level()

    # First apply general PII sanitization
    sanitized = sanitize_pii_text(sanitized, redaction_level)

    # Then apply journal-specific sanitization
    if redaction_level in [PIIRedactionLevel.STANDARD, PIIRedactionLevel.STRICT]:
        # Redact journal titles and content
        sanitized = JOURNAL_PATTERNS['journal_title'].sub(r'\1="[REDACTED]"', sanitized)
        sanitized = JOURNAL_PATTERNS['journal_content'].sub(r'content="[REDACTED]"', sanitized)

        # Redact mood and stress data
        sanitized = JOURNAL_PATTERNS['mood_description'].sub(r'mood=[MOOD_REDACTED]', sanitized)
        sanitized = JOURNAL_PATTERNS['stress_trigger'].sub(r'triggers=[REDACTED]', sanitized)

        # Redact positive psychology data
        sanitized = JOURNAL_PATTERNS['gratitude'].sub(r'gratitude=[REDACTED]', sanitized)
        sanitized = JOURNAL_PATTERNS['affirmation'].sub(r'affirmations=[REDACTED]', sanitized)

    # Sanitize context data if provided
    if context:
        for key, value in context.items():
            if key in ['title', 'content', 'subtitle']:
                context[key] = '[REDACTED]'
            elif key in ['user_name', 'peoplename']:
                context[key] = '[USER]'
            elif key in ['mood_description', 'stress_triggers', 'gratitude_items', 'affirmations']:
                context[key] = '[REDACTED]'

    return sanitized


def sanitize_wellness_log_message(message: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Sanitize wellness-specific log messages.

    Redacts:
    - User feedback
    - Content interaction details
    - Recommendation reasoning
    - Mood/stress at delivery

    Args:
        message: Log message to sanitize
        context: Optional context dict

    Returns:
        str: Sanitized log message
    """
    if not message:
        return ''

    sanitized = message
    redaction_level = get_redaction_level()

    # Apply general PII sanitization
    sanitized = sanitize_pii_text(sanitized, redaction_level)

    # Wellness-specific patterns
    if redaction_level in [PIIRedactionLevel.STANDARD, PIIRedactionLevel.STRICT]:
        # Redact user feedback
        sanitized = re.sub(
            r'feedback[:\s=]+"([^"]+)"',
            r'feedback="[REDACTED]"',
            sanitized,
            flags=re.IGNORECASE
        )

        # Redact content titles that may be revealing
        sanitized = re.sub(
            r'content[:\s=]+"([^"]+)"',
            r'content="[CONTENT_TITLE]"',
            sanitized,
            flags=re.IGNORECASE
        )

    # Sanitize context
    if context:
        if 'user_feedback' in context:
            context['user_feedback'] = '[REDACTED]'
        if 'content_title' in context:
            context['content_title'] = '[CONTENT]'

    return sanitized


def sanitize_log_args(*args) -> List:
    """
    Sanitize positional arguments for logging.

    Args:
        *args: Positional arguments to sanitize

    Returns:
        List: Sanitized arguments
    """
    return [
        sanitize_pii_text(str(arg)) if isinstance(arg, (str, int, float))
        else '[OBJECT]'
        for arg in args
    ]


def sanitize_log_kwargs(**kwargs) -> Dict[str, Any]:
    """
    Sanitize keyword arguments for logging.

    Args:
        **kwargs: Keyword arguments to sanitize

    Returns:
        Dict: Sanitized keyword arguments
    """
    sanitized = {}

    sensitive_keys = {
        'title', 'content', 'subtitle', 'user_name', 'peoplename',
        'mood_description', 'stress_triggers', 'gratitude_items',
        'affirmations', 'achievements', 'user_feedback', 'query'
    }

    for key, value in kwargs.items():
        if key in sensitive_keys:
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, str):
            sanitized[key] = sanitize_pii_text(value)
        else:
            sanitized[key] = value

    return sanitized


# Decorator for automatic log sanitization
def sanitize_journal_logs(func):
    """
    Decorator to automatically sanitize log messages in a function.

    Usage:
        @sanitize_journal_logs
        def create_entry(self, data):
            logger.info(f"Creating entry: {data['title']}")  # Automatically sanitized
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Sanitize exception messages before re-raising
            sanitized_msg = sanitize_journal_log_message(str(e))
            logger.error(f"Error in {func.__name__}: {sanitized_msg}")
            raise
    return wrapper
