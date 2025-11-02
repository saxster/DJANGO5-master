# Phase 4 Quick Reference Guide

## Command Cheat Sheet

### Deployment
```bash
# 1. Apply migrations
python manage.py migrate monitoring

# 2. Train drift detector
python manage.py train_drift_detector --days=30

# 3. Start workers
./scripts/celery_workers.sh start

# 4. Start beat scheduler
celery -A intelliwiz_config beat --loglevel=info
```

### Dashboard Access
```
URL: http://your-domain/admin/monitoring/unified-dashboard/
Auth: Staff users only
```

### Manual Task Triggers
```bash
# Collect metrics now
celery -A intelliwiz_config call monitoring.collect_infrastructure_metrics

# Detect anomalies now
celery -A intelliwiz_config call monitoring.detect_infrastructure_anomalies

# Auto-tune thresholds now
celery -A intelliwiz_config call monitoring.auto_tune_anomaly_thresholds
```

### Monitoring
```bash
# Check task status
celery -A intelliwiz_config inspect active

# View task history
celery -A intelliwiz_config inspect stats

# Monitor queues
celery -A intelliwiz_config inspect active_queues
```

### Database Queries
```sql
-- Recent metrics
SELECT metric_name, value, timestamp
FROM monitoring_infrastructure_metric
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC LIMIT 20;

-- Anomaly feedback status
SELECT * FROM monitoring_anomaly_feedback;

-- Metric counts by type
SELECT metric_name, COUNT(*)
FROM monitoring_infrastructure_metric
GROUP BY metric_name;
```

### Troubleshooting
```bash
# No metrics collected?
grep "collect_infrastructure_metrics" /var/log/celery/*.log

# Anomaly detection not running?
grep "detect_infrastructure_anomalies" /var/log/celery/*.log

# Check worker processes
ps aux | grep celery | grep monitoring
```

## Task Schedule Summary

| Task | Frequency | Time | Queue |
|------|-----------|------|-------|
| Collect Metrics | Every 60s | Continuous | monitoring |
| Detect Anomalies | Every 5 min | :01, :06, :11, etc. | monitoring |
| Cleanup Metrics | Daily | 2:00 AM UTC | maintenance |
| Auto-Tune Thresholds | Weekly | Sunday 3:00 AM | maintenance |

## Severity Mapping

| Anomaly Severity | Alert Severity | Trigger |
|------------------|----------------|---------|
| critical | CRITICAL | Z-score > 4 or spike > 3x |
| high | CRITICAL | Z-score 3-4 or spike 2-3x |
| medium | WARNING | Z-score 2-3 or spike 1.5-2x |
| low | INFO | Minor deviation |

## Metrics Collected

### System (via psutil)
- `cpu_percent` - CPU usage %
- `memory_percent` - Memory usage %
- `disk_io_read_mb` - Disk read MB/s
- `disk_io_write_mb` - Disk write MB/s

### Database (via Django)
- `db_connections_active` - Active connections
- `db_query_time_ms` - Avg query time (ms)

### Application (via Redis)
- `celery_queue_depth` - Task queue depth
- `request_latency_p95` - 95th percentile latency
- `error_rate` - Errors per second

## False Positive Handling

### Mark as False Positive
```python
from monitoring.services.anomaly_feedback_service import AnomalyFeedbackService

AnomalyFeedbackService.mark_as_false_positive(
    metric_name='cpu_percent',
    reason='Deployment spike - expected'
)
```

### Check Current Adjustment
```python
adjustment = AnomalyFeedbackService.get_threshold_adjustment('cpu_percent')
print(f"Current adjustment: {adjustment:+.2%}")
# Example output: +10% (threshold increased by 10%)
```

## File Locations

### Key Files
- Models: `/monitoring/models.py`
- Collector: `/monitoring/collectors/infrastructure_collector.py`
- Anomaly Service: `/monitoring/services/anomaly_alert_service.py`
- Feedback Service: `/monitoring/services/anomaly_feedback_service.py`
- Drift Detector: `/apps/ml/monitoring/drift_detection.py`
- Tasks: `/monitoring/tasks.py`
- Dashboard View: `/monitoring/views/unified_dashboard_view.py`
- Dashboard Template: `/frontend/templates/admin/monitoring/unified_dashboard.html`

### Configuration
- Celery Beat: `/intelliwiz_config/celery.py`
- Queue Config: `/apps/core/tasks/celery_settings.py`
- URLs: `/monitoring/urls.py`

## Support

For issues or questions:
1. Check `/PHASE_4_ANOMALY_DETECTION_IMPLEMENTATION_COMPLETE.md`
2. Review logs: `/var/log/celery/` and `/var/log/intelliwiz/`
3. Contact DevOps team
