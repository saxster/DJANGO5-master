# 🚀 Stream Testbench - Complete Documentation

## Overview

The **Stream Testbench** is an enterprise-grade real-time stream testing, monitoring, and anomaly detection system designed for Django-Kotlin streaming infrastructure. It provides end-to-end testing capabilities, AI-powered anomaly detection, and comprehensive observability for WebSocket, MQTT, and HTTP streams.

## 🎯 Key Features

### Core Capabilities
- **🔌 Multi-Protocol Support**: WebSocket, MQTT, HTTP/REST testing
- **🧪 Failure Injection**: Network delays, connection drops, schema drift simulation
- **🛡️ PII Protection**: Advanced data redaction with field-level allowlisting
- **🤖 AI Anomaly Detection**: Pattern-based and statistical anomaly detection
- **📊 Real-time Dashboards**: Live monitoring with HTMX and Chart.js
- **🔄 Auto-Fix Suggestions**: AI-generated fix recommendations
- **📈 Performance SLOs**: Automated SLO validation and regression detection
- **🗄️ Knowledge Base**: Issue tracking with recurrence analysis

### Security & Compliance
- **GDPR-Ready**: Data minimization and right to deletion
- **PII Redaction**: Automatic removal/hashing of sensitive data
- **Retention Policies**: Configurable data retention (14-90 days)
- **Access Controls**: Staff-only dashboards with audit logging
- **Encryption**: TLS in transit, optional field-level encryption

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Kotlin Load   │    │     Django      │    │   PostgreSQL    │
│   Generators    │───▶│  Stream Tests   │───▶│   + Redis DB    │
│                 │    │                 │    │                 │
│ • WebSocket     │    │ • Event Capture │    │ • Event Storage │
│ • MQTT Client   │    │ • PII Redaction │    │ • Metrics Cache │
│ • HTTP Client   │    │ • Anomaly Det.  │    │ • Channel Layer │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   Monitoring    │              │
         └──────────────┤   Dashboard     │◀─────────────┘
                        │                 │
                        │ • Live Metrics  │
                        │ • Anomaly Alerts│
                        │ • Fix Tracking  │
                        └─────────────────┘
```

### Data Flow

1. **Load Generation**: Kotlin generates realistic stream data
2. **Event Capture**: Django captures all stream events with PII redaction
3. **Anomaly Detection**: AI analyzes events for patterns and issues
4. **Fix Suggestions**: System generates actionable fix recommendations
5. **Dashboard Updates**: Real-time visualization of metrics and anomalies
6. **Knowledge Base**: Historical tracking and recurrence analysis

## 🚀 Quick Start

### 1. Installation

```bash
# Install Python dependencies
pip install -r requirements/base.txt

# Run database migrations
python manage.py migrate

# Install Kotlin dependencies
cd intelliwiz_kotlin
./gradlew build
```

### 2. Configuration

Add to your Django settings:

```python
# Enable Channels and Stream Testbench
INSTALLED_APPS += [
    'channels',
    'daphne',
    'apps.streamlab',
    'apps.issue_tracker',
]

# Configure Redis Channel Layer (DB 2 for isolation)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://127.0.0.1:6379/2"],
            "capacity": 10000,
            "expiry": 60
        }
    }
}

# Set ASGI application
ASGI_APPLICATION = "intelliwiz_config.asgi.application"
```

### 3. Create Test Scenario

```bash
# Generate example scenarios
cd intelliwiz_kotlin
./gradlew run --args="generate --type all --output ../scenarios/"

# Create custom scenario
python manage.py shell
>>> from apps.streamlab.models import TestScenario
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.first()
>>> scenario = TestScenario.objects.create(
...     name="My First Test",
...     protocol="websocket",
...     endpoint="ws://localhost:8000/ws/mobile/sync/",
...     expected_p95_latency_ms=100,
...     expected_error_rate=0.05,
...     created_by=user
... )
```

### 4. Run Tests

```bash
# Start Django server with ASGI
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# Run load test
cd intelliwiz_kotlin
java -jar build/libs/intelliwiz_kotlin-1.0.0-fat.jar \
  run --scenario ../scenarios/websocket_load_test.json

# Or use Django management command
python manage.py run_scenario "My First Test" --duration 60
```

### 5. Monitor Results

```bash
# View dashboard
open http://localhost:8000/streamlab/

# Check anomalies
open http://localhost:8000/streamlab/anomalies/

# Admin interface
open http://localhost:8000/admin/streamlab/
```

## 📋 Detailed Usage

### Test Scenario Configuration

Create test scenarios through Django admin or programmatically:

```python
from apps.streamlab.models import TestScenario

scenario = TestScenario.objects.create(
    name="High-Load WebSocket Test",
    description="Test WebSocket under high concurrent load",
    protocol="websocket",
    endpoint="ws://localhost:8000/ws/mobile/sync/",
    config={
        "connections": 100,
        "duration_seconds": 300,
        "messages_per_second": 15,
        "failure_injection": {
            "enabled": True,
            "network_delays": {"probability": 0.05}
        }
    },
    pii_redaction_rules={
        "allowlisted_fields": ["quality_score", "timestamp"],
        "hash_fields": ["user_id", "device_id"]
    },
    expected_p95_latency_ms=100,
    expected_error_rate=0.01,
    created_by=user
)
```

### Kotlin Load Generator

```bash
# Quick WebSocket test
java -jar streamtestbench.jar run \
  --protocol websocket \
  --endpoint localhost:8000/ws/mobile/sync/ \
  --duration 60 \
  --connections 10 \
  --rate 5

# MQTT load test
java -jar streamtestbench.jar run \
  --protocol mqtt \
  --endpoint localhost:1883 \
  --duration 120 \
  --connections 5 \
  --rate 3

# Run from scenario file
java -jar streamtestbench.jar run \
  --scenario scenarios/mobile_sync_stress.json \
  --output results.json

# Generate scenarios
java -jar streamtestbench.jar generate \
  --type all \
  --output my-scenarios/
```

### Anomaly Detection Configuration

Edit `apps/issue_tracker/rules/anomalies.yaml`:

```yaml
rules:
  - name: custom_latency_rule
    condition:
      latency_ms: {gt: 200}
      endpoint: {contains: "critical"}
    severity: error
    anomaly_type: critical_latency
    fixes:
      - type: index
        suggestion: "Add database index for critical path"
        confidence: 0.9
```

### Dashboard Usage

1. **Main Dashboard** (`/streamlab/`):
   - Live metrics for active test runs
   - Real-time charts (throughput, latency, error rates)
   - Test run management

2. **Anomaly Dashboard** (`/streamlab/anomalies/`):
   - Active anomaly signatures
   - Recent occurrences with timeline
   - Fix suggestions with confidence scores

3. **Admin Interface** (`/admin/streamlab/`):
   - Test scenario management
   - Detailed event inspection
   - Anomaly signature configuration

## 🔧 Operations

### Running Tests

#### Command Line (Kotlin)
```bash
# Single protocol test
java -jar streamtestbench.jar run \
  --protocol websocket \
  --endpoint localhost:8000/ws/mobile/sync/ \
  --duration 300 \
  --connections 50 \
  --rate 10 \
  --output results.json

# Validate scenario file
java -jar streamtestbench.jar validate scenarios/my_test.json

# Generate baseline scenarios
java -jar streamtestbench.jar generate --type all
```

#### Django Management Commands
```bash
# Run scenario by name
python manage.py run_scenario "Mobile Sync Load Test" --duration 300

# List available scenarios
python manage.py shell -c "
from apps.streamlab.models import TestScenario
for s in TestScenario.objects.filter(is_active=True):
    print(f'{s.name} ({s.protocol})')
"
```

#### Dashboard Interface
1. Navigate to `/streamlab/`
2. Select a scenario from admin panel
3. Click "Start Test" in dashboard
4. Monitor real-time metrics
5. Stop test when complete

### Monitoring and Alerting

#### Real-time Monitoring
- **Live Metrics**: Updates every 5 seconds via HTMX
- **WebSocket Updates**: Real-time anomaly alerts
- **Chart Visualization**: Throughput, latency, error rates

#### Alert Configuration
```python
from monitoring.real_time_alerts import performance_alerts

# Create custom alert
performance_alerts.slow_query_alert(
    sql="SELECT * FROM large_table WHERE ...",
    duration=2.5,
    threshold=1.0,
    request_path="/api/slow-endpoint"
)
```

#### SLO Monitoring
- **Automated Validation**: SLOs checked on every test run
- **Regression Detection**: Compare against baseline performance
- **CI/CD Gates**: Fail builds on SLO violations

### Anomaly Management

#### Viewing Anomalies
1. **Dashboard**: `/streamlab/anomalies/` for overview
2. **Admin Panel**: `/admin/issue_tracker/` for detailed management
3. **API**: `/streamlab/metrics/api/` for programmatic access

#### Resolving Anomalies
1. **Investigate**: Review occurrence details and stack traces
2. **Apply Fix**: Use suggested fixes or create custom solutions
3. **Verify**: Monitor recurrence after fix application
4. **Document**: Update knowledge base with resolution notes

#### Fix Suggestions
- **Auto-Generated**: AI creates suggestions based on patterns
- **Confidence Scoring**: 0.0-1.0 confidence for each suggestion
- **Risk Assessment**: Low/Medium/High risk categorization
- **Implementation Steps**: Detailed step-by-step guides

### Data Management

#### PII Protection
- **Automatic Redaction**: Sensitive data removed at capture boundary
- **Field Allowlisting**: Only explicitly allowed fields are stored
- **ID Hashing**: User/device IDs hashed with rotating salt
- **Location Bucketing**: GPS coordinates bucketed to city level

#### Data Retention
- **Raw Payloads**: Never stored (PII protection)
- **Sanitized Metadata**: 14 days
- **Stack Traces/Logs**: 30 days
- **Aggregated Metrics**: 90 days
- **Archived Data**: Compressed storage with TTL

#### Cleanup Commands
```bash
# Manual cleanup
python manage.py shell -c "
from apps.streamlab.models import StreamEvent
from django.utils import timezone
from datetime import timedelta

# Clean events older than 14 days
cutoff = timezone.now() - timedelta(days=14)
old_events = StreamEvent.objects.filter(timestamp__lt=cutoff)
print(f'Cleaning {old_events.count()} old events')
old_events.delete()
"
```

## 🔧 Troubleshooting

### Common Issues

#### WebSocket Connection Issues
```bash
# Check server status
curl -I http://localhost:8000/health/

# Test WebSocket endpoint
python << 'EOF'
import asyncio
import websockets

async def test_ws():
    try:
        async with websockets.connect("ws://localhost:8000/ws/mobile/sync/?device_id=test") as ws:
            print("✅ WebSocket connection successful")
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

asyncio.run(test_ws())
EOF
```

#### MQTT Connection Issues
```bash
# Test MQTT broker
mosquitto_pub -h localhost -p 1883 -t test/topic -m "test message"

# Check MQTT client logs
python apps/mqtt/client.py
```

#### Database Performance Issues
```bash
# Run database performance test
python testing/load_testing/database_performance_test.py

# Check PostgreSQL stats
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('SELECT count(*) FROM pg_stat_activity')
    print(f'Active connections: {cursor.fetchone()[0]}')
"
```

#### High Memory Usage
```bash
# Monitor Django memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"

# Check Redis memory usage
redis-cli info memory
```

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes for frequently queried fields
CREATE INDEX CONCURRENTLY idx_stream_events_correlation
ON streamlab_streamevent (correlation_id);

CREATE INDEX CONCURRENTLY idx_stream_events_timestamp
ON streamlab_streamevent (timestamp DESC);

CREATE INDEX CONCURRENTLY idx_anomaly_occurrences_created
ON issue_tracker_anomalyoccurrence (created_at DESC);
```

#### Django Settings Optimization
```python
# Optimize for high-throughput streaming
DATABASES['default']['OPTIONS'].update({
    'MAX_CONNS': 50,
    'MIN_CONNS': 10,
    'CONN_MAX_AGE': 600,
})

# Channel layer optimization
CHANNEL_LAYERS['default']['CONFIG'].update({
    'capacity': 50000,    # Increase capacity
    'expiry': 30,         # Reduce expiry for memory
})
```

#### Redis Optimization
```bash
# Redis configuration for high throughput
echo "
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-keepalive 300
timeout 300
" >> /etc/redis/redis.conf
```

### Debugging

#### Enable Debug Logging
```python
# Add to Django settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'streamlab_debug.log',
        },
    },
    'loggers': {
        'streamlab': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'issue_tracker': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

#### View Event Details
```python
# Django shell debugging
python manage.py shell

from apps.streamlab.models import StreamEvent, TestRun
from apps.issue_tracker.models import AnomalyOccurrence

# Latest events
events = StreamEvent.objects.order_by('-timestamp')[:10]
for event in events:
    print(f"{event.timestamp}: {event.endpoint} - {event.outcome} ({event.latency_ms}ms)")

# Active anomalies
anomalies = AnomalyOccurrence.objects.filter(status='new')
for anomaly in anomalies:
    print(f"{anomaly.signature.anomaly_type}: {anomaly.endpoint}")
```

## 📈 Performance Benchmarks

### Expected Performance

#### WebSocket Streams
- **Throughput**: 1000+ msgs/sec per server instance
- **Latency**: P95 < 50ms, P99 < 100ms
- **Connections**: 10K+ concurrent connections
- **Error Rate**: < 0.1% under normal load

#### MQTT Messages
- **Throughput**: 500+ msgs/sec per broker instance
- **Latency**: P95 < 100ms, P99 < 200ms
- **Topics**: 1000+ concurrent topics
- **Error Rate**: < 0.5% under normal load

#### Database Performance
- **Event Ingestion**: 10K+ events/sec
- **Query Response**: P95 < 20ms for simple queries
- **Anomaly Detection**: < 5ms per event analysis
- **Dashboard Updates**: < 100ms for metrics calculation

### SLO Definitions

```yaml
# Default SLOs by protocol
websocket:
  max_error_rate: 0.01          # 1%
  max_p95_latency_ms: 100       # 100ms
  min_throughput_qps: 10        # 10 QPS

mqtt:
  max_error_rate: 0.02          # 2%
  max_p95_latency_ms: 200       # 200ms
  min_throughput_qps: 5         # 5 QPS

http:
  max_error_rate: 0.005         # 0.5%
  max_p95_latency_ms: 300       # 300ms
  min_throughput_qps: 20        # 20 QPS
```

## 🛡️ Security

### PII Protection Policies

#### Data Classification
- **Level 1 (Keep)**: Quality scores, timestamps, event types, performance metrics
- **Level 2 (Hash)**: User IDs, device IDs, session IDs, correlation IDs
- **Level 3 (Bucket)**: GPS coordinates (city-level accuracy)
- **Level 4 (Remove)**: Voice samples, images, free text, precise locations, credentials

#### Implementation
```python
# Custom PII rules per endpoint
scenario.pii_redaction_rules = {
    "allowlisted_fields": [
        "quality_score", "duration_ms", "timestamp",
        "event_type", "confidence_score"
    ],
    "hash_fields": ["user_id", "device_id", "session_id"],
    "remove_fields": [
        "voice_sample", "audio_data", "image_data",
        "full_name", "email", "phone_number", "address"
    ]
}
```

#### Compliance Features
- **GDPR Right to Deletion**: Automated data removal by user ID hash
- **Data Minimization**: Only necessary data stored
- **Retention Enforcement**: Automatic cleanup after TTL
- **Audit Logging**: All access logged with correlation IDs

### Access Controls

#### Role-Based Access
- **Superusers**: Full access to all features
- **Staff Users**: Dashboard access, test management
- **Regular Users**: No access to Stream Testbench
- **API Keys**: Programmatic access with rate limiting

#### Implementation
```python
# View decorators
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def dashboard_view(request):
    # Dashboard logic

# WebSocket authentication
class StreamMetricsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not (self.scope["user"].is_staff or self.scope["user"].is_superuser):
            await self.close(code=4403)
```

## 🔄 CI/CD Integration

### GitHub Actions Workflows

#### 1. Stream Health Check (PR Gate)
- **Trigger**: Pull requests
- **Duration**: ~5 minutes
- **Tests**: Quick spike test, unit tests, security validation
- **SLO Gates**: Fail if error rate > 10% or P95 latency > 2s

#### 2. Nightly Soak Test
- **Trigger**: Daily at 2 AM UTC
- **Duration**: 2-8 hours configurable
- **Tests**: Extended load, memory stability, connection durability
- **Alerting**: Create GitHub issue on failure

#### 3. Performance Regression Detection
- **Trigger**: Main branch pushes, PRs
- **Comparison**: Against baseline performance metrics
- **Thresholds**: >15% latency increase or >50% error rate increase
- **Action**: Block merge on significant regressions

### Local CI Setup
```bash
# Run full test suite
python run_stream_tests.py

# Run specific test phases
python -m pytest apps/streamlab/tests/ -v
python -m pytest apps/issue_tracker/tests/ -v

# Performance validation
python testing/stream_load_testing/spike_test.py
python testing/stream_load_testing/check_slos.py results.json
```

## 🎛️ Advanced Configuration

### Custom Anomaly Rules

Create custom rules in `apps/issue_tracker/rules/anomalies.yaml`:

```yaml
rules:
  - name: custom_business_rule
    description: "Critical business process monitoring"
    condition:
      endpoint: {contains: "critical-business-process"}
      latency_ms: {gt: 50}  # Lower threshold for critical processes
    severity: critical
    anomaly_type: business_critical_latency
    tags: ["business_critical", "sla"]
    fixes:
      - type: infrastructure
        suggestion: "Scale critical process infrastructure immediately"
        confidence: 0.95
      - type: caching
        suggestion: "Implement aggressive caching for critical path"
        confidence: 0.85
```

### Custom Fix Templates

Add to `apps/issue_tracker/services/fix_suggester.py`:

```python
'custom_optimization': {
    'template': '''
# Custom optimization template
class OptimizedView(APIView):
    @method_decorator(cache_page(300))  # 5 minute cache
    def get(self, request):
        # Optimized logic here
        pass
''',
    'steps': [
        'Identify optimization opportunity',
        'Implement caching layer',
        'Add monitoring and alerting',
        'Verify performance improvement'
    ],
    'risk_level': 'low',
    'auto_applicable': False
}
```

### Dashboard Customization

#### Add Custom Metrics
```python
# In apps/streamlab/views.py
def custom_metrics_api(request):
    # Calculate custom business metrics
    custom_data = {
        'business_metric_1': calculate_business_metric(),
        'sla_compliance': check_sla_compliance(),
        'cost_per_transaction': calculate_cost_metrics()
    }
    return JsonResponse(custom_data)
```

#### Custom Chart Types
```javascript
// In dashboard template
function initializeCustomChart(data) {
    const ctx = document.getElementById('customChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Success', 'Errors', 'Timeouts'],
            datasets: [{
                data: [data.success, data.errors, data.timeouts],
                backgroundColor: ['#28a745', '#dc3545', '#ffc107']
            }]
        }
    });
}
```

## 🚀 Deployment

### Production Deployment

#### 1. Infrastructure Requirements
- **PostgreSQL 14+** with PostGIS
- **Redis 7+** for channel layer and caching
- **MQTT Broker** (Eclipse Mosquitto or similar)
- **Reverse Proxy** (Nginx) with WebSocket support

#### 2. Django Configuration
```python
# Production settings
ALLOWED_HOSTS = ['your-domain.com']
DEBUG = False

# Use production Redis
CHANNEL_LAYERS['default']['CONFIG']['hosts'] = [
    'redis://prod-redis:6379/2'
]

# Production database
DATABASES['default'] = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': 'youtility_prod',
    'OPTIONS': {
        'MAX_CONNS': 100,
        'MIN_CONNS': 20,
    }
}
```

#### 3. Nginx Configuration
```nginx
# WebSocket proxy
location /ws/ {
    proxy_pass http://django_asgi;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;
}

# Dashboard static files
location /streamlab/static/ {
    alias /app/staticfiles/streamlab/;
    expires 30d;
}
```

#### 4. Process Management (Supervisor)
```ini
[program:daphne]
command=daphne -b 0.0.0.0 -p 8001 intelliwiz_config.asgi:application
directory=/app
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/daphne.log

[program:streamlab_worker]
command=python manage.py run_monitoring_worker
directory=/app
user=www-data
autostart=true
autorestart=true
```

### Docker Deployment

```dockerfile
# Dockerfile for Stream Testbench
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt /tmp/
RUN pip install -r /tmp/base.txt

# Copy application
COPY . /app/
WORKDIR /app

# Run migrations and collect static files
RUN python manage.py migrate --run-syncdb
RUN python manage.py collectstatic --noinput

# Expose ports
EXPOSE 8000 8001

# Start ASGI server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "intelliwiz_config.asgi:application"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  django:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/youtility
      - REDIS_URL=redis://redis:6379/2
    depends_on:
      - db
      - redis
      - mqtt

  db:
    image: postgis/postgis:14-3.2
    environment:
      POSTGRES_DB: youtility
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes

  mqtt:
    image: eclipse-mosquitto:2.0
    ports:
      - "1883:1883"
```

## 📚 API Reference

### Django Models

#### TestScenario
```python
# Create scenario
scenario = TestScenario.objects.create(
    name="API Load Test",
    protocol="websocket",
    endpoint="ws://api.example.com/stream/",
    config={
        "duration_seconds": 300,
        "connections": 50,
        "rates": {"messagesPerSecond": 10.0}
    },
    expected_p95_latency_ms=100,
    expected_error_rate=0.01,
    created_by=request.user
)
```

#### StreamEvent
```python
# Query events
recent_events = StreamEvent.objects.filter(
    timestamp__gte=timezone.now() - timedelta(hours=1),
    outcome='success'
).order_by('-latency_ms')[:10]

# Anomaly events
anomaly_events = StreamEvent.objects.filter(
    outcome='anomaly',
    latency_ms__gt=100
)
```

#### AnomalySignature
```python
# Active anomalies
active_anomalies = AnomalySignature.objects.filter(
    status='active',
    severity__in=['critical', 'error']
)

# Recurring issues
recurring = AnomalySignature.objects.filter(
    occurrence_count__gt=5
)
```

### REST API Endpoints

```bash
# Get live metrics
curl http://localhost:8000/streamlab/metrics/api/

# Dashboard data
curl http://localhost:8000/streamlab/metrics/live/

# Start scenario (requires authentication)
curl -X POST http://localhost:8000/streamlab/scenarios/{uuid}/start/ \
  -H "Authorization: Bearer {token}"
```

### WebSocket API

```javascript
// Connect to metrics stream
const ws = new WebSocket('ws://localhost:8000/ws/streamlab/metrics/');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'metrics_update') {
        updateDashboard(data.data);
    }
};

// Request specific metrics
ws.send(JSON.stringify({type: 'get_metrics'}));
```

## 🎓 Best Practices

### Test Design
1. **Realistic Scenarios**: Model actual user behavior patterns
2. **Gradual Ramp**: Include ramp-up/ramp-down periods
3. **Failure Injection**: Test resilience with chaos engineering
4. **Multiple Protocols**: Test protocol interactions
5. **Long-running Tests**: Include soak tests for stability

### Anomaly Detection
1. **Baseline Establishment**: Run baseline tests before changes
2. **Threshold Tuning**: Adjust thresholds based on historical data
3. **False Positive Management**: Regularly review and tune rules
4. **Business Context**: Include business-critical paths in monitoring
5. **Escalation Paths**: Define clear escalation for critical anomalies

### Performance Monitoring
1. **Continuous Monitoring**: Always-on performance tracking
2. **Trend Analysis**: Track performance trends over time
3. **Capacity Planning**: Use metrics for infrastructure planning
4. **Alert Fatigue**: Balance sensitivity with actionability
5. **Business Metrics**: Include business KPIs in monitoring

### Security
1. **PII Minimization**: Only store necessary data
2. **Access Auditing**: Log all dashboard access
3. **Regular Reviews**: Periodic security and privacy reviews
4. **Incident Response**: Clear procedures for security incidents
5. **Compliance Checks**: Regular compliance validation

## 🆘 Support

### Getting Help
1. **Documentation**: Check this guide and inline documentation
2. **Logs**: Review Django and component logs
3. **Admin Panel**: Use Django admin for detailed inspection
4. **Test Scripts**: Run diagnostic test scripts
5. **GitHub Issues**: Report bugs and feature requests

### Contributing
1. **Code Style**: Follow Django and Kotlin conventions
2. **Testing**: Add tests for new features
3. **Documentation**: Update docs for changes
4. **Security**: Follow security best practices
5. **Performance**: Validate performance impact

### Maintenance
1. **Regular Updates**: Keep dependencies updated
2. **Database Cleanup**: Monitor and clean old data
3. **Performance Review**: Monthly performance reviews
4. **Security Audits**: Quarterly security assessments
5. **Capacity Planning**: Monitor growth and scale accordingly

---

**Stream Testbench** provides enterprise-grade stream testing with comprehensive monitoring, anomaly detection, and security features. For additional support, refer to the Django admin panel, component logs, and the troubleshooting guide above.