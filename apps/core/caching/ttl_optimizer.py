"""
TTL optimization and recommendation engine.
Extracted from ttl_monitor.py for .claude/rules.md compliance.
"""

import logging
from typing import Dict, Any, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

__all__ = ['recommend_ttl_adjustments', 'generate_ttl_recommendation']


def generate_ttl_recommendation(hit_ratio: float, avg_ttl: float, pattern: str) -> str:
    """Generate TTL optimization recommendation"""
    from apps.core.caching.utils import CACHE_TIMEOUTS

    current_ttl = CACHE_TIMEOUTS.get(pattern.upper().replace(':', '_'), CACHE_TIMEOUTS['DEFAULT'])

    if hit_ratio < 0.60:
        return f'Increase TTL from {current_ttl}s (hit ratio too low)'
    elif hit_ratio > 0.95 and avg_ttl > current_ttl * 0.8:
        return f'Consider increasing TTL from {current_ttl}s (high hit ratio, long remaining TTL)'
    elif hit_ratio > 0.90 and avg_ttl < current_ttl * 0.2:
        return f'Consider decreasing TTL from {current_ttl}s (hits occur near expiration)'
    return 'TTL is optimally configured'


def recommend_ttl_adjustments() -> List[Dict[str, Any]]:
    """
    Generate TTL adjustment recommendations.

    Returns:
        List of recommended adjustments
    """
    try:
        from apps.core.caching.ttl_monitor import get_ttl_health_report

        report = get_ttl_health_report()
        recommendations = []

        for pattern_name, health in report.get('patterns', {}).items():
            rec = health.get('recommendation', '')
            if rec and rec != 'TTL is optimally configured':
                recommendations.append({
                    'pattern': pattern_name,
                    'current_hit_ratio': health.get('hit_ratio', 0),
                    'recommendation': rec,
                    'priority': 'high' if health.get('hit_ratio', 1.0) < 0.60 else 'medium'
                })

        return sorted(recommendations, key=lambda x: x['current_hit_ratio'])

    except (KeyError, TypeError, ImportError) as e:
        logger.error(f"Error generating TTL recommendations: {e}")
        return []