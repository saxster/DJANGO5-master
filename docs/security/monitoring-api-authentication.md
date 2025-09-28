# Monitoring API Authentication Guide

## Overview

This guide explains how to configure and use API key authentication for external monitoring systems (Prometheus, Grafana, Datadog, etc.) to access read-only monitoring endpoints.

**Security Compliance:** Rule #3 Alternative Protection - API key authentication replaces CSRF protection for stateless, read-only monitoring endpoints.

---

## Quick Start

### 1. Generate Monitoring API Key

```python
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringPermission

# Create a key for Prometheus
prometheus_key, api_key = MonitoringAPIKey.create_key(
    name="Prometheus Production",
    monitoring_system="prometheus",
    permissions=[
        MonitoringPermission.HEALTH_CHECK.value,
        MonitoringPermission.METRICS.value,
        MonitoringPermission.PERFORMANCE.value,
    ],
    allowed_ips=[
        "10.0.1.100",  # Prometheus server IP
        "10.0.1.101",  # Backup Prometheus server
    ],
    expires_days=365,
    rotation_schedule='quarterly',
    created_by=request.user
)

# IMPORTANT: Store api_key securely - it cannot be retrieved later
print(f"API Key (SAVE THIS): {api_key}")
print(f"Key ID: {prometheus_key.id}")
```

### 2. Configure Monitoring System

#### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'django_monitoring'
    static_configs:
      - targets: ['your-app.com']
    scheme: https
    metrics_path: /monitoring/metrics/
    params:
      format: ['prometheus']
    authorization:
      credentials: 'YOUR_API_KEY_HERE'
```

#### Grafana Configuration

```json
{
  "name": "Django Monitoring API",
  "type": "json-datasource",
  "url": "https://your-app.com/monitoring/",
  "jsonData": {
    "httpHeaderName1": "Authorization"
  },
  "secureJsonData": {
    "httpHeaderValue1": "Bearer YOUR_API_KEY_HERE"
  }
}
```

#### Datadog Configuration

```yaml
# datadog.yaml
instances:
  - url: https://your-app.com/monitoring/health/
    headers:
      X-Monitoring-API-Key: YOUR_API_KEY_HERE
    timeout: 5
```

---

## Protected Endpoints

### Health & Status

```bash
# Health Check
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-app.com/monitoring/health/

# Metrics (JSON format)
curl -H "X-Monitoring-API-Key: YOUR_API_KEY" \
  https://your-app.com/monitoring/metrics/

# Metrics (Prometheus format)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://your-app.com/monitoring/metrics/?format=prometheus"
```

### Performance Monitoring

```bash
# Query Performance
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://your-app.com/monitoring/query-performance/?window=60"

# Cache Performance
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://your-app.com/monitoring/cache-performance/?window=60"
```

### Alerts & Dashboard

```bash
# Current Alerts
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-app.com/monitoring/alerts/

# Dashboard Data
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-app.com/monitoring/dashboard/
```

---

## API Key Management

### Creating Keys

```python
# Minimal key (all endpoints, no IP restriction)
key, api_key = MonitoringAPIKey.create_key(
    name="Development Monitoring",
    monitoring_system="custom",
    permissions=[MonitoringPermission.ADMIN.value]
)

# Restricted key (specific permissions)
key, api_key = MonitoringAPIKey.create_key(
    name="Grafana Dashboard",
    monitoring_system="grafana",
    permissions=[
        MonitoringPermission.METRICS.value,
        MonitoringPermission.DASHBOARD.value
    ],
    allowed_ips=["192.168.1.100"],
    expires_days=90
)
```

### Rotating Keys

```python
# Manual rotation
old_key = MonitoringAPIKey.objects.get(id=1)
new_key, new_api_key = old_key.rotate_key(created_by=request.user)

print(f"New API Key: {new_api_key}")
print(f"Old key valid until: {old_key.expires_at}")
print(f"Grace period: {old_key.rotation_grace_period_hours} hours")

# Automatic rotation (via management command)
python manage.py rotate_monitoring_keys --auto
```

### Revoking Keys

```python
# Soft revoke (deactivate but keep for audit)
key = MonitoringAPIKey.objects.get(id=1)
key.is_active = False
key.save()

# Hard delete (use sparingly, breaks audit trail)
key.delete()
```

---

## Permission Model

### Permission Levels

| Permission | Endpoints Granted | Use Case |
|------------|------------------|----------|
| `health` | Health check only | Load balancer health checks |
| `metrics` | Metrics endpoint | Prometheus scraping |
| `performance` | Query/cache performance | Performance monitoring |
| `alerts` | Alerts endpoint | Alert aggregation systems |
| `dashboard` | Dashboard data | Custom dashboards |
| `admin` | All endpoints | Full monitoring access |

### Permission Examples

```python
# Health checks only (minimal permissions)
permissions=[MonitoringPermission.HEALTH_CHECK.value]

# Metrics and performance (Prometheus + Grafana)
permissions=[
    MonitoringPermission.METRICS.value,
    MonitoringPermission.PERFORMANCE.value
]

# Full access (admin monitoring)
permissions=[MonitoringPermission.ADMIN.value]
```

---

## Security Best Practices

### 1. Use Strong API Keys
✅ Generated with `secrets.token_urlsafe(32)` (256 bits of entropy)
❌ Never use predictable or short keys

### 2. Rotate Keys Regularly
✅ Set `rotation_schedule='quarterly'` minimum
✅ Use grace periods for zero-downtime rotation
❌ Never disable rotation for production keys

### 3. Restrict IP Addresses
✅ Whitelist monitoring server IPs
✅ Update allowed_ips when infrastructure changes
❌ Never use `allowed_ips=None` in production

### 4. Use Least Privilege
✅ Grant only required permissions
✅ Create separate keys for different monitoring systems
❌ Never use `ADMIN` permission unless absolutely necessary

### 5. Monitor API Key Usage
✅ Review `MonitoringAPIAccessLog` regularly
✅ Alert on unusual usage patterns
✅ Revoke compromised keys immediately

---

## Rate Limiting

### Default Limits
- **1000 requests/hour** per API key
- Configurable per key via `rate_limit` field
- Returns `429 Too Many Requests` when exceeded

### Custom Rate Limits

```python
# High-frequency monitoring (10,000 requests/hour)
key.rate_limit = '10000/h'
key.save()

# Low-frequency dashboards (100 requests/hour)
key.rate_limit = '100/h'
key.save()

# Burst protection (10 requests/minute)
key.rate_limit = '10/m'
key.save()
```

---

## Troubleshooting

### Error: "API_KEY_REQUIRED"
**Cause:** No API key provided in request
**Fix:** Include API key in `Authorization: Bearer` header or `X-Monitoring-API-Key` header

```bash
# Correct usage
curl -H "Authorization: Bearer abc123..." https://your-app.com/monitoring/health/
```

### Error: "API_KEY_INVALID"
**Cause:** Invalid, expired, or revoked API key
**Fix:** Verify key is active and not expired

```python
key = MonitoringAPIKey.objects.get(key_hash=hash_of_your_key)
print(f"Active: {key.is_active}")
print(f"Expired: {key.is_expired()}")
```

### Error: "RATE_LIMIT_EXCEEDED"
**Cause:** Too many requests in time window
**Fix:** Wait for rate limit window to reset, or increase limit

```python
# Check current usage
from django.core.cache import cache
current = cache.get(f"monitoring_rate:{key.id}")
print(f"Current requests: {current}")
```

### Error: 401 with IP in Logs
**Cause:** Request from IP not in whitelist
**Fix:** Add IP to `allowed_ips` or remove restriction

```python
key = MonitoringAPIKey.objects.get(id=1)
key.allowed_ips = key.allowed_ips + ["new.ip.address"]
key.save()
```

---

## Management Commands

### Generate API Key

```bash
# Interactive key generation
python manage.py create_monitoring_key \
  --name "Prometheus Production" \
  --system prometheus \
  --permissions health,metrics,performance \
  --ips 10.0.1.100,10.0.1.101 \
  --expires-days 365

# Output:
# ✅ Created monitoring API key: Prometheus Production
# 📋 API Key: xyzabc123... (SAVE THIS - cannot be retrieved later)
# 🔑 Key ID: 42
```

### Rotate Keys

```bash
# Rotate all keys needing rotation
python manage.py rotate_monitoring_keys --auto

# Rotate specific key
python manage.py rotate_monitoring_keys --key-id 42

# Force immediate rotation
python manage.py rotate_monitoring_keys --key-id 42 --no-grace-period
```

### List Keys

```bash
# List all monitoring keys
python manage.py list_monitoring_keys

# List keys needing rotation
python manage.py list_monitoring_keys --needs-rotation

# List keys by system
python manage.py list_monitoring_keys --system prometheus
```

### Audit Usage

```bash
# Usage summary for key
python manage.py monitoring_key_usage --key-id 42 --days 30

# Detect anomalies
python manage.py monitor_api_key_anomalies --alert-threshold 1000
```

---

## Migration from @csrf_exempt

### Before (INSECURE)

```python
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class MetricsEndpoint(View):
    def get(self, request):
        return JsonResponse({'metrics': data})
```

### After (SECURE)

```python
from apps.core.decorators import require_monitoring_api_key

@method_decorator(require_monitoring_api_key, name='dispatch')
class MetricsEndpoint(View):
    """
    Metrics endpoint for monitoring systems.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    def get(self, request):
        return JsonResponse({'metrics': data})
```

---

## Compliance Checklist

- [x] All monitoring endpoints use `require_monitoring_api_key`
- [x] No `@csrf_exempt` on read-only monitoring endpoints
- [x] API keys use SHA-256 hashing (never plaintext)
- [x] Rate limiting configured per API key
- [x] IP whitelisting enabled for production keys
- [x] Automatic rotation schedule configured
- [x] Audit logging enabled for all accesses
- [x] Documentation references Rule #3 compliance

---

## Example: Complete Prometheus Setup

### Step 1: Create API Key

```python
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringPermission

prom_key, api_key = MonitoringAPIKey.create_key(
    name="Prometheus Production Scraper",
    monitoring_system="prometheus",
    permissions=[
        MonitoringPermission.HEALTH_CHECK.value,
        MonitoringPermission.METRICS.value
    ],
    allowed_ips=["10.0.50.10"],  # Prometheus server IP
    expires_days=365,
    rotation_schedule='quarterly',
    metadata={
        'contact_email': 'devops@company.com',
        'escalation': 'security-team@company.com'
    }
)

print(f"🔑 API Key: {api_key}")
```

### Step 2: Configure Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'django_app'
    static_configs:
      - targets: ['app.company.com']
    scheme: https
    metrics_path: '/monitoring/metrics/'
    params:
      format: ['prometheus']
    authorization:
      type: Bearer
      credentials: 'paste_api_key_here'
```

### Step 3: Verify

```bash
# Test endpoint
curl -H "Authorization: Bearer YOUR_KEY" \
  https://app.company.com/monitoring/metrics/?format=prometheus

# Should return Prometheus-format metrics
```

### Step 4: Set Up Key Rotation

```bash
# Add to cron (rotate quarterly)
0 0 1 */3 * /path/to/venv/bin/python manage.py rotate_monitoring_keys --auto --notify

# Email notification sent to contact_email with new key
```

---

## Support

For issues or questions:
- **Security concerns:** security-team@company.com
- **Configuration help:** devops@company.com
- **Documentation:** See `.claude/rules.md` Rule #3

---

**Last Updated:** 2025-09-27
**Compliance:** Rule #3 (Mandatory CSRF Protection - Alternative Methods)
**CVSS Fix:** 8.1 vulnerability remediation