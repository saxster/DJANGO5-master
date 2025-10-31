# Grafana Dashboards for REST API Monitoring

This directory contains production-ready Grafana dashboards for monitoring the REST API infrastructure (post-legacy query migration, Oct 2025).

## Available Dashboards

### 1. REST API Operations (`rest_api_operations.json`)

**Purpose:** Monitor overall API performance and usage patterns

**Panels:**
- Request rate by endpoint (time series)
- Response time P50/P95/P99 (graph)
- Error rate by status code (bar chart)
- Top 10 slowest endpoints (table)
- Request volume heatmap (24h view)
- Authentication success vs failure
- Total API calls counter
- Average response time trend with alerts

**Alerts:**
- High API Response Time (>500ms) - fires after 1 minute
- Annotates API-related Prometheus alerts

**Refresh:** 30 seconds
**Recommended for:** DevOps, Backend Engineers

---

### 2. REST API Security (`rest_api_security.json`)

**Purpose:** Monitor security threats and violations

**Panels:**
- Rate limit violations counter
- Authentication failures by endpoint (with alerts)
- Blocked IPs table (top 20)
- CSRF violations counter
- Permission denials by resource
- SQL injection attempts blocked
- XSS attempts blocked
- File upload security violations
- Suspicious IP activity heatmap

**Alerts:**
- High Authentication Failure Rate (>5 req/s) - potential brute force
- Annotates security-related Prometheus alerts

**Refresh:** 30 seconds
**Recommended for:** Security Team, DevOps

---

### 3. Mobile Sync Performance (`mobile_sync_performance.json`)

**Purpose:** Monitor mobile app synchronization and WebSocket connections

**Panels:**
- Sync operations per minute counter
- Active WebSocket connections (with open/close rates)
- Delta sync latency distribution (heatmap)
- Bulk sync latency distribution (heatmap)
- Conflict resolution rate
- Idempotency cache hit rate (gauge)
- Sync operations by type (pie chart)
- Sync errors by endpoint
- Mobile app versions distribution
- Average sync payload size (upload/download)
- WebSocket message queue depth (with alerts)
- Sync success rate (last hour)

**Alerts:**
- High WebSocket Queue Depth (>1000 messages)
- Annotates sync-related Prometheus alerts

**Refresh:** 30 seconds
**Recommended for:** Mobile Team, Backend Engineers

---

## Setup Instructions

### Prerequisites

1. **Prometheus** configured to scrape Django metrics
2. **Grafana** instance running (v7.0+)
3. **Django Prometheus Integration:**
   ```python
   # requirements.txt
   django-prometheus==2.3.1

   # settings.py
   INSTALLED_APPS += ['django_prometheus']

   # urls.py
   path('', include('django_prometheus.urls'))
   ```

### Import Dashboards

#### Option 1: Grafana UI
1. Login to Grafana
2. Click **"+"** → **"Import"**
3. Upload JSON files or paste contents
4. Select Prometheus data source
5. Click **"Import"**

#### Option 2: Grafana API
```bash
# Set variables
GRAFANA_URL="http://localhost:3000"
GRAFANA_API_KEY="your-api-key"

# Import each dashboard
for dashboard in rest_api_operations.json rest_api_security.json mobile_sync_performance.json; do
  curl -X POST \
    -H "Authorization: Bearer $GRAFANA_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$dashboard" \
    "$GRAFANA_URL/api/dashboards/db"
done
```

#### Option 3: Provisioning (Recommended for Production)
```yaml
# /etc/grafana/provisioning/dashboards/rest-api.yaml
apiVersion: 1

providers:
  - name: 'REST API Dashboards'
    orgId: 1
    folder: 'REST API'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /path/to/config/grafana/dashboards
```

### Configure Data Source

Ensure Prometheus data source is configured in Grafana:

```yaml
# /etc/grafana/provisioning/datasources/prometheus.yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
```

---

## Metrics Required

These dashboards expect the following Prometheus metrics from Django:

### HTTP Metrics
```python
django_http_requests_total_by_view_transport_method
django_http_request_duration_seconds_bucket
django_http_request_duration_seconds_sum
django_http_request_duration_seconds_count
```

### Security Metrics
```python
django_rate_limit_violations_total
django_csrf_violations_total
django_permission_denied_total
django_sql_injection_attempts_blocked_total
django_xss_attempts_blocked_total
django_file_upload_violations_total
rate_limit_blocked_ip_active
```

### Sync Metrics
```python
django_sync_operations_total
django_sync_operations_success_total
django_sync_latency_seconds_bucket
django_sync_conflicts_total
django_sync_errors_total
django_sync_payload_bytes
django_idempotency_cache_hits_total
django_idempotency_cache_misses_total
```

### WebSocket Metrics
```python
django_websocket_connections_active
django_websocket_connections_opened_total
django_websocket_connections_closed_total
django_websocket_message_queue_depth
django_mobile_app_version_active_connections
```

---

## Custom Metrics Implementation

If metrics don't exist, implement them using `django-prometheus`:

```python
# apps/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Sync metrics
sync_operations = Counter(
    'django_sync_operations_total',
    'Total sync operations',
    ['operation_type', 'sync_type']
)

sync_latency = Histogram(
    'django_sync_latency_seconds',
    'Sync operation latency',
    ['sync_type'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# WebSocket metrics
websocket_connections = Gauge(
    'django_websocket_connections_active',
    'Active WebSocket connections'
)

# Usage in views
from apps.core.metrics import sync_operations, sync_latency

@sync_latency.labels(sync_type='delta').time()
def perform_delta_sync(data):
    sync_operations.labels(operation_type='sync', sync_type='delta').inc()
    # ... sync logic
```

---

## Alert Configuration

Alerts are embedded in dashboards but can also be configured in Prometheus:

```yaml
# /etc/prometheus/rules/rest_api_alerts.yml
groups:
  - name: rest_api_alerts
    interval: 30s
    rules:
      - alert: HighAPIResponseTime
        expr: avg(rate(django_http_request_duration_seconds_sum[5m]) / rate(django_http_request_duration_seconds_count[5m])) > 0.5
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "API response time exceeded 500ms"

      - alert: HighAuthenticationFailureRate
        expr: sum(rate(django_http_requests_total_by_view_transport_method{status=~"401|403"}[5m])) > 5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Potential brute force attack detected"
```

---

## Troubleshooting

### Dashboard shows "No Data"

1. **Check Prometheus is scraping Django:**
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. **Verify metrics endpoint:**
   ```bash
   curl http://localhost:8000/metrics
   ```

3. **Check Grafana data source:**
   - Grafana → Configuration → Data Sources → Prometheus → Test

### Metrics not showing

1. **Ensure django-prometheus is installed:**
   ```bash
   pip list | grep django-prometheus
   ```

2. **Verify middleware is enabled:**
   ```python
   # settings.py
   MIDDLEWARE = [
       'django_prometheus.middleware.PrometheusBeforeMiddleware',
       # ... other middleware
       'django_prometheus.middleware.PrometheusAfterMiddleware',
   ]
   ```

### Alerts not firing

1. **Check alert rules in Prometheus:**
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```

2. **Verify Alertmanager integration**

---

## Dashboard Maintenance

- **Update frequency:** Review quarterly or after major changes
- **Owner:** DevOps Team
- **Feedback:** Create issue in project repository

**Created:** October 29, 2025
**Version:** 1.0
**Compatible with:** Grafana 7.0+, Prometheus 2.0+
