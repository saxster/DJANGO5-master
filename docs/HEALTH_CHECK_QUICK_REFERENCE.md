# Health Check System - Quick Reference

## 🚀 Quick Start

### Check System Health
```bash
# Basic health check
curl http://localhost:8000/health/

# Detailed health check with history
curl http://localhost:8000/health/detailed/

# Readiness probe (K8s)
curl http://localhost:8000/ready/

# Liveness probe (K8s)
curl http://localhost:8000/alive/
```

### Run Continuous Monitoring
```bash
# Monitor every 60 seconds
python manage.py monitor_health_continuous

# Custom interval (30s)
python manage.py monitor_health_continuous --interval 30

# Run 10 iterations then stop
python manage.py monitor_health_continuous --interval 60 --max-iterations 10
```

### Generate Health Reports
```bash
# Last 24 hours
python manage.py generate_health_report

# Last 7 days
python manage.py generate_health_report --hours 168

# Export as JSON
python manage.py generate_health_report --format json --output health_report.json
```

---

## 📊 Health Check Categories

### **Critical Checks** (Service fails if these fail)
| Check | What It Monitors | Location |
|-------|------------------|----------|
| `database_connectivity` | PostgreSQL connection | `apps/core/health_checks/database.py:29` |
| `postgis_extension` | PostGIS functionality | `apps/core/health_checks/database.py:88` |
| `postgresql_functions` | Custom DB functions | `apps/core/health_checks/database.py:227` |
| `redis_connectivity` | Redis ping test | `apps/core/health_checks/cache.py:25` |
| `default_cache` | Django cache read/write | `apps/core/health_checks/cache.py:98` |
| `task_queue` | Background task system | `apps/core/health_checks/background_tasks.py:28` |
| `disk_space` | Critical directories | `apps/core/health_checks/system.py:24` |
| `directory_permissions` | Write access | `apps/core/health_checks/filesystem.py:24` |

### **Non-Critical Checks** (Service degrades if these fail)
| Check | What It Monitors | Location |
|-------|------------------|----------|
| `database_performance` | Slow query detection | `apps/core/health_checks/database.py:132` |
| `connection_pool` | DB connection utilization | `apps/core/health_checks/database.py:186` |
| `select2_cache` | Materialized view cache | `apps/core/health_checks/cache.py:143` |
| `memory_usage` | System memory | `apps/core/health_checks/system.py:85` |
| `cpu_load` | CPU utilization | `apps/core/health_checks/system.py:140` |
| `channel_layer` | WebSocket connectivity | `apps/core/health_checks/channels.py:26` |
| `mqtt_broker` | IoT broker | `apps/core/health_checks/mqtt.py:26` |
| `aws_ses` | Email service | `apps/core/health_checks/external_apis.py:30` |
| `google_maps_api` | Maps API | `apps/core/health_checks/external_apis.py:99` |
| `openai_api` | OpenAI LLM | `apps/core/health_checks/external_apis.py:152` |
| `anthropic_api` | Anthropic LLM | `apps/core/health_checks/external_apis.py:194` |
| `pending_tasks` | Task queue depth | `apps/core/health_checks/background_tasks.py:67` |
| `failed_tasks` | Failed tasks (1h) | `apps/core/health_checks/background_tasks.py:116` |
| `task_workers` | Worker heartbeats | `apps/core/health_checks/background_tasks.py:156` |

---

## 🛠️ Adding Custom Health Checks

### **Step 1: Create Check Function**
```python
# In apps/core/health_checks/custom.py
from .utils import timeout_check, format_check_result

@timeout_check(timeout_seconds=5)
def check_custom_service():
    try:
        # Your check logic
        return format_check_result(
            status='healthy',
            message='Service OK'
        )
    except SpecificError as e:
        return format_check_result(
            status='error',
            message=str(e)
        )
```

### **Step 2: Register Check**
```python
# In apps/core/health_checks/__init__.py
from .custom import check_custom_service

def register_all_checks():
    # ... existing checks ...
    global_health_manager.register_check(
        'custom_service', check_custom_service, critical=False
    )

__all__ = [
    # ... existing exports ...
    'check_custom_service',
]
```

### **Step 3: Test Check**
```python
# In apps/core/tests/test_custom_health_check.py
def test_check_custom_service_success():
    result = check_custom_service()
    assert result['status'] == 'healthy'
```

---

## 🎭 Health Status Guide

### **`healthy`**
- All checks passed
- Service fully operational
- HTTP 200 response

### **`degraded`**
- Non-critical checks failed
- Service still operational
- Reduced functionality
- HTTP 200 response

### **`unhealthy`**
- Critical checks failed
- Service not ready
- Cannot serve traffic
- HTTP 503 response

---

## 🔧 Troubleshooting

### **Health Check Timing Out**
```bash
# Check timeout configuration
grep -r "timeout_seconds" apps/core/health_checks/
```
Default timeout: 5 seconds per check

### **Circuit Breaker Open**
Circuit breaker opens after 3 consecutive failures. Wait for timeout period:
- MQTT: 30 seconds
- External APIs: 60 seconds

### **Missing Dependencies**
```bash
# Install all requirements
pip install -r requirements/base.txt

# Verify psutil
python -c "import psutil; print(psutil.__version__)"
```

### **Database Migration Issues**
```bash
# Check migration status
python manage.py showmigrations core

# Run migrations
python manage.py migrate core
```

---

## 📈 Monitoring Integration

### **Grafana Dashboard Query Examples**
```sql
-- Health check success rate (last 24h)
SELECT
    check_name,
    COUNT(*) FILTER (WHERE status = 'healthy') * 100.0 / COUNT(*) as success_rate
FROM core_health_check_log
WHERE checked_at > NOW() - INTERVAL '24 hours'
GROUP BY check_name
ORDER BY success_rate DESC;

-- Service uptime ranking
SELECT
    service_name,
    uptime_percentage,
    total_checks,
    last_failure_at
FROM core_service_availability
ORDER BY uptime_percentage DESC;
```

---

## 🎯 Best Practices

1. **Use `/ready/` for load balancer health checks** - Faster, critical-only
2. **Use `/health/detailed/` for ops dashboards** - Complete visibility
3. **Run continuous monitoring in production** - Historical trend analysis
4. **Configure alert thresholds via Admin** - Customize per environment
5. **Monitor circuit breaker state** - Indicates upstream service issues

---

## 🆘 Support

For issues or questions:
1. Check logs: `tail -f /var/log/youtility/production.log`
2. Review health check logs: Django Admin → Core → Health Check Logs
3. Check service availability: Django Admin → Core → Service Availabilities

---

**Last Updated:** September 27, 2025
**Version:** 1.0.0