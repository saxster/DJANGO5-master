"""
TTL Health Monitoring Service for cache optimization.

Tracks cache expiration patterns and detects anomalies.
Complies with .claude/rules.md - file size < 200 lines.
"""

import logging
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = [
    'TTLMonitor',
    'get_ttl_health_report',
    'detect_ttl_anomalies',
]


class TTLMonitor:
    """
    Monitors cache TTL effectiveness and health.

    Features:
    - Track hit ratio per cache pattern
    - Detect expiration anomalies
    - Recommend optimal TTL values
    """

    METRICS_KEY_PREFIX = 'ttl:metrics'
    HEALTH_THRESHOLD = 0.80
    ANOMALY_THRESHOLD = 0.30

    def __init__(self):
        self.redis_cache = self._get_redis_client()

    def _get_redis_client(self):
        """Get Redis client with error handling"""
        try:
            return cache._cache.get_master_client()
        except (AttributeError, ConnectionError) as e:
            logger.error(f"Could not connect to Redis: {e}")
            return None

    def record_cache_access(self, pattern: str, hit: bool, ttl_remaining: Optional[int] = None):
        """Record cache access for analytics"""
        try:
            metrics_key = f"{self.METRICS_KEY_PREFIX}:{pattern}:daily"
            metrics = cache.get(metrics_key, {'hits': 0, 'misses': 0, 'total_accesses': 0, 'avg_ttl_at_hit': 0, 'ttl_samples': []})
            metrics['total_accesses'] += 1
            if hit:
                metrics['hits'] += 1
                if ttl_remaining is not None:
                    metrics['ttl_samples'].append(ttl_remaining)
                    if len(metrics['ttl_samples']) > 100:
                        metrics['ttl_samples'] = metrics['ttl_samples'][-100:]
                    metrics['avg_ttl_at_hit'] = sum(metrics['ttl_samples']) / len(metrics['ttl_samples'])
            else:
                metrics['misses'] += 1
            cache.set(metrics_key, metrics, timeout=86400)
        except (AttributeError, TypeError) as e:
            logger.warning(f"Error recording cache access: {e}")

    def get_pattern_health(self, pattern: str) -> Dict[str, Any]:
        """Get health metrics for a cache pattern"""
        try:
            metrics_key = f"{self.METRICS_KEY_PREFIX}:{pattern}:daily"
            metrics = cache.get(metrics_key, {})
            if not metrics or metrics.get('total_accesses', 0) == 0:
                return {'pattern': pattern, 'health_status': 'insufficient_data', 'hit_ratio': 0.0, 'recommendation': 'Need more data'}
            hit_ratio = metrics['hits'] / metrics['total_accesses']
            avg_ttl = metrics.get('avg_ttl_at_hit', 0)
            health_status = 'healthy' if hit_ratio >= self.HEALTH_THRESHOLD else 'unhealthy'
            return {
                'pattern': pattern,
                'health_status': health_status,
                'hit_ratio': round(hit_ratio, 4),
                'total_hits': metrics['hits'],
                'total_misses': metrics['misses'],
                'avg_ttl_remaining_at_hit': round(avg_ttl, 2),
                'recommendation': self._generate_recommendation(hit_ratio, avg_ttl, pattern)
            }
        except (KeyError, ZeroDivisionError) as e:
            logger.error(f"Error getting pattern health for {pattern}: {e}")
            return {'pattern': pattern, 'health_status': 'error', 'error': str(e)}

    def _generate_recommendation(self, hit_ratio: float, avg_ttl: float, pattern: str) -> str:
        """Generate TTL optimization recommendation"""
        from apps.core.caching.ttl_optimizer import generate_ttl_recommendation
        return generate_ttl_recommendation(hit_ratio, avg_ttl, pattern)

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect cache pattern anomalies"""
        try:
            from apps.core.caching.utils import CACHE_PATTERNS
            anomalies = []
            for pattern_name, pattern in CACHE_PATTERNS.items():
                health = self.get_pattern_health(pattern)
                if health['health_status'] == 'unhealthy':
                    anomalies.append({'pattern': pattern, 'pattern_name': pattern_name, 'severity': 'high' if health['hit_ratio'] < 0.50 else 'medium', 'hit_ratio': health['hit_ratio'], 'recommendation': health['recommendation'], 'detected_at': timezone.now().isoformat()})
            return anomalies
        except ImportError as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []


ttl_monitor = TTLMonitor()


def get_ttl_health_report() -> Dict[str, Any]:
    """Get comprehensive TTL health report for all cache patterns"""
    try:
        from apps.core.caching.utils import CACHE_PATTERNS
        report = {'generated_at': timezone.now().isoformat(), 'patterns': {}, 'overall_health': 'healthy', 'total_patterns_analyzed': 0, 'unhealthy_patterns': 0}
        for pattern_name, pattern in CACHE_PATTERNS.items():
            health = ttl_monitor.get_pattern_health(pattern)
            report['patterns'][pattern_name] = health
            report['total_patterns_analyzed'] += 1
            if health.get('health_status') == 'unhealthy':
                report['unhealthy_patterns'] += 1
        if report['unhealthy_patterns'] > 0:
            report['overall_health'] = 'needs_attention'
        return report
    except ImportError as e:
        logger.error(f"Error generating TTL health report: {e}")
        return {'error': str(e)}


def detect_ttl_anomalies() -> List[Dict[str, Any]]:
    """Detect TTL configuration anomalies"""
    return ttl_monitor.detect_anomalies()


