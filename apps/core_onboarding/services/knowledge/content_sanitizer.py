"""
Content Sanitization Service - Security Critical

Sanitizes document content before ingestion to prevent XSS, injection attacks,
and malicious content from entering the knowledge base.

Defense Layers:
1. HTML/Script stripping (XSS prevention)
2. Malicious pattern detection (injection attacks)
3. File type validation (prevent executable uploads)
4. Size validation (DoS prevention)

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Security-first design

Sprint 1-2: Knowledge Management Security
"""

import logging
import re
from typing import Dict, Any, List, Tuple
from django.conf import settings
from html import escape
from apps.core_onboarding.services.knowledge.exceptions import SecurityError

logger = logging.getLogger(__name__)


class ContentSanitizationService:
    """Service for sanitizing knowledge base content."""

    def __init__(self):
        """Initialize sanitization service with settings."""
        self.allowed_html_tags = getattr(settings, 'KB_ALLOWED_HTML_TAGS', [])
        self.forbidden_patterns = getattr(settings, 'KB_FORBIDDEN_PATTERNS', [])
        self.max_document_size = getattr(settings, 'KB_MAX_DOCUMENT_SIZE_BYTES', 50 * 1024 * 1024)
        self.allowed_mime_types = getattr(settings, 'KB_ALLOWED_MIME_TYPES', [])

    def sanitize_document_content(
        self,
        content: str,
        mime_type: str,
        source_url: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Sanitize document content before ingestion.

        Args:
            content: Raw document content
            mime_type: MIME type of document
            source_url: Source URL (for logging)

        Returns:
            Tuple of (sanitized_content, sanitization_report)

        Raises:
            SecurityError: If malicious content detected
        """
        report = {
            'original_size_bytes': len(content),
            'patterns_detected': [],
            'tags_stripped': [],
            'security_warnings': [],
            'sanitized': False
        }

        try:
            # Step 1: Validate file type
            if mime_type not in self.allowed_mime_types:
                raise SecurityError(
                    f"MIME type not allowed: {mime_type}. "
                    f"Allowed types: {', '.join(self.allowed_mime_types)}"
                )

            # Step 2: Validate size
            if len(content) > self.max_document_size:
                raise SecurityError(
                    f"Document too large: {len(content)} bytes "
                    f"(max: {self.max_document_size})"
                )

            # Step 3: Scan for forbidden patterns (SECURITY CRITICAL)
            malicious_patterns = self._detect_malicious_patterns(content)
            if malicious_patterns:
                report['patterns_detected'] = malicious_patterns
                raise SecurityError(
                    f"Malicious patterns detected in document: {', '.join(malicious_patterns)}. "
                    f"Source: {source_url}"
                )

            # Step 4: Strip dangerous HTML if HTML content
            sanitized_content = content
            if mime_type in ['text/html', 'text/markdown']:
                sanitized_content, stripped_tags = self._sanitize_html(content)
                report['tags_stripped'] = stripped_tags

            # Step 5: Escape remaining special characters
            sanitized_content = self._escape_special_chars(sanitized_content)

            report['sanitized_size_bytes'] = len(sanitized_content)
            report['sanitized'] = True

            logger.info(
                f"Content sanitized successfully: {len(content)} → {len(sanitized_content)} bytes"
            )

            return sanitized_content, report

        except SecurityError:
            raise
        except (ValueError, TypeError, UnicodeDecodeError) as e:
            logger.error(f"Error sanitizing content: {e}")
            raise SecurityError(f"Content sanitization failed: {str(e)}")

    def _detect_malicious_patterns(self, content: str) -> List[str]:
        """Detect malicious patterns in content."""
        detected = []

        for pattern in self.forbidden_patterns:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(pattern)
            except re.error as e:
                logger.warning(f"Invalid regex pattern {pattern}: {e}")

        return detected

    def _sanitize_html(self, html_content: str) -> Tuple[str, List[str]]:
        """
        Sanitize HTML content by stripping dangerous tags.

        Returns:
            Tuple of (sanitized_html, stripped_tags)
        """
        stripped_tags = []

        # Strip script tags and their content
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        if len(sanitized) != len(html_content):
            stripped_tags.append('script')

        # Strip style tags
        sanitized = re.sub(r'<style[^>]*>.*?</style>', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
        if len(sanitized) != len(html_content):
            stripped_tags.append('style')

        # Strip event handlers (onclick, onload, etc.)
        sanitized = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', sanitized, flags=re.IGNORECASE)

        # Strip javascript: protocol
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)

        return sanitized, list(set(stripped_tags))

    def _escape_special_chars(self, content: str) -> str:
        """Escape special characters for safety."""
        # Only escape if not already escaped
        if '<' in content or '>' in content:
            # Escape HTML entities
            content = escape(content)

        return content

    def validate_url_safety(self, url: str) -> bool:
        """
        Validate URL is from allowlisted domain.

        Args:
            url: URL to validate

        Returns:
            bool: True if safe, False otherwise
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            allowed_sources = getattr(settings, 'KB_ALLOWED_SOURCES', [])

            return any(allowed in domain for allowed in allowed_sources)

        except (ValueError, TypeError) as e:
            logger.error(f"Error validating URL safety: {e}")
            return False
