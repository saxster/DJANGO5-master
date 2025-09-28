"""
Context processors for Information Architecture optimization
Provides IA-related context variables to all templates
"""
from django.conf import settings
from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware


def ia_context(request):
    """
    Add IA-related context variables to all templates
    
    Available in templates as:
    - ia_settings: IA configuration
    - navigation_menu: Main navigation menu
    - breadcrumbs: Current page breadcrumbs
    - migration_status: URL migration status
    - deprecation_info: Deprecation information for current URL
    """
    
    # Get IA settings
    ia_settings = {
        'use_optimized_urls': getattr(settings, 'USE_OPTIMIZED_URLS', False),
        'enable_legacy_urls': getattr(settings, 'ENABLE_LEGACY_URLS', True),
        'show_deprecation_warnings': getattr(settings, 'SHOW_DEPRECATION_WARNINGS', True),
        'migration_phase': getattr(settings, 'IA_MIGRATION_PHASE', 'active'),
    }
    
    # Get navigation menu for current user
    navigation_menu = []
    admin_menu = []
    try:
        navigation_menu = OptimizedURLRouter.get_navigation_menu(
            user=request.user if request.user.is_authenticated else None,
            menu_type='main'
        )
        if request.user.is_authenticated and request.user.is_staff:
            admin_menu = OptimizedURLRouter.get_navigation_menu(
                user=request.user,
                menu_type='admin'
            )
    except (ValueError, TypeError):
        pass  # Fail silently
    
    # Get breadcrumbs for current page
    breadcrumbs = []
    try:
        breadcrumbs = OptimizedURLRouter.get_breadcrumbs(request.path)
    except (ValueError, TypeError):
        pass  # Fail silently
    
    # Get migration status
    migration_status = {}
    try:
        migration_report = OptimizedURLRouter.get_migration_report()
        migration_status = {
            'adoption_rate': migration_report['summary']['adoption_rate'],
            'total_redirects': migration_report['summary']['total_redirects'],
            'phase': ia_settings['migration_phase'],
        }
    except (ValueError, TypeError):
        pass  # Fail silently
    
    # Check if current URL is deprecated
    deprecation_info = {}
    if ia_settings['show_deprecation_warnings']:
        try:
            current_url = request.path.strip('/')
            if OptimizedURLRouter.should_show_deprecation_warning(current_url):
                deprecation_info = {
                    'is_deprecated': True,
                    'old_url': request.path,
                    'new_url': '/' + OptimizedURLRouter.get_new_url(current_url),
                }
        except (ValueError, TypeError):
            pass  # Fail silently
    
    # Get quick navigation statistics
    nav_stats = {}
    try:
        if getattr(settings, 'ENABLE_NAVIGATION_TRACKING', True):
            analytics = NavigationTrackingMiddleware.get_navigation_analytics()
            nav_stats = {
                'popular_pages': analytics.get('popular_paths', {}).get('top_paths', [])[:3],
                'recent_errors': analytics.get('dead_urls', {}).get('top_dead_urls', [])[:3],
                'active_sessions': analytics.get('user_flows', {}).get('active_sessions', 0),
            }
    except (ValueError, TypeError):
        pass  # Fail silently
    
    return {
        'ia_settings': ia_settings,
        'navigation_menu': navigation_menu,
        'admin_menu': admin_menu,
        'breadcrumbs': breadcrumbs,
        'migration_status': migration_status,
        'deprecation_info': deprecation_info,
        'nav_stats': nav_stats,
    }