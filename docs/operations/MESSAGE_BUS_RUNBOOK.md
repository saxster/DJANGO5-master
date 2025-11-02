# Message Bus & Streaming - Operations Runbook

**Last Updated:** November 1, 2025
**Audience:** DevOps, SRE, Production Support
**Version:** 2.0 (Post-Remediation)

---

## Quick Reference

| Service | Start | Stop | Status | Logs |
|---------|-------|------|--------|------|
| **Celery Critical** | `sudo systemctl start celery@critical` | `stop` | `status` | `/var/log/celery/critical.log` |
| **Celery General** | `sudo systemctl start celery@general` | `stop` | `status` | `/var/log/celery/general.log` |
| **Celery ML** | `sudo systemctl start celery@ml_training` | `stop` | `status` | `/var/log/celery/ml_training.log` |
| **MQTT Subscriber** | `sudo systemctl start mqtt-subscriber` | `stop` | `status` | `/var/log/mqtt_subscriber.log` |
| **MQTT Broker** | `sudo systemctl start mosquitto` | `stop` | `status` | `/var/log/mosquitto/mosquitto.log` |
| **Redis** | `sudo systemctl start redis` | `stop` | `status` | `/var/log/redis/redis-server.log` |
| **Django/Daphne** | `sudo systemctl start daphne` | `stop` | `status` | `/var/log/django/daphne.log` |

**Emergency Contacts:**
- DevOps On-Call: [Insert PagerDuty/Phone]
- Architecture Team: [Insert Slack Channel]
- Security Team: [Insert Email/Slack]

---

## Table of Contents

1. [Service Dependencies](#service-dependencies)
2. [Startup Procedures](#startup-procedures)
3. [Shutdown Procedures](#shutdown-procedures)
4. [Health Checks](#health-checks)
5. [Common Issues & Fixes](#common-issues--fixes)
6. [Performance Tuning](#performance-tuning)
7. [Scaling Procedures](#scaling-procedures)
8. [Disaster Recovery](#disaster-recovery)
9. [Monitoring & Alerts](#monitoring--alerts)

---

## Service Dependencies

### Dependency Graph

```
┌──────────────────────────────────────────────────────────┐
│                   Service Dependencies                    │
└──────────────────────────────────────────────────────────┘

                    ┌─────────┐
                    │  Redis  │ (MUST START FIRST)
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  ┌──────────┐    ┌───────────┐    ┌──────────┐
  │ Celery   │    │ Django/   │    │  MQTT    │
  │ Workers  │    │ Daphne    │    │ Broker   │
  └────┬─────┘    └───────────┘    └────┬─────┘
       │                                  │
       │                                  │
       ▼                                  ▼
  ┌──────────┐                     ┌──────────┐
  │ Message  │                     │   MQTT   │
  │   Bus    │                     │Subscriber│
  └──────────┘                     └──────────┘

STARTUP ORDER:
1. Redis (required by all)
2. MQTT Broker (required by subscriber)
3. Django/Daphne (required by Celery tasks)
4. Celery Workers (can start in parallel)
5. MQTT Subscriber (last)

SHUTDOWN ORDER: Reverse of startup
```

---

## Startup Procedures

### Cold Start (All Services Down)

**1. Pre-Flight Checks:**
```bash
# Verify disk space (need > 10% free)
df -h | grep -E '(/$|/var)'

# Verify Redis data directory permissions
ls -la /var/lib/redis/

# Verify MQTT config
mosquitto -c /etc/mosquitto/mosquitto.conf -t

# Verify systemd service files exist
ls -la /etc/systemd/system/{celery@.service,mqtt-subscriber.service,daphne.service}
```

**2. Start Core Services:**
```bash
# Start Redis (wait for ready)
sudo systemctl start redis
sleep 2
redis-cli ping  # Should return PONG

# Start MQTT Broker
sudo systemctl start mosquitto
sleep 1
mosquitto_sub -h localhost -t '$SYS/#' -C 1  # Should connect

# Start Django/Daphne
sudo systemctl start daphne
sleep 3
curl -f http://localhost:8000/monitoring/health/  # Should return 200
```

**3. Start Celery Workers:**
```bash
# Start in priority order (critical first)
sudo systemctl start celery@critical
sleep 2
celery -A intelliwiz_config inspect ping -d celery@critical@$(hostname)

sudo systemctl start celery@high_priority
sudo systemctl start celery@general
sudo systemctl start celery@ml_training

# Verify all workers
celery -A intelliwiz_config inspect active
```

**4. Start MQTT Subscriber:**
```bash
sudo systemctl start mqtt-subscriber
sleep 2
tail -n 20 /var/log/mqtt_subscriber.log | grep "Connected to MQTT Broker"
```

**5. Post-Start Verification:**
```bash
# Run health check script
./scripts/health_check_message_bus.sh

# Check Prometheus metrics
curl http://localhost:8000/metrics/export/ | grep celery_worker

# Verify WebSocket
wscat -c ws://localhost:8000/ws/noc/dashboard/
```

**Expected Startup Time:** 30-60 seconds (cold start)

---

### Warm Start (Redis Already Running)

```bash
# Start services in parallel (Redis already up)
sudo systemctl start mosquitto daphne &
sleep 3

# Start Celery workers in parallel
sudo systemctl start celery@{critical,high_priority,general,ml_training}
sleep 2

# Start MQTT subscriber
sudo systemctl start mqtt-subscriber

# Quick verification
./scripts/health_check_message_bus.sh
```

**Expected Startup Time:** 10-20 seconds (warm start)

---

## Shutdown Procedures

### Graceful Shutdown

**Purpose:** Drain queues before stopping workers

**1. Stop Accepting New Tasks:**
```bash
# Suspend MQTT subscriber (stop accepting new MQTT messages)
sudo systemctl stop mqtt-subscriber

# Optional: Disable Celery beat (stop scheduled tasks)
sudo systemctl stop celerybeat
```

**2. Wait for Queue Drain:**
```bash
# Monitor queue depth
watch -n 5 'celery -A intelliwiz_config inspect active | grep -c "task_id"'

# Typically drains in 30-120 seconds for normal load
# For large backlog, wait up to 10 minutes
```

**3. Stop Workers Gracefully:**
```bash
# Send TERM signal (allows tasks to finish)
sudo systemctl stop celery@critical
sudo systemctl stop celery@high_priority
sudo systemctl stop celery@general

# ML training workers need more time (tasks can be 4hr)
# Send TERM, wait 5min, then KILL if needed
sudo systemctl stop celery@ml_training
```

**4. Stop Supporting Services:**
```bash
sudo systemctl stop daphne
sudo systemctl stop mosquitto

# Redis last (only if full shutdown)
sudo systemctl stop redis
```

**Expected Shutdown Time:** 2-5 minutes (graceful)

---

### Emergency Shutdown

**Use when:** Immediate stop required (security incident, data corruption)

```bash
# Kill all Celery workers immediately
sudo pkill -9 -f celery

# Kill MQTT subscriber
sudo pkill -9 -f mqtt_subscriber

# Stop services forcefully
sudo systemctl kill --signal=SIGKILL daphne
sudo systemctl kill --signal=SIGKILL mosquitto

# Redis stop
sudo systemctl stop redis
```

**Expected Shutdown Time:** < 10 seconds

**⚠️ Warning:** Tasks in progress will be lost. Queues may have incomplete tasks.

**Recovery After Emergency Shutdown:**
1. Check Redis for corrupt data: `redis-cli --rdb /tmp/dump.rdb`
2. Verify MQTT persistence files: `ls -la /var/lib/mosquitto/`
3. Review Celery task states: `celery -A intelliwiz_config inspect reserved`
4. Requeue failed tasks if needed

---

## Health Checks

### Automated Health Checks

**Script:** `scripts/health_check_message_bus.sh`

```bash
#!/bin/bash
# Message Bus Health Check
# Exit 0 = healthy, Exit 1 = unhealthy

set -e

# Redis
redis-cli ping | grep -q PONG || exit 1

# MQTT Broker
mosquitto_sub -h localhost -t '$SYS/broker/uptime' -C 1 -W 2 || exit 1

# Celery Workers
celery -A intelliwiz_config inspect ping -t 5 | grep -q "pong" || exit 1

# MQTT Subscriber
pgrep -f "mqtt_subscriber.py" > /dev/null || exit 1

# WebSocket Channel Layer
python -c "from channels.layers import get_channel_layer; assert get_channel_layer() is not None" || exit 1

# Prometheus Metrics Endpoint
curl -sf http://localhost:8000/metrics/export/ | grep -q celery || exit 1

echo "✅ All message bus components healthy"
exit 0
```

**Run frequency:** Every 60 seconds (systemd timer or cron)

---

### Manual Health Checks

**Check 1: Celery Worker Health**
```bash
# List active tasks
celery -A intelliwiz_config inspect active

# Check queue depths
celery -A intelliwiz_config inspect reserved

# Check worker stats
celery -A intelliwiz_config inspect stats
```

**Check 2: MQTT Subscriber Health**
```bash
# Check process is running
ps aux | grep mqtt_subscriber

# Check recent log entries
tail -n 50 /var/log/mqtt_subscriber.log

# Test message processing
mosquitto_pub -h localhost -t "device/test/telemetry" \
  -m '{"battery": 100, "signal": 95, "timestamp": "'$(date -Is)'"}'

# Verify Celery task was triggered (check logs)
tail -f /var/log/celery/general.log | grep process_device_telemetry
```

**Check 3: WebSocket Health**
```bash
# Connect to WebSocket (requires wscat: npm install -g wscat)
wscat -c "ws://localhost:8000/ws/noc/dashboard/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should receive: {"type": "connected", "tenant_id": X}
```

**Check 4: Circuit Breaker Status**
```bash
# Check circuit breaker states in Redis
redis-cli
> KEYS circuit_breaker:*
> GET circuit_breaker:mqtt_broker
# Should return empty or {"failures": 0}
```

---

## Common Issues & Fixes

### Issue 1: Celery Workers Not Processing Tasks

**Symptoms:**
- Queue depth increasing
- `celery inspect active` shows no tasks
- Workers appear idle

**Diagnosis:**
```bash
# Check worker is registered
celery -A intelliwiz_config inspect registered

# Check worker can reach Redis
redis-cli -h $(grep CELERY_BROKER_URL .env | cut -d'@' -f2 | cut -d':' -f1) ping

# Check for errors in logs
tail -f /var/log/celery/general.log | grep ERROR
```

**Common Causes & Fixes:**

**Cause 1: Worker concurrency exhausted**
```bash
# Check active task count
celery -A intelliwiz_config inspect active | grep -c task_id

# If >= concurrency limit (default 8), scale up:
# Edit /etc/systemd/system/celery@.service
# Change: --concurrency=8 to --concurrency=16
sudo systemctl daemon-reload
sudo systemctl restart celery@general
```

**Cause 2: Tasks stuck in long-running state**
```bash
# Identify stuck tasks
celery -A intelliwiz_config inspect active | grep -A 5 "time_start"

# Revoke stuck task
celery -A intelliwiz_config revoke TASK_ID --terminate

# Kill worker and restart (if revoke doesn't work)
sudo systemctl restart celery@general
```

**Cause 3: Redis connection lost**
```bash
# Test Redis connectivity
redis-cli -h REDIS_HOST ping

# Check network/firewall
telnet REDIS_HOST 6379

# Restart worker to reconnect
sudo systemctl restart celery@general
```

---

### Issue 2: MQTT Subscriber Not Receiving Messages

**Symptoms:**
- MQTT broker shows clients connected
- Subscriber log shows no new messages
- Published messages not triggering Celery tasks

**Diagnosis:**
```bash
# Check subscriber is connected
tail -f /var/log/mqtt_subscriber.log | grep "Connected to MQTT Broker"

# Check subscriptions
mosquitto_sub -h localhost -t '#' -v | head -20

# Publish test message
mosquitto_pub -h localhost -t "device/test/telemetry" \
  -m '{"test": "data"}'
```

**Common Causes & Fixes:**

**Cause 1: Subscriber crashed**
```bash
# Check process status
sudo systemctl status mqtt-subscriber

# Check for Python errors in log
tail -n 100 /var/log/mqtt_subscriber.log | grep -A 10 "Traceback"

# Restart
sudo systemctl restart mqtt-subscriber
```

**Cause 2: Topic whitelist mismatch**
```bash
# Check allowed topics in subscriber.py
grep ALLOWED_TOPIC_PREFIXES apps/mqtt/subscriber.py

# Verify published topic matches allowed prefix
# Example: "custom/topic" would be rejected if not in whitelist
```

**Fix:** Add topic prefix to `ALLOWED_TOPIC_PREFIXES` in `apps/mqtt/subscriber.py`

**Cause 3: MQTT broker ACLs blocking**
```bash
# Check mosquitto ACL config
cat /etc/mosquitto/acl

# Test with authentication
mosquitto_pub -h localhost -u USERNAME -P PASSWORD \
  -t "device/test" -m "test"
```

---

### Issue 3: WebSocket Broadcasts Not Delivered

**Symptoms:**
- Celery task completes
- Metrics show `websocket_broadcast_success`
- WebSocket client doesn't receive message

**Diagnosis:**
```bash
# Check channel layer health
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> channel_layer is not None

# Check Redis DB 2 (channel layer)
redis-cli -n 2
> KEYS channels:*

# Check client is connected and subscribed
# In browser console:
console.log("WebSocket state:", ws.readyState)  // Should be 1 (OPEN)
```

**Common Causes & Fixes:**

**Cause 1: Message type mismatch**
```python
# Task broadcasts with type 'critical_alert'
self.broadcast_to_noc_dashboard(message_type='critical_alert', data={...})

# Consumer must have matching handler:
async def critical_alert(self, event):  # Method name MUST match message type
    ...
```

**Fix:** Ensure consumer has handler method matching message type

**Cause 2: Client not subscribed to group**
```python
# In consumer's connect():
await self.channel_layer.group_add(
    'noc_dashboard',  # Must match broadcast group_name
    self.channel_name
)
```

**Fix:** Verify `group_add()` is called on connect with correct group name

**Cause 3: Channel layer encryption key mismatch**
```bash
# Check production has encryption key set
echo $CHANNELS_ENCRYPTION_KEY  # Should not be empty

# Verify key is valid Fernet key (44 chars, ends with '=')
python -c "from cryptography.fernet import Fernet; Fernet('$CHANNELS_ENCRYPTION_KEY')"
```

---

### Issue 4: Circuit Breaker Stuck Open

**Symptoms:**
- All MQTT publish tasks fail immediately
- Logs show "Circuit breaker open for mqtt_broker"
- MQTT broker is healthy

**Fix:**
```bash
# Option 1: Wait for auto-recovery (5 minutes)
watch -n 10 'redis-cli GET circuit_breaker:mqtt_broker'

# Option 2: Manual reset
redis-cli DEL circuit_breaker:mqtt_broker

# Option 3: Restart worker (clears in-memory state)
sudo systemctl restart celery@external_api
```

**Prevention:**
- Ensure MQTT broker has high availability (mosquitto cluster)
- Increase circuit breaker threshold if false positives occur
- Set up alerts for circuit breaker state changes

---

## Performance Tuning

### Celery Worker Tuning

**Problem:** Tasks processing slowly

**Tuning Options:**

```bash
# Increase concurrency (CPU-bound tasks)
# Edit /etc/systemd/system/celery@.service
--concurrency=16  # Was 8, now 16

# Increase prefetch multiplier (I/O-bound tasks)
--prefetch-multiplier=8  # Was 4, now 8

# Use gevent pool for I/O-heavy tasks
--pool=gevent --concurrency=100

# Increase memory limit per child
--max-memory-per-child=300000  # 300MB (was 200MB)
```

**Reload after changes:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart celery@general
```

---

### Redis Tuning

**Problem:** High memory usage or slow operations

**Tuning Options:**

```bash
# Edit /etc/redis/redis.conf

# Increase max memory (if < 80% physical RAM)
maxmemory 4gb  # Was 2gb

# Change eviction policy (for cache use case)
maxmemory-policy allkeys-lru

# Increase max clients
maxclients 10000  # Was 4096

# Enable persistence (if needed)
save 900 1  # Save after 900s if 1 key changed

# Restart Redis
sudo systemctl restart redis
```

---

### MQTT Broker Tuning

**Problem:** Message delivery delays or client disconnections

**Tuning Options:**

```bash
# Edit /etc/mosquitto/mosquitto.conf

# Increase max queued messages
max_queued_messages 10000  # Was 1000

# Increase max connections
max_connections 10000  # Was 1000

# Enable persistence (for QoS 1/2)
persistence true
persistence_location /var/lib/mosquitto/

# Increase message size limit (if needed)
message_size_limit 10485760  # 10MB

# Restart Mosquitto
sudo systemctl restart mosquitto
```

---

## Scaling Procedures

### Horizontal Scaling (Add Workers)

**When to Scale:**
- Queue depth consistently > 100 tasks
- Worker CPU consistently > 80%
- Task latency > SLA

**Scaling Steps:**

**1. Add new worker node:**
```bash
# On new server
sudo apt-get update
sudo apt-get install -y python3.11 redis-tools

# Copy application code
rsync -av /opt/intelliwiz/ new-server:/opt/intelliwiz/

# Configure systemd services
sudo cp /etc/systemd/system/celery@.service new-server:/etc/systemd/system/

# Start worker
sudo systemctl daemon-reload
sudo systemctl start celery@general
```

**2. Verify new worker joined:**
```bash
celery -A intelliwiz_config inspect ping
# Should show new worker hostname
```

**3. Monitor distribution:**
```bash
celery -A intelliwiz_config inspect active_queues
# Verify tasks distribute across all workers
```

---

### Vertical Scaling (Increase Resources)

**CPU Scaling:**
```bash
# Increase worker concurrency to match vCPUs
celery -A intelliwiz_config worker --concurrency=$(nproc)
```

**Memory Scaling:**
```bash
# Increase Redis maxmemory
redis-cli CONFIG SET maxmemory 8gb

# Increase Celery max-memory-per-child
--max-memory-per-child=500000  # 500MB
```

---

## Disaster Recovery

### Redis Failure

**Scenario:** Redis crashes, all queue data lost

**Recovery Steps:**

**1. Restore Redis from backup:**
```bash
# Stop Redis
sudo systemctl stop redis

# Restore from last RDB snapshot
sudo cp /backup/redis/dump.rdb /var/lib/redis/

# Start Redis
sudo systemctl start redis
```

**2. Verify data integrity:**
```bash
redis-cli
> DBSIZE  # Should show restored key count
> KEYS celery:task*  # Check task data
```

**3. Restart dependent services:**
```bash
sudo systemctl restart celery@{critical,general,ml_training}
sudo systemctl restart daphne
```

**4. Requeue failed tasks (if needed):**
```bash
# Check for tasks that were in-flight during crash
celery -A intelliwiz_config inspect reserved

# Manually requeue if needed
# (Application-specific logic)
```

**Recovery Time:** 5-15 minutes (depends on backup size)

---

### MQTT Broker Failure

**Scenario:** Mosquitto crashes, device messages lost

**Recovery Steps:**

**1. Restart broker:**
```bash
sudo systemctl restart mosquitto
```

**2. Verify clients reconnect:**
```bash
mosquitto_sub -h localhost -t '$SYS/broker/clients/active' -C 1
```

**3. If persistence enabled, verify message queue:**
```bash
ls -lh /var/lib/mosquitto/*.db
# Persistent messages should be restored
```

**4. Restart MQTT subscriber:**
```bash
sudo systemctl restart mqtt-subscriber
```

**Recovery Time:** 1-3 minutes

---

## Monitoring & Alerts

### Critical Alerts (PagerDuty)

```yaml
# Prometheus alert rules

- alert: CeleryWorkersDown
  expr: up{job="celery"} == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Celery workers are down"

- alert: MQTTSubscriberDown
  expr: celery_mqtt_subscriber_connected_total == 0
  for: 2m
  labels:
    severity: critical

- alert: CeleryQueueBacklog
  expr: celery_queue_depth{queue="critical"} > 50
  for: 5m
  labels:
    severity: high

- alert: WebSocketBroadcastFailures
  expr: rate(celery_websocket_broadcast_failure_total[5m]) > 0.05
  for: 5m
  labels:
    severity: high
```

### Dashboards

**Grafana Dashboard:** Message Bus Overview

**Panels:**
1. Celery task rate (tasks/sec by queue)
2. Celery queue depth (by queue)
3. MQTT messages received (by topic prefix)
4. WebSocket connections (active count)
5. Circuit breaker states (open/closed)
6. Task execution latency (p50, p95, p99)

**Access:** `https://grafana.example.com/d/message-bus-overview`

---

## Appendix

### Service Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `celery@.service` | Systemd template for Celery workers | `/etc/systemd/system/` |
| `mqtt-subscriber.service` | Systemd service for MQTT subscriber | `/etc/systemd/system/` |
| `mosquitto.conf` | MQTT broker configuration | `/etc/mosquitto/` |
| `redis.conf` | Redis configuration | `/etc/redis/` |
| `celery_settings.py` | Celery queue/route config | `apps/core/tasks/` |

### Useful Commands

```bash
# View all Celery workers
celery -A intelliwiz_config inspect registered

# View task routes
celery -A intelliwiz_config inspect routes

# Purge all tasks from queue (DANGEROUS)
celery -A intelliwiz_config purge

# Get queue length
celery -A intelliwiz_config inspect reserved | grep -c task_id

# Test MQTT publishing
mosquitto_pub -h localhost -t "test/topic" -m "test"

# Monitor Redis memory
redis-cli INFO memory | grep used_memory_human
```

---

**Document Version:** 2.0
**Last Updated:** November 1, 2025
**Maintainer:** DevOps Team
**Review Cycle:** Monthly or after incidents
