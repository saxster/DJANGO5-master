# Streaming Anomaly Detection - Quick Start Guide

**Feature**: Real-time streaming anomaly detection for sub-minute detection
**Location**: `/ws/noc/anomaly-stream/`
**Status**: ✅ Production Ready

---

## 🚀 Quick Start

### WebSocket Connection (Frontend)
```javascript
// Connect to streaming anomaly detection
const ws = new WebSocket('ws://localhost:8000/ws/noc/anomaly-stream/');

ws.onopen = () => {
    console.log('Connected to streaming anomaly detection');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch(data.type) {
        case 'connection_established':
            console.log(`Connected to tenant ${data.tenant_id}`);
            console.log(`Max events/sec: ${data.max_events_per_second}`);
            break;

        case 'anomaly_detected':
            console.log(`${data.findings_count} anomalies detected!`);
            console.log(`Detection latency: ${data.detection_latency_ms}ms`);
            data.findings.forEach(finding => {
                showAlert(finding.severity, finding.title, finding.description);
            });
            break;

        case 'event_processed':
            console.log(`Event ${data.event_id} processed - no anomalies`);
            break;

        case 'error':
            console.error(`Error: ${data.message}`);
            break;
    }
};

// Heartbeat to keep connection alive
setInterval(() => {
    ws.send(JSON.stringify({type: 'ping'}));
}, 30000);
```

---

## 📊 Get Metrics (Backend)
```python
from apps.noc.services.streaming_anomaly_service import StreamingAnomalyService

# Get metrics for tenant
metrics = StreamingAnomalyService.get_metrics(tenant_id=1, time_window_minutes=60)

print(f"Total events processed: {metrics['overall']['total_events']}")
print(f"Average latency: {metrics['overall']['avg_latency_ms']}ms")
print(f"Finding rate: {metrics['overall']['overall_finding_rate']}")

# Check latency improvement
improvement = StreamingAnomalyService.get_latency_improvement(tenant_id=1)
print(f"Improvement: {improvement['improvement_factor']}x faster than batch processing")
print(f"Target met: {improvement['target_met']}")  # Should be True (<1 minute)
```

---

## 🔧 Health Check
```python
from apps.noc.services.streaming_anomaly_service import StreamingAnomalyService

# Check system health
status = StreamingAnomalyService.get_health_status()

if status['is_healthy']:
    print("✅ Streaming anomaly detection is healthy")
    print(f"Max events/sec: {status['max_events_per_second']}")
else:
    print(f"❌ Health check failed: {status.get('error')}")
```

---

## 📈 Event Types

The system automatically detects and processes these events:

### 1. Attendance Events
- **Trigger**: `PeopleEventlog` created (check-in/check-out)
- **Detection**: Unusual attendance patterns
- **Example**: Late check-in, missing check-out, unexpected location

### 2. Task Events
- **Trigger**: `Jobneed` created (task/tour assigned)
- **Detection**: Task completion anomalies
- **Example**: Overdue tasks, skipped checkpoints, unusual completion times

### 3. Location Events
- **Trigger**: `Location` created (GPS tracking)
- **Detection**: GPS/movement anomalies
- **Example**: Unexpected movement, geofence violations, location spoofing

---

## ⚙️ Configuration

### Optional Settings Override
```python
# intelliwiz_config/settings/base.py

# Adjust rate limiting (default: 100 events/sec per tenant)
STREAMING_ANOMALY_MAX_EVENTS_PER_SECOND = 150
```

### Channel Layer (Already configured)
```python
# Uses existing Redis channel layer
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

---

## 🧪 Testing

### Run Tests
```bash
# Run streaming anomaly tests
python -m pytest apps/noc/tests/test_streaming_anomaly.py -v

# Run with coverage
python -m pytest apps/noc/tests/test_streaming_anomaly.py --cov=apps.noc.consumers --cov=apps.noc.signals --cov=apps.noc.services
```

### Manual Testing
```bash
# Start development server with WebSocket support
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# In another terminal, connect with websocat
websocat ws://localhost:8000/ws/noc/anomaly-stream/

# Create test event (in Django shell)
from apps.attendance.models import PeopleEventlog
from django.utils import timezone

pel = PeopleEventlog.objects.create(
    people_id=1,
    bu_id=1,
    client_id=1,
    tenant_id=1,
    timein=timezone.now()
)
# Signal will automatically publish to streaming consumer
```

---

## 🐛 Troubleshooting

### Issue: No WebSocket Connection
**Solution**: Ensure Daphne is running (not runserver)
```bash
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

### Issue: Events Not Received
**Check**:
1. Channel layer configured (Redis running)
2. User authenticated (WebSocket requires auth)
3. User has valid `tenant_id`

```python
# Check channel layer
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()
print(f"Channel layer: {channel_layer}")  # Should not be None
```

### Issue: High Latency
**Check**:
1. Redis performance (should be <1ms)
2. AnomalyDetector performance (existing service)
3. Rate limiting not triggered

```python
# Check metrics
metrics = StreamingAnomalyService.get_metrics(tenant_id=1)
print(f"Avg latency: {metrics['overall']['avg_latency_ms']}ms")
# Should be <1000ms
```

---

## 📚 API Reference

### WebSocket Message Types (Client → Server)
```typescript
// Ping (keep-alive)
{type: 'ping'}

// Get statistics
{type: 'get_stats'}
```

### WebSocket Message Types (Server → Client)
```typescript
// Connection established
{
    type: 'connection_established',
    timestamp: '2025-11-03T12:00:00Z',
    tenant_id: '1',
    max_events_per_second: 100
}

// Event processed (no anomalies)
{
    type: 'event_processed',
    timestamp: '2025-11-03T12:00:01Z',
    event_id: 'uuid-here',
    event_type: 'attendance',
    anomalies_found: false,
    detection_latency_ms: 45.2
}

// Anomaly detected
{
    type: 'anomaly_detected',
    timestamp: '2025-11-03T12:00:02Z',
    event_id: 'uuid-here',
    event_type: 'attendance',
    findings_count: 2,
    detection_latency_ms: 52.1,
    findings: [
        {
            id: 'finding-uuid',
            finding_type: 'ANOMALY_PHONE_EVENTS_BELOW',
            category: 'DEVICE_HEALTH',
            severity: 'HIGH',
            title: 'Anomalous phone events detected',
            description: 'Phone events below baseline...',
            evidence: {z_score: -2.5, ...},
            created_at: '2025-11-03T12:00:02Z'
        }
    ]
}

// Error
{
    type: 'error',
    timestamp: '2025-11-03T12:00:03Z',
    message: 'Anomaly detection failed: ...'
}

// Pong (heartbeat response)
{
    type: 'pong',
    timestamp: '2025-11-03T12:00:04Z'
}

// Statistics
{
    type: 'stats',
    uptime_seconds: 3600,
    events_processed: 1523,
    tenant_id: '1',
    group_name: 'anomaly_stream_1'
}
```

---

## 🔗 Related Documentation

- **Master Plan**: `NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md`
- **Implementation Report**: `STREAMING_ANOMALY_DETECTION_IMPLEMENTATION.md`
- **AnomalyDetector Service**: `apps/noc/security_intelligence/services/anomaly_detector.py`
- **Consumer Tests**: `apps/noc/tests/test_streaming_anomaly.py`

---

## 📞 Support

**Issues**: Contact NOC team
**Architecture Questions**: Review implementation report
**Performance Issues**: Check metrics via `StreamingAnomalyService.get_metrics()`

---

**Last Updated**: November 3, 2025
**Version**: 1.0.0
**Status**: Production Ready ✅
