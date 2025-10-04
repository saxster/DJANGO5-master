"""
Enhanced URL Configuration
Adds SEO optimization, analytics tracking, and enhanced user experience to URL routing
"""

from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.decorators import login_required

from apps.core.utils_new.url_optimization import (
    UrlOptimizer,
    URLAnalytics,
    LegacyURLRedirector
)
from apps.core.views.admin_dashboard_views import ModernAdminDashboardView


class EnhancedRedirectView(RedirectView):
    """
    Enhanced redirect view with analytics tracking
    """
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        # Track legacy URL usage
        old_url = self.request.path
        new_url = super().get_redirect_url(*args, **kwargs)

        if new_url:
            LegacyURLRedirector.track_legacy_usage(old_url, new_url, self.request)

        return new_url

    def get(self, request, *args, **kwargs):
        url = self.get_redirect_url(*args, **kwargs)
        if url:
            return HttpResponsePermanentRedirect(url)
        else:
            from django.http import Http404
            raise Http404("No redirect URL found")


# Enhanced URL patterns with SEO and analytics
enhanced_urlpatterns = [

    # ========== SEO-OPTIMIZED CORE URLS ==========

    # Semantic dashboard URLs
    path('dashboard/',
         cache_page(60 * 5)(login_required(ModernAdminDashboardView.as_view())),
         name='dashboard'),

    # Enhanced admin URLs with semantic structure
    path('admin/dashboard/',
         cache_page(60 * 2)(ModernAdminDashboardView.as_view()),
         name='admin_dashboard'),

    # ========== SMART LEGACY REDIRECTS ==========

    # People/User management redirects
    path('peoples/',
         EnhancedRedirectView.as_view(url='/people/directory/'),
         name='peoples_redirect'),

    path('peoples/people/',
         EnhancedRedirectView.as_view(url='/people/directory/'),
         name='peoples_people_redirect'),

    path('admin/peoples/people/',
         EnhancedRedirectView.as_view(url='/people/directory/'),
         name='admin_peoples_redirect'),

    # Activity/Task management redirects
    path('activity/',
         EnhancedRedirectView.as_view(url='/operations/tasks/'),
         name='activity_redirect'),

    path('activity/task/',
         EnhancedRedirectView.as_view(url='/operations/tasks/'),
         name='activity_task_redirect'),

    path('schedhuler/',
         EnhancedRedirectView.as_view(url='/operations/tasks/'),
         name='schedhuler_redirect'),

    # Common typo redirects
    path('schedhule/',
         EnhancedRedirectView.as_view(url='/operations/tasks/'),
         name='schedhuler_typo_redirect'),

    # Help desk redirects
    path('y_helpdesk/',
         EnhancedRedirectView.as_view(url='/help-desk/tickets/'),
         name='helpdesk_redirect'),

    path('helpdesk/',
         EnhancedRedirectView.as_view(url='/help-desk/'),
         name='helpdesk_alt_redirect'),

    # Work order redirects
    path('work_order_management/',
         EnhancedRedirectView.as_view(url='/operations/work-orders/'),
         name='work_order_redirect'),

    path('workorder/',
         EnhancedRedirectView.as_view(url='/operations/work-orders/'),
         name='workorder_redirect'),

    # ========== SEO ENHANCEMENT ENDPOINTS ==========

    # Sitemap generation
    path('sitemap.xml',
         cache_page(60 * 60 * 24)(generate_sitemap),
         name='sitemap'),

    # Robots.txt
    path('robots.txt',
         cache_page(60 * 60 * 24)(generate_robots_txt),
         name='robots_txt'),

    # ========== ANALYTICS ENDPOINTS ==========

    # Page view tracking (for internal analytics)
    path('analytics/track/',
         track_page_view,
         name='track_page_view'),

    # URL error tracking
    path('analytics/url-error/',
         track_url_error,
         name='track_url_error'),

]


# View functions for enhanced features
@ensure_csrf_cookie
def generate_sitemap(request):
    """
    Generate dynamic sitemap.xml
    """
    from django.http import HttpResponse
    from django.template import loader

    # Get all semantic URLs
    urls = [
        {'loc': '/', 'priority': 1.0, 'changefreq': 'daily'},
        {'loc': '/dashboard/', 'priority': 0.9, 'changefreq': 'daily'},
        {'loc': '/operations/', 'priority': 0.8, 'changefreq': 'weekly'},
        {'loc': '/operations/tasks/', 'priority': 0.8, 'changefreq': 'daily'},
        {'loc': '/operations/tours/', 'priority': 0.7, 'changefreq': 'weekly'},
        {'loc': '/operations/work-orders/', 'priority': 0.8, 'changefreq': 'daily'},
        {'loc': '/assets/', 'priority': 0.7, 'changefreq': 'weekly'},
        {'loc': '/assets/inventory/', 'priority': 0.7, 'changefreq': 'weekly'},
        {'loc': '/people/', 'priority': 0.8, 'changefreq': 'weekly'},
        {'loc': '/people/directory/', 'priority': 0.8, 'changefreq': 'weekly'},
        {'loc': '/help-desk/', 'priority': 0.7, 'changefreq': 'daily'},
        {'loc': '/help-desk/tickets/', 'priority': 0.7, 'changefreq': 'daily'},
        {'loc': '/reports/', 'priority': 0.6, 'changefreq': 'weekly'},
    ]

    # Build absolute URLs
    for url_info in urls:
        url_info['loc'] = request.build_absolute_uri(url_info['loc'])

    template = loader.get_template('seo/sitemap.xml')
    sitemap_xml = template.render({'urls': urls})

    return HttpResponse(sitemap_xml, content_type='application/xml')


def generate_robots_txt(request):
    """
    Generate dynamic robots.txt
    """
    from django.http import HttpResponse

    sitemap_url = request.build_absolute_uri('/sitemap.xml')

    robots_content = f"""User-agent: *
Allow: /

# Sitemap
Sitemap: {sitemap_url}

# Disallow admin areas
Disallow: /admin/
Disallow: /api/

# Disallow error pages
Disallow: /errors/

# Allow specific API documentation
Allow: /api/docs/
Allow: /api/redoc/

# Crawl delay
Crawl-delay: 1
"""

    return HttpResponse(robots_content, content_type='text/plain')


def track_page_view(request):
    """
    Track page view for analytics
    """
    from django.http import JsonResponse

    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)

            # Track the page view
            analytics_data = URLAnalytics.track_page_view(request, data)

            return JsonResponse({
                'success': True,
                'tracked': True,
                'analytics_id': analytics_data.get('id')
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Failed to track page view'
            }, status=400)

    return JsonResponse({'success': False, 'error': 'POST required'}, status=405)


def track_url_error(request):
    """
    Track URL errors for analysis
    """
    from django.http import JsonResponse

    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)

            error_code = data.get('error_code', 404)
            error_type = data.get('error_type', 'not_found')

            # Track the error
            URLAnalytics.track_url_error(request, error_code, error_type)

            return JsonResponse({
                'success': True,
                'tracked': True
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Failed to track URL error'
            }, status=400)

    return JsonResponse({'success': False, 'error': 'POST required'}, status=405)


# Middleware for automatic URL optimization
class URLOptimizationMiddleware:
    """
    Middleware to apply URL optimizations automatically
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for legacy URL redirects
        legacy_redirect = LegacyURLRedirector.get_redirect_url(request.path)
        if legacy_redirect:
            LegacyURLRedirector.track_legacy_usage(request.path, legacy_redirect, request)
            return HttpResponsePermanentRedirect(legacy_redirect)

        # Add URL metadata to request
        request.url_metadata = UrlOptimizer.generate_page_metadata(request)
        request.breadcrumbs = UrlOptimizer.generate_breadcrumbs(request)

        response = self.get_response(request)

        # Add SEO headers
        if hasattr(request, 'url_metadata'):
            canonical_url = request.url_metadata.get('canonical_url')
            if canonical_url:
                response['Link'] = f'<{canonical_url}>; rel="canonical"'

        return response


# Context processor for URL optimization
def url_optimization_context(request):
    """
    Context processor to add URL optimization data to templates
    """
    if not hasattr(request, 'url_metadata'):
        request.url_metadata = UrlOptimizer.generate_page_metadata(request)
        request.breadcrumbs = UrlOptimizer.generate_breadcrumbs(request)

    return {
        'url_metadata': request.url_metadata,
        'breadcrumbs': request.breadcrumbs,
        'canonical_url': request.url_metadata.get('canonical_url'),
        'page_title': request.url_metadata.get('title'),
        'page_description': request.url_metadata.get('description'),
    }