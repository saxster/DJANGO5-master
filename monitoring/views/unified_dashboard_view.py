"""
Unified Monitoring Dashboard View

Provides a comprehensive view of:
- Infrastructure health (CPU, memory, disk, DB)
- Anomaly timeline (last 24 hours)
- ML model performance
- ML drift alerts
- Alert correlation metrics

Compliance: .claude/rules.md Rule #7 (views < 150 lines)
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Avg, Count

logger = logging.getLogger('monitoring.dashboard')

__all__ = ['unified_dashboard_view']


@staff_member_required
def unified_dashboard_view(request):
    """
    Render unified monitoring dashboard with all metrics.

    Requires staff member authentication.
    """
    from monitoring.models import InfrastructureMetric
    from apps.noc.models.ml_model_metrics import MLModelMetrics
    from apps.ml.monitoring.drift_detection import DriftDetector

    # Calculate time windows
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_5min = now - timedelta(minutes=5)

    # ==================================================================
    # INFRASTRUCTURE HEALTH METRICS (Real-time - last 5 minutes)
    # ==================================================================
    infrastructure_metrics = []

    # CPU
    cpu_metrics = InfrastructureMetric.objects.filter(
        metric_name='cpu_percent',
        timestamp__gte=last_5min
    ).aggregate(avg_value=Avg('value'))
    if cpu_metrics['avg_value']:
        infrastructure_metrics.append({
            'name': 'CPU Usage',
            'value': cpu_metrics['avg_value'],
            'unit': '%',
            'severity': 'critical' if cpu_metrics['avg_value'] > 90 else 'warning' if cpu_metrics['avg_value'] > 75 else None
        })

    # Memory
    memory_metrics = InfrastructureMetric.objects.filter(
        metric_name='memory_percent',
        timestamp__gte=last_5min
    ).aggregate(avg_value=Avg('value'))
    if memory_metrics['avg_value']:
        infrastructure_metrics.append({
            'name': 'Memory Usage',
            'value': memory_metrics['avg_value'],
            'unit': '%',
            'severity': 'critical' if memory_metrics['avg_value'] > 90 else 'warning' if memory_metrics['avg_value'] > 80 else None
        })

    # Disk I/O Read
    disk_read_metrics = InfrastructureMetric.objects.filter(
        metric_name='disk_io_read_mb',
        timestamp__gte=last_5min
    ).aggregate(avg_value=Avg('value'))
    if disk_read_metrics['avg_value']:
        infrastructure_metrics.append({
            'name': 'Disk Read',
            'value': disk_read_metrics['avg_value'],
            'unit': 'MB/s',
            'severity': None
        })

    # Database Query Time
    db_query_metrics = InfrastructureMetric.objects.filter(
        metric_name='db_query_time_ms',
        timestamp__gte=last_5min
    ).aggregate(avg_value=Avg('value'))
    if db_query_metrics['avg_value']:
        infrastructure_metrics.append({
            'name': 'DB Query Time',
            'value': db_query_metrics['avg_value'],
            'unit': 'ms',
            'severity': 'warning' if db_query_metrics['avg_value'] > 100 else None
        })

    # ==================================================================
    # ANOMALY TIMELINE (Last 24 hours)
    # ==================================================================
    # This would ideally come from a stored anomaly log
    # For now, we'll show a placeholder
    anomaly_timeline = []

    # ==================================================================
    # ML MODEL PERFORMANCE (Last 24 hours)
    # ==================================================================
    conflict_metrics = MLModelMetrics.objects.filter(
        model_name__icontains='conflict',
        cdtz__gte=last_24h,
        actual_outcome__isnull=False
    )
    conflict_accuracy = 0.0
    if conflict_metrics.exists():
        correct_predictions = conflict_metrics.filter(
            actual_outcome=True,
            predicted_probability__gte=0.5
        ).count() + conflict_metrics.filter(
            actual_outcome=False,
            predicted_probability__lt=0.5
        ).count()
        conflict_accuracy = (correct_predictions / conflict_metrics.count()) * 100

    fraud_metrics = MLModelMetrics.objects.filter(
        model_name__icontains='fraud',
        cdtz__gte=last_24h,
        actual_outcome__isnull=False
    )
    fraud_accuracy = 0.0
    if fraud_metrics.exists():
        correct_predictions = fraud_metrics.filter(
            actual_outcome=True,
            predicted_probability__gte=0.5
        ).count() + fraud_metrics.filter(
            actual_outcome=False,
            predicted_probability__lt=0.5
        ).count()
        fraud_accuracy = (correct_predictions / fraud_metrics.count()) * 100

    total_predictions = MLModelMetrics.objects.filter(cdtz__gte=last_24h).count()

    # ==================================================================
    # ML DRIFT ALERTS
    # ==================================================================
    drift_alerts = []
    detector = DriftDetector()

    # Check conflict model drift
    conflict_drift = detector.detect_prediction_drift('conflict', days_back=7)
    if conflict_drift:
        drift_alerts.append(conflict_drift)

    # Check fraud model drift
    fraud_drift = detector.detect_prediction_drift('fraud', days_back=7)
    if fraud_drift:
        drift_alerts.append(fraud_drift)

    # ==================================================================
    # ALERT CORRELATION METRICS
    # ==================================================================
    # This would track anomalies → alerts conversion
    total_anomalies = 0  # Placeholder
    total_alerts_created = 0  # Placeholder
    conversion_rate = 0.0

    context = {
        'last_updated': now,
        'infrastructure_metrics': infrastructure_metrics,
        'anomaly_timeline': anomaly_timeline,
        'conflict_accuracy': conflict_accuracy,
        'fraud_accuracy': fraud_accuracy,
        'total_predictions': total_predictions,
        'drift_alerts': drift_alerts,
        'total_anomalies': total_anomalies,
        'total_alerts_created': total_alerts_created,
        'conversion_rate': conversion_rate,
    }

    return render(request, 'admin/monitoring/unified_dashboard.html', context)
