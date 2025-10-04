# 🚀 Sprint 4 Quick Reference Guide

**Quick access to Sprint 4 mobile sync features**

---

## 📁 File Structure

```
apps/
├── api/v1/
│   ├── services/
│   │   ├── conflict_resolution_service.py      # Conflict auto-resolution
│   │   └── bandwidth_optimization_service.py   # Compression & delta sync
│   ├── views/
│   │   └── sync_queue_views.py                # Queue management endpoints
│   └── tests/
│       ├── test_conflict_resolution.py
│       ├── test_bandwidth_optimization.py
│       └── test_sync_queue.py
└── core/
    ├── models/
    │   ├── sync_conflict_policy.py            # Tenant policies + logs
    │   └── sync_analytics.py                  # Analytics models
    ├── services/
    │   └── sync_analytics_service.py          # Analytics aggregation
    ├── views/
    │   └── sync_analytics_views.py            # Dashboard endpoints
    └── tests/
        └── test_sync_analytics.py
```

---

## ⚡ Quick Start

### 1. Conflict Resolution
```python
from apps.api.v1.services.conflict_resolution_service import ConflictResolutionService

service = ConflictResolutionService()

# Resolve a conflict
result = service.resolve_conflict(
    domain='task',
    server_entry={'mobile_id': 'uuid', 'version': 3, 'status': 'done'},
    client_entry={'mobile_id': 'uuid', 'version': 2, 'status': 'pending'},
    tenant_id=1
)

# Result:
# {
#     'resolution': 'resolved',
#     'winning_entry': {...},
#     'strategy_used': 'most_recent_wins',
#     'merge_details': {...}
# }
```

### 2. Configure Tenant Policy
```python
from apps.core.models.sync_conflict_policy import TenantConflictPolicy

# Set custom policy for a tenant
policy = TenantConflictPolicy.objects.create(
    tenant=tenant,
    domain='task',
    resolution_policy='client_wins',  # Override default
    auto_resolve=True,
    notify_on_conflict=True
)
```

### 3. Sync Analytics
```python
from apps.core.services.sync_analytics_service import SyncAnalyticsService

service = SyncAnalyticsService()

# Create snapshot
snapshot = service.create_snapshot(tenant_id=1, time_window_hours=1)

# Update device health
device = service.update_device_health(
    device_id='device-123',
    user=user,
    sync_success=True,
    sync_duration_ms=150.0,
    conflict_occurred=False
)

# Get dashboard metrics
metrics = service.get_dashboard_metrics(tenant_id=1)
```

### 4. Bandwidth Optimization
```python
from apps.api.v1.services.bandwidth_optimization_service import BandwidthOptimizationService

service = BandwidthOptimizationService()

# Compress payload
compressed = service.compress_payload(data, compression_level='adaptive')

# Calculate delta
delta = service.calculate_delta(server_version, client_version)

# Adaptive batching
batches = service.adaptive_batch_sizing(items, network_quality='good')

# Prioritize items
prioritized = service.prioritize_items(items, priority_field='priority')
```

---

## 🔗 API Endpoints

### Analytics Dashboard
```
GET /api/sync/dashboard/
    Returns: {latest_snapshot, trend_7days, unhealthy_devices, conflict_hotspots}

POST /api/sync/snapshot/create/
    Body: {time_window_hours: 1}
    Returns: {snapshot_id, status, timestamp}

GET /api/sync/device-health/?device_id=...
    Returns: {device_id, health_score, total_syncs, ...}
```

### Queue Management
```
GET /api/v1/sync/queue-status
    Returns: {pending_items, high_priority, estimated_sync_time_sec, queue_healthy}

POST /api/v1/sync/partial
    Body: {priority: 'high', max_items: 10, network_quality: 'good'}
    Returns: {synced_items: [...], remaining: 32}

GET /api/v1/sync/optimal-time
    Returns: {recommendation, server_load, queue_size, is_peak_hour}
```

---

## 📊 Resolution Policies

| Domain | Default Policy | Description |
|--------|---------------|-------------|
| `journal` | `client_wins` | User's device is authoritative |
| `attendance` | `server_wins` | Organization is authoritative |
| `task` | `most_recent_wins` | Latest timestamp wins |
| `ticket` | `preserve_escalation` | Complex merge for critical fields |
| `work_order` | `most_recent_wins` | Latest timestamp wins |

**Available Policies:**
- `client_wins` - Client version always wins
- `server_wins` - Server version always wins
- `most_recent_wins` - Timestamp-based resolution
- `preserve_escalation` - Smart merge preserving critical fields
- `manual` - Requires human intervention

---

## 🧪 Running Tests

```bash
# All Sprint 4 tests
pytest apps/api/v1/tests/test_conflict_resolution.py \
       apps/core/tests/test_sync_analytics.py \
       apps/api/v1/tests/test_bandwidth_optimization.py \
       apps/api/v1/tests/test_sync_queue.py -v

# Conflict resolution only
pytest apps/api/v1/tests/test_conflict_resolution.py -v

# Sync analytics only
pytest apps/core/tests/test_sync_analytics.py -v

# Unit tests only
pytest -m unit apps/api/v1/tests/ apps/core/tests/ -v

# Integration tests only
pytest -m integration apps/api/v1/tests/ apps/core/tests/ -v
```

---

## 🗄️ Database Models

### TenantConflictPolicy
```python
tenant               ForeignKey(Tenant)
domain               CharField (choices: journal, attendance, task, ticket, work_order)
resolution_policy    CharField (choices: client_wins, server_wins, most_recent_wins, ...)
auto_resolve         BooleanField
notify_on_conflict   BooleanField
```

### ConflictResolutionLog
```python
mobile_id            UUIDField
domain               CharField
server_version       IntegerField
client_version       IntegerField
resolution_strategy  CharField
resolution_result    CharField (resolved, manual_required, failed)
winning_version      CharField (client, server, merged, none)
merge_details        JSONField
```

### SyncAnalyticsSnapshot
```python
timestamp                    DateTimeField
total_sync_requests          IntegerField
successful_syncs             IntegerField
failed_syncs                 IntegerField
avg_sync_duration_ms         FloatField
p95_sync_duration_ms         FloatField
total_conflicts              IntegerField
auto_resolved_conflicts      IntegerField
manual_conflicts             IntegerField
conflict_rate_pct            FloatField
bandwidth_efficiency_pct     FloatField
domain_breakdown             JSONField
```

### SyncDeviceHealth
```python
device_id                UUIDField
user                     ForeignKey(People)
last_sync_at             DateTimeField
total_syncs              IntegerField
failed_syncs_count       IntegerField
avg_sync_duration_ms     FloatField
conflicts_encountered    IntegerField
health_score             FloatField (0-100)
network_type             CharField (wifi, 4g, 3g, 2g)
```

---

## 🎯 Common Use Cases

### Use Case 1: Configure Custom Conflict Policy
```python
# Marketing team wants client to always win for journal entries
policy = TenantConflictPolicy.objects.create(
    tenant=marketing_tenant,
    domain='journal',
    resolution_policy='client_wins',
    auto_resolve=True
)
```

### Use Case 2: Monitor Sync Health
```python
# Get unhealthy devices
unhealthy = SyncDeviceHealth.objects.filter(
    health_score__lt=70.0,
    tenant=tenant
).order_by('health_score')

for device in unhealthy:
    print(f"Device {device.device_id}: {device.health_score}%")
    print(f"Failed syncs: {device.failed_syncs_count}/{device.total_syncs}")
```

### Use Case 3: Analyze Conflict Trends
```python
# Get conflict hotspots
from apps.core.models.sync_conflict_policy import ConflictResolutionLog

hotspots = ConflictResolutionLog.objects.filter(
    created_at__gte=timezone.now() - timedelta(days=7)
).values('domain').annotate(
    conflict_count=Count('id')
).order_by('-conflict_count')

for hotspot in hotspots:
    print(f"{hotspot['domain']}: {hotspot['conflict_count']} conflicts")
```

### Use Case 4: Optimize Bandwidth for Poor Network
```python
from apps.api.v1.services.bandwidth_optimization_service import BandwidthOptimizationService

service = BandwidthOptimizationService()

# Client detects poor network
network_quality = 'poor'

# Prioritize high-priority items
prioritized = service.prioritize_items(pending_items)

# Create small batches
batches = service.adaptive_batch_sizing(prioritized, network_quality)
# Returns 10 items per batch for poor network

# Compress each batch
for batch in batches:
    compressed = service.compress_payload({'items': batch}, 'adaptive')
    sync_to_server(compressed['data'])
```

---

## 🔧 Configuration

### Django Settings
```python
# intelliwiz_config/settings/sync.py

SYNC_CONFIG = {
    # Analytics
    'analytics_snapshot_interval_hours': 1,
    'device_health_threshold': 70.0,

    # Queue Management
    'queue_healthy_threshold': 100,
    'high_priority_threshold': 20,

    # Bandwidth Optimization
    'compression_threshold_bytes': 1024,
    'min_compression_ratio': 0.8,

    # Batch Sizes
    'batch_sizes': {
        'excellent': 100,
        'good': 50,
        'fair': 25,
        'poor': 10,
    }
}
```

### Cron Jobs
```bash
# Hourly analytics snapshot
0 * * * * python manage.py create_sync_snapshot --tenant-id=all

# Daily device health check
0 2 * * * python manage.py check_device_health --threshold=70

# Weekly conflict resolution report
0 0 * * 0 python manage.py conflict_resolution_report --days=7
```

---

## 📈 Monitoring

### Key Metrics to Track
1. **Conflict Rate:** `auto_resolved_conflicts / total_conflicts`
2. **Sync Success Rate:** `successful_syncs / total_sync_requests`
3. **Bandwidth Efficiency:** `bytes_saved_via_delta / total_bytes_synced`
4. **Device Health:** Average `health_score` across all devices
5. **Queue Health:** `pending_items < 100 AND high_priority < 20`

### Alerts
```python
# Low sync success rate
if snapshot.success_rate_pct < 90.0:
    alert("Sync success rate below 90%")

# High conflict rate
if snapshot.conflict_rate_pct > 10.0:
    alert("Conflict rate above 10%")

# Unhealthy devices
if SyncDeviceHealth.objects.filter(health_score__lt=50).count() > 10:
    alert("More than 10 devices with health < 50%")
```

---

## 🐛 Troubleshooting

### Problem: High Conflict Rate
**Solution:**
1. Check tenant conflict policies
2. Review client sync frequency
3. Analyze conflict logs for patterns
4. Consider switching to `most_recent_wins` policy

### Problem: Low Device Health Score
**Solution:**
1. Check network quality
2. Review sync error logs
3. Verify server availability
4. Analyze avg_sync_duration_ms

### Problem: Large Queue Size
**Solution:**
1. Use partial sync for high-priority items
2. Schedule syncs during off-peak hours
3. Increase batch sizes for good networks
4. Enable compression for large payloads

---

## 📚 Related Documentation
- `SPRINT4_IMPLEMENTATION_SUMMARY.md` - Full implementation details
- `.claude/rules.md` - Coding guidelines
- `apps/api/v1/services/base_sync_service.py` - Base sync patterns

---

**Last Updated:** September 28, 2025
**Version:** 1.0.0