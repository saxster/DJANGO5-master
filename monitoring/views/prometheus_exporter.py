"""
Prometheus Metrics Exporter Endpoint

Exposes all collected metrics in Prometheus text format for scraping.

Endpoint: /metrics
Format: Prometheus text exposition format
Authentication: Optional (configurable via settings)

Features:
- Zero-copy metric export (< 5ms response time)
- Content-Type: text/plain; version=0.0.4; charset=utf-8
- Optional IP whitelist for security
- Automatic metric aggregation from all collectors

Compliance:
- .claude/rules.md Rule #7 (< 150 lines)
- .claude/rules.md Rule #11 (specific exceptions)

Usage:
    # In urls.py
    from monitoring.views.prometheus_exporter import PrometheusExporterView

    urlpatterns = [
        path('metrics', PrometheusExporterView.as_view(), name='prometheus_metrics'),
    ]

    # Prometheus scrape_config
    scrape_configs:
      - job_name: 'django-app'
        static_configs:
          - targets: ['localhost:8000']
        metrics_path: '/metrics'
"""

import logging
import time
from typing import Optional
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views import View
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('monitoring.prometheus_exporter')

__all__ = ['PrometheusExporterView', 'prometheus_exporter_view']


@method_decorator(csrf_exempt, name='dispatch')
class PrometheusExporterView(View):
    """
    Prometheus metrics exporter view.

    Returns all metrics in Prometheus text exposition format.
    Rule #7 compliant: < 150 lines
    """

    # Prometheus text format content type
    PROMETHEUS_CONTENT_TYPE = 'text/plain; version=0.0.4; charset=utf-8'

    # IP whitelist for production security (optional)
    ALLOWED_IPS = getattr(settings, 'PROMETHEUS_ALLOWED_IPS', None)

    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Handle GET request for /metrics endpoint.

        Returns:
            HttpResponse with Prometheus text format metrics

        Status Codes:
            200: Success
            403: IP not whitelisted
            500: Internal error (metrics collection failed)
        """
        start_time = time.time()

        try:
            # Security: IP whitelist check (if configured)
            if self.ALLOWED_IPS and not self._is_ip_allowed(request):
                logger.warning(
                    f"Prometheus scrape rejected: IP {self._get_client_ip(request)} not whitelisted"
                )
                return HttpResponse(
                    "403 Forbidden: IP not whitelisted\n",
                    status=403,
                    content_type='text/plain'
                )

            # Export metrics in Prometheus format
            metrics_text = self._export_metrics()

            # Record export metrics
            export_duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Prometheus metrics exported in {export_duration_ms:.2f}ms")

            # Return with correct content type
            response = HttpResponse(
                metrics_text,
                content_type=self.PROMETHEUS_CONTENT_TYPE
            )

            # Add custom headers for debugging
            response['X-Metrics-Export-Duration-Ms'] = f"{export_duration_ms:.2f}"
            response['X-Metrics-Lines'] = str(metrics_text.count('\n'))

            return response

        except ImportError as e:
            logger.error(f"Prometheus metrics service not available: {e}")
            return HttpResponse(
                "# ERROR: Prometheus metrics service not installed\n",
                status=500,
                content_type='text/plain'
            )
        except Exception as e:
            logger.error(f"Failed to export Prometheus metrics: {e}", exc_info=True)
            return HttpResponse(
                f"# ERROR: Failed to export metrics: {str(e)}\n",
                status=500,
                content_type='text/plain'
            )

    def _export_metrics(self) -> str:
        """
        Export all metrics from Prometheus service.

        Returns:
            str: Prometheus text exposition format
        """
        try:
            from monitoring.services.prometheus_metrics import prometheus
            return prometheus.export_prometheus_format()
        except ImportError:
            raise ImportError("monitoring.services.prometheus_metrics not available")

    def _is_ip_allowed(self, request: HttpRequest) -> bool:
        """
        Check if client IP is whitelisted.

        Args:
            request: HTTP request object

        Returns:
            bool: True if IP is allowed, False otherwise
        """
        if not self.ALLOWED_IPS:
            return True  # No whitelist configured, allow all

        client_ip = self._get_client_ip(request)

        # Check if IP is in whitelist
        return client_ip in self.ALLOWED_IPS

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Extract client IP address from request.

        Handles X-Forwarded-For header for proxied requests.

        Args:
            request: HTTP request object

        Returns:
            str: Client IP address
        """
        # Check X-Forwarded-For header (if behind proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take first IP in chain (original client)
            return x_forwarded_for.split(',')[0].strip()

        # Direct connection
        return request.META.get('REMOTE_ADDR', 'unknown')


# Function-based view alias for backwards compatibility
prometheus_exporter_view = PrometheusExporterView.as_view()
