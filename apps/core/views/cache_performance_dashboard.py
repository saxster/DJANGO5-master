"""
Cache Performance Dashboard - Redis monitoring

Author: Claude Code
Date: 2025-10-27
"""

import logging
from datetime import timezone
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)


class CachePerformanceDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Cache performance monitoring dashboard"""
    
    template_name = 'core/monitoring/cache_performance.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get cache statistics
        stats = self._get_cache_stats()
        
        context.update({
            'page_title': 'Cache Performance',
            'last_updated': dj_timezone.now(),
            'cache_stats': stats,
        })
        return context
    
    def _get_cache_stats(self):
        """Get basic cache statistics"""
        try:
            # Try to get Redis info
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
            }
        except (ConnectionError, TypeError, ValueError, KeyError) as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
