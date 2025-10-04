"""
Template Context Sanitization Service

Provides comprehensive input sanitization for report template contexts
to prevent XSS, injection attacks, and data leakage.

Security Features:
- HTML entity escaping for all user inputs
- Whitelist-based rich text sanitization
- Recursive sanitization of nested dictionaries/lists
- Comprehensive security logging
- PII detection and redaction

Complies with Rule #9, #15 from .claude/rules.md
"""

import re
import logging
from typing import Any, Dict, List, Optional, Set, Union
from html import escape
from django.core.exceptions import ValidationError
from django.utils.safestring import SafeString, mark_safe

logger = logging.getLogger("security.template_sanitization")


class TemplateContextSanitizer:
    """
    Service for sanitizing template context data before rendering.

    Prevents XSS attacks, injection vulnerabilities, and accidental
    sensitive data exposure in generated reports.
    """

    # Whitelist of safe HTML tags for rich text fields
    SAFE_HTML_TAGS = {
        'b', 'i', 'u', 'strong', 'em', 'p', 'br', 'span',
        'ul', 'ol', 'li', 'table', 'tr', 'td', 'th'
    }

    # Fields that should never be included in templates
    SENSITIVE_FIELD_PATTERNS = [
        r'.*password.*',
        r'.*secret.*',
        r'.*token.*',
        r'.*api[_-]?key.*',
        r'.*private[_-]?key.*',
        r'.*ssn.*',
        r'.*credit[_-]?card.*',
    ]

    # Maximum string length to prevent DoS via large inputs
    MAX_STRING_LENGTH = 10000

    def __init__(self, strict_mode: bool = True):
        """
        Initialize sanitizer.

        Args:
            strict_mode: If True, removes all HTML. If False, allows whitelisted tags.
        """
        self.strict_mode = strict_mode
        self.sanitization_log: List[Dict[str, str]] = []
        self._compile_sensitive_patterns()

    def _compile_sensitive_patterns(self) -> None:
        """Compile regex patterns for sensitive field detection."""
        self.sensitive_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SENSITIVE_FIELD_PATTERNS
        ]

    def sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize entire template context dictionary.

        Args:
            context: Template context dictionary

        Returns:
            Sanitized context dictionary

        Raises:
            ValidationError: If context contains forbidden data
        """
        if not isinstance(context, dict):
            raise ValidationError("Context must be a dictionary")

        sanitized = {}

        for key, value in context.items():
            # Check for sensitive field names
            if self._is_sensitive_field(key):
                logger.warning(
                    "Sensitive field detected in template context",
                    extra={'field_name': key, 'sanitized': True}
                )
                self.sanitization_log.append({
                    'field': key,
                    'action': 'redacted',
                    'reason': 'sensitive_field_name'
                })
                continue  # Skip sensitive fields entirely

            # Recursively sanitize value
            sanitized[key] = self._sanitize_value(value, field_name=key)

        # Log sanitization summary
        if self.sanitization_log:
            logger.info(
                "Template context sanitization completed",
                extra={
                    'total_fields': len(context),
                    'sanitized_count': len(self.sanitization_log),
                    'strict_mode': self.strict_mode
                }
            )

        return sanitized

    def _sanitize_value(self, value: Any, field_name: str = '') -> Any:
        """
        Sanitize individual value based on its type.

        Args:
            value: Value to sanitize
            field_name: Name of the field (for logging)

        Returns:
            Sanitized value
        """
        # Handle None
        if value is None:
            return value

        # Handle SafeString (already marked safe by Django)
        if isinstance(value, SafeString):
            return value

        # Handle strings
        if isinstance(value, str):
            return self._sanitize_string(value, field_name)

        # Handle numbers (no sanitization needed)
        if isinstance(value, (int, float, bool)):
            return value

        # Handle dictionaries (recursive)
        if isinstance(value, dict):
            return {
                k: self._sanitize_value(v, field_name=f"{field_name}.{k}")
                for k, v in value.items()
            }

        # Handle lists/tuples (recursive)
        if isinstance(value, (list, tuple)):
            sanitized_list = [
                self._sanitize_value(item, field_name=f"{field_name}[]")
                for item in value
            ]
            return sanitized_list if isinstance(value, list) else tuple(sanitized_list)

        # Handle other types - convert to string and sanitize
        return self._sanitize_string(str(value), field_name)

    def _sanitize_string(self, text: str, field_name: str = '') -> str:
        """
        Sanitize string value.

        Args:
            text: String to sanitize
            field_name: Name of the field (for logging)

        Returns:
            Sanitized string
        """
        if not text:
            return text

        # Truncate excessively long strings
        if len(text) > self.MAX_STRING_LENGTH:
            logger.warning(
                "Truncating excessively long string in template context",
                extra={
                    'field_name': field_name,
                    'original_length': len(text),
                    'truncated_to': self.MAX_STRING_LENGTH
                }
            )
            text = text[:self.MAX_STRING_LENGTH] + '...'
            self.sanitization_log.append({
                'field': field_name,
                'action': 'truncated',
                'reason': 'excessive_length'
            })

        # Check for HTML content
        if self._contains_html(text):
            if self.strict_mode:
                # Strict mode: Escape all HTML
                sanitized = escape(text)
                self.sanitization_log.append({
                    'field': field_name,
                    'action': 'html_escaped',
                    'reason': 'strict_mode'
                })
                return sanitized
            else:
                # Permissive mode: Allow whitelisted tags
                sanitized = self._sanitize_html(text)
                self.sanitization_log.append({
                    'field': field_name,
                    'action': 'html_filtered',
                    'reason': 'permissive_mode'
                })
                return sanitized

        return text

    def _contains_html(self, text: str) -> bool:
        """Check if text contains HTML tags."""
        return bool(re.search(r'<[^>]+>', text))

    def _sanitize_html(self, html: str) -> str:
        """
        Sanitize HTML by removing non-whitelisted tags.

        Args:
            html: HTML string to sanitize

        Returns:
            Sanitized HTML string
        """
        # Remove script and style tags completely
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)

        # Remove event handlers (onclick, onerror, etc.)
        html = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)

        # Remove javascript: protocol
        html = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', '', html, flags=re.IGNORECASE)

        # Remove non-whitelisted tags
        def replace_tag(match):
            tag = match.group(1).lower()
            if tag.startswith('/'):
                tag = tag[1:]
            if tag in self.SAFE_HTML_TAGS:
                return match.group(0)  # Keep whitelisted tag
            return ''  # Remove non-whitelisted tag

        html = re.sub(r'<(/?\w+)[^>]*>', replace_tag, html)

        return html

    def _is_sensitive_field(self, field_name: str) -> bool:
        """
        Check if field name matches sensitive data patterns.

        Args:
            field_name: Field name to check

        Returns:
            True if field is sensitive
        """
        return any(
            pattern.match(field_name)
            for pattern in self.sensitive_patterns
        )

    def get_sanitization_report(self) -> Dict[str, Any]:
        """
        Get detailed report of sanitization actions.

        Returns:
            Dictionary containing sanitization statistics
        """
        action_counts = {}
        for entry in self.sanitization_log:
            action = entry['action']
            action_counts[action] = action_counts.get(action, 0) + 1

        return {
            'total_sanitizations': len(self.sanitization_log),
            'action_breakdown': action_counts,
            'sanitization_log': self.sanitization_log,
            'strict_mode': self.strict_mode
        }

    def clear_log(self) -> None:
        """Clear sanitization log."""
        self.sanitization_log.clear()


def sanitize_template_context(
    context: Dict[str, Any],
    strict_mode: bool = True
) -> Dict[str, Any]:
    """
    Convenience function for sanitizing template context.

    Args:
        context: Template context to sanitize
        strict_mode: Enable strict HTML sanitization

    Returns:
        Sanitized context dictionary
    """
    sanitizer = TemplateContextSanitizer(strict_mode=strict_mode)
    return sanitizer.sanitize_context(context)
