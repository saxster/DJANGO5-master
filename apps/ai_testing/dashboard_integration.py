"""
AI Testing Dashboard Integration
Helper functions to provide AI insights for Stream Testbench dashboard
"""

from django.utils import timezone
from django.db.models import Count, Avg
from datetime import timedelta

from .models.test_coverage_gaps import TestCoverageGap
from .models.regression_predictions import RegressionPrediction
from .models.adaptive_thresholds import AdaptiveThreshold
from apps.streamlab.models import TestRun


def get_ai_insights_summary():
    """
    Get comprehensive AI insights summary for dashboard display
    Returns a dictionary with all AI testing insights
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # Coverage Gaps Analysis
    coverage_gaps = _get_coverage_gaps_summary()

    # Regression Risk Analysis
    regression_risk = _get_regression_risk_summary()

    # Adaptive Thresholds Status
    threshold_status = _get_threshold_status_summary()

    # Pattern Analysis Results
    pattern_insights = _get_pattern_analysis_summary()

    # Overall AI Health Score (0-100)
    health_score = _calculate_ai_health_score(coverage_gaps, regression_risk, threshold_status)

    return {
        'health_score': health_score,
        'coverage_gaps': coverage_gaps,
        'regression_risk': regression_risk,
        'threshold_status': threshold_status,
        'pattern_insights': pattern_insights,
        'last_updated': now,
    }


def _get_coverage_gaps_summary():
    """Get coverage gaps summary with priority breakdown"""
    total_gaps = TestCoverageGap.objects.filter(status='identified').count()

    # Priority breakdown
    priority_counts = TestCoverageGap.objects.filter(
        status='identified'
    ).values('priority').annotate(count=Count('id'))

    priority_breakdown = {item['priority']: item['count'] for item in priority_counts}

    # Recent gaps (last 7 days)
    recent_gaps = TestCoverageGap.objects.filter(
        status='identified',
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()

    # High priority gaps needing immediate attention
    critical_gaps = TestCoverageGap.objects.filter(
        status='identified',
        priority__in=['critical', 'high']
    ).count()

    return {
        'total': total_gaps,
        'critical_count': critical_gaps,
        'recent_7d': recent_gaps,
        'priority_breakdown': priority_breakdown,
        'alert_level': _get_coverage_alert_level(total_gaps, critical_gaps)
    }


def _get_regression_risk_summary():
    """Get latest regression prediction summary"""
    latest_prediction = RegressionPrediction.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at').first()

    if not latest_prediction:
        return {
            'risk_score': 0,
            'confidence': 0,
            'alert_level': 'info',
            'prediction_age': None,
            'risk_factors': []
        }

    # Extract key risk factors from risk_factors JSON field
    risk_factors = latest_prediction.risk_factors.get('top_factors', [])[:3] if latest_prediction.risk_factors else []

    return {
        'risk_score': round(latest_prediction.risk_score * 100, 1),
        'confidence': round(latest_prediction.confidence * 100, 1),
        'alert_level': _get_regression_alert_level(latest_prediction.risk_score),
        'prediction_age': (timezone.now() - latest_prediction.created_at).total_seconds() / 3600,  # hours
        'risk_factors': risk_factors
    }


def _get_threshold_status_summary():
    """Get adaptive threshold status summary"""
    total_thresholds = AdaptiveThreshold.objects.count()

    # Recent threshold updates (last 24 hours)
    recent_updates = AdaptiveThreshold.objects.filter(
        updated_at__gte=timezone.now() - timedelta(hours=24)
    ).count()

    # Thresholds that haven't been updated in a while (over 7 days)
    stale_thresholds = AdaptiveThreshold.objects.filter(
        updated_at__lt=timezone.now() - timedelta(days=7)
    ).count()

    # Average threshold performance
    avg_threshold_performance = AdaptiveThreshold.objects.aggregate(
        avg_accuracy=Avg('accuracy'),
        avg_precision=Avg('precision')
    )

    return {
        'total_thresholds': total_thresholds,
        'recent_updates': recent_updates,
        'stale_count': stale_thresholds,
        'avg_accuracy': round(avg_threshold_performance.get('avg_accuracy', 0) * 100, 1),
        'avg_precision': round(avg_threshold_performance.get('avg_precision', 0) * 100, 1),
        'alert_level': _get_threshold_alert_level(stale_thresholds, total_thresholds)
    }


def _get_pattern_analysis_summary():
    """Get pattern analysis insights from recent test runs"""
    recent_runs = TestRun.objects.filter(
        started_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-started_at')

    if not recent_runs.exists():
        return {
            'patterns_detected': 0,
            'anomaly_clusters': 0,
            'trend_direction': 'stable',
            'confidence': 0
        }

    # Analyze test run patterns
    total_runs = recent_runs.count()
    failed_runs = recent_runs.filter(status='failed').count()
    failure_rate = (failed_runs / total_runs * 100) if total_runs > 0 else 0

    # Determine trend direction based on recent performance
    recent_half = recent_runs[:total_runs//2] if total_runs > 4 else recent_runs
    older_half = recent_runs[total_runs//2:] if total_runs > 4 else recent_runs

    recent_failure_rate = (recent_half.filter(status='failed').count() / len(recent_half) * 100) if recent_half else 0
    older_failure_rate = (older_half.filter(status='failed').count() / len(older_half) * 100) if older_half else 0

    if recent_failure_rate > older_failure_rate + 5:
        trend_direction = 'degrading'
    elif recent_failure_rate < older_failure_rate - 5:
        trend_direction = 'improving'
    else:
        trend_direction = 'stable'

    return {
        'patterns_detected': min(total_runs // 2, 10),  # Simulated pattern count
        'anomaly_clusters': max(0, failed_runs - 1),
        'trend_direction': trend_direction,
        'confidence': min(95, total_runs * 5),  # Confidence based on data volume
        'failure_rate': round(failure_rate, 1)
    }


def _calculate_ai_health_score(coverage_gaps, regression_risk, threshold_status):
    """Calculate overall AI system health score (0-100)"""
    score = 100

    # Deduct for coverage gaps
    if coverage_gaps['critical_count'] > 0:
        score -= min(30, coverage_gaps['critical_count'] * 5)

    if coverage_gaps['total'] > 10:
        score -= min(20, (coverage_gaps['total'] - 10) * 2)

    # Deduct for regression risk
    if regression_risk['risk_score'] > 70:
        score -= min(25, (regression_risk['risk_score'] - 70) * 0.5)

    # Deduct for stale thresholds
    if threshold_status['stale_count'] > 0:
        total_thresholds = threshold_status['total_thresholds']
        if total_thresholds > 0:
            stale_percentage = (threshold_status['stale_count'] / total_thresholds) * 100
            score -= min(15, stale_percentage * 0.3)

    return max(0, min(100, round(score)))


def _get_coverage_alert_level(total_gaps, critical_gaps):
    """Determine alert level for coverage gaps"""
    if critical_gaps > 5:
        return 'danger'
    elif critical_gaps > 0 or total_gaps > 10:
        return 'warning'
    elif total_gaps > 0:
        return 'info'
    else:
        return 'success'


def _get_regression_alert_level(risk_score):
    """Determine alert level for regression risk"""
    if risk_score > 0.8:
        return 'danger'
    elif risk_score > 0.6:
        return 'warning'
    elif risk_score > 0.3:
        return 'info'
    else:
        return 'success'


def _get_threshold_alert_level(stale_count, total_count):
    """Determine alert level for threshold status"""
    if total_count == 0:
        return 'info'

    stale_percentage = (stale_count / total_count) * 100

    if stale_percentage > 50:
        return 'danger'
    elif stale_percentage > 25:
        return 'warning'
    elif stale_percentage > 10:
        return 'info'
    else:
        return 'success'


def get_ai_insights_for_htmx():
    """
    Lightweight version of AI insights for HTMX partial updates
    Returns only essential data for frequent updates
    """
    insights = get_ai_insights_summary()

    return {
        'health_score': insights['health_score'],
        'critical_gaps': insights['coverage_gaps']['critical_count'],
        'regression_risk': insights['regression_risk']['risk_score'],
        'alert_level': _get_overall_alert_level(insights),
        'last_updated': insights['last_updated']
    }


def _get_overall_alert_level(insights):
    """Determine overall system alert level"""
    alert_levels = [
        insights['coverage_gaps']['alert_level'],
        insights['regression_risk']['alert_level'],
        insights['threshold_status']['alert_level']
    ]

    if 'danger' in alert_levels:
        return 'danger'
    elif 'warning' in alert_levels:
        return 'warning'
    elif 'info' in alert_levels:
        return 'info'
    else:
        return 'success'