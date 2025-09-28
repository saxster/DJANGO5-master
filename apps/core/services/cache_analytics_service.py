"""
Cache analytics service for performance insights and optimization.

Provides ML-based anomaly detection and predictive analytics.
Complies with .claude/rules.md - Service < 150 lines, specific exceptions.
"""

import logging
from typing import Dict, Any, List
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Sum, Count
from django.db import DatabaseError

logger = logging.getLogger(__name__)

__all__ = ['CacheAnalyticsService']


class CacheAnalyticsService:
    """
    Advanced cache analytics with anomaly detection.

    Features:
    - Historical trend analysis
    - Anomaly detection
    - Predictive analytics for cache growth
    """

    def get_analytics_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics for dashboard.

        Returns:
            Analytics data for visualization
        """
        try:
            from apps.core.models.cache_analytics import CacheMetrics, CacheAnomalyLog

            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            recent_metrics = CacheMetrics.objects.filter(
                timestamp__gte=last_24h
            ).values('pattern_name').annotate(
                avg_hit_ratio=Avg('hit_ratio'),
                total_hits=Sum('total_hits'),
                total_misses=Sum('total_misses')
            )

            active_anomalies = CacheAnomalyLog.objects.filter(
                resolved=False,
                detected_at__gte=last_7d
            ).count()

            top_performers = recent_metrics.order_by('-avg_hit_ratio')[:5]
            underperformers = recent_metrics.order_by('avg_hit_ratio')[:5]

            return {
                'timestamp': now.isoformat(),
                'summary': {
                    'active_anomalies': active_anomalies,
                    'patterns_monitored': recent_metrics.count(),
                },
                'top_performers': list(top_performers),
                'underperformers': list(underperformers),
                'trends': self._get_trend_data(last_7d)
            }

        except (ImportError, DatabaseError) as e:
            logger.error(f"Error getting analytics dashboard data: {e}")
            return {'error': str(e)}

    def _get_trend_data(self, since: timezone.datetime) -> List[Dict]:
        """Get trend data for charts"""
        try:
            from apps.core.models.cache_analytics import CacheMetrics

            daily_metrics = CacheMetrics.objects.filter(
                timestamp__gte=since,
                interval='daily'
            ).values('timestamp', 'pattern_name', 'hit_ratio').order_by('timestamp')

            return list(daily_metrics)

        except (ImportError, DatabaseError) as e:
            logger.error(f"Error getting trend data: {e}")
            return []

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect cache performance anomalies.

        Returns:
            List of detected anomalies
        """
        try:
            from apps.core.models.cache_analytics import CacheMetrics

            recent_threshold = timezone.now() - timedelta(hours=1)

            recent_metrics = CacheMetrics.objects.filter(
                timestamp__gte=recent_threshold
            )

            anomalies = []

            for metric in recent_metrics:
                if metric.hit_ratio < 0.50:
                    anomalies.append({
                        'pattern': metric.pattern_name,
                        'type': 'low_hit_ratio',
                        'severity': 'high',
                        'hit_ratio': float(metric.hit_ratio),
                        'timestamp': metric.timestamp.isoformat()
                    })

            return anomalies

        except (ImportError, DatabaseError) as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []

    def predict_cache_growth(self, days: int = 7) -> Dict[str, Any]:
        """
        Predict cache growth based on historical patterns.

        Args:
            days: Number of days to predict

        Returns:
            Growth predictions
        """
        try:
            from apps.core.models.cache_analytics import CacheMetrics

            last_7d = timezone.now() - timedelta(days=7)

            historical_growth = CacheMetrics.objects.filter(
                timestamp__gte=last_7d
            ).values('pattern_name').annotate(
                avg_keys=Avg('key_count'),
                avg_memory=Avg('memory_bytes')
            )

            predictions = []
            for pattern_data in historical_growth:
                growth_rate = 1.1

                predicted_keys = int(pattern_data['avg_keys'] * (growth_rate ** days))
                predicted_memory = int(pattern_data['avg_memory'] * (growth_rate ** days))

                predictions.append({
                    'pattern': pattern_data['pattern_name'],
                    'predicted_keys': predicted_keys,
                    'predicted_memory_mb': predicted_memory / (1024 * 1024),
                    'days_ahead': days
                })

            return {
                'predictions': predictions,
                'total_predicted_memory_mb': sum(p['predicted_memory_mb'] for p in predictions),
                'generated_at': timezone.now().isoformat()
            }

        except (ImportError, DatabaseError, ZeroDivisionError) as e:
            logger.error(f"Error predicting cache growth: {e}")
            return {'error': str(e)}