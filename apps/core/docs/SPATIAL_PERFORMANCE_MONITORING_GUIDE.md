# Spatial Query Performance Monitoring - Usage Guide

**Date:** 2025-09-30
**Status:** ✅ Production Ready
**Module:** `apps.core.services.spatial_query_performance_monitor`

---

## 📊 Overview

The Spatial Query Performance Monitoring system provides real-time tracking of spatial query execution times, automatic slow query detection, and dashboard integration for monitoring GPS/geolocation operations.

**Key Features:**
- ✅ Automatic execution time tracking
- ✅ Slow query detection (>500ms threshold)
- ✅ Severity-based alerting (MEDIUM, HIGH, CRITICAL)
- ✅ Real-time dashboard metrics
- ✅ Health status monitoring
- ✅ Zero performance overhead (uses async caching)

---

## 🚀 Quick Start

### Basic Usage

```python
from apps.core.services.spatial_query_performance_monitor import spatial_query_monitor

# Track a spatial query
with spatial_query_monitor.track_query('geofence_check', {'geofence_id': 123}):
    # Your spatial query code here
    is_inside = check_if_point_in_geofence(lat, lon, geofence)
```

### Integration Example

```python
from apps.core.services.spatial_query_performance_monitor import spatial_query_monitor
from apps.core.services.geofence_validation_service import geofence_validation_service

def check_employee_location(people_id, lat, lon, geofence_id):
    """Check if employee is inside assigned geofence."""

    # Track this spatial query
    with spatial_query_monitor.track_query(
        query_type='employee_geofence_check',
        query_params={'people_id': people_id, 'geofence_id': geofence_id}
    ):
        # Get geofence
        geofence = get_geofence_by_id(geofence_id)

        # Validate location
        is_inside = geofence_validation_service.is_point_in_geofence(
            lat, lon, geofence
        )

        return is_inside
```

---

## 📈 Dashboard Integration

### API Endpoints

All endpoints require authentication and admin/staff permissions.

#### 1. Dashboard Summary

```bash
GET /api/spatial-performance/dashboard/

Response:
{
    "status": "success",
    "data": {
        "total_queries_today": 1523,
        "avg_query_time_ms": 42.5,
        "slow_queries_count": 8,
        "slow_queries_by_severity": {
            "CRITICAL": 1,
            "HIGH": 2,
            "MEDIUM": 5
        },
        "health_status": "HEALTHY",
        "queries_by_type": {
            "geofence_check": {
                "count": 845,
                "avg_time_ms": 38.2
            }
        }
    }
}
```

#### 2. Slow Queries List

```bash
GET /api/spatial-performance/slow-queries/?severity=HIGH&limit=10

Response:
{
    "status": "success",
    "data": [
        {
            "timestamp": "2025-09-30T14:23:45.123456",
            "query_type": "geofence_check",
            "execution_time_ms": 752.3,
            "severity": "HIGH",
            "query_params": {
                "geofence_id": 123,
                "people_id": 456
            }
        }
    ],
    "count": 8
}
```

#### 3. Detailed Metrics

```bash
GET /api/spatial-performance/metrics/?date=2025-09-30

Response:
{
    "status": "success",
    "data": {
        "total_queries": 1523,
        "total_time_ms": 64725.3,
        "avg_time_ms": 42.5,
        "queries_by_type": {
            "geofence_check": {
                "count": 845,
                "total_time_ms": 32289.0,
                "avg_time_ms": 38.2,
                "min_time_ms": 5.1,
                "max_time_ms": 752.3
            },
            "distance_calculation": {
                "count": 678,
                "avg_time_ms": 47.8,
                "min_time_ms": 8.2,
                "max_time_ms": 425.1
            }
        }
    }
}
```

#### 4. Health Check

```bash
GET /api/spatial-performance/health/

Response:
{
    "status": "success",
    "health": "HEALTHY",
    "checks": {
        "avg_query_time_ok": true,
        "slow_query_rate_ok": true,
        "critical_queries_ok": true
    },
    "metrics": {
        "avg_query_time_ms": 42.5,
        "total_queries": 1523,
        "slow_queries": 8,
        "critical_queries": 1
    }
}
```

---

## 🎯 Query Types

Use descriptive query types for better monitoring:

| Query Type | Description | Example Usage |
|------------|-------------|---------------|
| `geofence_check` | Point-in-geofence validation | Employee location check |
| `distance_calculation` | Haversine distance | Route planning |
| `geofence_batch_check` | Bulk point validation | Asset tracking |
| `spatial_clustering` | Coordinate clustering | Heat map generation |
| `nearest_neighbor` | Find closest point | Find nearest site |
| `route_optimization` | Path calculation | Delivery routing |

---

## ⚡ Performance Thresholds

### Severity Levels

| Threshold | Severity | Action |
|-----------|----------|--------|
| < 500ms | Normal | No action |
| 500-1000ms | MEDIUM | Log warning |
| 1000-2000ms | HIGH | Alert + log |
| > 2000ms | CRITICAL | Immediate alert |

### Customizing Thresholds

```python
from apps.core.services.spatial_query_performance_monitor import (
    SpatialQueryPerformanceMonitor
)

# Create custom monitor with different thresholds
custom_monitor = SpatialQueryPerformanceMonitor()
custom_monitor.SLOW_QUERY_THRESHOLD_MS = 300  # More sensitive
custom_monitor.CRITICAL_SLOW_QUERY_THRESHOLD_MS = 1500
```

---

## 🔔 Alert Configuration

### Setting Up Alert Callbacks

```python
from apps.core.services.spatial_query_performance_monitor import spatial_query_monitor
import logging

logger = logging.getLogger('spatial_alerts')

def alert_slow_query(query_info):
    """Custom alert handler for slow queries."""
    severity = query_info['severity']
    query_type = query_info['query_type']
    execution_time = query_info['execution_time_ms']

    if severity == 'CRITICAL':
        # Send urgent notification
        logger.critical(
            f"CRITICAL slow query: {query_type} "
            f"took {execution_time}ms"
        )
        # Could integrate with Slack, PagerDuty, etc.
        # send_slack_alert(query_info)
    else:
        logger.warning(
            f"{severity} slow query: {query_type} "
            f"took {execution_time}ms"
        )

# Register callback
spatial_query_monitor.set_alert_callback(alert_slow_query)
```

---

## 📊 Health Status Calculation

The health status is calculated based on three factors:

### HEALTHY ✅
- Average query time < 500ms
- Slow query rate < 10%
- Critical slow queries < 5

### WARNING ⚠️
- Average query time 500-1000ms
- Slow query rate 10-20%
- Critical slow queries 5-10

### CRITICAL 🔴
- Average query time > 1000ms
- Slow query rate > 20%
- Critical slow queries > 10

---

## 🧪 Testing Integration

```python
from apps.core.tests.test_spatial_operations_comprehensive import *
from apps.core.services.spatial_query_performance_monitor import spatial_query_monitor

class MyServiceTests(TestCase):
    """Test spatial service with performance monitoring."""

    def test_geofence_check_performance(self):
        """Test that geofence check completes within threshold."""

        with spatial_query_monitor.track_query('geofence_check') as tracking:
            # Perform geofence check
            is_inside = check_if_in_geofence(lat, lon, geofence)

            # Verify execution time
            elapsed_ms = (time.time() - tracking['start_time']) * 1000
            self.assertLess(
                elapsed_ms,
                500,  # Should complete in under 500ms
                "Geofence check too slow"
            )
```

---

## 📦 Production Deployment

### 1. URL Configuration

Add to your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... other patterns ...

    path(
        'api/spatial-performance/',
        include('apps.core.urls.spatial_performance_urls')
    ),
]
```

### 2. Settings Configuration

No additional settings required - uses existing Django cache configuration.

**Optional:** Customize cache backend for metrics:

```python
# settings/production.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    },
    # Optional: Dedicated cache for performance metrics
    'metrics': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/2',
    }
}
```

### 3. Monitoring Integration

Integrate with existing monitoring tools:

```python
# Integration with Prometheus
from prometheus_client import Histogram

spatial_query_histogram = Histogram(
    'spatial_query_duration_seconds',
    'Spatial query execution time',
    ['query_type']
)

def prometheus_callback(query_info):
    """Send metrics to Prometheus."""
    spatial_query_histogram.labels(
        query_type=query_info['query_type']
    ).observe(query_info['execution_time_ms'] / 1000)

spatial_query_monitor.set_alert_callback(prometheus_callback)
```

---

## 🎛️ Dashboard UI Example

### HTML/JavaScript Integration

```html
<!DOCTYPE html>
<html>
<head>
    <title>Spatial Performance Dashboard</title>
</head>
<body>
    <div id="dashboard">
        <h1>Spatial Query Performance</h1>
        <div id="health-status"></div>
        <div id="metrics"></div>
        <div id="slow-queries"></div>
    </div>

    <script>
        async function updateDashboard() {
            // Fetch dashboard data
            const response = await fetch('/api/spatial-performance/dashboard/');
            const data = await response.json();

            // Update UI
            document.getElementById('health-status').innerHTML = `
                <h2>Health: ${data.data.health_status}</h2>
                <p>Total Queries: ${data.data.total_queries_today}</p>
                <p>Avg Time: ${data.data.avg_query_time_ms}ms</p>
            `;
        }

        // Update every minute
        setInterval(updateDashboard, 60000);
        updateDashboard();
    </script>
</body>
</html>
```

---

## 🔍 Troubleshooting

### Slow Queries Not Being Tracked

**Problem:** Queries aren't showing up in slow query list.

**Solution:**
1. Verify you're using the `track_query()` context manager
2. Check that query actually exceeds 500ms threshold
3. Verify cache backend is working properly

### Memory Issues

**Problem:** Cache growing too large with metrics.

**Solution:** The system automatically limits storage:
- Max 10,000 metrics per day
- Max 100 slow queries stored per day
- Metrics expire after 24 hours

### Dashboard Shows Stale Data

**Problem:** Dashboard not updating.

**Solution:**
1. Check cache expiry settings
2. Verify cache backend connectivity
3. Clear cache: `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`

---

## 📚 API Reference

### SpatialQueryPerformanceMonitor Class

```python
class SpatialQueryPerformanceMonitor:
    """Monitor spatial query performance."""

    SLOW_QUERY_THRESHOLD_MS = 500
    VERY_SLOW_QUERY_THRESHOLD_MS = 1000
    CRITICAL_SLOW_QUERY_THRESHOLD_MS = 2000

    def track_query(query_type: str, query_params: Dict = None):
        """Context manager to track query execution."""

    def get_performance_metrics(date: datetime = None) -> Dict:
        """Get performance metrics for a date."""

    def get_slow_queries(date: datetime = None, severity: str = None) -> List:
        """Get slow queries with optional filtering."""

    def get_dashboard_summary() -> Dict:
        """Get summary for dashboard display."""

    def set_alert_callback(callback: Callable):
        """Set custom alert handler."""
```

---

## 🎓 Best Practices

### 1. Use Descriptive Query Types
```python
# ❌ BAD:
with spatial_query_monitor.track_query('query'):
    ...

# ✅ GOOD:
with spatial_query_monitor.track_query('employee_geofence_validation'):
    ...
```

### 2. Include Relevant Parameters
```python
# ✅ GOOD: Include context for debugging
with spatial_query_monitor.track_query(
    'geofence_check',
    {'people_id': 123, 'geofence_id': 456, 'business_unit': 'NY'}
):
    ...
```

### 3. Track Only Critical Paths
```python
# Don't track every single operation
# Focus on user-facing and performance-critical queries

# ✅ Track user-facing operations
with spatial_query_monitor.track_query('user_location_check'):
    validate_employee_location(...)

# ❌ Don't track internal utility calls
# haversine_distance(...) - already optimized with LRU cache
```

### 4. Set Up Alerts for Production
```python
# Configure alerting in production
if settings.ENVIRONMENT == 'production':
    spatial_query_monitor.set_alert_callback(send_to_monitoring_system)
```

---

**Generated:** 2025-09-30
**Status:** ✅ Production Ready
**Maintainer:** Backend Team
**Support:** See monitoring team for dashboard access