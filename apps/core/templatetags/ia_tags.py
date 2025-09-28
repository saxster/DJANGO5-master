"""
Template tags for Information Architecture optimization
Provides navigation helpers, breadcrumbs, and URL utilities
"""
from django import template
from django.utils.html import format_html
from django.conf import settings
import json

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware

register = template.Library()


@register.simple_tag(takes_context=True)
def get_navigation_menu(context, menu_type='main'):
    """
    Generate navigation menu structure based on user permissions
    
    Usage: {% get_navigation_menu 'main' as menu %}
    """
    request = context.get('request')
    user = request.user if request else None
    
    return OptimizedURLRouter.get_navigation_menu(user, menu_type)


@register.simple_tag(takes_context=True)
def get_breadcrumbs(context):
    """
    Generate breadcrumb navigation for current page
    
    Usage: {% get_breadcrumbs as breadcrumbs %}
    """
    request = context.get('request')
    if not request:
        return []
    
    return OptimizedURLRouter.get_breadcrumbs(request.path)


@register.inclusion_tag('core/partials/navigation_menu.html', takes_context=True)
def render_navigation_menu(context, menu_type='main', css_class='nav'):
    """
    Render complete navigation menu with HTML
    
    Usage: {% render_navigation_menu 'main' 'nav-pills' %}
    """
    menu_items = get_navigation_menu(context, menu_type)
    request = context.get('request')
    current_path = request.path if request else ''
    
    return {
        'menu_items': menu_items,
        'current_path': current_path,
        'css_class': css_class,
        'request': request
    }


@register.inclusion_tag('core/partials/breadcrumb_nav.html', takes_context=True)
def render_breadcrumbs(context, css_class='breadcrumb'):
    """
    Render breadcrumb navigation with HTML
    
    Usage: {% render_breadcrumbs 'breadcrumb-dark' %}
    """
    breadcrumbs = get_breadcrumbs(context)
    
    return {
        'breadcrumbs': breadcrumbs,
        'css_class': css_class
    }


@register.simple_tag
def get_new_url(old_url):
    """
    Get the new optimized URL for a legacy URL
    
    Usage: {{ "activity/asset/"|get_new_url }}
    """
    return OptimizedURLRouter.get_new_url(old_url.strip('/') + '/')


@register.simple_tag
def is_deprecated_url(url):
    """
    Check if a URL is deprecated
    
    Usage: {% if current_url|is_deprecated_url %}...{% endif %}
    """
    clean_url = url.strip('/')
    return OptimizedURLRouter.should_show_deprecation_warning(clean_url)


@register.simple_tag(takes_context=True)
def navigation_active_class(context, url_pattern, css_class='active'):
    """
    Return CSS class if current URL matches pattern
    
    Usage: <li class="nav-item {% navigation_active_class 'operations:*' %}">
    """
    request = context.get('request')
    if not request:
        return ''
    
    current_path = request.path.strip('/')
    
    # Handle wildcard patterns
    if '*' in url_pattern:
        pattern = url_pattern.replace('*', '')
        if current_path.startswith(pattern):
            return css_class
    else:
        if current_path == url_pattern.strip('/'):
            return css_class
    
    return ''


@register.simple_tag
def migration_progress():
    """
    Get current migration progress percentage
    
    Usage: {% migration_progress as progress %}
    """
    report = OptimizedURLRouter.get_migration_report()
    return report['summary']['adoption_rate']


@register.simple_tag
def legacy_url_count():
    """
    Get count of legacy URLs still in use
    
    Usage: {% legacy_url_count as count %}
    """
    report = OptimizedURLRouter.get_migration_report()
    return report['summary']['used_legacy_urls']


@register.filter
def url_domain(url):
    """
    Extract domain from URL for grouping
    
    Usage: {{ url|url_domain }}
    """
    parts = url.strip('/').split('/')
    return parts[0] if parts else ''


@register.filter
def format_response_time(seconds):
    """
    Format response time for display
    
    Usage: {{ time|format_response_time }}
    """
    if not seconds:
        return 'N/A'
    
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    else:
        return f"{seconds:.2f}s"


@register.simple_tag
def get_ia_settings():
    """
    Get IA-related settings for templates
    
    Usage: {% get_ia_settings as ia_settings %}
    """
    return {
        'use_optimized_urls': getattr(settings, 'USE_OPTIMIZED_URLS', False),
        'enable_legacy_urls': getattr(settings, 'ENABLE_LEGACY_URLS', True),
        'show_deprecation_warnings': getattr(settings, 'SHOW_DEPRECATION_WARNINGS', True),
        'enable_navigation_tracking': getattr(settings, 'ENABLE_NAVIGATION_TRACKING', True),
    }


@register.inclusion_tag('core/partials/deprecation_warning.html', takes_context=True)
def show_deprecation_warning(context, url=None):
    """
    Show deprecation warning for legacy URLs
    
    Usage: {% show_deprecation_warning current_url %}
    """
    request = context.get('request')
    current_url = url or (request.path if request else '')
    
    if not getattr(settings, 'SHOW_DEPRECATION_WARNINGS', True):
        return {'show_warning': False}
    
    is_deprecated = is_deprecated_url(current_url)
    new_url = get_new_url(current_url) if is_deprecated else None
    
    return {
        'show_warning': is_deprecated,
        'old_url': current_url,
        'new_url': new_url,
        'request': request
    }


@register.simple_tag(takes_context=True)
def track_navigation_click(context, menu_item, target_url):
    """
    Generate onclick handler for navigation tracking
    
    Usage: {% track_navigation_click 'Dashboard' '/dashboard/' as onclick %}
    """
    if not getattr(settings, 'ENABLE_NAVIGATION_TRACKING', True):
        return ''
    
    return format_html(
        "onclick=\"trackNavClick('{}', '{}')\"",
        menu_item,
        target_url
    )


@register.simple_tag
def get_popular_pages(limit=5):
    """
    Get most popular pages from navigation tracking
    
    Usage: {% get_popular_pages 10 as popular %}
    """
    analytics = NavigationTrackingMiddleware.get_navigation_analytics()
    popular_paths = analytics.get('popular_paths', {}).get('top_paths', [])
    return popular_paths[:limit]


@register.simple_tag
def get_recent_errors(limit=5):
    """
    Get recent 404 errors
    
    Usage: {% get_recent_errors 5 as errors %}
    """
    analytics = NavigationTrackingMiddleware.get_navigation_analytics()
    dead_urls = analytics.get('dead_urls', {}).get('top_dead_urls', [])
    return dead_urls[:limit]


@register.filter
def json_encode(value):
    """
    JSON encode a value for use in JavaScript
    
    Usage: {{ data|json_encode }}
    """
    return mark_safe(json.dumps(value))


@register.simple_tag
def url_health_indicator(url):
    """
    Get health status indicator for a URL
    
    Usage: {% url_health_indicator '/some/url/' as status %}
    """
    analytics = NavigationTrackingMiddleware.get_navigation_analytics()
    
    # Check if URL is in dead URLs
    dead_urls = analytics.get('dead_urls', {}).get('top_dead_urls', [])
    for dead_url in dead_urls:
        if dead_url.get('url') == url:
            return 'error'
    
    # Check if URL is deprecated
    if is_deprecated_url(url):
        return 'warning'
    
    # Check performance
    popular_paths = analytics.get('popular_paths', {}).get('top_paths', [])
    for path_data in popular_paths:
        if path_data.get('path') == url:
            response_time = path_data.get('avg_response_time', 0)
            if response_time > 3:
                return 'warning'
            elif response_time > 1:
                return 'caution'
            else:
                return 'good'
    
    return 'unknown'


@register.simple_tag
def generate_sitemap_data():
    """
    Generate sitemap data based on new URL structure
    
    Usage: {% generate_sitemap_data as sitemap %}
    """
    menu = OptimizedURLRouter.get_navigation_menu()
    sitemap = []
    
    def extract_urls(items, parent_path=''):
        for item in items:
            url_data = {
                'url': item['url'],
                'name': item['name'],
                'parent': parent_path,
                'priority': 0.8 if not parent_path else 0.6,
                'changefreq': 'weekly'
            }
            sitemap.append(url_data)
            
            # Process children
            if 'children' in item and item['children']:
                extract_urls(item['children'], item['name'])
    
    extract_urls(menu)
    return sitemap


@register.simple_tag(takes_context=True)
def get_user_navigation_history(context, limit=10):
    """
    Get user's recent navigation history
    
    Usage: {% get_user_navigation_history 5 as history %}
    """
    request = context.get('request')
    if not request or not hasattr(request, 'session'):
        return []
    
    session_key = request.session.session_key
    if not session_key:
        return []
    
    from django.core.cache import cache
    user_flows = cache.get('nav_tracking_user_flows', {})
    
    if session_key in user_flows:
        paths = user_flows[session_key].get('paths', [])
        return paths[-limit:] if paths else []
    
    return []