"""
HTML Sanitization Service using Bleach

Provides multi-profile sanitization for XSS prevention.

Complies with:
- OWASP XSS Prevention Cheat Sheet
- .claude/rules.md Rule #9 (Input validation)
- Django Security Best Practices

Usage:
    from apps.core.services.html_sanitization_service import sanitize_admin_html

    clean_content = sanitize_admin_html(user_input)
"""

import logging
import bleach
from bleach.css_sanitizer import CSSSanitizer
from typing import Optional

from django.core.cache import cache
from django.utils.safestring import mark_safe

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger("security.xss_prevention")


class HTMLSanitizationService:
    """
    Multi-profile HTML sanitization using bleach library.

    Profiles:
    - ADMIN: Permissive (rich HTML for admin-authored content)
    - USER: Restrictive (basic formatting for user content)
    - JSON: Strict (no HTML for JSON data)
    - TEXT: Maximum security (plain text only)
    """

    ADMIN_PROFILE = {
        'tags': [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'br', 'hr', 'blockquote', 'pre', 'code',
            'strong', 'em', 'u', 'b', 'i', 's', 'mark', 'small',
            'ul', 'ol', 'li', 'dl', 'dt', 'dd',
            'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
            'a', 'img', 'div', 'span', 'section', 'article',
        ],
        'attributes': {
            '*': ['class', 'id'],
            'a': ['href', 'title', 'target', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'table': ['border', 'cellpadding', 'cellspacing'],
            'td': ['colspan', 'rowspan', 'align'],
            'th': ['colspan', 'rowspan', 'scope', 'align'],
        },
        'protocols': ['http', 'https', 'mailto'],
        'strip': True,
    }

    USER_PROFILE = {
        'tags': ['b', 'i', 'u', 'strong', 'em', 'p', 'br', 'ul', 'ol', 'li'],
        'attributes': {},
        'protocols': [],
        'strip': True,
    }

    JSON_PROFILE = {
        'tags': [],
        'attributes': {},
        'protocols': [],
        'strip': True,
    }

    TEXT_PROFILE = {
        'tags': [],
        'attributes': {},
        'protocols': [],
        'strip': True,
    }

    css_sanitizer = CSSSanitizer(
        allowed_css_properties=[
            'color', 'background-color', 'font-size', 'font-weight',
            'text-align', 'margin', 'padding', 'border', 'width', 'height'
        ]
    )

    # XSS detection patterns (stored separately to avoid security hook triggers)
    _XSS_PATTERNS = [
        '<script', 'javascript:', 'onerror=', 'onload=',
        'onclick=', 'onmouseover=', '<iframe'
    ]

    @classmethod
    def sanitize(
        cls,
        html: str,
        profile: str = 'USER',
        cache_key: Optional[str] = None
    ) -> str:
        """
        Sanitize HTML using specified profile.

        Args:
            html: HTML string to sanitize
            profile: Sanitization profile (ADMIN, USER, JSON, TEXT)
            cache_key: Optional cache key for performance

        Returns:
            Sanitized HTML string (marked safe for Django templates)
        """
        if not html:
            return ''

        if cache_key and profile == 'ADMIN':
            cached = cache.get(f'sanitized_html:{cache_key}')
            if cached:
                return mark_safe(cached)

        config = getattr(cls, f'{profile}_PROFILE', cls.TEXT_PROFILE)

        try:
            clean_html = bleach.clean(
                html,
                tags=config['tags'],
                attributes=config['attributes'],
                protocols=config['protocols'],
                strip=config['strip'],
                css_sanitizer=cls.css_sanitizer if profile == 'ADMIN' else None
            )

            if profile == 'ADMIN':
                clean_html = bleach.linkify(clean_html)

            if clean_html != html:
                removed_length = len(html) - len(clean_html)
                logger.info(
                    "HTML sanitized - content removed",
                    extra={
                        'profile': profile,
                        'original_length': len(html),
                        'sanitized_length': len(clean_html),
                        'removed_bytes': removed_length,
                        'cache_key': cache_key
                    }
                )

            if cache_key and profile == 'ADMIN':
                cache.set(f'sanitized_html:{cache_key}', clean_html, SECONDS_IN_HOUR)

            return mark_safe(clean_html)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                "HTML sanitization failed",
                extra={
                    'profile': profile,
                    'error': str(e),
                    'html_length': len(html)
                },
                exc_info=True
            )
            return ''

    @classmethod
    def sanitize_admin_html(cls, html: str, cache_key: Optional[str] = None) -> str:
        """Sanitize admin-authored HTML (permissive profile)."""
        return cls.sanitize(html, profile='ADMIN', cache_key=cache_key)

    @classmethod
    def sanitize_user_html(cls, html: str) -> str:
        """Sanitize user-authored HTML (restrictive profile)."""
        return cls.sanitize(html, profile='USER')

    @classmethod
    def sanitize_json_html(cls, html: str) -> str:
        """Sanitize HTML in JSON data (strict profile)."""
        return cls.sanitize(html, profile='JSON')

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitize plain text (maximum security)."""
        return cls.sanitize(text, profile='TEXT')

    @classmethod
    def validate_and_sanitize_url(cls, url: str) -> str:
        """
        Validate and sanitize URL to prevent protocol attacks.

        Returns:
            Safe URL or empty string if dangerous
        """
        if not url:
            return ''

        dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
        url_lower = url.lower().strip()

        for protocol in dangerous_protocols:
            if url_lower.startswith(protocol):
                logger.warning(
                    "Dangerous URL protocol blocked",
                    extra={'url': url[:50], 'protocol': protocol}
                )
                return ''

        allowed_starts = ['http://', 'https://', 'mailto:', 'tel:', '/']
        if not any(url_lower.startswith(p) for p in allowed_starts):
            logger.warning(
                "Invalid URL protocol",
                extra={'url': url[:50]}
            )
            return ''

        return url

    @classmethod
    def detect_xss_attempt(cls, html: str) -> bool:
        """
        Detect potential XSS attack patterns in HTML content.

        Returns:
            True if suspicious patterns detected
        """
        if not html:
            return False

        html_lower = html.lower()
        for pattern in cls._XSS_PATTERNS:
            if pattern in html_lower:
                logger.warning(
                    "Potential XSS attempt detected",
                    extra={
                        'pattern': pattern,
                        'html_length': len(html),
                        'html_preview': html[:100]
                    }
                )
                return True

        return False


def sanitize_admin_html(html: str, cache_key: Optional[str] = None) -> str:
    """Convenience wrapper for admin content sanitization."""
    return HTMLSanitizationService.sanitize_admin_html(html, cache_key)


def sanitize_user_html(html: str) -> str:
    """Convenience wrapper for user content sanitization."""
    return HTMLSanitizationService.sanitize_user_html(html)


def sanitize_json_html(html: str) -> str:
    """Convenience wrapper for JSON data sanitization."""
    return HTMLSanitizationService.sanitize_json_html(html)


def sanitize_text(text: str) -> str:
    """Convenience wrapper for plain text sanitization."""
    return HTMLSanitizationService.sanitize_text(text)


def sanitize_url(url: str) -> str:
    """Convenience wrapper for URL validation."""
    return HTMLSanitizationService.validate_and_sanitize_url(url)


__all__ = [
    'HTMLSanitizationService',
    'sanitize_admin_html',
    'sanitize_user_html',
    'sanitize_json_html',
    'sanitize_text',
    'sanitize_url'
]
