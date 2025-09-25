# Production Monitoring Setup Guide

This guide covers setting up comprehensive monitoring for the Django ORM migration in production.

## Overview

The monitoring system provides:
- Real-time performance metrics
- Alert notifications
- Health checks
- Query performance tracking
- Cache effectiveness monitoring
- Error tracking and alerting

## Components

### 1. Django Monitoring Middleware

Add to your Django settings:

```python
# settings.py

INSTALLED_APPS = [
    # ... other apps
    'monitoring',
]

MIDDLEWARE = [
    # ... other middleware
    'monitoring.django_monitoring.QueryMonitoringMiddleware',
    'monitoring.django_monitoring.CacheMonitoringMiddleware',
]

# Monitoring configuration
MONITOR_QUERIES = True  # Enable query monitoring
SITE_NAME = 'YOUTILITY3'  # Used in alerts

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'monitoring': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/monitoring.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'monitoring': {
            'handlers': ['monitoring'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 2. URL Configuration

Add monitoring URLs to your main urls.py:

```python
# urls.py

from django.urls import path, include

urlpatterns = [
    # ... other URLs
    path('monitoring/', include('monitoring.urls')),
]
```

### 3. Environment Variables

Configure monitoring settings via environment variables:

```bash
# Alert email configuration
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_RECIPIENTS=devops@example.com,oncall@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
ALERT_FROM_EMAIL=monitoring@youtility.com

# Slack configuration
ALERT_SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#alerts

# PagerDuty configuration
ALERT_PAGERDUTY_ENABLED=true
PAGERDUTY_INTEGRATION_KEY=your-integration-key

# Metrics retention
METRICS_RETENTION_HOURS=24
METRICS_COLLECTION_INTERVAL=60
```

## Monitoring Endpoints

The following endpoints are available:

### Health Checks
- `/monitoring/health/` - Basic health check for load balancers
- `/monitoring/healthz/` - Kubernetes-style health check

### Metrics
- `/monitoring/metrics/` - JSON metrics
- `/monitoring/metrics/?format=prometheus` - Prometheus format

### Performance
- `/monitoring/performance/queries/` - Query performance details
- `/monitoring/performance/cache/` - Cache performance metrics

### Alerts
- `/monitoring/alerts/` - Current active alerts
- `/monitoring/dashboard/` - Dashboard data

## Setting Up Prometheus

1. Install Prometheus:
```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.37.0/prometheus-2.37.0.linux-amd64.tar.gz
tar xvf prometheus-2.37.0.linux-amd64.tar.gz
cd prometheus-2.37.0.linux-amd64
```

2. Configure Prometheus (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'django'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/monitoring/metrics/'
    params:
      format: ['prometheus']
```

3. Start Prometheus:
```bash
./prometheus --config.file=prometheus.yml
```

## Setting Up Grafana

1. Install Grafana:
```bash
wget https://dl.grafana.com/oss/release/grafana-9.0.0.linux-amd64.tar.gz
tar -zxvf grafana-9.0.0.linux-amd64.tar.gz
cd grafana-9.0.0
```

2. Start Grafana:
```bash
./bin/grafana-server
```

3. Import the Django ORM dashboard:
   - Go to http://localhost:3000
   - Login (admin/admin)
   - Go to Dashboards → Import
   - Upload `monitoring/dashboards/grafana_django_orm.json`

## Running the Monitoring Service

Start the background monitoring service:

```bash
# Run continuously
python manage.py run_monitoring

# Run with custom interval (30 seconds)
python manage.py run_monitoring --interval 30

# Run once (for testing)
python manage.py run_monitoring --once
```

For production, use systemd service:

```ini
# /etc/systemd/system/django-monitoring.service
[Unit]
Description=Django Monitoring Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/youtility3
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python manage.py run_monitoring
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable django-monitoring
sudo systemctl start django-monitoring
```

## Alert Configuration

### Email Alerts

Configure SMTP settings and recipients in environment variables. Alerts will be sent for:
- Response time > 1s (p95)
- Query time > 100ms (p95)
- Error rate > 5%
- Cache hit rate < 50%

### Slack Alerts

1. Create a Slack webhook:
   - Go to https://api.slack.com/apps
   - Create new app → Incoming Webhooks
   - Add webhook to workspace
   - Copy webhook URL

2. Set environment variables:
   ```bash
   ALERT_SLACK_ENABLED=true
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   ```

### PagerDuty Integration

1. In PagerDuty:
   - Configuration → Services → Add Service
   - Integration Type: Events API v2
   - Copy Integration Key

2. Set environment variables:
   ```bash
   ALERT_PAGERDUTY_ENABLED=true
   PAGERDUTY_INTEGRATION_KEY=your-key
   ```

## Performance Tuning

### 1. Query Monitoring

Monitor slow queries in real-time:
```bash
curl http://localhost:8000/monitoring/performance/queries/
```

### 2. Cache Monitoring

Check cache effectiveness:
```bash
curl http://localhost:8000/monitoring/performance/cache/
```

### 3. Alert Thresholds

Adjust thresholds in `monitoring/config.py`:
```python
THRESHOLDS = {
    'response_time': 1.0,      # Adjust based on your SLA
    'query_time': 0.1,         # Database query threshold
    'error_rate': 0.05,        # Error rate threshold
    'cache_miss_rate': 0.5,    # Cache effectiveness
}
```

## Troubleshooting

### 1. No Metrics Showing

Check middleware is loaded:
```python
from django.conf import settings
print(settings.MIDDLEWARE)  # Should include monitoring middleware
```

### 2. Alerts Not Sending

Check logs:
```bash
tail -f logs/monitoring.log
```

Verify environment variables:
```python
import os
print(os.environ.get('ALERT_EMAIL_ENABLED'))
```

### 3. High Memory Usage

Metrics are kept in memory. Adjust retention:
```bash
export METRICS_RETENTION_HOURS=6  # Reduce from 24 to 6 hours
```

## Best Practices

1. **Regular Monitoring**
   - Check dashboard daily
   - Review weekly performance trends
   - Adjust alert thresholds based on baseline

2. **Alert Response**
   - Document runbooks for each alert type
   - Set up on-call rotation
   - Test alert channels monthly

3. **Performance Baselines**
   - Establish normal performance ranges
   - Track improvements after optimizations
   - Compare before/after deployment metrics

4. **Capacity Planning**
   - Monitor resource usage trends
   - Plan scaling based on metrics
   - Set up predictive alerts

## Integration with APM Tools

### New Relic
```python
# Install New Relic
pip install newrelic

# Configure
export NEW_RELIC_CONFIG_FILE=newrelic.ini
export NEW_RELIC_ENVIRONMENT=production

# Run with New Relic
newrelic-admin run-program python manage.py runserver
```

### Datadog
```python
# Install Datadog
pip install ddtrace

# Configure
export DD_SERVICE=youtility3
export DD_ENV=production

# Run with Datadog
ddtrace-run python manage.py runserver
```

### Sentry
```python
# Install Sentry
pip install sentry-sdk

# In settings.py
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
)
```

## Monitoring Checklist

- [ ] Middleware configured in settings
- [ ] URLs added to urlpatterns
- [ ] Environment variables set
- [ ] Prometheus configured and running
- [ ] Grafana dashboard imported
- [ ] Alert channels configured
- [ ] Monitoring service running
- [ ] Health check endpoint tested
- [ ] Metrics endpoint verified
- [ ] Test alert sent successfully
- [ ] Performance baselines established
- [ ] Runbooks documented
- [ ] On-call rotation setup

## Next Steps

1. Monitor for 1 week to establish baselines
2. Tune alert thresholds based on actual performance
3. Create custom dashboards for specific use cases
4. Integrate with existing monitoring infrastructure
5. Set up automated performance reports