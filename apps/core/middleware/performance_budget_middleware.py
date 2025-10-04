"""
Performance Budget Enforcement Middleware

Tracks and enforces per-endpoint SLA budgets.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import time
import logging
from typing import Optional, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache

from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


class PerformanceBudgetMiddleware(MiddlewareMixin):
    """
    Middleware to enforce performance budgets per endpoint.

    Tracks P50, P95, P99 latencies and triggers alerts on violations.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.budgets = getattr(
            settings,
            'ENDPOINT_PERFORMANCE_BUDGETS',
            {}
        )

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Record request start time."""
        request._performance_start_time = time.time()
        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """Record request duration and check budget."""
        if not hasattr(request, '_performance_start_time'):
            return response

        # Calculate duration
        duration_ms = (time.time() - request._performance_start_time) * 1000

        # Get budget for endpoint
        budget = self._get_budget(request.path)

        # Store metrics
        self._record_metrics(request.path, duration_ms)

        # Check budget violations
        if duration_ms > budget['p99']:
            logger.warning(
                f"P99 budget violation: {request.path}",
                extra={
                    'path': request.path,
                    'duration_ms': duration_ms,
                    'budget_p99': budget['p99'],
                    'method': request.method
                }
            )

        elif duration_ms > budget['p95']:
            logger.info(
                f"P95 budget exceeded: {request.path}",
                extra={
                    'path': request.path,
                    'duration_ms': duration_ms,
                    'budget_p95': budget['p95']
                }
            )

        # Add performance headers
        response['X-Response-Time-Ms'] = str(int(duration_ms))

        return response

    def _get_budget(self, path: str) -> Dict[str, int]:
        """Get performance budget for path."""
        # Check exact match
        if path in self.budgets:
            return self.budgets[path]

        # Check prefix matches
        for budget_path, budget in self.budgets.items():
            if path.startswith(budget_path):
                return budget

        # Return default budget
        return self.budgets.get('default', {
            'p50': 300,
            'p95': 1000,
            'p99': 3000
        })

    def _record_metrics(self, path: str, duration_ms: float):
        """Record performance metrics in cache."""
        try:
            cache_key = f"perf_metrics:{path}"

            # Get existing metrics
            metrics = cache.get(cache_key, {'durations': []})

            # Add new duration
            metrics['durations'].append(duration_ms)

            # Keep last 1000 requests
            if len(metrics['durations']) > 1000:
                metrics['durations'] = metrics['durations'][-1000:]

            # Store for 1 hour
            cache.set(cache_key, metrics, 3600)

        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Failed to record metrics: {e}")
