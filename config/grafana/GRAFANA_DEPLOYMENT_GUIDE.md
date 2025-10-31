# Grafana + Prometheus Deployment Guide

**Purpose:** Deploy REST API monitoring stack (post-legacy query migration, Oct 2025)
**Components:** Grafana, Prometheus, Alertmanager
**Estimated Setup Time:** 30 minutes

---

## 🚀 Quick Start (Docker Compose)

### Option 1: Docker Compose (Recommended)

**Start all services:**
```bash
cd config/grafana
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f grafana
docker-compose logs -f prometheus
```

**Access services:**
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

**Stop services:**
```bash
docker-compose down
```

---

## 📋 Manual Setup

### Step 1: Install Prometheus

**macOS:**
```bash
brew install prometheus
brew services start prometheus
```

**Linux:**
```bash
# Download latest release
wget https://github.com/prometheus/prometheus/releases/download/v2.47.0/prometheus-2.47.0.linux-amd64.tar.gz
tar -xvf prometheus-2.47.0.linux-amd64.tar.gz
cd prometheus-2.47.0.linux-amd64

# Copy config
cp /path/to/config/grafana/prometheus/prometheus.yml .
cp /path/to/config/grafana/prometheus/alerts.yml .

# Start Prometheus
./prometheus --config.file=prometheus.yml
```

### Step 2: Install Grafana

**macOS:**
```bash
brew install grafana
brew services start grafana
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana

sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Step 3: Configure Data Source

**Option A: Provisioning (Automatic)**
```bash
# Copy provisioning files
sudo cp config/grafana/provisioning/datasources/prometheus.yaml \
  /etc/grafana/provisioning/datasources/

sudo systemctl restart grafana-server
```

**Option B: Manual (Grafana UI)**
1. Login to Grafana: http://localhost:3000
2. Go to **Configuration** → **Data Sources**
3. Click **"Add data source"**
4. Select **"Prometheus"**
5. Set URL: `http://localhost:9090`
6. Click **"Save & Test"**

### Step 4: Import Dashboards

**Method 1: Provisioning (Recommended)**
```bash
# Copy provisioning config
sudo cp config/grafana/provisioning/dashboards/rest-api-dashboards.yaml \
  /etc/grafana/provisioning/dashboards/

# Create dashboard directory
sudo mkdir -p /etc/grafana/dashboards/rest-api

# Copy dashboards
sudo cp config/grafana/dashboards/*.json \
  /etc/grafana/dashboards/rest-api/

# Restart Grafana
sudo systemctl restart grafana-server
```

**Method 2: Deployment Script**
```bash
# Set Grafana API key (get from Grafana UI → Configuration → API Keys)
export GRAFANA_API_KEY="your-api-key-here"

# Run deployment script
./scripts/deploy_grafana_dashboards.sh http://localhost:3000 $GRAFANA_API_KEY
```

**Method 3: Manual Import (Grafana UI)**
1. Login to Grafana
2. Click **"+"** → **"Import"**
3. Click **"Upload JSON file"**
4. Select dashboard file (e.g., `rest_api_operations.json`)
5. Select Prometheus data source
6. Click **"Import"**
7. Repeat for all 3 dashboards

---

## 🔧 Django Metrics Configuration

### Install django-prometheus

```bash
pip install django-prometheus==2.3.1
```

### Update Settings

**File:** `intelliwiz_config/settings/base.py`

```python
INSTALLED_APPS = [
    'django_prometheus',  # Add at the top
    # ... rest of apps
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # First
    # ... your middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',  # Last
]

# Prometheus metrics configuration
PROMETHEUS_EXPORT_MIGRATIONS = False  # Don't export migration metrics
PROMETHEUS_LATENCY_BUCKETS = (
    0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75,
    1.0, 2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, float('inf')
)
```

### Update URLs

**File:** `intelliwiz_config/urls_optimized.py`

```python
from django.urls import path, include

urlpatterns = [
    # Prometheus metrics endpoint
    path('', include('django_prometheus.urls')),

    # ... rest of your URLs
]
```

### Verify Metrics Endpoint

```bash
# Start Django
python manage.py runserver

# Check metrics
curl http://localhost:8000/metrics

# Should see output like:
# django_http_requests_total_by_view_transport_method{...} 42
# django_http_request_duration_seconds_bucket{...} 0.15
```

---

## 📊 Custom Metrics for Mobile Sync

Create custom metrics for sync operations:

**File:** `apps/core/metrics.py`

```python
"""
Custom Prometheus Metrics for REST API and Mobile Sync

Following .claude/rules.md:
- Rule #7: Service <150 lines
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from django.conf import settings

# Sync operation metrics
sync_operations_total = Counter(
    'django_sync_operations_total',
    'Total sync operations',
    ['operation_type', 'sync_type', 'status']
)

sync_operations_success = Counter(
    'django_sync_operations_success_total',
    'Successful sync operations',
    ['operation_type', 'sync_type']
)

sync_latency = Histogram(
    'django_sync_latency_seconds',
    'Sync operation latency in seconds',
    ['sync_type'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

sync_conflicts = Counter(
    'django_sync_conflicts_total',
    'Total sync conflicts detected',
    ['entity_type']
)

sync_errors = Counter(
    'django_sync_errors_total',
    'Total sync errors',
    ['endpoint', 'error_type']
)

sync_payload_bytes = Histogram(
    'django_sync_payload_bytes',
    'Sync payload size in bytes',
    ['operation', 'sync_type'],
    buckets=(1024, 10240, 102400, 1048576, 10485760)  # 1KB to 10MB
)

# Idempotency metrics
idempotency_cache_hits = Counter(
    'django_idempotency_cache_hits_total',
    'Idempotency cache hits',
    ['endpoint']
)

idempotency_cache_misses = Counter(
    'django_idempotency_cache_misses_total',
    'Idempotency cache misses',
    ['endpoint']
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'django_websocket_connections_active',
    'Active WebSocket connections'
)

websocket_connections_opened = Counter(
    'django_websocket_connections_opened_total',
    'Total WebSocket connections opened'
)

websocket_connections_closed = Counter(
    'django_websocket_connections_closed_total',
    'Total WebSocket connections closed',
    ['reason']
)

websocket_message_queue_depth = Gauge(
    'django_websocket_message_queue_depth',
    'WebSocket message queue depth'
)

# Mobile app metrics
mobile_app_version_connections = Gauge(
    'django_mobile_app_version_active_connections',
    'Active connections by mobile app version',
    ['app_version', 'platform']
)

# Security metrics
rate_limit_violations = Counter(
    'django_rate_limit_violations_total',
    'Rate limit violations',
    ['endpoint', 'violation_type']
)

csrf_violations = Counter(
    'django_csrf_violations_total',
    'CSRF violations',
    ['endpoint']
)

permission_denied = Counter(
    'django_permission_denied_total',
    'Permission denied events',
    ['endpoint', 'resource']
)

sql_injection_attempts = Counter(
    'django_sql_injection_attempts_blocked_total',
    'SQL injection attempts blocked'
)

xss_attempts = Counter(
    'django_xss_attempts_blocked_total',
    'XSS attempts blocked'
)

file_upload_violations = Counter(
    'django_file_upload_violations_total',
    'File upload security violations',
    ['violation_type']
)


__all__ = [
    'sync_operations_total',
    'sync_operations_success',
    'sync_latency',
    'sync_conflicts',
    'sync_errors',
    'sync_payload_bytes',
    'idempotency_cache_hits',
    'idempotency_cache_misses',
    'websocket_connections_active',
    'websocket_connections_opened',
    'websocket_connections_closed',
    'websocket_message_queue_depth',
    'mobile_app_version_connections',
    'rate_limit_violations',
    'csrf_violations',
    'permission_denied',
    'sql_injection_attempts',
    'xss_attempts',
    'file_upload_violations',
]
