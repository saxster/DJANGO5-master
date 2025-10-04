"""
Dashboard Mixins

Standard mixins for dashboard views providing:
- Unified API response structure
- Common data gathering patterns
- Caching decorators
- Export functionality
- Real-time update support

All dashboards should use these mixins to ensure consistent
API contracts and user experience.

Architecture Compliance:
- Single Responsibility Principle
- DRY (Don't Repeat Yourself)
- Standardized error handling
- Performance optimization via caching

Author: Dashboard Infrastructure Team
Date: 2025-10-04
"""

import csv
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from io import StringIO

from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import cache_page

logger = logging.getLogger(__name__)


class DashboardAPIMixin:
    """
    Base mixin for dashboard API responses.

    Provides standardized JSON response format with:
    - Version information
    - Timestamp
    - Tenant context
    - Cache information
    - Consistent error handling
    """

    API_VERSION = 'v1'

    def get_api_response(self,
                         dashboard_id: str,
                         data: Dict[str, Any],
                         cache_hit: bool = False,
                         cache_ttl: int = 0) -> JsonResponse:
        """
        Generate standardized dashboard API response.

        Args:
            dashboard_id: Dashboard identifier
            data: Dashboard-specific data
            cache_hit: Whether response came from cache
            cache_ttl: Cache TTL in seconds

        Returns:
            Standardized JSON response
        """
        # Get tenant context from session
        tenant_context = self._get_tenant_context()

        response_data = {
            'version': self.API_VERSION,
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant_context,
            'dashboard_id': dashboard_id,
            'data': data,
            'cache_info': {
                'hit': cache_hit,
                'ttl': cache_ttl,
                'generated_at': data.get('generated_at', timezone.now().isoformat())
            }
        }

        return JsonResponse(response_data)

    def get_error_response(self,
                           error_type: str,
                           message: str,
                           status_code: int = 500,
                           details: Optional[Dict] = None) -> JsonResponse:
        """
        Generate standardized error response.

        Args:
            error_type: Type of error (e.g., 'database_error', 'permission_denied')
            message: User-friendly error message
            status_code: HTTP status code
            details: Optional error details (for debugging)

        Returns:
            Standardized error JSON response
        """
        error_data = {
            'version': self.API_VERSION,
            'timestamp': timezone.now().isoformat(),
            'error': {
                'type': error_type,
                'message': message,
                'status_code': status_code
            }
        }

        if details and not getattr(self, 'request', None) or self.request.user.is_staff:
            # Only include details for staff users
            error_data['error']['details'] = details

        return JsonResponse(error_data, status=status_code)

    def _get_tenant_context(self) -> Dict[str, Any]:
        """
        Get tenant context from session.

        Returns:
            Dictionary with tenant information
        """
        if not hasattr(self, 'request'):
            return {}

        return {
            'bu_id': self.request.session.get('bu_id'),
            'client_id': self.request.session.get('client_id'),
            'sitecode': self.request.session.get('sitecode'),
            'sitename': self.request.session.get('sitename')
        }


class DashboardDataMixin:
    """
    Mixin for common dashboard data gathering patterns.

    Provides standard methods for:
    - Metrics collection
    - Chart data generation
    - Alert aggregation
    - Time range filtering
    """

    def get_time_range(self, default_hours: int = 24) -> Tuple[datetime, datetime]:
        """
        Get time range from request parameters.

        Args:
            default_hours: Default time range in hours

        Returns:
            Tuple of (start_time, end_time)
        """
        if not hasattr(self, 'request'):
            now = timezone.now()
            return now - timedelta(hours=default_hours), now

        # Parse time range from request
        time_range = self.request.GET.get('range', f'{default_hours}h')

        try:
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                end_time = timezone.now()
                start_time = end_time - timedelta(hours=hours)
            elif time_range.endswith('d'):
                days = int(time_range[:-1])
                end_time = timezone.now()
                start_time = end_time - timedelta(days=days)
            else:
                # Default fallback
                end_time = timezone.now()
                start_time = end_time - timedelta(hours=default_hours)

            return start_time, end_time

        except ValueError:
            logger.warning(f"Invalid time range format: {time_range}, using default")
            now = timezone.now()
            return now - timedelta(hours=default_hours), now

    def format_metrics(self, **metrics) -> Dict[str, Any]:
        """
        Format metrics in standard structure.

        Args:
            **metrics: Key-value pairs of metrics

        Returns:
            Formatted metrics dictionary
        """
        return {
            'timestamp': timezone.now().isoformat(),
            'metrics': metrics
        }

    def format_chart_data(self,
                          labels: List[str],
                          datasets: List[Dict[str, Any]],
                          chart_type: str = 'line') -> Dict[str, Any]:
        """
        Format chart data in standard structure.

        Args:
            labels: X-axis labels
            datasets: List of dataset dictionaries
            chart_type: Type of chart (line, bar, pie, etc.)

        Returns:
            Formatted chart data
        """
        return {
            'type': chart_type,
            'labels': labels,
            'datasets': datasets,
            'generated_at': timezone.now().isoformat()
        }

    def format_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format alerts in standard structure.

        Args:
            alerts: List of alert dictionaries

        Returns:
            Formatted alerts data
        """
        return {
            'total': len(alerts),
            'alerts': alerts,
            'severity_counts': self._count_severity(alerts),
            'timestamp': timezone.now().isoformat()
        }

    def _count_severity(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count alerts by severity level."""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

        for alert in alerts:
            severity = alert.get('severity', 'low').lower()
            if severity in counts:
                counts[severity] += 1

        return counts


class DashboardCacheMixin:
    """
    Mixin for dashboard caching strategies.

    Provides:
    - Cache key generation
    - Cache retrieval with tenant isolation
    - Cache invalidation helpers
    """

    CACHE_KEY_PREFIX = 'dashboard'
    CACHE_TTL = 300  # 5 minutes default

    def get_cache_key(self,
                      dashboard_id: str,
                      *args,
                      include_tenant: bool = True) -> str:
        """
        Generate cache key for dashboard data.

        Args:
            dashboard_id: Dashboard identifier
            *args: Additional key components
            include_tenant: Include tenant context in key

        Returns:
            Cache key string
        """
        key_parts = [self.CACHE_KEY_PREFIX, dashboard_id]

        if include_tenant and hasattr(self, 'request'):
            bu_id = self.request.session.get('bu_id', 'global')
            client_id = self.request.session.get('client_id', 'global')
            key_parts.extend([str(bu_id), str(client_id)])

        key_parts.extend(str(arg) for arg in args)

        return ':'.join(key_parts)

    def get_cached_data(self,
                        cache_key: str,
                        default: Any = None) -> Tuple[Any, bool]:
        """
        Get data from cache.

        Args:
            cache_key: Cache key
            default: Default value if not cached

        Returns:
            Tuple of (data, cache_hit)
        """
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data, True
            return default, False
        except (ConnectionError, ValueError) as e:
            logger.error(f"Cache retrieval error: {e}")
            return default, False

    def set_cached_data(self,
                        cache_key: str,
                        data: Any,
                        ttl: Optional[int] = None) -> bool:
        """
        Set data in cache.

        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds (None = use default)

        Returns:
            True if cached successfully
        """
        try:
            cache.set(cache_key, data, ttl or self.CACHE_TTL)
            return True
        except (ConnectionError, ValueError) as e:
            logger.error(f"Cache set error: {e}")
            return False

    def invalidate_cache(self, dashboard_id: str, *args) -> bool:
        """
        Invalidate dashboard cache.

        Args:
            dashboard_id: Dashboard identifier
            *args: Additional key components

        Returns:
            True if invalidated successfully
        """
        try:
            cache_key = self.get_cache_key(dashboard_id, *args)
            cache.delete(cache_key)
            return True
        except (ConnectionError, ValueError) as e:
            logger.error(f"Cache invalidation error: {e}")
            return False


class DashboardExportMixin:
    """
    Mixin for dashboard data export functionality.

    Provides:
    - CSV export
    - JSON export
    - Excel export (if openpyxl available)
    """

    def export_to_csv(self,
                      data: List[Dict[str, Any]],
                      filename: str = 'dashboard_export.csv') -> HttpResponse:
        """
        Export dashboard data to CSV.

        Args:
            data: List of dictionaries to export
            filename: Output filename

        Returns:
            HTTP response with CSV file
        """
        if not data:
            response = HttpResponse('No data to export', content_type='text/plain')
            return response

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        # Create response
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    def export_to_json(self,
                       data: Dict[str, Any],
                       filename: str = 'dashboard_export.json') -> HttpResponse:
        """
        Export dashboard data to JSON.

        Args:
            data: Dictionary to export
            filename: Output filename

        Returns:
            HTTP response with JSON file
        """
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


class DashboardPermissionMixin(UserPassesTestMixin):
    """
    Mixin for dashboard permission checks.

    Provides role-based access control for dashboards.
    """

    dashboard_permission = None  # Override in subclass
    require_staff = False
    require_superuser = False

    def test_func(self):
        """Test if user has required permissions."""
        if not self.request.user.is_authenticated:
            return False

        if self.require_superuser:
            return self.request.user.is_superuser

        if self.require_staff:
            return self.request.user.is_staff

        if self.dashboard_permission:
            return self.request.user.has_perm(self.dashboard_permission)

        # Default: require authentication only
        return True


class BaseDashboardView(LoginRequiredMixin,
                        DashboardAPIMixin,
                        DashboardDataMixin,
                        DashboardCacheMixin,
                        DashboardExportMixin):
    """
    Base class for all dashboard views.

    Combines all dashboard mixins to provide standard functionality.
    Subclasses should implement:
    - get_dashboard_data() - Return dashboard-specific data
    - dashboard_id - Unique dashboard identifier
    """

    dashboard_id = None  # Override in subclass
    cache_ttl = 300  # 5 minutes default

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard-specific data.

        Override this method in subclass to provide dashboard data.

        Returns:
            Dictionary with dashboard data
        """
        raise NotImplementedError("Subclasses must implement get_dashboard_data()")

    def get(self, request, *args, **kwargs):
        """
        Handle GET request with caching.

        Returns:
            JSON response with dashboard data
        """
        if not self.dashboard_id:
            return self.get_error_response(
                'configuration_error',
                'Dashboard ID not configured',
                status_code=500
            )

        try:
            # Check cache
            cache_key = self.get_cache_key(self.dashboard_id)
            cached_data, cache_hit = self.get_cached_data(cache_key)

            if cache_hit:
                logger.info(f"Dashboard cache hit: {self.dashboard_id}")
                return self.get_api_response(
                    self.dashboard_id,
                    cached_data,
                    cache_hit=True,
                    cache_ttl=self.cache_ttl
                )

            # Generate fresh data
            logger.info(f"Generating dashboard data: {self.dashboard_id}")
            data = self.get_dashboard_data()

            # Cache the data
            self.set_cached_data(cache_key, data, self.cache_ttl)

            return self.get_api_response(
                self.dashboard_id,
                data,
                cache_hit=False,
                cache_ttl=self.cache_ttl
            )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in dashboard {self.dashboard_id}: {e}", exc_info=True)
            return self.get_error_response(
                'database_error',
                'Database error occurred',
                status_code=500,
                details={'error': str(e)}
            )

        except ObjectDoesNotExist as e:
            logger.error(f"Object not found in dashboard {self.dashboard_id}: {e}", exc_info=True)
            return self.get_error_response(
                'not_found',
                'Required data not found',
                status_code=404,
                details={'error': str(e)}
            )

        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Data error in dashboard {self.dashboard_id}: {e}", exc_info=True)
            return self.get_error_response(
                'data_error',
                'Data processing error',
                status_code=500,
                details={'error': str(e)}
            )


# Export public API
__all__ = [
    'DashboardAPIMixin',
    'DashboardDataMixin',
    'DashboardCacheMixin',
    'DashboardExportMixin',
    'DashboardPermissionMixin',
    'BaseDashboardView'
]
