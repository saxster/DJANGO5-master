"""
Template tags for CSP nonce injection
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def csp_nonce(context):
    """
    Get the CSP nonce for the current request.
    
    Usage in templates:
        <script nonce="{% csp_nonce %}">
            // Your inline JavaScript
        </script>
        
        <style nonce="{% csp_nonce %}">
            /* Your inline CSS */
        </style>
    """
    request = context.get('request')
    if request and hasattr(request, 'csp_nonce'):
        return request.csp_nonce
    return ''


@register.simple_tag(takes_context=True)
def script_tag(context, *args, **kwargs):
    """
    Generate a script tag with CSP nonce automatically included.
    
    Usage in templates:
        {% script_tag %}
            // Your inline JavaScript
        {% endscript_tag %}
    """
    request = context.get('request')
    nonce = ''
    if request and hasattr(request, 'csp_nonce'):
        nonce = f' nonce="{request.csp_nonce}"'
    
    # Get additional attributes
    attrs = []
    if 'type' in kwargs:
        attrs.append(f'type="{kwargs["type"]}"')
    if 'id' in kwargs:
        attrs.append(f'id="{kwargs["id"]}"')
    if 'class' in kwargs:
        attrs.append(f'class="{kwargs["class"]}"')
    
    attrs_str = ' '.join(attrs)
    if attrs_str:
        attrs_str = ' ' + attrs_str
        
    return mark_safe(f'<script{nonce}{attrs_str}>')


@register.simple_tag
def endscript_tag():
    """Close script tag."""
    return mark_safe('</script>')


@register.simple_tag(takes_context=True)
def style_tag(context, *args, **kwargs):
    """
    Generate a style tag with CSP nonce automatically included.
    
    Usage in templates:
        {% style_tag %}
            /* Your inline CSS */
        {% endstyle_tag %}
    """
    request = context.get('request')
    nonce = ''
    if request and hasattr(request, 'csp_nonce'):
        nonce = f' nonce="{request.csp_nonce}"'
    
    # Get additional attributes
    attrs = []
    if 'type' in kwargs:
        attrs.append(f'type="{kwargs["type"]}"')
    else:
        attrs.append('type="text/css"')
    if 'id' in kwargs:
        attrs.append(f'id="{kwargs["id"]}"')
    if 'class' in kwargs:
        attrs.append(f'class="{kwargs["class"]}"')
    
    attrs_str = ' '.join(attrs)
    if attrs_str:
        attrs_str = ' ' + attrs_str
        
    return mark_safe(f'<style{nonce}{attrs_str}>')


@register.simple_tag
def endstyle_tag():
    """Close style tag."""
    return mark_safe('</style>')


@register.inclusion_tag('core/csp_meta.html', takes_context=True)
def csp_meta_tags(context):
    """
    Include CSP-related meta tags in the document head.
    
    Usage in templates:
        <head>
            {% load csp_tags %}
            {% csp_meta_tags %}
            ...
        </head>
    """
    request = context.get('request')
    return {
        'request': request,
        'csp_nonce': getattr(request, 'csp_nonce', ''),
    }