"""
Advanced template cache tags with tenant awareness and intelligent invalidation
Provides template fragment caching for expensive UI components
"""

import hashlib
import logging
from typing import Any, Dict, Optional
from django import template
from django.core.cache import cache
from django.template.context import Context
from django.utils.safestring import mark_safe
from django.template import TemplateSyntaxError

from apps.core.caching.utils import (
    get_tenant_cache_key,
    get_user_cache_key,
    CACHE_TIMEOUTS
)

register = template.Library()
logger = logging.getLogger(__name__)


@register.tag('cache_fragment')
def cache_fragment(parser, token):
    """
    Advanced template fragment caching with tenant and user awareness

    Usage:
        {% cache_fragment 'fragment_name' timeout=900 vary_on='user,tenant' %}
            <expensive template content>
        {% endcache_fragment %}

        {% cache_fragment 'dashboard_stats' timeout=600 vary_on='tenant' %}
            {% include 'dashboard/stats_widget.html' %}
        {% endcache_fragment %}

    Arguments:
        - fragment_name: Unique name for the cached fragment
        - timeout: Cache timeout in seconds (optional, defaults to pattern-based timeout)
        - vary_on: What to vary cache on ('user', 'tenant', 'user,tenant', 'none')
        - version: Cache version for invalidation (optional)
    """
    try:
        # Parse arguments
        tokens = token.split_contents()
        if len(tokens) < 2:
            raise TemplateSyntaxError("cache_fragment tag requires at least a fragment name")

        tag_name = tokens[0]
        fragment_name = tokens[1].strip('"\'')

        # Parse optional arguments
        kwargs = {}
        for token_part in tokens[2:]:
            if '=' in token_part:
                key, value = token_part.split('=', 1)
                kwargs[key] = value.strip('"\'')

        # Parse until endcache_fragment
        nodelist = parser.parse(('endcache_fragment',))
        parser.delete_first_token()

        return CacheFragmentNode(fragment_name, nodelist, kwargs)

    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing cache_fragment tag: {e}")
        raise TemplateSyntaxError(f"Error in cache_fragment tag: {e}")


class CacheFragmentNode(template.Node):
    """
    Template node for fragment caching with advanced features
    """

    def __init__(self, fragment_name: str, nodelist: template.NodeList, options: Dict[str, str]):
        self.fragment_name = fragment_name
        self.nodelist = nodelist
        self.options = options

    def render(self, context: Context) -> str:
        try:
            # Get cache configuration
            timeout = int(self.options.get('timeout', CACHE_TIMEOUTS['DEFAULT']))
            vary_on = self.options.get('vary_on', 'tenant').lower()
            version = self.options.get('version', '1')

            # Generate cache key based on vary_on setting
            cache_key = self._generate_cache_key(context, vary_on, version)

            # Try to get from cache
            cached_content = cache.get(cache_key)
            if cached_content is not None:
                logger.debug(f"Template fragment cache HIT: {self.fragment_name}")
                return cached_content

            # Cache miss - render content
            logger.debug(f"Template fragment cache MISS: {self.fragment_name}")
            content = self.nodelist.render(context)

            # Cache the rendered content
            try:
                cache.set(cache_key, content, timeout)
                logger.debug(f"Cached template fragment: {self.fragment_name} for {timeout}s")
            except (ConnectionError, ValueError) as e:
                logger.error(f"Error caching fragment {self.fragment_name}: {e}")

            return content

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error rendering cached fragment {self.fragment_name}: {e}")
            # Fallback to rendering without cache
            return self.nodelist.render(context)

    def _generate_cache_key(self, context: Context, vary_on: str, version: str) -> str:
        """
        Generate cache key based on vary_on configuration

        Args:
            context: Template context
            vary_on: What to vary cache on
            version: Cache version

        Returns:
            Generated cache key
        """
        base_key = f"template:fragment:{self.fragment_name}:v{version}"

        # Get request from context
        request = context.get('request')

        if vary_on == 'none':
            return base_key

        elif vary_on == 'user' and request and hasattr(request, 'user'):
            if request.user.is_authenticated:
                return get_user_cache_key(base_key, request.user.id, include_tenant=False)
            else:
                return f"anonymous:{base_key}"

        elif vary_on == 'tenant' and request:
            return get_tenant_cache_key(base_key, request)

        elif vary_on in ('user,tenant', 'tenant,user') and request:
            if hasattr(request, 'user') and request.user.is_authenticated:
                return get_user_cache_key(base_key, request.user.id, request)
            else:
                return get_tenant_cache_key(f"anonymous:{base_key}", request)

        else:
            # Default to tenant-aware caching
            if request:
                return get_tenant_cache_key(base_key, request)
            else:
                return base_key


@register.inclusion_tag('core/cached_widget.html', takes_context=True)
def cached_widget(context, widget_name: str, **kwargs):
    """
    Render a cached widget with automatic cache key generation

    Usage:
        {% cached_widget 'dashboard_metrics' timeout=600 %}
        {% cached_widget 'user_profile' vary_on='user' %}

    Args:
        widget_name: Name of the widget template
        **kwargs: Additional arguments (timeout, vary_on, etc.)
    """
    try:
        timeout = int(kwargs.get('timeout', CACHE_TIMEOUTS['DEFAULT']))
        vary_on = kwargs.get('vary_on', 'tenant')

        # Generate cache key
        cache_key_base = f"widget:{widget_name}"
        request = context.get('request')

        if vary_on == 'user' and request and hasattr(request, 'user') and request.user.is_authenticated:
            cache_key = get_user_cache_key(cache_key_base, request.user.id, request)
        elif request:
            cache_key = get_tenant_cache_key(cache_key_base, request)
        else:
            cache_key = cache_key_base

        # Try cache first
        cached_widget = cache.get(cache_key)
        if cached_widget is not None:
            logger.debug(f"Widget cache HIT: {widget_name}")
            return {'content': mark_safe(cached_widget), 'cached': True}

        # Cache miss - render widget
        logger.debug(f"Widget cache MISS: {widget_name}")

        # Create widget context
        widget_context = context.flatten()
        widget_context.update(kwargs)

        # Render widget template
        template_name = f'widgets/{widget_name}.html'
        try:
            widget_template = template.loader.get_template(template_name)
            rendered_content = widget_template.render(widget_context)

            # Cache the result
            cache.set(cache_key, rendered_content, timeout)
            logger.debug(f"Cached widget: {widget_name} for {timeout}s")

            return {'content': mark_safe(rendered_content), 'cached': False}

        except template.TemplateDoesNotExist:
            logger.error(f"Widget template not found: {template_name}")
            return {'content': '', 'cached': False, 'error': f'Template {template_name} not found'}

    except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
        logger.error(f"Error rendering cached widget {widget_name}: {e}")
        return {'content': '', 'cached': False, 'error': str(e)}


@register.simple_tag(takes_context=True)
def cache_key_for(context, key_type: str, identifier: str = '', **kwargs) -> str:
    """
    Generate cache keys in templates for manual cache operations

    Usage:
        {% cache_key_for 'dashboard' 'metrics' as cache_key %}
        {% cache_key_for 'user' user.id vary_on='tenant' as user_cache_key %}

    Args:
        key_type: Type of cache key (dashboard, user, form, etc.)
        identifier: Additional identifier
        **kwargs: Additional options (vary_on, version, etc.)

    Returns:
        Generated cache key
    """
    try:
        base_key = f"{key_type}:{identifier}" if identifier else key_type
        vary_on = kwargs.get('vary_on', 'tenant')
        version = kwargs.get('version', '1')

        if version != '1':
            base_key = f"{base_key}:v{version}"

        request = context.get('request')

        if vary_on == 'user' and request and hasattr(request, 'user') and request.user.is_authenticated:
            return get_user_cache_key(base_key, request.user.id, include_tenant=False)
        elif vary_on == 'tenant' and request:
            return get_tenant_cache_key(base_key, request)
        elif vary_on == 'user,tenant' and request:
            if hasattr(request, 'user') and request.user.is_authenticated:
                return get_user_cache_key(base_key, request.user.id, request)
            else:
                return get_tenant_cache_key(base_key, request)
        else:
            return base_key

    except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
        logger.error(f"Error generating cache key: {e}")
        return f"error:{key_type}:{identifier}"


@register.filter
def cache_bust(value: str, version: str = None) -> str:
    """
    Add cache busting parameter to URLs

    Usage:
        {{ asset_url|cache_bust }}
        {{ css_file|cache_bust:'v2' }}

    Args:
        value: URL or file path
        version: Cache version

    Returns:
        URL with cache busting parameter
    """
    try:
        import time
        if version:
            cache_param = version
        else:
            cache_param = str(int(time.time()))

        separator = '&' if '?' in value else '?'
        return f"{value}{separator}_cb={cache_param}"

    except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
        logger.error(f"Error adding cache bust to {value}: {e}")
        return value


@register.simple_tag
def cache_stats():
    """
    Get cache statistics for debugging

    Usage:
        {% cache_stats as stats %}
        Cache hit ratio: {{ stats.hit_ratio }}%
    """
    try:
        from apps.core.caching.utils import get_cache_stats
        return get_cache_stats()
    except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'error': str(e)}


@register.tag('cache_conditional')
def cache_conditional(parser, token):
    """
    Conditional caching based on template variables

    Usage:
        {% cache_conditional condition='user.is_staff' timeout=900 %}
            <admin-only expensive content>
        {% endcache_conditional %}
    """
    try:
        tokens = token.split_contents()
        kwargs = {}

        for token_part in tokens[1:]:
            if '=' in token_part:
                key, value = token_part.split('=', 1)
                kwargs[key] = value.strip('"\'')

        nodelist = parser.parse(('endcache_conditional',))
        parser.delete_first_token()

        return ConditionalCacheNode(nodelist, kwargs)

    except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
        logger.error(f"Error parsing cache_conditional tag: {e}")
        raise TemplateSyntaxError(f"Error in cache_conditional tag: {e}")


class ConditionalCacheNode(template.Node):
    """
    Template node for conditional caching
    """

    def __init__(self, nodelist: template.NodeList, options: Dict[str, str]):
        self.nodelist = nodelist
        self.options = options

    def render(self, context: Context) -> str:
        try:
            # Evaluate condition
            condition = self.options.get('condition', 'True')
            should_cache = template.Variable(condition).resolve(context)

            if not should_cache:
                # Don't cache - render directly
                return self.nodelist.render(context)

            # Cache enabled - use fragment caching
            timeout = int(self.options.get('timeout', CACHE_TIMEOUTS['DEFAULT']))
            fragment_name = f"conditional:{hashlib.md5(condition.encode()).hexdigest()[:8]}"

            # Generate cache key
            request = context.get('request')
            if request:
                cache_key = get_tenant_cache_key(f"template:conditional:{fragment_name}", request)
            else:
                cache_key = f"template:conditional:{fragment_name}"

            # Try cache
            cached_content = cache.get(cache_key)
            if cached_content is not None:
                return cached_content

            # Render and cache
            content = self.nodelist.render(context)
            cache.set(cache_key, content, timeout)

            return content

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error in conditional cache: {e}")
            return self.nodelist.render(context)