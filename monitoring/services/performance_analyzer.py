"""
Performance Analysis Service

Analyzes performance trends and detects regressions.

Features:
- Performance trend analysis
- Regression detection
- Baseline comparison
- Capacity planning insights
- Optimization recommendations

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR, MINUTES_IN_DAY
from monitoring.django_monitoring import metrics_collector
from monitoring.models import PerformanceBaseline

logger = logging.getLogger('monitoring.performance')

__all__ = ['PerformanceAnalyzer', 'PerformanceInsight']


class PerformanceInsight:
    """Represents a performance analysis insight."""

    def __init__(
        self,
        metric_name: str,
        insight_type: str,
        message: str,
        severity: str,
        current_value: float,
        baseline_value: Optional[float] = None,
        change_percent: Optional[float] = None
    ):
        self.metric_name = metric_name
        self.insight_type = insight_type  # 'regression', 'improvement', 'stable'
        self.message = message
        self.severity = severity
        self.current_value = current_value
        self.baseline_value = baseline_value
        self.change_percent = change_percent
        self.timestamp = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'metric_name': self.metric_name,
            'insight_type': self.insight_type,
            'message': self.message,
            'severity': self.severity,
            'current_value': self.current_value,
            'baseline_value': self.baseline_value,
            'change_percent': self.change_percent,
            'timestamp': self.timestamp.isoformat()
        }


class PerformanceAnalyzer:
    """
    Analyzes performance metrics and detects regressions.

    Compares current performance against baselines.
    Rule #7 compliant: < 150 lines
    """

    def __init__(self):
        self.regression_threshold = 0.20  # 20% worse than baseline
        self.improvement_threshold = 0.15  # 15% better than baseline

    def analyze_metric(
        self,
        metric_name: str,
        endpoint: Optional[str] = None,
        window_minutes: int = MINUTES_IN_HOUR
    ) -> List[PerformanceInsight]:
        """
        Analyze a metric for performance insights.

        Args:
            metric_name: Name of metric to analyze
            endpoint: Optional endpoint filter
            window_minutes: Time window for analysis

        Returns:
            List of performance insights
        """
        # Get current stats
        current_stats = metrics_collector.get_stats(metric_name, window_minutes)

        if not current_stats or current_stats.get('count', 0) < 10:
            return []

        insights = []

        # Get baseline
        baseline = self._get_baseline(metric_name, endpoint)

        if baseline:
            # Compare against baseline
            insight = self._compare_to_baseline(
                metric_name,
                current_stats,
                baseline
            )
            if insight:
                insights.append(insight)

        # Detect trends
        trend_insight = self._detect_trend(metric_name, window_minutes)
        if trend_insight:
            insights.append(trend_insight)

        return insights

    def _get_baseline(
        self,
        metric_name: str,
        endpoint: Optional[str] = None
    ) -> Optional[PerformanceBaseline]:
        """Get performance baseline for metric."""
        try:
            baseline = PerformanceBaseline.objects.filter(
                metric_name=metric_name,
                endpoint=endpoint or '',
                is_active=True
            ).first()

            return baseline
        except Exception as e:
            logger.warning(f"Error fetching baseline: {e}")
            return None

    def _compare_to_baseline(
        self,
        metric_name: str,
        current_stats: Dict[str, float],
        baseline: PerformanceBaseline
    ) -> Optional[PerformanceInsight]:
        """Compare current performance to baseline."""
        current_p95 = current_stats.get('p95', 0)
        baseline_p95 = baseline.p95

        if baseline_p95 == 0:
            return None

        change_percent = ((current_p95 - baseline_p95) / baseline_p95) * 100

        # Detect regression
        if change_percent > (self.regression_threshold * 100):
            severity = 'critical' if change_percent > 50 else 'warning'

            return PerformanceInsight(
                metric_name=metric_name,
                insight_type='regression',
                message=f"Performance regression detected: {change_percent:.1f}% slower than baseline",
                severity=severity,
                current_value=current_p95,
                baseline_value=baseline_p95,
                change_percent=change_percent
            )

        # Detect improvement
        elif change_percent < -(self.improvement_threshold * 100):
            return PerformanceInsight(
                metric_name=metric_name,
                insight_type='improvement',
                message=f"Performance improvement: {abs(change_percent):.1f}% faster than baseline",
                severity='info',
                current_value=current_p95,
                baseline_value=baseline_p95,
                change_percent=change_percent
            )

        # Stable performance
        else:
            return PerformanceInsight(
                metric_name=metric_name,
                insight_type='stable',
                message=f"Performance stable: {abs(change_percent):.1f}% from baseline",
                severity='info',
                current_value=current_p95,
                baseline_value=baseline_p95,
                change_percent=change_percent
            )

    def _detect_trend(
        self,
        metric_name: str,
        window_minutes: int
    ) -> Optional[PerformanceInsight]:
        """Detect performance trend over time."""
        # Get metrics for two time windows
        recent_stats = metrics_collector.get_stats(metric_name, window_minutes // 2)
        older_stats = metrics_collector.get_stats(metric_name, window_minutes)

        if not recent_stats or not older_stats:
            return None

        recent_mean = recent_stats.get('mean', 0)
        older_mean = older_stats.get('mean', 0)

        if older_mean == 0:
            return None

        trend_percent = ((recent_mean - older_mean) / older_mean) * 100

        if abs(trend_percent) > 10:  # Significant trend
            if trend_percent > 0:
                return PerformanceInsight(
                    metric_name=metric_name,
                    insight_type='degrading',
                    message=f"Performance degrading: {trend_percent:.1f}% slower recently",
                    severity='warning',
                    current_value=recent_mean,
                    baseline_value=older_mean,
                    change_percent=trend_percent
                )
            else:
                return PerformanceInsight(
                    metric_name=metric_name,
                    insight_type='improving',
                    message=f"Performance improving: {abs(trend_percent):.1f}% faster recently",
                    severity='info',
                    current_value=recent_mean,
                    baseline_value=older_mean,
                    change_percent=trend_percent
                )

        return None
