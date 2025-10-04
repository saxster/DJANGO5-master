"""
NOC Metrics Middleware for Prometheus Integration.

Automatically collects request metrics for NOC API endpoints.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import time
import logging
from django.utils.deprecation import MiddlewareMixin

__all__ = ['NOCMetricsMiddleware']

logger = logging.getLogger('noc.metrics')


class NOCMetricsMiddleware(MiddlewareMixin):
    """Django middleware to collect NOC API metrics."""

    def process_request(self, request):
        """Record request start time."""
        if request.path.startswith('/api/noc/'):
            request._noc_start_time = time.time()
        return None

    def process_response(self, request, response):
        """Record request completion metrics."""
        if hasattr(request, '_noc_start_time'):
            duration = time.time() - request._noc_start_time
            self._record_metrics(request, response, duration)
        return response

    def _record_metrics(self, request, response, duration):
        """Record metrics to cache for Prometheus scraping."""
        try:
            from django.core.cache import cache

            endpoint = request.path.replace('/api/noc/', '')
            status_code = response.status_code

            counter_key = f"noc:metrics:requests:{endpoint}:{status_code}"
            cache.incr(counter_key, delta=1)

            latency_key = f"noc:metrics:latency:{endpoint}"
            latencies = cache.get(latency_key, [])
            latencies.append(duration)
            if len(latencies) > 1000:
                latencies = latencies[-1000:]
            cache.set(latency_key, latencies, 3600)

        except (ValueError, ConnectionError) as e:
            logger.error(f"Failed to record metrics: {e}")