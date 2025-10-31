# Grafana + Prometheus Deployment Guide

**Purpose:** Deploy REST API monitoring stack (post-legacy query migration, Oct 2025)
**Components:** Grafana, Prometheus, Alertmanager
**Estimated Setup Time:** 30 minutes

---

## 🚀 Quick Start (Docker Compose)

### Start Monitoring Stack

```bash
cd config/grafana
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f grafana
docker-compose logs -f prometheus
```

**Access Services:**
- **Grafana:** http://localhost:3000 (username: `admin`, password: `admin`)
- **Prometheus:** http://localhost:9090
- **Alertmanager:** http://localhost:9093

**Stop Services:**
```bash
docker-compose down

# With data cleanup
docker-compose down -v
```

---

## 📊 Verify Dashboard Import

### Check Dashboards Loaded

1. Open Grafana: http://localhost:3000
2. Login with `admin/admin`
3. Go to **Dashboards** → **Browse**
4. Look for **"REST API"** folder
5. Should see 3 dashboards:
   - REST API Operations
   - REST API Security
   - Mobile Sync Performance

### Test Dashboard

1. Open **"REST API Operations"** dashboard
2. Set time range to **Last 6 hours**
3. Verify panels show data (or "No data" if Django not running)
4. Click panel titles to edit and verify queries

---

## 🔧 Django Integration

### Install django-prometheus

```bash
source venv/bin/activate
pip install django-prometheus==2.3.1
pip freeze | grep django-prometheus >> requirements/observability.txt
```

### Configure Django

Add to `intelliwiz_config/settings/base.py`:

```python
INSTALLED_APPS = [
    'django_prometheus',  # Add at top
    # ... existing apps
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # FIRST
    # ... existing middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',  # LAST
]
```

Add metrics endpoint to `intelliwiz_config/urls_optimized.py`:

```python
urlpatterns = [
    path('', include('django_prometheus.urls')),  # Adds /metrics endpoint
    # ... existing URLs
]
```

### Test Metrics Endpoint

```bash
./venv/bin/python manage.py runserver

# In another terminal
curl http://localhost:8000/metrics | head -20
```

---

## 📈 Production Deployment

### Prometheus Configuration

**Edit:** `config/grafana/prometheus/prometheus.yml`

Update Django target for production:

```yaml
scrape_configs:
  - job_name: 'django-app'
    static_configs:
      - targets:
          - 'your-production-domain.com:443'  # Update this
    scheme: https
    metrics_path: '/metrics'
    scrape_interval: 10s
```

### Grafana Security

**Change default password:**
```bash
# First login, Grafana will prompt to change password
# Or use environment variable:
docker-compose up -d \
  -e GF_SECURITY_ADMIN_PASSWORD=your-secure-password
```

**Enable HTTPS:**
```yaml
# docker-compose.yml
services:
  grafana:
    environment:
      - GF_SERVER_PROTOCOL=https
      - GF_SERVER_CERT_FILE=/etc/grafana/ssl/grafana.crt
      - GF_SERVER_CERT_KEY=/etc/grafana/ssl/grafana.key
    volumes:
      - ./ssl:/etc/grafana/ssl:ro
```

### Alert Notifications

**Configure Slack webhook:**

Edit `config/grafana/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'security-team'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/HERE'
        channel: '#security-alerts'
```

**Test alerts:**
```bash
# Trigger test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H 'Content-Type: application/json' \
  -d '[{
    "labels": {"alertname": "TestAlert", "severity": "warning"},
    "annotations": {"summary": "Test alert"}
  }]'
```

---

## ✅ Verification Checklist

- [ ] Prometheus accessible at http://localhost:9090
- [ ] Grafana accessible at http://localhost:3000
- [ ] 3 dashboards visible in Grafana
- [ ] Django metrics endpoint working: http://localhost:8000/metrics
- [ ] Prometheus scraping Django (check Targets page)
- [ ] Dashboard panels showing data
- [ ] Alerts configured in Alertmanager
- [ ] Notifications working (Slack/Email)

---

## 🐛 Troubleshooting

### Dashboard Shows "No Data"

**Check 1: Prometheus Scraping Django**
```bash
# Visit Prometheus targets page
open http://localhost:9090/targets

# Should see django-app target in "UP" state
```

**Check 2: Django Metrics Endpoint**
```bash
curl http://localhost:8000/metrics
# Should return Prometheus-formatted metrics
```

**Check 3: Grafana Data Source**
- Grafana → Configuration → Data Sources → Prometheus
- Click "Test" button - should show "Data source is working"

### Alerts Not Firing

**Check alert rules in Prometheus:**
```bash
open http://localhost:9090/alerts
# Should see rules from alerts.yml
```

**Check Alertmanager:**
```bash
open http://localhost:9093
# Should show configured receivers
```

### Permission Denied Errors

```bash
# Fix ownership
sudo chown -R 472:472 grafana_data/  # Grafana user ID
sudo chown -R 65534:65534 prometheus_data/  # Nobody user ID
```

---

## 📁 File Structure

```
config/grafana/
├── docker-compose.yml                           # Docker Compose config
├── DEPLOYMENT_GUIDE.md                          # This file
├── dashboards/
│   ├── README.md                                # Dashboard setup guide
│   ├── rest_api_operations.json                # Operations dashboard
│   ├── rest_api_security.json                  # Security dashboard
│   └── mobile_sync_performance.json            # Mobile sync dashboard
├── provisioning/
│   ├── dashboards/
│   │   └── rest-api-dashboards.yaml           # Dashboard provisioning
│   └── datasources/
│       └── prometheus.yaml                     # Data source provisioning
├── prometheus/
│   ├── prometheus.yml                          # Prometheus config
│   └── alerts.yml                              # Alert rules
└── alertmanager/
    └── alertmanager.yml                        # Alert routing
```

---

## 🚀 Quick Commands

```bash
# Start monitoring stack
cd config/grafana && docker-compose up -d

# Check logs
docker-compose logs -f

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Deploy dashboards manually
./scripts/deploy_grafana_dashboards.sh http://localhost:3000 $GRAFANA_API_KEY

# Update dashboards
docker-compose restart grafana
```

---

**Created:** October 29, 2025
**Status:** Production Ready
**Last Updated:** October 29, 2025
