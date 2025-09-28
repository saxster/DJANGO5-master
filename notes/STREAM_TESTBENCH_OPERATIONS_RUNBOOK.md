# 🎯 Stream Testbench Operations Runbook

## 🚨 Emergency Response

### Critical Anomaly Response (Severity: Critical)

#### Immediate Actions (0-5 minutes)
1. **Acknowledge Alert**
   ```bash
   # Check dashboard
   open http://localhost:8000/streamlab/anomalies/

   # View critical anomalies
   python manage.py shell -c "
   from apps.issue_tracker.models import AnomalyOccurrence
   critical = AnomalyOccurrence.objects.filter(
       signature__severity='critical',
       status='new'
   )
   for a in critical:
       print(f'{a.signature.anomaly_type}: {a.endpoint}')
   "
   ```

2. **Stop Affected Test Runs**
   ```bash
   # List running tests
   python manage.py shell -c "
   from apps.streamlab.models import TestRun
   running = TestRun.objects.filter(status='running')
   for r in running:
       print(f'{r.id}: {r.scenario.name}')
   "

   # Stop specific run via dashboard or:
   curl -X POST http://localhost:8000/streamlab/runs/{run_id}/stop/
   ```

3. **Check System Health**
   ```bash
   # Check Django health
   curl http://localhost:8000/health/

   # Check database connections
   python manage.py shell -c "
   from django.db import connection
   with connection.cursor() as cursor:
       cursor.execute('SELECT count(*) FROM pg_stat_activity')
       print(f'DB connections: {cursor.fetchone()[0]}')
   "

   # Check Redis
   redis-cli ping

   # Check MQTT broker
   mosquitto_pub -h localhost -p 1883 -t test/health -m "ping"
   ```

#### Investigation Actions (5-15 minutes)
1. **Analyze Root Cause**
   ```bash
   # View anomaly details
   python manage.py shell -c "
   from apps.issue_tracker.models import AnomalyOccurrence
   recent = AnomalyOccurrence.objects.filter(
       created_at__gte=timezone.now() - timedelta(hours=1)
   ).order_by('-created_at')[:5]

   for a in recent:
       print(f'Type: {a.signature.anomaly_type}')
       print(f'Endpoint: {a.endpoint}')
       print(f'Error: {a.error_message}')
       print(f'Latency: {a.latency_ms}ms')
       print('---')
   "
   ```

2. **Check Fix Suggestions**
   ```bash
   # View suggested fixes
   python manage.py shell -c "
   from apps.issue_tracker.models import FixSuggestion
   high_confidence = FixSuggestion.objects.filter(
       confidence__gte=0.8,
       status='suggested'
   ).order_by('-priority_score')[:5]

   for f in high_confidence:
       print(f'{f.title} (confidence: {f.confidence})')
       print(f'Type: {f.fix_type}')
       print(f'Steps: {len(f.implementation_steps)}')
       print('---')
   "
   ```

3. **Apply Immediate Mitigations**
   ```bash
   # Scale up if resource exhaustion
   # Add rate limiting if overload
   # Enable circuit breakers if cascading failures
   ```

### High Error Rate Response (>5%)

#### Quick Checks
1. **Database Performance**
   ```sql
   -- Check for blocking queries
   SELECT pid, query, state, query_start
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY query_start;

   -- Check locks
   SELECT l.pid, l.mode, l.granted, a.query
   FROM pg_locks l
   JOIN pg_stat_activity a ON l.pid = a.pid
   WHERE NOT l.granted;
   ```

2. **Connection Pool Status**
   ```python
   python manage.py shell -c "
   from django.db import connections
   db = connections['default']
   print(f'Connection info: {db.connection}')
   "
   ```

3. **Redis Memory Usage**
   ```bash
   redis-cli info memory | grep used_memory_human
   redis-cli info clients | grep connected_clients
   ```

#### Mitigation Actions
1. **Reduce Load**
   ```bash
   # Stop non-critical test scenarios
   # Reduce message rates in active tests
   # Enable rate limiting
   ```

2. **Scale Resources**
   ```bash
   # Increase database connections
   # Scale Redis memory
   # Add server instances
   ```

### Memory Leak Detection

#### Monitoring Commands
```bash
# Monitor Python memory usage
python << 'EOF'
import psutil
import os
import time

process = psutil.Process(os.getpid())

for i in range(10):
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.1f} MB")
    time.sleep(10)
EOF

# Monitor Redis memory
redis-cli --latency-history -i 10

# Check for database connection leaks
psql -c "SELECT count(*) as connections, state FROM pg_stat_activity GROUP BY state;"
```

#### Memory Leak Response
1. **Identify Source**
   ```bash
   # Check Django debug toolbar
   # Profile memory usage
   # Review recent code changes
   ```

2. **Immediate Mitigation**
   ```bash
   # Restart workers
   supervisorctl restart streamlab_worker

   # Clear Redis cache
   redis-cli FLUSHDB

   # Restart Django with lower concurrency
   ```

## 📊 Routine Operations

### Daily Health Checks

#### Morning Checklist
```bash
#!/bin/bash
# daily_health_check.sh

echo "🌅 Daily Stream Testbench Health Check"
echo "Date: $(date)"
echo "="*40

# 1. Check service status
echo "🔍 Service Status:"
curl -s http://localhost:8000/health/ | jq .

# 2. Check overnight anomalies
echo "🚨 Overnight Anomalies:"
python manage.py shell -c "
from apps.issue_tracker.models import AnomalyOccurrence
from django.utils import timezone
from datetime import timedelta

last_24h = timezone.now() - timedelta(hours=24)
anomalies = AnomalyOccurrence.objects.filter(
    created_at__gte=last_24h
)
print(f'Total: {anomalies.count()}')
if anomalies.exists():
    for a in anomalies[:5]:
        print(f'  {a.signature.anomaly_type}: {a.endpoint}')
"

# 3. Check performance trends
echo "📈 Performance Trends:"
python manage.py shell -c "
from apps.streamlab.models import StreamEvent
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg

last_24h = timezone.now() - timedelta(hours=24)
events = StreamEvent.objects.filter(timestamp__gte=last_24h)

if events.exists():
    avg_latency = events.aggregate(avg=Avg('latency_ms'))['avg']
    error_rate = events.filter(outcome='error').count() / events.count()
    print(f'  Avg Latency: {avg_latency:.1f}ms')
    print(f'  Error Rate: {error_rate:.1%}')
    print(f'  Total Events: {events.count()}')
else:
    print('  No events in last 24h')
"

# 4. Check disk usage
echo "💿 Disk Usage:"
df -h | grep -E "/(data|var|tmp)"

# 5. Check database size
echo "🗄️ Database Size:"
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE schemaname IN ('streamlab', 'issue_tracker')
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 5
    ''')

    for row in cursor.fetchall():
        print(f'  {row[1]}: {row[2]}')
"

echo "✅ Daily health check complete"
```

### Weekly Maintenance

#### Performance Review
```bash
#!/bin/bash
# weekly_performance_review.sh

echo "📊 Weekly Performance Review"
echo "Week ending: $(date)"
echo "="*40

# Generate performance report
python << 'EOF'
from apps.streamlab.models import TestRun, StreamEvent
from apps.issue_tracker.models import AnomalySignature
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count, Max, Min

week_ago = timezone.now() - timedelta(days=7)

# Test run statistics
runs = TestRun.objects.filter(started_at__gte=week_ago)
print(f"Test Runs This Week: {runs.count()}")

if runs.exists():
    avg_latency = runs.aggregate(avg=Avg('p95_latency_ms'))['avg']
    avg_throughput = runs.aggregate(avg=Avg('throughput_qps'))['avg']
    avg_error_rate = runs.aggregate(avg=Avg('error_rate'))['avg']

    print(f"Average P95 Latency: {avg_latency:.1f}ms")
    print(f"Average Throughput: {avg_throughput:.1f} QPS")
    print(f"Average Error Rate: {(avg_error_rate or 0):.1%}")

# Anomaly trends
anomalies = AnomalySignature.objects.filter(last_seen__gte=week_ago)
print(f"\nAnomalies This Week: {anomalies.count()}")

anomaly_types = anomalies.values('anomaly_type').annotate(
    count=Count('id')
).order_by('-count')[:5]

print("Top Anomaly Types:")
for at in anomaly_types:
    print(f"  {at['anomaly_type']}: {at['count']} occurrences")

# Performance trends
events = StreamEvent.objects.filter(timestamp__gte=week_ago)
if events.exists():
    latency_trend = events.values('timestamp__date').annotate(
        avg_latency=Avg('latency_ms')
    ).order_by('timestamp__date')

    print("\nDaily Latency Trends:")
    for day in latency_trend:
        print(f"  {day['timestamp__date']}: {day['avg_latency']:.1f}ms")
EOF
```

#### Data Cleanup
```bash
#!/bin/bash
# weekly_cleanup.sh

echo "🧹 Weekly Data Cleanup"
echo "="*30

# Clean old stream events (>14 days)
python manage.py shell -c "
from apps.streamlab.models import StreamEvent
from django.utils import timezone
from datetime import timedelta

cutoff = timezone.now() - timedelta(days=14)
old_events = StreamEvent.objects.filter(timestamp__lt=cutoff)
count = old_events.count()

if count > 0:
    print(f'Cleaning {count} old stream events')
    old_events.delete()
    print('✅ Cleanup complete')
else:
    print('No old events to clean')
"

# Clean resolved anomaly occurrences (>30 days)
python manage.py shell -c "
from apps.issue_tracker.models import AnomalyOccurrence
from django.utils import timezone
from datetime import timedelta

cutoff = timezone.now() - timedelta(days=30)
old_occurrences = AnomalyOccurrence.objects.filter(
    status='resolved',
    resolved_at__lt=cutoff
)
count = old_occurrences.count()

if count > 0:
    print(f'Archiving {count} old resolved occurrences')
    # In production, archive before deleting
    old_occurrences.delete()
    print('✅ Archive complete')
else:
    print('No old occurrences to archive')
"

# Vacuum database
echo "🗄️ Database maintenance..."
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('VACUUM ANALYZE streamlab_streamevent')
    cursor.execute('VACUUM ANALYZE issue_tracker_anomalyoccurrence')
    print('✅ Database vacuum complete')
"

# Clear Redis expired keys
redis-cli --scan --pattern "*" | wc -l
echo "Redis keys before cleanup: $(redis-cli --scan --pattern '*' | wc -l)"
redis-cli EVAL "return redis.call('del', unpack(redis.call('keys', ARGV[1])))" 0 "*expired*"
echo "✅ Redis cleanup complete"
```

### Monthly Optimization

#### Performance Optimization Review
```bash
#!/bin/bash
# monthly_optimization.sh

echo "🎯 Monthly Performance Optimization Review"
echo "="*45

# 1. Database index analysis
python manage.py shell -c "
from django.db import connection

with connection.cursor() as cursor:
    # Check unused indexes
    cursor.execute('''
        SELECT schemaname, tablename, indexname, idx_scan
        FROM pg_stat_user_indexes
        WHERE schemaname IN ('streamlab', 'issue_tracker')
        AND idx_scan < 100
        ORDER BY idx_scan
    ''')

    print('Potentially unused indexes:')
    for row in cursor.fetchall():
        print(f'  {row[1]}.{row[2]}: {row[3]} scans')

    # Check missing indexes
    cursor.execute('''
        SELECT query, calls, mean_exec_time
        FROM pg_stat_statements
        WHERE query LIKE '%streamlab%' OR query LIKE '%issue_tracker%'
        ORDER BY mean_exec_time DESC
        LIMIT 5
    ''')

    print('\nSlowest queries:')
    for row in cursor.fetchall():
        print(f'  {row[2]:.2f}ms avg: {row[0][:80]}...')
"

# 2. Memory usage analysis
echo "💾 Memory Usage Analysis:"
python << 'EOF'
import psutil

# System memory
memory = psutil.virtual_memory()
print(f"System Memory: {memory.percent}% used ({memory.used // 1024 // 1024} MB / {memory.total // 1024 // 1024} MB)")

# Django process memory (if running)
for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
    if 'python' in proc.info['name']:
        memory_mb = proc.info['memory_info'].rss / 1024 / 1024
        if memory_mb > 100:  # Only show processes using >100MB
            print(f"Python process {proc.info['pid']}: {memory_mb:.1f} MB")
EOF

# 3. Redis analysis
echo "🔴 Redis Analysis:"
redis-cli info memory | grep -E "(used_memory_human|maxmemory_human|mem_fragmentation_ratio)"
redis-cli info clients | grep connected_clients

# 4. Suggest optimizations
python manage.py shell -c "
from apps.streamlab.models import StreamEvent, TestRun
from apps.issue_tracker.models import AnomalySignature
from django.utils import timezone
from datetime import timedelta

month_ago = timezone.now() - timedelta(days=30)

# Data growth analysis
recent_events = StreamEvent.objects.filter(timestamp__gte=month_ago)
total_events = StreamEvent.objects.count()

print(f'Events last 30 days: {recent_events.count():,}')
print(f'Total events: {total_events:,}')
print(f'Growth rate: {(recent_events.count() / max(total_events - recent_events.count(), 1)):.1f}x')

# Anomaly pattern analysis
signatures = AnomalySignature.objects.filter(last_seen__gte=month_ago)
print(f'Active anomaly patterns: {signatures.count()}')

recurring = signatures.filter(occurrence_count__gt=10)
print(f'Frequently recurring issues: {recurring.count()}')

if recurring.exists():
    print('Top recurring issues:')
    for sig in recurring.order_by('-occurrence_count')[:3]:
        print(f'  {sig.anomaly_type}: {sig.occurrence_count} times')
"
```

## 🔧 Maintenance Procedures

### Database Maintenance

#### Daily Database Health Check
```sql
-- Check table sizes and growth
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables
WHERE schemaname IN ('streamlab', 'issue_tracker')
ORDER BY size_bytes DESC;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname IN ('streamlab', 'issue_tracker')
ORDER BY idx_scan DESC;

-- Check query performance
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%streamlab%' OR query LIKE '%issue_tracker%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

#### Index Optimization
```sql
-- Add recommended indexes based on query patterns
CREATE INDEX CONCURRENTLY idx_streamevents_run_timestamp
ON streamlab_streamevent (run_id, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_streamevents_outcome_timestamp
ON streamlab_streamevent (outcome, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_anomalies_signature_status
ON issue_tracker_anomalyoccurrence (signature_id, status);

-- Monitor index creation
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE schemaname IN ('streamlab', 'issue_tracker')
ORDER BY pg_relation_size(indexname::regclass) DESC;
```

### Redis Maintenance

#### Redis Health Monitoring
```bash
# Daily Redis check
redis-cli info server | grep redis_version
redis-cli info memory | grep -E "(used_memory|maxmemory|fragmentation)"
redis-cli info persistence | grep -E "(rdb_last_save_time|aof_enabled)"

# Check channel layer usage
redis-cli eval "
local keys = redis.call('keys', 'asgi:*')
return #keys
" 0

# Monitor slow queries
redis-cli slowlog get 10
```

#### Redis Optimization
```bash
# Configure memory optimization
redis-cli config set maxmemory-policy allkeys-lru
redis-cli config set save "900 1 300 10 60 10000"

# Monitor memory fragmentation
redis-cli info memory | grep mem_fragmentation_ratio

# If fragmentation > 1.5, restart Redis during maintenance window
```

### Application Monitoring

#### Performance Monitoring Script
```python
#!/usr/bin/env python3
# monitor_performance.py

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.streamlab.models import StreamEvent, TestRun
from apps.issue_tracker.models import AnomalyOccurrence
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count, Max

def generate_performance_report():
    now = timezone.now()
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)
    last_week = now - timedelta(days=7)

    print("📊 Stream Testbench Performance Report")
    print(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # Hourly metrics
    hour_events = StreamEvent.objects.filter(timestamp__gte=last_hour)
    if hour_events.exists():
        hour_stats = hour_events.aggregate(
            avg_latency=Avg('latency_ms'),
            max_latency=Max('latency_ms'),
            total=Count('id')
        )
        hour_errors = hour_events.filter(outcome='error').count()

        print(f"\n🕐 Last Hour ({hour_stats['total']} events):")
        print(f"   Avg Latency: {hour_stats['avg_latency']:.1f}ms")
        print(f"   Max Latency: {hour_stats['max_latency']:.1f}ms")
        print(f"   Error Rate: {(hour_errors / hour_stats['total'] * 100):.1f}%")

    # Daily metrics
    day_events = StreamEvent.objects.filter(timestamp__gte=last_day)
    if day_events.exists():
        day_stats = day_events.aggregate(
            avg_latency=Avg('latency_ms'),
            total=Count('id')
        )
        day_errors = day_events.filter(outcome='error').count()

        print(f"\n📅 Last 24 Hours ({day_stats['total']} events):")
        print(f"   Avg Latency: {day_stats['avg_latency']:.1f}ms")
        print(f"   Error Rate: {(day_errors / day_stats['total'] * 100):.1f}%")

    # Anomaly summary
    week_anomalies = AnomalyOccurrence.objects.filter(created_at__gte=last_week)
    print(f"\n🚨 Anomalies (7 days): {week_anomalies.count()}")

    if week_anomalies.exists():
        by_type = week_anomalies.values('signature__anomaly_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        for item in by_type:
            print(f"   {item['signature__anomaly_type']}: {item['count']}")

    # Active test runs
    active_runs = TestRun.objects.filter(status='running')
    print(f"\n🏃‍♂️ Active Test Runs: {active_runs.count()}")
    for run in active_runs:
        duration = (now - run.started_at).total_seconds()
        print(f"   {run.scenario.name}: {duration:.0f}s running")

if __name__ == "__main__":
    generate_performance_report()
```

## 🛠️ Troubleshooting Guide

### Issue: High Latency Anomalies

#### Diagnosis
```bash
# Check database query performance
python manage.py shell -c "
from django.db import connection
from django.conf import settings

with connection.cursor() as cursor:
    # Enable query logging temporarily
    cursor.execute('SET log_statement = \"all\"')
    cursor.execute('SET log_min_duration_statement = 100')  # Log queries >100ms

    # Check current locks
    cursor.execute('''
        SELECT l.pid, l.mode, l.granted, a.query_start, a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON l.pid = a.pid
        WHERE NOT l.granted
    ''')

    locks = cursor.fetchall()
    if locks:
        print(f'Found {len(locks)} blocking queries')
    else:
        print('No blocking queries found')
"

# Check connection pool
python manage.py shell -c "
from django.db import connections
print(f'Default connection: {connections[\"default\"].connection}')
"
```

#### Resolution
```bash
# Add database indexes
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE INDEX CONCURRENTLY idx_events_latency ON streamlab_streamevent (latency_ms DESC)')
    print('✅ Added latency index')
"

# Optimize queries
# Review and add select_related/prefetch_related
# Consider query result caching
```

### Issue: Memory Leaks

#### Diagnosis
```python
# memory_profiler.py
import tracemalloc
import psutil
import time

tracemalloc.start()

# Monitor memory over time
for i in range(10):
    current, peak = tracemalloc.get_traced_memory()
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024

    print(f"Iteration {i}: {memory_mb:.1f} MB (traced: {current / 1024 / 1024:.1f} MB)")

    # Simulate load
    # ... your test code here ...

    time.sleep(30)

tracemalloc.stop()
```

#### Resolution
```python
# Implement memory management
from django.core.cache import cache

# Clear caches periodically
cache.clear()

# Use database connection pooling
DATABASES['default']['OPTIONS']['MAX_CONNS'] = 20

# Limit queryset sizes
events = StreamEvent.objects.filter(run=run)[:1000]  # Limit to 1000
```

### Issue: WebSocket Connection Failures

#### Diagnosis
```bash
# Test WebSocket connectivity
python << 'EOF'
import asyncio
import websockets
import json

async def test_websocket():
    try:
        uri = "ws://localhost:8000/ws/mobile/sync/?device_id=test_device"
        async with websockets.connect(uri, timeout=10) as ws:
            print("✅ WebSocket connection successful")

            # Send test message
            test_msg = {
                "type": "heartbeat",
                "client_time": "2024-01-01T12:00:00Z"
            }
            await ws.send(json.dumps(test_msg))

            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"✅ Received response: {response[:100]}...")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Invalid status code: {e}")
    except websockets.exceptions.ConnectionRefused:
        print("❌ Connection refused - check if server is running")
    except asyncio.TimeoutError:
        print("❌ Connection timeout - check network")
    except Exception as e:
        print(f"❌ Connection error: {e}")

asyncio.run(test_websocket())
EOF
```

#### Resolution
```bash
# Check server status
ps aux | grep daphne
ps aux | grep manage.py

# Restart ASGI server
pkill -f daphne
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# Check ASGI configuration
python manage.py shell -c "
from django.conf import settings
print(f'ASGI_APPLICATION: {settings.ASGI_APPLICATION}')
print(f'CHANNEL_LAYERS: {settings.CHANNEL_LAYERS}')
"
```

### Issue: MQTT Broker Problems

#### Diagnosis
```bash
# Test MQTT connectivity
mosquitto_sub -h localhost -p 1883 -t test/topic &
sleep 2
mosquitto_pub -h localhost -p 1883 -t test/topic -m "test message"
pkill mosquitto_sub

# Check broker logs
sudo journalctl -u mosquitto -f

# Test from Python
python << 'EOF'
import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc):
    print(f"MQTT connected with result code {rc}")
    client.subscribe("test/response")

def on_message(client, userdata, msg):
    print(f"Received: {msg.topic} {msg.payload.decode()}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect("localhost", 1883, 60)
    client.loop_start()
    time.sleep(2)
    client.publish("test/request", "test message")
    time.sleep(2)
    print("✅ MQTT test successful")
except Exception as e:
    print(f"❌ MQTT test failed: {e}")
finally:
    client.loop_stop()
    client.disconnect()
EOF
```

## 📋 Runbook Checklists

### Pre-Deployment Checklist

- [ ] **Dependencies Updated**
  ```bash
  pip install -r requirements/base.txt
  cd intelliwiz_kotlin && ./gradlew build
  ```

- [ ] **Database Migrations**
  ```bash
  python manage.py makemigrations streamlab issue_tracker
  python manage.py migrate --check
  python manage.py migrate
  ```

- [ ] **Configuration Validation**
  ```bash
  python manage.py check --deploy
  python test_channels_setup.py
  ```

- [ ] **Security Tests**
  ```bash
  python -m pytest apps/streamlab/tests/test_security.py -v
  ```

- [ ] **Performance Baseline**
  ```bash
  python testing/stream_load_testing/spike_test.py
  python testing/stream_load_testing/check_slos.py spike_test_results.json
  ```

### Post-Deployment Verification

- [ ] **Service Health**
  ```bash
  curl http://localhost:8000/health/
  curl http://localhost:8000/streamlab/
  ```

- [ ] **WebSocket Connectivity**
  ```bash
  # Test WebSocket endpoint
  python -c "
  import asyncio
  import websockets

  async def test():
      async with websockets.connect('ws://localhost:8000/ws/mobile/sync/?device_id=health_check') as ws:
          print('✅ WebSocket OK')

  asyncio.run(test())
  "
  ```

- [ ] **MQTT Connectivity**
  ```bash
  mosquitto_pub -h localhost -p 1883 -t health/check -m "deployment verification"
  ```

- [ ] **Dashboard Access**
  ```bash
  curl -u admin:password http://localhost:8000/streamlab/metrics/api/
  ```

- [ ] **Anomaly Detection**
  ```bash
  # Trigger test anomaly
  python manage.py shell -c "
  from apps.issue_tracker.services.anomaly_detector import anomaly_detector
  import asyncio

  test_event = {
      'latency_ms': 500,  # High latency
      'endpoint': 'ws/test',
      'outcome': 'success'
  }

  result = asyncio.run(anomaly_detector.analyze_event(test_event))
  print(f'Anomaly detection: {\"✅ Working\" if result else \"❌ Not working\"}')
  "
  ```

### Incident Response Checklist

#### Severity 1 (Critical)
- [ ] **Immediate Response (0-5 min)**
  - [ ] Acknowledge alert
  - [ ] Check system health
  - [ ] Stop affected test runs
  - [ ] Notify stakeholders

- [ ] **Investigation (5-15 min)**
  - [ ] Identify root cause
  - [ ] Check fix suggestions
  - [ ] Apply immediate mitigations
  - [ ] Document findings

- [ ] **Resolution (15-60 min)**
  - [ ] Implement permanent fix
  - [ ] Verify fix effectiveness
  - [ ] Resume normal operations
  - [ ] Update runbooks

#### Severity 2 (High)
- [ ] **Response (0-15 min)**
  - [ ] Acknowledge alert
  - [ ] Assess impact
  - [ ] Schedule investigation

- [ ] **Investigation (15-60 min)**
  - [ ] Analyze patterns
  - [ ] Review fix suggestions
  - [ ] Plan resolution

- [ ] **Resolution (1-4 hours)**
  - [ ] Implement fix
  - [ ] Test thoroughly
  - [ ] Monitor results

### Weekly Maintenance Checklist

- [ ] **Performance Review**
  ```bash
  bash weekly_performance_review.sh
  ```

- [ ] **Data Cleanup**
  ```bash
  bash weekly_cleanup.sh
  ```

- [ ] **Security Review**
  ```bash
  python -m pytest apps/streamlab/tests/test_security.py
  ```

- [ ] **Anomaly Pattern Analysis**
  ```bash
  python manage.py shell -c "
  from apps.issue_tracker.models import AnomalySignature

  # Review recurring patterns
  recurring = AnomalySignature.objects.filter(
      occurrence_count__gt=5,
      status='active'
  ).order_by('-occurrence_count')

  print('🔄 Recurring Issues:')
  for sig in recurring:
      print(f'  {sig.anomaly_type}: {sig.occurrence_count} times')

      # Check if fixes are available
      fixes = sig.fix_suggestions.filter(confidence__gte=0.8)
      if fixes.exists():
          print(f'    💡 {fixes.count()} high-confidence fixes available')
  "
  ```

- [ ] **Capacity Planning Review**
  - [ ] Review growth trends
  - [ ] Check resource utilization
  - [ ] Plan scaling needs
  - [ ] Update capacity alerts

## 📞 Escalation Procedures

### Level 1: On-Call Engineer
- **Response Time**: 15 minutes
- **Responsibilities**:
  - Acknowledge alerts
  - Apply known fixes
  - Escalate if unresolved in 1 hour

### Level 2: Stream Testbench Team Lead
- **Response Time**: 30 minutes
- **Responsibilities**:
  - Complex problem solving
  - Code changes if needed
  - Coordinate with other teams

### Level 3: Engineering Management
- **Response Time**: 1 hour
- **Responsibilities**:
  - Business impact decisions
  - Resource allocation
  - External communication

### Contact Information
```yaml
contacts:
  on_call_engineer:
    slack: "#stream-testbench-alerts"
    email: "oncall-engineer@company.com"

  team_lead:
    slack: "@stream-lead"
    email: "team-lead@company.com"

  engineering_manager:
    slack: "@eng-manager"
    email: "eng-manager@company.com"
```

---

**This runbook should be reviewed and updated monthly to reflect operational learnings and system changes.**