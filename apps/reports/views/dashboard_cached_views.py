"""
Cached dashboard views for Reports app.

Demonstrates caching implementation for expensive dashboard operations.

Created: 2025-11-07
"""

import logging
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.http import JsonResponse
from django.db.models import Count, Avg, Sum, Q
from apps.reports.services.dashboard_cache_service import DashboardCacheService
from apps.peoples.services.permission_cache_service import PermissionCacheService
from apps.core.utils_new.cache_utils import cache_result, get_cache_stats
from apps.activity.models.task_model import Task
from apps.work_order_management.models import WorkOrder

logger = logging.getLogger(__name__)


# Method 1: View-level caching with decorator
@login_required
@cache_page(60 * 5)  # Cache entire response for 5 minutes
def dashboard_overview(request):
    """
    Dashboard overview with view-level caching.
    
    Entire response is cached, suitable for static/public dashboards.
    """
    site_id = request.user.organizational.site_id
    
    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Get metrics (will be computed once and cached)
    metrics = DashboardCacheService.get_dashboard_metrics(
        site_id,
        (start_date, end_date)
    )
    
    context = {
        'metrics': metrics,
        'site_id': site_id,
    }
    
    return render(request, 'reports/dashboard_overview.html', context)


# Method 2: Data-level caching
@login_required
def dashboard_metrics_api(request):
    """
    Dashboard metrics API with data-level caching.
    
    Response personalized per user, so only data is cached.
    """
    site_id = request.GET.get('site_id', request.user.organizational.site_id)
    
    # Get date range from request
    days = int(request.GET.get('days', 30))
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get cached metrics
    metrics = DashboardCacheService.get_dashboard_metrics(
        site_id,
        (start_date, end_date)
    )
    
    # Get user permissions (cached separately)
    permissions = PermissionCacheService.get_user_permissions(request.user)
    
    return JsonResponse({
        'metrics': metrics,
        'permissions': permissions,
        'cache_stats': get_cache_stats(),
    })


# Method 3: Decorator pattern with custom caching
@cache_result(timeout=600, key_prefix='site_statistics')
def get_site_statistics(site_id):
    """
    Get site statistics with decorator-based caching.
    
    Cached for 10 minutes. Function can be called from anywhere.
    """
    # Expensive aggregations
    tasks = Task.objects.filter(site_id=site_id)
    work_orders = WorkOrder.objects.filter(site_id=site_id)
    
    return {
        'total_tasks': tasks.count(),
        'completed_tasks': tasks.filter(status='completed').count(),
        'avg_completion_days': tasks.filter(
            status='completed',
            completion_date__isnull=False
        ).aggregate(
            avg_days=Avg('completion_date')
        )['avg_days'] or 0,
        'total_work_orders': work_orders.count(),
        'pending_work_orders': work_orders.filter(status='pending').count(),
    }


@login_required
def site_statistics_view(request):
    """View using cached site statistics."""
    site_id = request.user.organizational.site_id
    
    # This will use cached data if available
    stats = get_site_statistics(site_id)
    
    return JsonResponse(stats)


# Method 4: Manual cache management
@login_required
def dashboard_chart_data(request):
    """
    Chart data with manual cache management.
    
    Demonstrates manual cache get/set with custom logic.
    """
    site_id = request.user.organizational.site_id
    chart_type = request.GET.get('type', 'tasks')
    days = int(request.GET.get('days', 30))
    
    # Create cache key
    cache_key = f"chart_data_{site_id}_{chart_type}_{days}"
    
    # Try to get from cache
    chart_data = cache.get(cache_key)
    
    if chart_data is None:
        # Cache miss - compute chart data
        logger.info(f"Cache miss for chart: {chart_type}")
        
        # Use service method (which is also cached)
        chart_data = DashboardCacheService.get_chart_data(
            site_id,
            chart_type,
            days
        )
        
        # Cache for 10 minutes
        cache.set(cache_key, chart_data, 600)
    else:
        logger.info(f"Cache hit for chart: {chart_type}")
    
    return JsonResponse(chart_data)


# Method 5: Conditional caching
@login_required
def dashboard_live_data(request):
    """
    Dashboard with conditional caching based on user role.
    
    Admin users get real-time data, regular users get cached data.
    """
    site_id = request.user.organizational.site_id
    
    # Admin users bypass cache for real-time data
    if request.user.is_staff:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Compute fresh data
        metrics = {
            'total_tasks': Task.objects.filter(site_id=site_id).count(),
            'pending_tasks': Task.objects.filter(
                site_id=site_id,
                status='pending'
            ).count(),
            'cached': False,
        }
    else:
        # Regular users get cached data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        metrics = DashboardCacheService.get_dashboard_metrics(
            site_id,
            (start_date, end_date)
        )
        metrics['cached'] = True
    
    return JsonResponse(metrics)


# Cache invalidation endpoint
@login_required
def invalidate_site_cache(request):
    """
    Invalidate cached data for a site.
    
    Useful for admin actions or after bulk updates.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    site_id = request.GET.get('site_id')
    if not site_id:
        return JsonResponse({'error': 'site_id required'}, status=400)
    
    # Invalidate all site-related cache
    deleted = DashboardCacheService.invalidate_site_cache(site_id)
    
    return JsonResponse({
        'success': True,
        'cache_entries_deleted': deleted,
        'message': f'Cache invalidated for site {site_id}'
    })


# Cache warming endpoint
@login_required
def warm_site_cache(request):
    """
    Pre-warm cache for a site.
    
    Useful after deployments or scheduled via cron.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    site_id = request.GET.get('site_id')
    if not site_id:
        return JsonResponse({'error': 'site_id required'}, status=400)
    
    # Warm cache
    DashboardCacheService.warm_site_cache(site_id)
    
    return JsonResponse({
        'success': True,
        'message': f'Cache warmed for site {site_id}'
    })


# Cache statistics endpoint
@login_required
def cache_statistics(request):
    """
    Get cache hit/miss statistics.
    
    For monitoring cache performance.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    stats = get_cache_stats()
    
    return JsonResponse({
        'cache_stats': stats,
        'recommendation': _get_cache_recommendation(stats['hit_rate'])
    })


def _get_cache_recommendation(hit_rate: float) -> str:
    """Get recommendation based on cache hit rate."""
    if hit_rate >= 80:
        return "Excellent cache performance"
    elif hit_rate >= 60:
        return "Good cache performance"
    elif hit_rate >= 40:
        return "Consider increasing cache timeouts or warming cache"
    else:
        return "Poor cache performance - review caching strategy"


__all__ = [
    'dashboard_overview',
    'dashboard_metrics_api',
    'site_statistics_view',
    'dashboard_chart_data',
    'dashboard_live_data',
    'invalidate_site_cache',
    'warm_site_cache',
    'cache_statistics',
]
