"""
Google Maps Admin Dashboard Views
Administrative interface for monitoring Google Maps API performance.
"""

import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from apps.core.decorators import csrf_protect_ajax
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from apps.core.monitoring.google_maps_monitor import google_maps_monitor
from apps.core.services.google_maps_service import google_maps_service
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class GoogleMapsAdminDashboard(View):
    """Main admin dashboard for Google Maps monitoring."""

    def get(self, request):
        """Render the Google Maps admin dashboard."""
        try:
            # Get current performance stats
            stats = google_maps_monitor.get_performance_stats()

            # Get recent metrics for charts
            recent_metrics = google_maps_monitor.get_recent_metrics(hours=24)

            context = {
                'page_title': 'Google Maps Performance Dashboard',
                'stats': stats,
                'recent_metrics': recent_metrics,
                'api_configured': bool(google_maps_service.api_key),
                'client_initialized': bool(google_maps_service._client),
                'cache_backend': str(google_maps_service.cache),
                'debug_mode': settings.DEBUG,
                'refresh_interval': 30000,  # 30 seconds
            }

            return render(request, 'core/admin/google_maps_dashboard.html', context)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to load Google Maps dashboard: {str(e, exc_info=True)}")
            return render(request, 'core/admin/google_maps_dashboard_error.html', {
                'error_message': str(e)
            })


@staff_member_required
@require_http_methods(["GET"])
def google_maps_stats_api(request):
    """API endpoint for real-time statistics."""
    try:
        stats = google_maps_monitor.get_performance_stats()
        return JsonResponse({
            'status': 'success',
            'data': stats,
            'timestamp': datetime.now().isoformat()
        })
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to get Google Maps stats: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def google_maps_metrics_api(request):
    """API endpoint for historical metrics."""
    try:
        hours = int(request.GET.get('hours', 24))
        metrics = google_maps_monitor.get_recent_metrics(hours=hours)

        return JsonResponse({
            'status': 'success',
            'data': metrics,
            'hours': hours,
            'timestamp': datetime.now().isoformat()
        })
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to get Google Maps metrics: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@staff_member_required
@csrf_protect_ajax
@require_http_methods(["POST"])
def google_maps_clear_cache_api(request):
    """API endpoint to clear Google Maps cache."""
    try:
        # Clear service cache
        google_maps_service.clear_cache()

        # Clear monitoring metrics if requested
        if request.POST.get('clear_metrics') == 'true':
            google_maps_monitor.clear_metrics()

        return JsonResponse({
            'status': 'success',
            'message': 'Cache cleared successfully',
            'timestamp': datetime.now().isoformat()
        })
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to clear Google Maps cache: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def google_maps_test_connection(request):
    """Test Google Maps API connection."""
    try:
        if not google_maps_service.api_key:
            return JsonResponse({
                'status': 'error',
                'message': 'Google Maps API key not configured'
            }, status=400)

        # Test with a simple geocoding request
        test_result = google_maps_service.geocode_with_cache("Mumbai, India", request)

        if test_result:
            return JsonResponse({
                'status': 'success',
                'message': 'Google Maps API connection successful',
                'test_result': {
                    'address': test_result.get('formatted_address'),
                    'coordinates': {
                        'lat': test_result.get('latitude'),
                        'lng': test_result.get('longitude')
                    }
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Google Maps API test failed - no results returned'
            }, status=500)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Google Maps connection test failed: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Connection test failed: {str(e)}'
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def google_maps_export_metrics(request):
    """Export metrics in various formats."""
    try:
        format_type = request.GET.get('format', 'json').lower()

        if format_type not in ['json', 'csv']:
            return JsonResponse({
                'status': 'error',
                'message': 'Supported formats: json, csv'
            }, status=400)

        metrics_data = google_maps_monitor.export_metrics(format=format_type)

        if format_type == 'csv':
            response = HttpResponse(metrics_data, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="google_maps_metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            return response
        else:
            response = HttpResponse(metrics_data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="google_maps_metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to export Google Maps metrics: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def google_maps_health_check(request):
    """Comprehensive health check for Google Maps integration."""
    try:
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'components': {}
        }

        # Check API key configuration
        health_status['components']['api_key'] = {
            'status': 'healthy' if google_maps_service.api_key else 'error',
            'message': 'API key configured' if google_maps_service.api_key else 'API key not configured'
        }

        # Check client initialization
        try:
            client_status = bool(google_maps_service.client)
            health_status['components']['client'] = {
                'status': 'healthy' if client_status else 'error',
                'message': 'Client initialized' if client_status else 'Client not initialized'
            }
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            health_status['components']['client'] = {
                'status': 'error',
                'message': f'Client initialization failed: {str(e)}'
            }

        # Check cache connectivity
        try:
            google_maps_service.cache.get('health_check_test')
            health_status['components']['cache'] = {
                'status': 'healthy',
                'message': 'Cache accessible'
            }
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            health_status['components']['cache'] = {
                'status': 'error',
                'message': f'Cache not accessible: {str(e)}'
            }

        # Check performance metrics
        stats = google_maps_monitor.get_performance_stats()
        performance_status = 'healthy'
        performance_message = 'Performance within normal parameters'

        if stats.get('status') in ['Critical - High Error Rate', 'Warning - Slow Response']:
            performance_status = 'warning'
            performance_message = stats.get('status')

        health_status['components']['performance'] = {
            'status': performance_status,
            'message': performance_message,
            'stats': {
                'total_calls': stats.get('total_calls', 0),
                'success_rate': f"{stats.get('success_rate', 0)*100:.1f}%",
                'avg_response_time': f"{stats.get('avg_response_time', 0):.1f}ms",
                'cache_hit_rate': f"{stats.get('cache_hit_rate', 0)*100:.1f}%"
            }
        }

        # Determine overall status
        component_statuses = [comp['status'] for comp in health_status['components'].values()]
        if 'error' in component_statuses:
            health_status['overall_status'] = 'error'
        elif 'warning' in component_statuses:
            health_status['overall_status'] = 'warning'

        # Return appropriate HTTP status
        if health_status['overall_status'] == 'error':
            return JsonResponse(health_status, status=503)
        elif health_status['overall_status'] == 'warning':
            return JsonResponse(health_status, status=200)
        else:
            return JsonResponse(health_status, status=200)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Google Maps health check failed: {str(e, exc_info=True)}")
        return JsonResponse({
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'error',
            'message': f'Health check failed: {str(e)}'
        }, status=500)


@staff_member_required
@require_http_methods(["GET"])
def google_maps_config_info(request):
    """Get current Google Maps configuration information."""
    try:
        config_info = {
            'api_key_configured': bool(google_maps_service.api_key),
            'api_key_prefix': google_maps_service.api_key[:8] + '...' if google_maps_service.api_key else None,
            'cache_ttl': {
                'geocoding': google_maps_service.geocoding_cache_ttl,
                'directions': google_maps_service.directions_cache_ttl
            },
            'cache_backend': str(google_maps_service.cache),
            'client_initialized': bool(google_maps_service._client),
            'monitoring': {
                'enabled': True,
                'retention_hours': google_maps_monitor.metrics_retention_hours,
                'alert_thresholds': google_maps_monitor.alert_thresholds
            },
            'performance_config': google_maps_service.get_secure_config(),
            'timestamp': datetime.now().isoformat()
        }

        return JsonResponse({
            'status': 'success',
            'data': config_info
        })

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Failed to get Google Maps config info: {str(e, exc_info=True)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)