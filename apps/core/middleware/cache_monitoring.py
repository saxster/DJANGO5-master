"""
Cache monitoring middleware for Django application.

Tracks cache hit rates, response times, and cache performance metrics.
Provides periodic logging and performance insights.

Created: 2025-11-07
"""

import logging
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class CacheMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor cache performance and hit rates.
    
    Features:
    - Tracks cache hits and misses
    - Monitors response times
    - Logs periodic cache statistics
    - Detects cache performance issues
    """
    
    # Log stats every N requests
    LOG_INTERVAL = 100
    
    # Slow cache threshold (ms)
    SLOW_CACHE_THRESHOLD = 50
    
    def __init__(self, get_response: Callable):
        """Initialize middleware."""
        super().__init__(get_response)
        self.get_response = get_response
        self.request_count = 0
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and track cache metrics."""
        # Track request start time
        start_time = time.time()
        
        # Get cache stats before request
        cache_stats_before = self._get_cache_stats()
        
        # Process request
        response = self.get_response(request)
        
        # Get cache stats after request
        cache_stats_after = self._get_cache_stats()
        
        # Calculate cache operations during this request
        cache_hits = cache_stats_after['hits'] - cache_stats_before['hits']
        cache_misses = cache_stats_after['misses'] - cache_stats_before['misses']
        
        # Track response time
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Increment request counter
        self.request_count += 1
        
        # Add cache metrics to response headers (for debugging)
        if hasattr(request, 'user') and request.user.is_staff:
            response['X-Cache-Hits'] = str(cache_hits)
            response['X-Cache-Misses'] = str(cache_misses)
            response['X-Response-Time'] = f"{response_time:.2f}ms"
        
        # Log periodic statistics
        if self.request_count % self.LOG_INTERVAL == 0:
            self._log_cache_statistics(cache_stats_after)
        
        # Detect slow cache operations
        if response_time > self.SLOW_CACHE_THRESHOLD and (cache_hits + cache_misses) > 0:
            logger.warning(
                f"Slow cache operation detected: {response_time:.2f}ms "
                f"for {request.path} "
                f"(hits: {cache_hits}, misses: {cache_misses})"
            )
        
        return response
    
    def _get_cache_stats(self) -> dict:
        """
        Get current cache statistics.
        
        Returns:
            Dictionary with hits and misses
        """
        return {
            'hits': cache.get('_cache_stats_hits', 0),
            'misses': cache.get('_cache_stats_misses', 0)
        }
    
    def _log_cache_statistics(self, stats: dict) -> None:
        """
        Log cache statistics.
        
        Args:
            stats: Cache statistics dictionary
        """
        hits = stats['hits']
        misses = stats['misses']
        total = hits + misses
        
        if total > 0:
            hit_rate = (hits / total) * 100
            logger.info(
                f"Cache Statistics - "
                f"Requests: {self.request_count}, "
                f"Hits: {hits}, "
                f"Misses: {misses}, "
                f"Hit Rate: {hit_rate:.2f}%"
            )
            
            # Warn if hit rate is too low
            if hit_rate < 60:
                logger.warning(
                    f"Low cache hit rate detected: {hit_rate:.2f}% "
                    f"(target: >60%)"
                )
