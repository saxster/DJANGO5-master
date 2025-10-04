# Monitoring Implementation Guide

**Comprehensive enterprise-grade monitoring system for Django 5 application**

## Overview

This monitoring system provides:
- **PII Redaction**: Automatic sanitization of sensitive data in logs, SQL queries, URLs, and dashboards
- **Correlation ID Tracking**: End-to-end request tracing across all services
- **GraphQL Security Monitoring**: Query complexity/depth tracking, DoS attack detection
- **WebSocket Connection Monitoring**: Throttling metrics, connection duration, message throughput
- **Anomaly Detection**: Statistical algorithms (Z-score, IQR, spike detection)
- **Alert Aggregation**: Smart deduplication, storm prevention, grouping
- **Performance Analysis**: Regression detection, baseline comparison, trending
- **Security Intelligence**: Attack pattern detection, IP reputation, threat scoring

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Request → Middleware → Metrics Collection → PII Redaction     │
│                ↓              ↓                    ↓            │
│         Correlation ID   Services Layer    Sanitization        │
│                ↓              ↓                    ↓            │
│         Anomaly Detect   Alert Aggreg      Security Intel      │
│                ↓              ↓                    ↓            │
│         Performance     Background Tasks    Prometheus          │
│           Analysis                                ↓             │
│                                            Grafana Dashboards   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# Already in requirements/base.txt
pip install -r requirements/base.txt
```

### 2. Configure Settings

Add to `settings.py`:

```python
# Monitoring Configuration
MONITORING_ENABLED = True
MONITORING_PII_REDACTION = True
MONITORING_CORRELATION_TRACKING = True

# Prometheus Configuration
PROMETHEUS_METRICS_EXPORT_ENABLED = True
PROMETHEUS_METRICS_PATH = '/metrics'
```

### 3. Enable Middleware

Ensure monitoring middleware is enabled (already in `settings.py`):

```python
MIDDLEWARE = [
    # ... other middleware
    'monitoring.middleware.pii_sanitization.PIISanitizationMiddleware',
    'apps.core.middleware.graphql_complexity_validation.GraphQLComplexityValidationMiddleware',
    'apps.core.middleware.websocket_throttling.ThrottlingMiddleware',
]
```

### 4. Configure Celery Tasks

Add monitoring tasks to Celery beat schedule:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'detect-anomalies': {
        'task': 'monitoring.detect_anomalies',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'analyze-performance': {
        'task': 'monitoring.analyze_performance',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'scan-security-threats': {
        'task': 'monitoring.scan_security_threats',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'update-performance-baselines': {
        'task': 'monitoring.update_performance_baselines',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
    'cleanup-old-metrics': {
        'task': 'monitoring.cleanup_old_metrics',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

### 5. Configure Prometheus

Update `config/prometheus/prometheus.yml` (already done):

```yaml
rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'django_monitoring'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/monitoring/metrics/'
    scrape_interval: 15s
```

### 6. Import Grafana Dashboards

```bash
# Import dashboards into Grafana
# 1. Open Grafana UI
# 2. Navigate to Dashboards → Import
# 3. Upload each JSON file from config/grafana/dashboards/
```

## Component Details

### PII Redaction Service

**Location**: `monitoring/services/pii_redaction_service.py`

**Purpose**: Sanitize sensitive data in all monitoring outputs

**Usage**:

```python
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

# Sanitize SQL query
safe_sql = MonitoringPIIRedactionService.sanitize_sql_query(
    "SELECT * FROM users WHERE email = 'john@example.com'"
)
# Output: "SELECT * FROM users WHERE email = '[EMAIL]'"

# Sanitize URL
safe_url = MonitoringPIIRedactionService.sanitize_request_path(
    "/api/users/12345/profile"
)
# Output: "/api/users/[ID]/profile"

# Sanitize metric tags
safe_tags = MonitoringPIIRedactionService.sanitize_metric_tags({
    'user_email': 'test@example.com',
    'client_ip': '192.168.1.100'
})
# Output: {'user_email': '[EMAIL]', 'client_ip': '[IP]'}
```

### Correlation ID Tracking

**Location**: `monitoring/services/correlation_tracking.py`

**Purpose**: Track requests end-to-end across all services

**Usage**:

```python
from monitoring.services.correlation_tracking import CorrelationTrackingService

# Create correlation context
correlation_id = CorrelationTrackingService.generate_correlation_id()
context = CorrelationTrackingService.create_context(
    correlation_id=correlation_id,
    metadata={'source': 'api_gateway'}
)

# Add events to context
context.add_event('query_validation', {'status': 'accepted'})
context.add_event('database_query', {'duration_ms': 150})

# Retrieve context later
context = CorrelationTrackingService.get_context(correlation_id)
```

### GraphQL Metrics

**Location**: `monitoring/services/graphql_metrics_collector.py`

**Metrics Collected**:
- Query validation (accepted/rejected)
- Query complexity distribution
- Query depth distribution
- Field count statistics
- Validation time percentiles
- Rejection reasons breakdown

**Usage**:

```python
from monitoring.services.graphql_metrics_collector import graphql_metrics

# Record query validation
graphql_metrics.record_query_validation(
    passed=False,
    complexity=1200,
    depth=12,
    field_count=50,
    validation_time_ms=15.2,
    rejection_reason='complexity_exceeded',
    correlation_id=correlation_id
)

# Get statistics
stats = graphql_metrics.get_graphql_stats(window_minutes=60)
```

### WebSocket Metrics

**Location**: `monitoring/services/websocket_metrics_collector.py`

**Metrics Collected**:
- Connection attempts (accepted/rejected)
- Active connections by user type
- Connection duration statistics
- Message throughput (sent/received)
- Throttle hits and rejection reasons

**Usage**:

```python
from monitoring.services.websocket_metrics_collector import websocket_metrics

# Record connection attempt
websocket_metrics.record_connection_attempt(
    accepted=False,
    user_type='anonymous',
    client_ip='192.168.1.100',
    rejection_reason='rate_limit_exceeded',
    correlation_id=correlation_id
)

# Record connection lifecycle
websocket_metrics.record_connection_opened(
    user_type='authenticated',
    user_id=123
)

websocket_metrics.record_connection_closed(
    user_type='authenticated',
    duration_seconds=120.5
)

# Get statistics
stats = websocket_metrics.get_websocket_stats(window_minutes=30)
```

### Anomaly Detection

**Location**: `monitoring/services/anomaly_detector.py`

**Detection Methods**:
1. **Z-score**: Detects values outside 3 standard deviations
2. **IQR (Interquartile Range)**: Detects outliers beyond 1.5× IQR
3. **Spike Detection**: Detects sudden 2x increases/decreases

**Usage**:

```python
from monitoring.services.anomaly_detector import anomaly_detector

# Detect anomalies in a metric
anomalies = anomaly_detector.detect_anomalies(
    metric_name='request_duration',
    window_minutes=60
)

# Process anomalies
for anomaly in anomalies:
    if anomaly.severity in ('high', 'critical'):
        # Create alert
        send_alert(anomaly.to_dict())
```

### Alert Aggregation

**Location**: `monitoring/services/alert_aggregator.py`

**Features**:
- 5-minute deduplication window
- Storm prevention (10 alerts/minute threshold)
- Alert grouping by source and severity
- Summary alert generation

**Usage**:

```python
from monitoring.services.alert_aggregator import alert_aggregator, Alert

# Create and process alert
alert = Alert(
    title="Performance Regression Detected",
    message="P95 latency 50% above baseline",
    severity='warning',
    source='performance_analysis',
    metadata={'metric': 'request_duration', 'regression': 0.50}
)

# Process alert (with automatic deduplication)
should_send = alert_aggregator.process_alert(alert)

if should_send:
    # Send to external alerting system
    send_to_pagerduty(alert.to_dict())
```

### Performance Analysis

**Location**: `monitoring/services/performance_analyzer.py`

**Features**:
- Baseline comparison
- Regression detection (20% threshold)
- Performance trend analysis
- Improvement detection

**Usage**:

```python
from monitoring.services.performance_analyzer import performance_analyzer

# Analyze metric performance
insights = performance_analyzer.analyze_metric(
    metric_name='request_duration',
    endpoint='/api/users',
    window_minutes=60
)

# Process insights
for insight in insights:
    if insight.insight_type == 'regression':
        print(f"Regression: {insight.message}")
        print(f"Current: {insight.current_value}, Baseline: {insight.baseline_value}")
```

### Security Intelligence

**Location**: `monitoring/services/security_intelligence.py`

**Features**:
- GraphQL bomb attack detection
- WebSocket flood detection
- IP reputation tracking
- Automatic IP blocking (threat score > 100)

**Usage**:

```python
from monitoring.services.security_intelligence import security_intelligence

# Analyze GraphQL pattern
threat = security_intelligence.analyze_graphql_pattern(
    ip_address='192.168.1.100',
    rejection_reason='complexity_exceeded',
    correlation_id=correlation_id
)

if threat:
    print(f"Threat detected: {threat.threat_type}")
    print(f"Severity: {threat.severity}, Confidence: {threat.confidence}")

# Check IP reputation
reputation = security_intelligence.get_ip_reputation('192.168.1.100')
print(f"Threat score: {reputation.threat_score}")
print(f"Blocked: {reputation.blocked}")

# Manual IP blocking
security_intelligence.block_ip(
    ip_address='192.168.1.100',
    reason='Repeated attack attempts',
    duration=900  # 15 minutes
)
```

## Monitoring Endpoints

### GraphQL Security Dashboard
**URL**: `/monitoring/graphql/`

**Response**:
```json
{
  "window_minutes": 60,
  "total_validations": 1234,
  "accepted_count": 1100,
  "rejected_count": 134,
  "acceptance_rate": 0.89,
  "complexity": {
    "avg": 250.5,
    "p50": 200.0,
    "p95": 600.0,
    "max": 1200.0
  },
  "depth": {
    "avg": 5.2,
    "p95": 8.0,
    "max": 12.0
  },
  "rejection_reasons": {
    "complexity_exceeded": 90,
    "depth_exceeded": 44
  }
}
```

### WebSocket Monitoring Dashboard
**URL**: `/monitoring/websocket/`

**Response**:
```json
{
  "window_minutes": 60,
  "active_connections": 450,
  "connections_by_user_type": {
    "anonymous": 50,
    "authenticated": 350,
    "staff": 50
  },
  "connection_attempts": 5000,
  "accepted_connections": 4800,
  "rejected_connections": 200,
  "acceptance_rate": 0.96,
  "avg_connection_duration": 180.5,
  "messages_per_second": 125.5
}
```

## Testing

Run comprehensive test suite:

```bash
# Run all monitoring tests (191 tests total)
python -m pytest monitoring/tests/ -v

# Run specific test categories
python -m pytest monitoring/tests/test_pii_redaction.py -v       # 35 tests
python -m pytest monitoring/tests/test_graphql_metrics.py -v     # 40 tests
python -m pytest monitoring/tests/test_websocket_metrics.py -v   # 38 tests
python -m pytest monitoring/tests/test_anomaly_detection.py -v   # 28 tests
python -m pytest monitoring/tests/test_monitoring_integration.py -v  # 50 tests
```

## Prometheus Alerts

Key alerts configured:

| Alert | Threshold | Severity |
|-------|-----------|----------|
| GraphQLComplexityAttack | 10 rejections/5min | Critical |
| WebSocketConnectionFlood | 20 rejections/min | Critical |
| PerformanceRegression | 20% above baseline | Warning |
| IPThreatScoreHigh | Score > 100 | Critical |
| MonitoringTasksFailing | >0.1 failures/sec | Warning |

## Grafana Dashboards

### GraphQL Security Dashboard
**File**: `config/grafana/dashboards/graphql_security.json`

**Panels**:
- Query rate (accepted vs rejected)
- Query rejection rate gauge
- Complexity/depth gauges (P95)
- Validation time stats
- Rejection reasons timeline
- Top rejected query patterns
- Attack detection events
- Complexity distribution heatmap

### WebSocket Connections Dashboard
**File**: `config/grafana/dashboards/websocket_connections.json`

**Panels**:
- Active connections by user type
- Total active connections
- Connection attempts timeline
- Connection rejection rate
- Average connection duration
- Messages per second
- Throttle hits counter
- Rejection reasons breakdown
- WebSocket flood attacks
- Top source IPs table
- Connection duration heatmap

### Security Overview Dashboard
**File**: `config/grafana/dashboards/security_overview.json`

**Panels**:
- Total security events
- Critical threats counter
- Anomalies detected
- Blocked IPs counter
- Security events by type/severity
- Attack types distribution
- Average IP threat score
- Performance regressions
- Top threat sources table
- Anomaly detection timeline
- Alert storm prevention
- Recent security events logs
- Critical anomalies table
- Security events heatmap

## Troubleshooting

### Issue: Metrics not appearing in Prometheus

**Solution**:
1. Check Prometheus scrape configuration
2. Verify Django app is serving metrics at `/monitoring/metrics/`
3. Check Prometheus logs: `docker logs prometheus`

### Issue: High memory usage from metrics collection

**Solution**:
1. Adjust metric retention: Run cleanup task more frequently
2. Reduce collection window: Set shorter `window_minutes` values
3. Enable metric sampling: Only collect 10% of requests

### Issue: PII appearing in dashboards

**Solution**:
1. Verify `PIISanitizationMiddleware` is enabled
2. Check `MONITORING_PII_REDACTION = True` in settings
3. Review sanitization patterns in `pii_redaction_service.py`

### Issue: Correlation IDs not propagating

**Solution**:
1. Ensure correlation ID is generated in middleware
2. Pass `correlation_id` parameter to all monitoring calls
3. Check Redis cache if using distributed architecture

## Performance Considerations

**Monitoring Overhead**:
- PII Redaction: <5ms per request
- Correlation Tracking: <2ms per request
- Metrics Collection: <3ms per metric
- Total Overhead: <10ms per request

**Optimization Tips**:
1. Enable metric sampling for high-traffic endpoints
2. Use Redis for distributed metric aggregation
3. Run background tasks on separate worker pool
4. Increase Celery worker concurrency for monitoring queue

## Security Best Practices

1. **API Key Protection**: Require API key for monitoring endpoints
2. **Rate Limiting**: Apply rate limits to monitoring APIs
3. **PII Redaction**: Always enabled in production
4. **Access Control**: Restrict monitoring dashboard access to operations team
5. **Audit Logging**: Log all monitoring API access

## Integration with External Services

### PagerDuty Integration

```python
from monitoring.services.alert_aggregator import alert_aggregator, Alert

def send_to_pagerduty(alert_data):
    import requests

    response = requests.post(
        'https://events.pagerduty.com/v2/enqueue',
        json={
            'routing_key': settings.PAGERDUTY_KEY,
            'event_action': 'trigger',
            'payload': {
                'summary': alert_data['title'],
                'severity': alert_data['severity'],
                'source': 'monitoring-system',
                'custom_details': alert_data['metadata']
            }
        },
        timeout=(5, 15)
    )
    return response.status_code == 202
```

### Slack Integration

```python
def send_to_slack(alert_data):
    import requests

    response = requests.post(
        settings.SLACK_WEBHOOK_URL,
        json={
            'text': f"🚨 {alert_data['title']}",
            'attachments': [{
                'color': 'danger' if alert_data['severity'] == 'critical' else 'warning',
                'fields': [
                    {'title': 'Message', 'value': alert_data['message']},
                    {'title': 'Source', 'value': alert_data['source']},
                    {'title': 'Severity', 'value': alert_data['severity']}
                ]
            }]
        },
        timeout=(5, 15)
    )
    return response.status_code == 200
```

## Maintenance

### Daily Tasks
- Review critical alerts in Grafana
- Check anomaly detection reports
- Verify IP reputation scores

### Weekly Tasks
- Review performance baselines
- Analyze security threat trends
- Update alert thresholds if needed

### Monthly Tasks
- Review and update Prometheus retention policies
- Optimize slow Grafana dashboard queries
- Audit PII redaction effectiveness
- Update security intelligence patterns

## Support

For issues and questions:
- GitHub Issues: `https://github.com/your-org/your-repo/issues`
- Internal Documentation: `/docs/monitoring/`
- Runbooks: `/docs/runbooks/monitoring-*.md`
