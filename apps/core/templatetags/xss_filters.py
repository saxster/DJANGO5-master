"""
XSS Prevention Template Filters

Provides safe HTML rendering with profile-based sanitization.

Usage:
    {% load xss_filters %}

    {{ article.content|sanitize_html }}         # Admin profile
    {{ user.comment|sanitize_user_text }}       # User profile
    {{ json_data|sanitize_json }}               # JSON profile
    {{ url|sanitize_url }}                      # URL validation

Following .claude/rules.md Rule #9: Comprehensive input validation
"""

from django import template
from django.utils.safestring import mark_safe

from apps.core.services.html_sanitization_service import (
    HTMLSanitizationService,
    sanitize_admin_html,
    sanitize_user_html,
    sanitize_json_html,
    sanitize_text,
    sanitize_url
)

register = template.Library()


@register.filter(name='sanitize_html', is_safe=True)
def sanitize_html_filter(value):
    """
    Sanitize HTML using ADMIN profile (permissive).

    Allows semantic HTML tags for admin-authored content.
    Blocks scripts, event handlers, dangerous protocols.

    Usage: {{ article.content|sanitize_html }}
    """
    if value is None:
        return ''
    return sanitize_admin_html(str(value))


@register.filter(name='sanitize_user_text', is_safe=True)
def sanitize_user_text_filter(value):
    """
    Sanitize HTML using USER profile (restrictive).

    Allows only basic formatting tags (b, i, u, p, lists).
    Strips all attributes, links, and images.

    Usage: {{ comment.text|sanitize_user_text }}
    """
    if value is None:
        return ''
    return sanitize_user_html(str(value))


@register.filter(name='sanitize_json', is_safe=True)
def sanitize_json_filter(value):
    """
    Sanitize HTML in JSON data (strict).

    Strips ALL HTML tags, preserving only text content.
    Use for JSON data embedded in templates.

    Usage: {{ metrics_data|sanitize_json }}
    """
    if value is None:
        return ''
    return sanitize_json_html(str(value))


@register.filter(name='sanitize_text', is_safe=True)
def sanitize_text_filter(value):
    """
    Sanitize plain text (maximum security).

    Strips all HTML tags and attributes.
    Use for user-provided names, titles, descriptions.

    Usage: {{ user.name|sanitize_text }}
    """
    if value is None:
        return ''
    return sanitize_text(str(value))


@register.filter(name='sanitize_url', is_safe=False)
def sanitize_url_filter(value):
    """
    Validate and sanitize URL.

    Blocks dangerous protocols (javascript, data, vbscript).
    Allows only http, https, mailto, tel, relative paths.

    Usage: <a href="{{ external_url|sanitize_url }}">Link</a>
    """
    if value is None:
        return ''
    return sanitize_url(str(value))


@register.filter(name='detect_xss')
def detect_xss_filter(value):
    """
    Detect XSS attempts in content (for admin dashboards).

    Returns True if suspicious patterns detected.
    Use for security monitoring and alerts.

    Usage: {% if content|detect_xss %}⚠️ XSS Detected{% endif %}
    """
    if value is None:
        return False
    return HTMLSanitizationService.detect_xss_attempt(str(value))
