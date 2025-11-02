# Message Bus Architecture - Production Deployment Checklist

**Version:** 1.0
**Date:** November 1, 2025
**Deployment Type:** Complete Message Bus Remediation (100%)
**Estimated Deployment Time:** 2-3 hours

---

## Pre-Deployment Checklist

### Environment Verification

- [ ] **Python 3.11.9** installed and active
- [ ] **Redis 7.x** running with TLS enabled (production)
- [ ] **PostgreSQL 14.2** running with PostGIS extension
- [ ] **Mosquitto 2.x** MQTT broker installed
- [ ] **Virtual environment** activated
- [ ] **All dependencies** installed (`requirements/base-*.txt`, `observability.txt`, `encryption.txt`)

### Configuration Files

- [ ] **.env.production** exists with all required variables:
  ```bash
  # WebSocket Encryption (MANDATORY)
  CHANNELS_ENCRYPTION_KEY=<44-char Fernet key>

  # MQTT Broker
  MQTT_BROKER_ADDRESS=<broker-host>
  MQTT_BROKER_PORT=1883
  MQTT_BROKER_USERNAME=<username>
  MQTT_BROKER_PASSWORD=<password>

  # Alert Notifications (optional)
  ALERT_EMAIL_RECIPIENTS=supervisor1@example.com,supervisor2@example.com
  ALERT_SMS_RECIPIENTS=+919876543210,+918765432109
  TWILIO_ACCOUNT_SID=<sid>
  TWILIO_AUTH_TOKEN=<token>
  TWILIO_PHONE_NUMBER=+1234567890
  FCM_SERVER_KEY=<fcm-key>

  # Prometheus (optional)
  PROMETHEUS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16
  ```

- [ ] **Generate encryption key** if missing:
  ```bash
  python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  ```

### Code Verification

- [ ] **Git status clean** (all changes committed)
- [ ] **Tests pass**: `pytest tests/integration/test_message_bus_pipeline.py -v`
- [ ] **No syntax errors**: `python -m py_compile apps/mqtt/*.py background_tasks/mqtt_handler_tasks.py`
- [ ] **Import check**: `python manage.py check --deploy`

---

## Deployment Steps

### Step 1: Database Migrations (15 minutes)

```bash
# Activate virtual environment
source venv/bin/activate  # or your venv path

# Create MQTT model migrations
python manage.py makemigrations mqtt

# Review migration files
cat apps/mqtt/migrations/0001_initial.py

# Apply migrations (TEST ENVIRONMENT FIRST!)
python manage.py migrate mqtt --database=default

# Verify models created
python manage.py dbshell
\dt mqtt_*
# Should show: mqtt_device_telemetry, mqtt_guard_location, mqtt_sensor_reading, mqtt_device_alert
\q
```

**Rollback if issues:**
```bash
python manage.py migrate mqtt zero
```

---

### Step 2: Deploy Code (10 minutes)

```bash
# Pull latest code
git pull origin main

# Install any new dependencies
pip install -r requirements/base-linux.txt

# Collect static files (if needed)
python manage.py collectstatic --noinput

# Restart Django/Daphne
sudo systemctl restart daphne
```

---

### Step 3: Deploy MQTT Subscriber (15 minutes)

```bash
# Copy systemd service file
sudo cp scripts/systemd/mqtt-subscriber.service /etc/systemd/system/

# IMPORTANT: Update paths in service file for your environment
sudo nano /etc/systemd/system/mqtt-subscriber.service
# Change:
#   WorkingDirectory=/opt/intelliwiz  → YOUR_PATH
#   ExecStart=/opt/intelliwiz/venv/bin/python → YOUR_PATH

# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable mqtt-subscriber

# Start service
sudo systemctl start mqtt-subscriber

# Verify started
sudo systemctl status mqtt-subscriber
tail -f /var/log/mqtt_subscriber.log  # Should show "Connected to MQTT Broker"
```

---

### Step 4: Restart Celery Workers (10 minutes)

```bash
# Restart workers to load new task routes
sudo systemctl restart celery@critical
sudo systemctl restart celery@high_priority
sudo systemctl restart celery@general
sudo systemctl restart celery@ml_training  # If ML training is active

# Verify workers registered
celery -A intelliwiz_config inspect registered

# Check new MQTT handler tasks are registered
celery -A intelliwiz_config inspect registered | grep mqtt_handler_tasks
# Should show:
#   - background_tasks.mqtt_handler_tasks.process_device_telemetry
#   - background_tasks.mqtt_handler_tasks.process_guard_gps
#   - background_tasks.mqtt_handler_tasks.process_sensor_data
#   - background_tasks.mqtt_handler_tasks.process_device_alert
#   - background_tasks.mqtt_handler_tasks.process_system_health
```

---

### Step 5: Health Checks (10 minutes)

```bash
# Run automated health check
./scripts/health_check_message_bus.sh

# Should output:
# ✓ Redis DB 0 (Celery broker)
# ✓ Redis DB 1 (Celery results)
# ✓ Redis DB 2 (Channel layers)
# ✓ Mosquitto broker
# ✓ Celery workers ping
# ✓ MQTT Subscriber process running
# ✓ Django Channels layer
# ✓ Prometheus /metrics/export/
# ✓ Django /monitoring/health/
# ✅ ALL COMPONENTS HEALTHY

# If any checks fail, see troubleshooting section in runbook:
# docs/operations/MESSAGE_BUS_RUNBOOK.md
```

---

### Step 6: Integration Testing (20 minutes)

**Test 1: MQTT Device Telemetry**
```bash
# Publish test telemetry message
mosquitto_pub -h localhost -t "device/test-sensor-001/telemetry" \
  -m '{"battery": 85, "signal": -65, "temperature": 25.5, "timestamp": "'$(date -Iseconds)'"}'

# Check database
python manage.py shell
>>> from apps.mqtt.models import DeviceTelemetry
>>> DeviceTelemetry.objects.latest('received_at')
# Should show the test message stored

# Check logs
tail -n 20 /var/log/mqtt_subscriber.log | grep "Device.*telemetry stored"
```

**Test 2: Guard GPS with Geofence**
```bash
# Publish test GPS message
mosquitto_pub -h localhost -t "guard/guard-123/gps" \
  -m '{"lat": 12.9716, "lon": 77.5946, "accuracy": 10.5, "guard_id": 123, "client_id": 1, "timestamp": "'$(date -Iseconds)'"}'

# Check database
python manage.py shell
>>> from apps.mqtt.models import GuardLocation
>>> location = GuardLocation.objects.latest('received_at')
>>> print(f"In geofence: {location.in_geofence}, Violation: {location.geofence_violation}")

# If violation detected, check alert created
>>> from apps.mqtt.models import DeviceAlert
>>> DeviceAlert.objects.filter(alert_type='GEOFENCE_VIOLATION').latest('received_at')
```

**Test 3: Critical Alert with Notifications**
```bash
# Publish panic button alert
mosquitto_pub -h localhost -t "alert/panic/guard-789" \
  -m '{"alert_type": "panic", "severity": "critical", "message": "Panic button pressed", "location": {"lat": 12.97, "lon": 77.59}, "timestamp": "'$(date -Iseconds)'"}'

# Check alert stored
python manage.py shell
>>> from apps.mqtt.models import DeviceAlert
>>> alert = DeviceAlert.objects.latest('received_at')
>>> print(f"Alert: {alert.alert_type}, SMS sent: {alert.sms_sent}, Email sent: {alert.email_sent}")

# Check NOC WebSocket received broadcast
# (Open browser console on NOC dashboard, should see critical_alert message)
```

**Test 4: WebSocket Broadcast**
```bash
# Connect to WebSocket (requires wscat: npm install -g wscat)
wscat -c "ws://localhost:8000/ws/noc/dashboard/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should receive:
# {"type": "connected", "tenant_id": X}

# Publish alert, should receive:
# {"type": "critical_alert", "data": {...}}
```

**Test 5: Prometheus Metrics**
```bash
# Check metrics endpoint
curl http://localhost:8000/metrics/export/ | head -50

# Should include:
# celery_mqtt_message_processed_total{topic_prefix="device"} X
# celery_websocket_broadcast_success_total{group_prefix="noc"} Y
# celery_task_success_total{task_name="process_device_alert"} Z
```

---

### Step 7: Grafana Dashboard Import (15 minutes)

```bash
# Option 1: Manual import via Grafana UI
# 1. Open Grafana → Dashboards → Import
# 2. Upload each JSON file:
#    - monitoring/grafana/celery_dashboard.json
#    - monitoring/grafana/mqtt_dashboard.json
#    - monitoring/grafana/websocket_dashboard.json
#    - monitoring/grafana/message_bus_unified.json
# 3. Select Prometheus data source
# 4. Click Import

# Option 2: API import (automated)
GRAFANA_URL="http://localhost:3000"
GRAFANA_API_KEY="<your-api-key>"

for dashboard in monitoring/grafana/*.json; do
  curl -X POST "$GRAFANA_URL/api/dashboards/db" \
    -H "Authorization: Bearer $GRAFANA_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$dashboard"
done
```

---

### Step 8: Verify Metrics Collection (10 minutes)

```bash
# Wait 2-3 minutes for metrics to accumulate
sleep 180

# Check Grafana dashboards show data
# Open: http://localhost:3000/d/message-bus-unified

# Verify panels populate:
# - Celery Workers: > 0
# - MQTT Subscriber: 1 (connected)
# - WebSocket Connections: Shows active count
# - Message rates: Shows data (if traffic exists)
```

---

### Step 9: Production Smoke Test (15 minutes)

**Test complete pipeline with real device:**

```bash
# If you have a real guard device or IoT sensor:
# 1. Configure device to publish to your MQTT broker
# 2. Have device send test message
# 3. Verify message appears in database
# 4. Verify NOC dashboard updates in real-time
# 5. Verify Prometheus metrics increment

# If no real device, simulate with script:
python << EOF
import paho.mqtt.client as mqtt
import json
from datetime import datetime

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect('localhost', 1883, 60)

# Send device telemetry
client.publish('device/production-test/telemetry', json.dumps({
    'battery': 95,
    'signal': -55,
    'temperature': 24.0,
    'timestamp': datetime.now().isoformat()
}))

# Send guard GPS
client.publish('guard/production-guard/gps', json.dumps({
    'lat': 12.9716,
    'lon': 77.5946,
    'accuracy': 8.0,
    'guard_id': 1,
    'client_id': 1,
    'timestamp': datetime.now().isoformat()
}))

client.disconnect()
print("✅ Production test messages published")
EOF

# Verify in Django admin
# → MQTT → Device Telemetry (should see test message)
# → MQTT → Guard Locations (should see GPS record)
```

---

## Post-Deployment Verification

### Checklist

- [ ] **All services running**: `sudo systemctl status {redis,mosquitto,celery@*,mqtt-subscriber,daphne}`
- [ ] **Health check passes**: `./scripts/health_check_message_bus.sh` returns exit code 0
- [ ] **Celery workers processing**: `celery -A intelliwiz_config inspect active` shows workers
- [ ] **MQTT subscriber connected**: Logs show "Connected to MQTT Broker"
- [ ] **Database models created**: Django admin shows MQTT section
- [ ] **Grafana dashboards** imported and showing data
- [ ] **Prometheus metrics** exporting: `/metrics/export/` returns data
- [ ] **WebSocket connections** working: NOC dashboard connects
- [ ] **End-to-end test passes**: MQTT → Database → WebSocket confirmed
- [ ] **Alert notifications** working (if configured): Test SMS/Email sent

---

## Rollback Plan

**If critical issues arise:**

### Quick Rollback (Revert to Pre-Deployment State)

```bash
# 1. Stop MQTT subscriber
sudo systemctl stop mqtt-subscriber
sudo systemctl disable mqtt-subscriber

# 2. Revert database migrations
python manage.py migrate mqtt zero

# 3. Revert code
git revert <commit-hash>

# 4. Restart services
sudo systemctl restart celery@{critical,general}
sudo systemctl restart daphne

# 5. Verify system stable
./scripts/health_check_message_bus.sh
```

**Estimated Rollback Time:** 10-15 minutes

---

## Monitoring Setup

### Alerts to Configure

**Critical (page immediately):**
- MQTT subscriber down for > 2 minutes
- Celery critical queue depth > 50 tasks
- WebSocket broadcast failure rate > 5%
- Geofence violation detected

**High (notify within 15 minutes):**
- Task failure rate > 10%
- MQTT message processing latency > 1 second
- Circuit breaker open for > 5 minutes

**Medium (notify within 1 hour):**
- Queue depth > 100 tasks for > 10 minutes
- Worker utilization > 90% sustained

### Dashboard URLs

After import, dashboards available at:
- Celery: `http://grafana.example.com/d/celery-monitoring`
- MQTT: `http://grafana.example.com/d/mqtt-monitoring`
- WebSocket: `http://grafana.example.com/d/websocket-monitoring`
- Unified: `http://grafana.example.com/d/message-bus-unified`

---

## Validation Criteria (All Must Pass)

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Migrations applied | `python manage.py showmigrations mqtt` | All [X] checked |
| MQTT models in admin | Open Django admin | MQTT section visible with 4 models |
| MQTT subscriber running | `pgrep -f mqtt_subscriber` | Returns PID |
| Celery routes loaded | `celery inspect routes \| grep mqtt_handler` | Shows 5 MQTT handler routes |
| WebSocket encryption | Start Django in production | No ValueError about CHANNELS_ENCRYPTION_KEY |
| Health check passes | `./scripts/health_check_message_bus.sh` | Exit code 0 |
| End-to-end test | Publish MQTT → Check DB | Message persisted |
| Prometheus export | `curl localhost:8000/metrics/export/ \| grep mqtt` | Shows MQTT metrics |

---

## Troubleshooting Common Deployment Issues

### Issue 1: Migration Fails - Foreign Key Error

**Error:** `django.db.utils.IntegrityError: ... foreign key constraint`

**Cause:** GuardLocation.guard references People model

**Fix:**
```bash
# Ensure People model exists and has data
python manage.py shell
>>> from apps.peoples.models import People
>>> People.objects.count()  # Should be > 0
```

---

### Issue 2: MQTT Subscriber Won't Start

**Error:** `ModuleNotFoundError: No module named 'apps'`

**Cause:** DJANGO_SETTINGS_MODULE not set or wrong path

**Fix:**
```bash
# Check systemd service file paths
sudo nano /etc/systemd/system/mqtt-subscriber.service

# Verify:
WorkingDirectory=/YOUR/ACTUAL/PATH
ExecStart=/YOUR/ACTUAL/PATH/venv/bin/python /YOUR/ACTUAL/PATH/apps/mqtt/subscriber.py

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart mqtt-subscriber
```

---

### Issue 3: WebSocket Encryption Key Missing

**Error:** `ValueError: CHANNELS_ENCRYPTION_KEY MUST be set`

**Cause:** Production environment missing encryption key

**Fix:**
```bash
# Generate key
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

# Add to .env.production
echo "CHANNELS_ENCRYPTION_KEY=<generated-key>" >> .env.production

# Restart Django
sudo systemctl restart daphne
```

---

## Success Metrics (Monitor for 24 hours)

After deployment, monitor these metrics:

| Metric | Target | Alert If |
|--------|--------|----------|
| MQTT messages received | > 0/min | 0 for > 5 min |
| Task success rate | > 95% | < 90% |
| WebSocket connections | Stable | Drops > 20% |
| Alert notification delivery | > 98% | < 95% |
| End-to-end latency (MQTT→WS) | < 200ms | > 500ms |
| Database growth | Predictable | > 10GB/day unexpected |

---

## Sign-Off

**Pre-Deployment:**
- [ ] Dev Team Lead approval
- [ ] DevOps approval
- [ ] Security review (if first deployment)

**Post-Deployment:**
- [ ] All health checks passing
- [ ] Grafana dashboards populated
- [ ] No critical alerts triggered
- [ ] Production team notified

**Deployment Lead:** _________________
**Date/Time:** _________________
**Sign-Off:** _________________

---

**Checklist Version:** 1.0
**Last Updated:** November 1, 2025
**Next Review:** After first production deployment
