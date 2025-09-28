"""
Cache monitoring and management dashboard views
Provides comprehensive cache performance metrics and management tools
"""

import json
import logging
from typing import Any, Dict, List, Optional
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.core.cache import cache
from datetime import datetime, timedelta

from apps.core.caching.utils import (
    get_cache_stats,
    clear_cache_pattern,
    warm_cache_pattern,
    CACHE_PATTERNS,
    CACHE_TIMEOUTS
)
from apps.core.caching.invalidation import (
    cache_invalidation_manager,
    get_cache_invalidation_stats
)

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class CacheMonitoringDashboard(LoginRequiredMixin, TemplateView):
    """
    Main cache monitoring dashboard
    Shows cache performance metrics and management tools
    """
    template_name = 'admin/cache_monitoring_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Get cache statistics
            cache_stats = get_cache_stats()
            invalidation_stats = get_cache_invalidation_stats()

            # Get cache patterns overview
            patterns_overview = self._get_patterns_overview()

            context.update({
                'page_title': 'Cache Monitoring Dashboard',
                'cache_stats': cache_stats,
                'invalidation_stats': invalidation_stats,
                'patterns_overview': patterns_overview,
                'cache_patterns': CACHE_PATTERNS,
                'cache_timeouts': CACHE_TIMEOUTS,
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error loading cache monitoring dashboard: {e}")
            context['error'] = f"Error loading dashboard: {str(e)}"

        return context

    def _get_patterns_overview(self) -> Dict[str, Any]:
        """
        Get overview of cache patterns and their estimated usage
        """
        try:
            redis_cache = cache._cache.get_master_client()
            patterns_info = {}

            for pattern_name, pattern in CACHE_PATTERNS.items():
                # Count keys matching each pattern
                search_pattern = f"*{pattern}*"
                keys = redis_cache.keys(search_pattern)

                patterns_info[pattern_name] = {
                    'pattern': pattern,
                    'key_count': len(keys),
                    'timeout': CACHE_TIMEOUTS.get(pattern_name, CACHE_TIMEOUTS['DEFAULT']),
                    'sample_keys': keys[:5] if keys else []  # First 5 keys as samples
                }

            return patterns_info

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Error getting patterns overview: {e}")
            return {}


@method_decorator(staff_member_required, name='dispatch')
class CacheMetricsAPI(LoginRequiredMixin, TemplateView):
    """
    API endpoint for real-time cache metrics
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        try:
            # Get current cache statistics
            cache_stats = get_cache_stats()

            # Add timestamp
            cache_stats['timestamp'] = datetime.now().isoformat()

            # Get hit ratio trend (simplified - in production, store in time series)
            cache_stats['trend'] = self._get_hit_ratio_trend()

            # Get memory usage breakdown
            cache_stats['memory_breakdown'] = self._get_memory_breakdown()

            return JsonResponse({
                'status': 'success',
                'data': cache_stats
            })

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Error getting cache metrics: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    def _get_hit_ratio_trend(self) -> List[Dict[str, Any]]:
        """
        Get hit ratio trend data (simplified implementation)
        In production, this would come from a time-series database
        """
        try:
            redis_cache = cache._cache.get_master_client()
            info = redis_cache.info()

            # Simplified trend - in reality you'd store historical data
            current_ratio = 0
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)

            if hits + misses > 0:
                current_ratio = round(hits / (hits + misses) * 100, 2)

            # Generate mock trend data for demonstration
            trend_data = []
            for i in range(24):  # Last 24 hours
                timestamp = datetime.now() - timedelta(hours=23-i)
                # In production, get actual historical data
                ratio = max(0, current_ratio + (i - 12) * 2)  # Mock variation
                trend_data.append({
                    'timestamp': timestamp.isoformat(),
                    'hit_ratio': min(100, max(0, ratio))
                })

            return trend_data

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Error getting hit ratio trend: {e}")
            return []

    def _get_memory_breakdown(self) -> Dict[str, Any]:
        """
        Get memory usage breakdown by cache pattern
        """
        try:
            redis_cache = cache._cache.get_master_client()
            breakdown = {}

            for pattern_name, pattern in CACHE_PATTERNS.items():
                search_pattern = f"*{pattern}*"
                keys = redis_cache.keys(search_pattern)

                # Estimate memory usage (simplified)
                total_memory = 0
                for key in keys[:100]:  # Sample first 100 keys
                    try:
                        memory_usage = redis_cache.memory_usage(key)
                        if memory_usage:
                            total_memory += memory_usage
                    except:
                        pass

                # Extrapolate for all keys
                if keys:
                    estimated_total = (total_memory / min(len(keys), 100)) * len(keys)
                else:
                    estimated_total = 0

                breakdown[pattern_name] = {
                    'estimated_memory_bytes': estimated_total,
                    'key_count': len(keys),
                    'avg_memory_per_key': total_memory / min(len(keys), 100) if keys else 0
                }

            return breakdown

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Error getting memory breakdown: {e}")
            return {}


@method_decorator(staff_member_required, name='dispatch')
class CacheManagementAPI(LoginRequiredMixin, TemplateView):
    """
    API for cache management operations (clear, warm, etc.)
    """

    def post(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        try:
            action = request.POST.get('action')
            pattern = request.POST.get('pattern', '')

            if action == 'clear_pattern':
                result = self._clear_cache_pattern(pattern)
            elif action == 'clear_all':
                result = self._clear_all_cache()
            elif action == 'warm_pattern':
                result = self._warm_cache_pattern(pattern)
            elif action == 'invalidate_model':
                model_name = request.POST.get('model_name', '')
                result = self._invalidate_model_caches(model_name)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }, status=400)

            logger.info(f"Cache management action '{action}' executed by user {request.user.id}")

            return JsonResponse({
                'status': 'success',
                'action': action,
                'result': result
            })

        except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in cache management action: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    def _clear_cache_pattern(self, pattern: str) -> Dict[str, Any]:
        """Clear caches matching a pattern"""
        if not pattern:
            return {'error': 'Pattern is required'}

        # Security check - only allow predefined patterns
        allowed_patterns = list(CACHE_PATTERNS.values()) + ['tenant:*', 'user:*']
        if pattern not in allowed_patterns:
            return {'error': f'Pattern {pattern} not allowed'}

        return clear_cache_pattern(f"*{pattern}*")

    def _clear_all_cache(self) -> Dict[str, Any]:
        """Clear all application caches (dangerous operation)"""
        try:
            cache.clear()
            return {
                'success': True,
                'message': 'All caches cleared'
            }
        except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            return {'error': str(e)}

    def _warm_cache_pattern(self, pattern: str) -> Dict[str, Any]:
        """Warm caches for a specific pattern"""
        if pattern == 'dropdown':
            # Warm dropdown caches
            return self._warm_dropdown_caches()
        else:
            return {'error': f'Cache warming not implemented for pattern: {pattern}'}

    def _warm_dropdown_caches(self) -> Dict[str, Any]:
        """Warm dropdown caches for common forms"""
        try:
            from apps.core.caching.form_mixins import warm_form_dropdown_caches
            from apps.schedhuler.forms import Schd_I_TourJobForm

            # Warm caches for common forms
            warm_form_dropdown_caches(Schd_I_TourJobForm)

            return {
                'success': True,
                'message': 'Dropdown caches warmed'
            }

        except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            return {'error': str(e)}

    def _invalidate_model_caches(self, model_name: str) -> Dict[str, Any]:
        """Invalidate caches for a specific model"""
        if not model_name:
            return {'error': 'Model name is required'}

        from apps.core.caching.invalidation import invalidate_model_caches
        return invalidate_model_caches(model_name)


@method_decorator(staff_member_required, name='dispatch')
class CacheKeyExplorer(LoginRequiredMixin, TemplateView):
    """
    Tool for exploring cache keys and their contents
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        try:
            pattern = request.GET.get('pattern', '*')
            limit = int(request.GET.get('limit', 50))

            redis_cache = cache._cache.get_master_client()
            keys = redis_cache.keys(pattern)[:limit]

            key_details = []
            for key in keys:
                try:
                    ttl = redis_cache.ttl(key)
                    memory_usage = redis_cache.memory_usage(key)
                    value_type = redis_cache.type(key).decode('utf-8')

                    key_details.append({
                        'key': key.decode('utf-8') if isinstance(key, bytes) else key,
                        'ttl': ttl,
                        'memory_usage': memory_usage,
                        'type': value_type,
                        'expires_in': f"{ttl}s" if ttl > 0 else "No expiry" if ttl == -1 else "Expired"
                    })

                except (ConnectionError, ValueError) as e:
                    logger.error(f"Error getting details for key {key}: {e}")

            return JsonResponse({
                'status': 'success',
                'pattern': pattern,
                'total_keys': len(keys),
                'keys': key_details
            })

        except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error exploring cache keys: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


def cache_health_check(request: HttpRequest) -> JsonResponse:
    """
    Simple cache health check endpoint
    """
    try:
        # Test cache write/read
        test_key = f"health_check_{datetime.now().timestamp()}"
        test_value = "cache_working"

        cache.set(test_key, test_value, 60)
        cached_value = cache.get(test_key)

        if cached_value == test_value:
            cache.delete(test_key)  # Cleanup
            return JsonResponse({
                'status': 'healthy',
                'message': 'Cache is working properly'
            })
        else:
            return JsonResponse({
                'status': 'unhealthy',
                'message': 'Cache read/write test failed'
            }, status=500)

    except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Cache health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'message': f'Cache health check error: {str(e)}'
        }, status=500)