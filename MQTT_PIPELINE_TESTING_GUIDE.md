# MQTT Pipeline Testing Guide

**Version:** 1.0
**Date:** November 1, 2025
**Purpose:** Complete guide to test the MQTT → Celery → Database → WebSocket pipeline

---

## Quick Start (5 Minutes)

**Prerequisites:**
- Mosquitto MQTT broker running
- Redis running
- Django application running
- Celery workers running
- MQTT subscriber running

**Quick Test:**
```bash
# 1. Generate test data
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

# 2. Wait for processing (2-3 seconds)
sleep 3

# 3. Verify pipeline
python scripts/testing/verify_mqtt_pipeline.py --verbose

# Expected output:
# ✅ Device telemetry records created
# ✅ Guard GPS records created
# ✅ Sensor reading records created
# ✅ Device alert records created
# ✅ Prometheus metrics exported
# 🎉 ALL CHECKS PASSED - Pipeline is working correctly!
```

---

## Complete Testing Procedure

### Step 1: Start All Services

```bash
# If services not running, start them:
sudo systemctl start redis
sudo systemctl start mosquitto
sudo systemctl start daphne
sudo systemctl start celery@critical
sudo systemctl start celery@general
sudo systemctl start mqtt-subscriber

# Verify all services healthy
./scripts/health_check_message_bus.sh
# Should output: ✅ ALL COMPONENTS HEALTHY
```

---

### Step 2: Generate Test Data

**Scenario 1: Device Telemetry**
```bash
python scripts/testing/generate_mqtt_test_data.py \
  --scenario device_telemetry \
  --count 10 \
  --verbose

# Expected output:
# ✓ Published to device/sensor-001/telemetry
# ✓ Published to device/sensor-002/telemetry
# ...
# 📊 Summary: 10 published, 0 failed
```

**Scenario 2: Guard GPS (with geofence violations)**
```bash
python scripts/testing/generate_mqtt_test_data.py \
  --scenario guard_gps \
  --count 10

# Generates:
# - 70% GPS locations IN geofence (normal)
# - 30% GPS locations OUT of geofence (violations)
#
# Expected:
# ✓ Published to guard/guard-101/gps
# ✓ Published to guard/guard-102/gps
# ...
```

**Scenario 3: Sensor Readings**
```bash
python scripts/testing/generate_mqtt_test_data.py \
  --scenario sensor_readings \
  --count 10

# Generates:
# - Door sensors (OPEN/CLOSED)
# - Motion sensors (DETECTED/CLEAR)
# - Smoke detectors (NORMAL/ALARM)
# - Temperature sensors
```

**Scenario 4: Critical Alerts**
```bash
python scripts/testing/generate_mqtt_test_data.py \
  --scenario critical_alerts \
  --count 3

# Generates:
# - Panic button (QoS 2 - exactly once)
# - SOS distress signal (QoS 2)
# - Intrusion detection (QoS 2)
#
# These should trigger SMS/Email notifications!
```

**Scenario 5: All Combined**
```bash
python scripts/testing/generate_mqtt_test_data.py \
  --scenario all \
  --count 5

# Generates 5 of each message type (25 total messages)
```

---

### Step 3: Monitor Processing

**Watch MQTT Subscriber Logs:**
```bash
tail -f /var/log/mqtt_subscriber.log

# Expected output:
# INFO - Received message on topic: device/sensor-001/telemetry (QoS 1, 156 bytes)
# INFO - Routed device telemetry to Celery: device/sensor-001/telemetry
# INFO - Received message on topic: guard/guard-101/gps (QoS 1, 234 bytes)
# INFO - Routed guard GPS to Celery: guard/guard-101/gps
```

**Watch Celery Worker Logs:**
```bash
tail -f /var/log/celery/general.log | grep mqtt_handler_tasks

# Expected output:
# INFO - Processing telemetry from device sensor-001
# INFO - Device sensor-001 telemetry stored (ID: 123): battery=85%, signal=-65
# INFO - Processing GPS for guard 101: (12.9716, 77.5946)
# INFO - GPS location stored for guard 101 (ID: 456): (12.9716, 77.5946), geofence=IN
```

**Watch for Critical Alerts:**
```bash
tail -f /var/log/celery/critical.log | grep process_device_alert

# Expected output (if critical alerts sent):
# CRITICAL - CRITICAL ALERT from guard-101: panic - Panic button pressed
# INFO - Device alert stored (ID: 789): panic from guard-101 (critical)
# INFO - Notifications sent for alert 789: SMS=True, Email=True, Push=False
```

---

### Step 4: Verify Database Storage

**Check Database Records:**
```bash
python manage.py shell

# Device Telemetry
>>> from apps.mqtt.models import DeviceTelemetry
>>> DeviceTelemetry.objects.count()
10  # Should match messages sent
>>> latest = DeviceTelemetry.objects.latest('received_at')
>>> print(f"Device: {latest.device_id}, Battery: {latest.battery_level}%, Received: {latest.received_at}")

# Guard GPS
>>> from apps.mqtt.models import GuardLocation
>>> GuardLocation.objects.count()
10
>>> violations = GuardLocation.objects.filter(geofence_violation=True)
>>> print(f"Geofence violations: {violations.count()}")
>>> for loc in violations:
...     print(f"  Guard {loc.guard_id} at {loc.timestamp}: ({loc.location.y}, {loc.location.x})")

# Sensor Readings
>>> from apps.mqtt.models import SensorReading
>>> SensorReading.objects.count()
10
>>> smoke_alarms = SensorReading.objects.filter(sensor_type='SMOKE', value__gt=100)
>>> print(f"Smoke alarms: {smoke_alarms.count()}")

# Device Alerts
>>> from apps.mqtt.models import DeviceAlert
>>> DeviceAlert.objects.count()
5  # Critical alerts + any triggered by smoke/geofence
>>> critical = DeviceAlert.objects.filter(severity='CRITICAL')
>>> for alert in critical:
...     print(f"{alert.alert_type} from {alert.source_id}: SMS sent={alert.sms_sent}")
```

---

### Step 5: Run Automated Verification

**Use Verification Script:**
```bash
python scripts/testing/verify_mqtt_pipeline.py --last-minutes 10 --verbose

# Expected output:
# ============================================================
#   Device Telemetry Verification
# ============================================================
# ✅ Device telemetry records created
#    Found 10 records in last 10 minutes
# ✅ Telemetry has battery data
#    Battery: 85%
# ✅ Telemetry has signal data
#    Signal: -65 dBm
# ✅ Telemetry has raw MQTT payload
#    Raw data keys: ['battery', 'signal', 'temperature', 'timestamp']
#
# ============================================================
#   Guard GPS Tracking Verification
# ============================================================
# ✅ Guard GPS records created
#    Found 10 records in last 10 minutes
# ✅ GPS has PostGIS Point data
#    Location: 12.971600°N, 77.594600°E
# ✅ Geofence validation ran
#    In geofence: True, Violation: False
#    ⚠️  3 geofence violations detected
# ✅ Geofence violations triggered alerts
#    Found 3 geofence violation alerts
#
# ... (continues for all components)
#
# ============================================================
#   Verification Summary
# ============================================================
# ✅ Passed: 20
# ❌ Failed: 0
# 📊 Success Rate: 100.0%
#
# 🎉 ALL CHECKS PASSED - Pipeline is working correctly!
```

---

### Step 6: Test WebSocket Real-Time Updates

**Option 1: Using Browser Console**

1. Open NOC dashboard in browser
2. Open browser console (F12)
3. Verify WebSocket connection:
```javascript
console.log("WebSocket state:", ws.readyState);  // Should be 1 (OPEN)
```

4. Generate critical alert:
```bash
python scripts/testing/generate_mqtt_test_data.py --scenario critical_alerts --count 1
```

5. Watch browser console:
```javascript
// Should receive within 1-2 seconds:
{
  type: "critical_alert",
  data: {
    source_id: "guard-101",
    alert_type: "PANIC",
    severity: "CRITICAL",
    message: "Panic button pressed",
    timestamp: "2025-11-01T10:30:45Z"
  },
  priority: "critical"
}
```

**Option 2: Using wscat (CLI)**

```bash
# Install wscat if not installed
npm install -g wscat

# Connect to WebSocket (replace with your JWT token)
wscat -c "ws://localhost:8000/ws/noc/dashboard/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should receive:
# < {"type": "connected", "tenant_id": 1, "timestamp": "..."}

# In another terminal, generate alert:
python scripts/testing/generate_mqtt_test_data.py --scenario critical_alerts --count 1

# WebSocket should receive alert within 1-2 seconds:
# < {"type": "critical_alert", "data": {...}}
```

---

### Step 7: Check Prometheus Metrics

**View Raw Metrics:**
```bash
curl http://localhost:8000/metrics/export/ | grep -E "(mqtt|websocket|celery)" | head -20

# Expected output:
# celery_mqtt_message_processed_total{topic_prefix="device",qos="1"} 10
# celery_mqtt_message_processed_total{topic_prefix="guard",qos="1"} 10
# celery_mqtt_message_processed_total{topic_prefix="sensor",qos="1"} 10
# celery_mqtt_message_processed_total{topic_prefix="alert",qos="2"} 3
# celery_mqtt_device_telemetry_processed_total{device_id="sensor-001"} 3
# celery_mqtt_guard_gps_processed_total{guard_id="101"} 2
# celery_mqtt_critical_alert_processed_total{alert_type="panic"} 1
# celery_websocket_broadcast_success_total{group_prefix="noc"} 4
# celery_task_success_total{task_name="process_device_alert"} 3
```

**View in Grafana:**
```bash
# Open Grafana dashboards
# http://localhost:3000/d/message-bus-unified

# Should see:
# - MQTT Subscriber: Connected (green)
# - Messages Received: Graph showing spikes when test data generated
# - Critical Alerts: Table showing recent alerts
# - Task Success Rate: 100%
```

---

### Step 8: Performance Verification

**Measure End-to-End Latency:**
```bash
# Generate timestamp before publishing
START=$(date +%s%N)

# Publish message
mosquitto_pub -h localhost -t "device/latency-test/telemetry" \
  -m '{"battery": 100, "signal": -50, "timestamp": "'$(date -Iseconds)'"}'

# Wait for database write
sleep 2

# Check when record was received
python manage.py shell << EOF
from apps.mqtt.models import DeviceTelemetry
from datetime import datetime
latest = DeviceTelemetry.objects.filter(device_id='latency-test').latest('received_at')
print(f"Received at: {latest.received_at}")
EOF

# Calculate latency
# Typical: 50-150ms from publish to database storage
```

---

## Test Scenarios

### Scenario 1: Normal Operations (Low Volume)

```bash
# Simulate 1 hour of normal IoT traffic (1 message per device per minute)
for i in {1..60}; do
  python scripts/testing/generate_mqtt_test_data.py --scenario all --count 1
  sleep 60
done

# Expected:
# - 60 telemetry records per device
# - 60 GPS locations per guard
# - Smooth processing, no queue backlog
# - Metrics steadily increasing
```

---

### Scenario 2: Load Test (High Volume)

```bash
# Simulate high traffic (1000 messages in 1 minute)
python scripts/testing/generate_mqtt_test_data.py --scenario device_telemetry --count 1000

# Monitor:
# - Celery queue depth (should drain within 30 seconds)
# - CPU usage (should stay < 80%)
# - Database connections (should not exhaust pool)

# Verify:
python scripts/testing/verify_mqtt_pipeline.py --last-minutes 2
# All 1000 messages should be stored
```

---

### Scenario 3: Critical Alert Response Time

```bash
# Measure time from panic button to supervisor notification

# Start timer
START=$(date +%s)

# Publish panic button
python scripts/testing/generate_mqtt_test_data.py --scenario critical_alerts --count 1

# Check supervisor email/SMS arrival time
# (Monitor your actual email/phone)

# Check database
python manage.py shell
>>> from apps.mqtt.models import DeviceAlert
>>> alert = DeviceAlert.objects.filter(alert_type='PANIC').latest('received_at')
>>> print(f"Alert created at: {alert.received_at}")
>>> print(f"SMS sent: {alert.sms_sent}, Email sent: {alert.email_sent}")

# Expected response time: < 30 seconds (panic → supervisor notification)
```

---

### Scenario 4: Geofence Violation Detection

```bash
# Generate GPS locations that violate geofence
python scripts/testing/generate_mqtt_test_data.py --scenario guard_gps --count 20

# 30% should be violations (6 out of 20)

# Verify geofence violations detected
python manage.py shell
>>> from apps.mqtt.models import GuardLocation, DeviceAlert
>>> violations = GuardLocation.objects.filter(geofence_violation=True).count()
>>> print(f"Geofence violations detected: {violations}")
>>>
>>> # Check alerts were triggered
>>> geofence_alerts = DeviceAlert.objects.filter(alert_type='GEOFENCE_VIOLATION')
>>> print(f"Geofence alerts created: {geofence_alerts.count()}")
>>>
>>> # Should be equal (each violation triggers an alert)
>>> assert violations == geofence_alerts.count(), "Mismatch!"
>>> print("✅ All geofence violations triggered alerts")
```

---

### Scenario 5: Smoke Detector → Fire Alarm

```bash
# Generate sensor readings with high smoke levels
# (Automatically triggers fire alerts if smoke > 100ppm)

python << EOF
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
from datetime import datetime

client = mqtt.Client(CallbackAPIVersion.VERSION2)
client.connect('localhost', 1883, 60)

# Send high smoke level
payload = json.dumps({
    'type': 'smoke',
    'value': 150,  # > 100 threshold
    'state': 'ALARM',
    'timestamp': datetime.now().isoformat()
})

client.publish('sensor/smoke-301/status', payload, qos=1)
client.loop(2)
client.disconnect()

print("🔥 High smoke level published")
EOF

# Wait for processing
sleep 3

# Verify fire alert created
python manage.py shell
>>> from apps.mqtt.models import DeviceAlert, SensorReading
>>> smoke = SensorReading.objects.filter(sensor_type='SMOKE', value__gt=100).latest('received_at')
>>> print(f"Smoke level: {smoke.value} ppm (ALARM)")
>>>
>>> fire_alerts = DeviceAlert.objects.filter(alert_type='FIRE')
>>> if fire_alerts.exists():
...     alert = fire_alerts.latest('received_at')
...     print(f"✅ Fire alert triggered: {alert.message}")
...     print(f"   Notifications sent: SMS={alert.sms_sent}, Email={alert.email_sent}")
```

---

## Verification Checklist

### Database Verification ✅

After generating test data, check Django admin:

**1. Navigate to Django Admin:**
```
http://localhost:8000/admin/
```

**2. Check MQTT Section:**
- **Device Telemetry:** Should show latest device health metrics
- **Guard Locations:** Should show GPS points with geofence status
- **Sensor Readings:** Should show facility sensor data
- **Device Alerts:** Should show critical alerts with severity badges

**3. Verify Data Quality:**
- Timestamps are recent (within last few minutes)
- Battery levels are 0-100%
- GPS coordinates are valid (lat: -90 to 90, lon: -180 to 180)
- Geofence violations have `geofence_violation=True`
- Critical alerts have `status='NEW'`

---

### Metrics Verification ✅

**Check Prometheus Metrics:**
```bash
curl http://localhost:8000/metrics/export/ | grep mqtt_message_processed

# Expected output (after publishing 25 messages):
# celery_mqtt_message_processed_total{topic_prefix="device",qos="1"} 5
# celery_mqtt_message_processed_total{topic_prefix="guard",qos="1"} 5
# celery_mqtt_message_processed_total{topic_prefix="sensor",qos="1"} 5
# celery_mqtt_message_processed_total{topic_prefix="alert",qos="2"} 3
# celery_mqtt_message_processed_total{topic_prefix="system",qos="0"} 5
```

**Check TaskMetrics in Cache:**
```bash
python manage.py shell
>>> from django.core.cache import cache
>>> keys = cache.keys('task_metrics:mqtt*')
>>> print(f"MQTT metric keys: {len(keys)}")
>>> for key in keys[:5]:
...     value = cache.get(key)
...     print(f"{key}: {value}")
```

---

### WebSocket Verification ✅

**Check WebSocket received broadcasts:**

1. Open NOC dashboard with browser console open
2. Generate critical alert
3. Verify console shows message within 1-2 seconds:
```javascript
// Console output:
WebSocket message received: {
  type: "critical_alert",
  data: {
    source_id: "guard-101",
    alert_type: "PANIC",
    severity: "CRITICAL",
    message: "Panic button pressed",
    location: {lat: 12.9716, lon: 77.5946},
    timestamp: "2025-11-01T10:45:23Z"
  },
  priority: "critical",
  task_id: "abc-123-def",
  task_name: "process_device_alert"
}
```

---

## Troubleshooting Test Failures

### Issue: Messages Published but Not in Database

**Diagnosis:**
```bash
# Check MQTT subscriber is running
sudo systemctl status mqtt-subscriber

# Check subscriber logs for errors
tail -n 50 /var/log/mqtt_subscriber.log | grep -i error

# Check Celery workers are running
celery -A intelliwiz_config inspect active

# Check for task failures
tail -n 50 /var/log/celery/general.log | grep -i error
```

**Common Causes:**
1. MQTT subscriber not running → `sudo systemctl start mqtt-subscriber`
2. Topic not whitelisted → Check `ALLOWED_TOPIC_PREFIXES` in subscriber.py
3. Celery worker crashed → Check logs, restart worker
4. Database error → Check PostgreSQL logs, verify PostGIS installed

---

### Issue: Geofence Validation Not Working

**Diagnosis:**
```bash
python manage.py shell
>>> from apps.onboarding.models import ApprovedLocation
>>> ApprovedLocation.objects.filter(client_id=1, is_active=True).count()
0  # ← PROBLEM: No approved locations configured

# Solution: Create test geofence
>>> from django.contrib.gis.geos import Point
>>> ApprovedLocation.objects.create(
...     client_id=1,
...     location_name="Test Geofence",
...     latitude=12.9716,
...     longitude=77.5946,
...     radius_meters=1000,  # 1km radius
...     is_active=True
... )
```

---

### Issue: Notifications Not Sending

**Diagnosis:**
```bash
# Check Twilio configured
python manage.py shell
>>> from django.conf import settings
>>> print(f"Twilio configured: {hasattr(settings, 'TWILIO_ACCOUNT_SID')}")
>>> print(f"Email configured: {settings.DEFAULT_FROM_EMAIL}")

# Check alert notification service logs
tail -f /var/log/celery/critical.log | grep notification

# Common causes:
# - Twilio credentials missing → Set in .env
# - Email server not configured → Configure SMTP in settings
# - FCM key missing → Set FCM_SERVER_KEY in .env
```

---

## Performance Benchmarks

### Expected Performance

| Metric | Target | Typical | Alert If |
|--------|--------|---------|----------|
| MQTT publish → Subscriber receive | < 10ms | 5-10ms | > 50ms |
| Subscriber → Celery queue | < 5ms | 2-5ms | > 20ms |
| Celery task execution | < 50ms | 20-50ms | > 200ms |
| Database write | < 20ms | 10-20ms | > 100ms |
| WebSocket broadcast | < 15ms | 5-15ms | > 50ms |
| **Total (end-to-end)** | **< 150ms** | **50-100ms** | **> 300ms** |

### Measure Performance

```bash
# Use verification script with timing
time python scripts/testing/verify_mqtt_pipeline.py

# Should complete in < 5 seconds for checking 25 messages
```

---

## Success Criteria

### All Must Pass ✅

- [ ] Test data generator publishes without errors
- [ ] MQTT subscriber receives all messages
- [ ] All 4 model types have database records
- [ ] Geofence violations detected correctly
- [ ] Critical alerts trigger notifications
- [ ] WebSocket broadcasts reach connected clients
- [ ] Prometheus metrics increment
- [ ] Health check script returns exit code 0
- [ ] End-to-end latency < 150ms
- [ ] No errors in logs

---

## Continuous Testing

### Daily Smoke Test (Automated)

```bash
# Add to cron (run every hour)
0 * * * * /path/to/scripts/testing/generate_mqtt_test_data.py --scenario all --count 1 && /path/to/scripts/testing/verify_mqtt_pipeline.py --last-minutes 10 || echo "MQTT pipeline test failed!" | mail -s "Alert: MQTT Pipeline" ops@example.com
```

### Load Testing (Weekly)

```bash
# Simulate 1 hour of high traffic
for i in {1..60}; do
  python scripts/testing/generate_mqtt_test_data.py --scenario all --count 10 &
  sleep 60
done

# Monitor Grafana dashboards for:
# - Queue depths (should stay < 100)
# - Task duration (should not increase)
# - Success rate (should stay > 99%)
```

---

## Conclusion

**You now have:**
✅ Test data generator for all MQTT message types
✅ Automated verification script
✅ Step-by-step testing procedures
✅ Performance benchmarks
✅ Troubleshooting guides
✅ Continuous testing automation

**To verify the complete pipeline:**
```bash
# 1. Generate test data
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

# 2. Verify pipeline
python scripts/testing/verify_mqtt_pipeline.py --verbose

# 3. Check health
./scripts/health_check_message_bus.sh

# Expected result: 🎉 ALL CHECKS PASSED
```

---

**Testing Guide Version:** 1.0
**Last Updated:** November 1, 2025
**Next Review:** After first production deployment
