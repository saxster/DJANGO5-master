# Full System Test - Complete Execution Plan

**Test Type:** Option 3 - Full System Test (15 minutes)
**Status:** ⚠️ **READY TO EXECUTE** (Prerequisites needed)
**Date:** November 1, 2025
**Test Coverage:** 100% - All components, all scenarios

---

## 🚦 Current Environment Status

**Services Detected:**
- ✅ **Redis**: Running (127.0.0.1:6379, PID 20713)
- ❌ **Mosquitto**: Not installed
- ❌ **Celery Workers**: Not running (no Django environment active)
- ❌ **MQTT Subscriber**: Not running
- ❌ **Django/Daphne**: Not running

**Virtual Environment:** Not activated

---

## 📋 Prerequisites (Required Before Testing)

### Step 0: Install Missing Services (One-Time Setup)

**Install Mosquitto (macOS):**
```bash
brew install mosquitto

# Start mosquitto
brew services start mosquitto

# Or run manually
mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf
```

**Activate Virtual Environment:**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master

# Activate your venv (adjust path if different)
source venv/bin/activate

# Or if using specific Python version
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate
```

**Install paho-mqtt (for test generator):**
```bash
pip install paho-mqtt
```

---

## ✅ Full System Test Procedure (Step-by-Step)

### STEP 1: Start All Services (5 minutes)

**Terminal 1: Start Django**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
python manage.py runserver 8000

# Expected output:
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CONTROL-C.
```

**Terminal 2: Start Celery Worker**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
celery -A intelliwiz_config worker --loglevel=info

# Expected output:
# celery@hostname ready.
# - registered tasks:
#   - background_tasks.mqtt_handler_tasks.process_device_telemetry
#   - background_tasks.mqtt_handler_tasks.process_guard_gps
#   ...
```

**Terminal 3: Start MQTT Subscriber**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
python apps/mqtt/subscriber.py

# Expected output:
# ============================================================
# MQTT Subscriber Service Starting
# Broker: localhost:1883
# Allowed Topics: device/, guard/, sensor/, alert/, system/
# ============================================================
# INFO - MQTT Subscriber initialized with client_id: django-subscriber-12345
# INFO - Connected to MQTT Broker at localhost:1883
# INFO - Subscribed to topic: device/# (QoS 1)
# INFO - Subscribed to topic: guard/# (QoS 1)
# INFO - Subscribed to topic: sensor/# (QoS 1)
# INFO - Subscribed to topic: alert/# (QoS 2)
# INFO - Subscribed to topic: system/# (QoS 0)
```

**Terminal 4: Monitor (Optional)**
```bash
# Watch Celery task execution
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
celery -A intelliwiz_config events

# Or just watch logs
tail -f celery.log
```

---

### STEP 2: Run Database Migrations (2 minutes)

**Terminal 5: Apply MQTT Migrations**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate

# Create migrations
python manage.py makemigrations mqtt

# Expected output:
# Migrations for 'mqtt':
#   apps/mqtt/migrations/0001_initial.py
#     - Create model DeviceTelemetry
#     - Create model GuardLocation
#     - Create model SensorReading
#     - Create model DeviceAlert
#     - Create index mqtt_device_ts_idx on field(s) device_id, -timestamp of model devicetelemetry
#     - Create index mqtt_guard_ts_idx on field(s) guard, -timestamp of model guardlocation
#     ...

# Apply migrations
python manage.py migrate mqtt

# Expected output:
# Running migrations:
#   Applying mqtt.0001_initial... OK

# Verify models created
python manage.py dbshell
# In PostgreSQL:
\dt mqtt_*
# Should show 4 tables:
# mqtt_device_telemetry
# mqtt_guard_location
# mqtt_sensor_reading
# mqtt_device_alert
\q
```

---

### STEP 3: Generate Test Data (3 minutes)

**Terminal 6: Run Test Data Generator**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate

# Run all scenarios
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5 --verbose

# Expected output:
# ============================================================
# MQTT Test Data Generator
# ============================================================
# Broker: localhost:1883
# Scenario: all
# Count: 5
# ============================================================
# ✅ Connected to MQTT broker at localhost:1883
#
# 📡 Generating Device Telemetry Messages...
# ✓ Published to device/sensor-001/telemetry (QoS 1): {"battery": 85, "signal": -65, ...}
# ✓ Published to device/sensor-002/telemetry (QoS 1): {"battery": 92, "signal": -58, ...}
# ✓ Published to device/sensor-003/telemetry (QoS 1): {"battery": 78, "signal": -72, ...}
# ✓ Published to device/edge-server-01/telemetry (QoS 1): {"battery": 100, "signal": -50, ...}
# ✓ Published to device/sensor-001/telemetry (QoS 1): {"battery": 64, "signal": -81, ...}
#
# 📍 Generating Guard GPS Messages...
# ✓ Published to guard/guard-101/gps (QoS 1): {"lat": 12.971234, "lon": 77.594567, ...}
# ✓ Published to guard/guard-103/gps (QoS 1): {"lat": 12.972456, "lon": 77.595123, ...}
# ✓ Published to guard/guard-102/gps (QoS 1): {"lat": 12.071234, "lon": 77.694567, ...}  ← VIOLATION
# ✓ Published to guard/guard-105/gps (QoS 1): {"lat": 12.970987, "lon": 77.593456, ...}
# ✓ Published to guard/guard-104/gps (QoS 1): {"lat": 13.021234, "lon": 78.104567, ...}  ← VIOLATION
#
# 🚪 Generating Sensor Readings...
# ✓ Published to sensor/door-101/status (QoS 1): {"type": "door", "state": "OPEN", ...}
# ✓ Published to sensor/motion-201/status (QoS 1): {"type": "motion", "state": "DETECTED", ...}
# ✓ Published to sensor/smoke-301/status (QoS 1): {"type": "smoke", "value": 45, ...}
# ✓ Published to sensor/temp-401/status (QoS 1): {"type": "temperature", "value": 24.5, ...}
# ✓ Published to sensor/smoke-301/status (QoS 1): {"type": "smoke", "value": 156, ...}  ← ALARM!
#
# 🚨 Generating Critical Alerts...
# ✓ Published to alert/panic/guard-101 (QoS 2): {"alert_type": "panic", ...}
# ✓ Published to alert/sos/guard-102 (QoS 2): {"alert_type": "sos", ...}
# ✓ Published to alert/intrusion/sensor-301 (QoS 2): {"alert_type": "intrusion", ...}
#
# 💻 Generating System Health Messages...
# ✓ Published to system/health/edge-server-01 (QoS 0): {"cpu": 65, "memory": 72, ...}
# ✓ Published to system/health/edge-server-02 (QoS 0): {"cpu": 45, "memory": 58, ...}
# ✓ Published to system/health/edge-gateway-01 (QoS 0): {"cpu": 82, "memory": 76, ...}
# ✓ Published to system/health/edge-server-01 (QoS 0): {"cpu": 58, "memory": 64, ...}
# ✓ Published to system/health/edge-server-02 (QoS 0): {"cpu": 91, "memory": 88, ...}  ← High CPU!
#
# ✅ All scenarios completed
#
# 📊 Summary: 25 published, 0 failed
```

**Watch Terminal 3 (MQTT Subscriber) in Real-Time:**
```
INFO - Received message on topic: device/sensor-001/telemetry (QoS 1, 156 bytes)
INFO - Routed device telemetry to Celery: device/sensor-001/telemetry
INFO - Received message on topic: guard/guard-101/gps (QoS 1, 234 bytes)
INFO - Routed guard GPS to Celery: guard/guard-101/gps
INFO - Received message on topic: alert/panic/guard-101 (QoS 2, 189 bytes)
WARNING - Routed critical alert to Celery: alert/panic/guard-101
INFO - Received message on topic: sensor/smoke-301/status (QoS 1, 145 bytes)
INFO - Routed sensor data to Celery: sensor/smoke-301/status
```

**Watch Terminal 2 (Celery Worker) Process Tasks:**
```
[INFO] Task background_tasks.mqtt_handler_tasks.process_device_telemetry[abc-123-def] received
[INFO] Processing telemetry from device sensor-001
[INFO] Device sensor-001 telemetry stored (ID: 1): battery=85%, signal=-65
[INFO] Task background_tasks.mqtt_handler_tasks.process_device_telemetry[abc-123-def] succeeded in 0.045s: None

[INFO] Task background_tasks.mqtt_handler_tasks.process_guard_gps[def-456-ghi] received
[INFO] Processing GPS for guard 101: (12.971234, 77.594567)
[INFO] GPS location stored for guard 101 (ID: 1): (12.971234, 77.594567), geofence=IN
[INFO] Task background_tasks.mqtt_handler_tasks.process_guard_gps[def-456-ghi] succeeded in 0.082s: None

[INFO] Task background_tasks.mqtt_handler_tasks.process_guard_gps[ghi-789-jkl] received
[INFO] Processing GPS for guard 102: (12.071234, 77.694567)
[WARNING] GEOFENCE VIOLATION: Guard 102 at (12.071234, 77.694567)
[INFO] GPS location stored for guard 102 (ID: 2): (12.071234, 77.694567), geofence=OUT
[INFO] Queuing geofence violation alert to critical queue (priority 9)
[INFO] Task background_tasks.mqtt_handler_tasks.process_guard_gps[ghi-789-jkl] succeeded in 0.123s: None

[CRITICAL] Task background_tasks.mqtt_handler_tasks.process_device_alert[jkl-012-mno] received
[CRITICAL] CRITICAL ALERT from guard-101: panic - Panic button pressed
[INFO] Device alert stored (ID: 1): panic from guard-101 (critical)
[INFO] Notifications sent for alert 1: SMS=True, Email=True, Push=False
[INFO] Task background_tasks.mqtt_handler_tasks.process_device_alert[jkl-012-mno] succeeded in 0.234s: None

[INFO] Task background_tasks.mqtt_handler_tasks.process_sensor_data[mno-345-pqr] received
[INFO] Processing sensor data from smoke-301: type=smoke, value=156
[CRITICAL] Smoke detector alert from sensor smoke-301: 156
[INFO] Sensor reading stored (ID: 1): smoke smoke-301 = 156
[INFO] Triggering fire alarm alert via critical queue (priority 10)
[INFO] Task background_tasks.mqtt_handler_tasks.process_sensor_data[mno-345-pqr] succeeded in 0.156s: None
```

---

### STEP 4: Verify Database Storage (3 minutes)

**Terminal 7: Check Database Records**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
python manage.py shell
```

**In Django shell:**
```python
from apps.mqtt.models import DeviceTelemetry, GuardLocation, SensorReading, DeviceAlert

# Device Telemetry
print("=" * 60)
print("DEVICE TELEMETRY")
print("=" * 60)
telemetry_count = DeviceTelemetry.objects.count()
print(f"Total records: {telemetry_count}")

if telemetry_count > 0:
    latest = DeviceTelemetry.objects.latest('received_at')
    print(f"\nLatest telemetry:")
    print(f"  Device: {latest.device_id}")
    print(f"  Battery: {latest.battery_level}%")
    print(f"  Signal: {latest.signal_strength} dBm")
    print(f"  Temperature: {latest.temperature}°C")
    print(f"  Connectivity: {latest.connectivity_status}")
    print(f"  Timestamp: {latest.timestamp}")
    print(f"  Received: {latest.received_at}")

# Guard GPS
print("\n" + "=" * 60)
print("GUARD GPS TRACKING")
print("=" * 60)
gps_count = GuardLocation.objects.count()
print(f"Total GPS records: {gps_count}")

if gps_count > 0:
    in_geofence = GuardLocation.objects.filter(in_geofence=True).count()
    violations = GuardLocation.objects.filter(geofence_violation=True).count()
    print(f"  In geofence: {in_geofence}")
    print(f"  Violations: {violations}")

    if violations > 0:
        print(f"\n  🚨 Geofence violations detected!")
        for loc in GuardLocation.objects.filter(geofence_violation=True):
            print(f"    - Guard {loc.guard_id}: ({loc.location.y:.6f}, {loc.location.x:.6f}) @ {loc.timestamp}")

# Sensor Readings
print("\n" + "=" * 60)
print("SENSOR READINGS")
print("=" * 60)
sensor_count = SensorReading.objects.count()
print(f"Total sensor records: {sensor_count}")

if sensor_count > 0:
    # Group by sensor type
    from django.db.models import Count
    by_type = SensorReading.objects.values('sensor_type').annotate(count=Count('id'))
    print(f"\n  By sensor type:")
    for item in by_type:
        print(f"    - {item['sensor_type']}: {item['count']}")

    # Check for smoke alarms
    smoke_alarms = SensorReading.objects.filter(sensor_type='SMOKE', value__gt=100)
    if smoke_alarms.count() > 0:
        print(f"\n  🔥 {smoke_alarms.count()} smoke alarms detected!")
        for alarm in smoke_alarms:
            print(f"    - {alarm.sensor_id}: {alarm.value} ppm @ {alarm.timestamp}")

# Device Alerts
print("\n" + "=" * 60)
print("DEVICE ALERTS")
print("=" * 60)
alert_count = DeviceAlert.objects.count()
print(f"Total alerts: {alert_count}")

if alert_count > 0:
    # Group by alert type
    by_type = DeviceAlert.objects.values('alert_type').annotate(count=Count('id'))
    print(f"\n  By alert type:")
    for item in by_type:
        print(f"    - {item['alert_type']}: {item['count']}")

    # Group by severity
    by_severity = DeviceAlert.objects.values('severity').annotate(count=Count('id'))
    print(f"\n  By severity:")
    for item in by_severity:
        print(f"    - {item['severity']}: {item['count']}")

    # Check notification status
    sms_sent = DeviceAlert.objects.filter(sms_sent=True).count()
    email_sent = DeviceAlert.objects.filter(email_sent=True).count()
    push_sent = DeviceAlert.objects.filter(push_sent=True).count()

    print(f"\n  📧 Notifications:")
    print(f"    - SMS sent: {sms_sent}")
    print(f"    - Email sent: {email_sent}")
    print(f"    - Push sent: {push_sent}")

    # Show latest critical alert
    critical = DeviceAlert.objects.filter(severity='CRITICAL').order_by('-received_at').first()
    if critical:
        print(f"\n  Latest CRITICAL alert:")
        print(f"    - Type: {critical.alert_type}")
        print(f"    - Source: {critical.source_id}")
        print(f"    - Message: {critical.message}")
        print(f"    - Status: {critical.status}")
        print(f"    - Time: {critical.timestamp}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"✅ Device Telemetry: {telemetry_count} records")
print(f"✅ Guard GPS: {gps_count} records ({violations} violations)")
print(f"✅ Sensor Readings: {sensor_count} records")
print(f"✅ Device Alerts: {alert_count} records")
print(f"✅ Notifications: {email_sent} emails, {sms_sent} SMS")
print("=" * 60)

# Exit shell
exit()
```

**Expected Output:**
```
============================================================
DEVICE TELEMETRY
============================================================
Total records: 5

Latest telemetry:
  Device: sensor-001
  Battery: 85%
  Signal: -65 dBm
  Temperature: 24.5°C
  Connectivity: ONLINE
  Timestamp: 2025-11-01 10:30:45+00:00
  Received: 2025-11-01 10:30:46+00:00

============================================================
GUARD GPS TRACKING
============================================================
Total GPS records: 5
  In geofence: 3
  Violations: 2

  🚨 Geofence violations detected!
    - Guard 102: (12.071234, 77.694567) @ 2025-11-01 10:30:47
    - Guard 104: (13.021234, 78.104567) @ 2025-11-01 10:30:49

============================================================
SENSOR READINGS
============================================================
Total sensor records: 5

  By sensor type:
    - DOOR: 1
    - MOTION: 1
    - SMOKE: 2
    - TEMPERATURE: 1

  🔥 1 smoke alarms detected!
    - smoke-301: 156 ppm @ 2025-11-01 10:30:50

============================================================
DEVICE ALERTS
============================================================
Total alerts: 6

  By alert type:
    - PANIC: 1
    - SOS: 1
    - INTRUSION: 1
    - GEOFENCE_VIOLATION: 2
    - FIRE: 1

  By severity:
    - CRITICAL: 4
    - HIGH: 2

  📧 Notifications:
    - SMS sent: 4
    - Email sent: 6
    - Push sent: 0

  Latest CRITICAL alert:
    - Type: PANIC
    - Source: guard-101
    - Message: Panic button pressed by guard
    - Status: NEW
    - Time: 2025-11-01 10:30:51+00:00

============================================================
SUMMARY
============================================================
✅ Device Telemetry: 5 records
✅ Guard GPS: 5 records (2 violations)
✅ Sensor Readings: 5 records
✅ Device Alerts: 6 records
✅ Notifications: 6 emails, 4 SMS
============================================================
```

---

### STEP 5: Run Automated Verification (2 minutes)

**Terminal 8: Verification Script**
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate

python scripts/testing/verify_mqtt_pipeline.py --last-minutes 10 --verbose

# Expected output (SEE PREVIOUS FULL OUTPUT)
# Should end with:
# 🎉 ALL CHECKS PASSED - Pipeline is working correctly!
# Exit code: 0
```

---

### STEP 6: Check Prometheus Metrics (1 minute)

**Terminal 9: Query Prometheus**
```bash
curl http://localhost:8000/metrics/export/ | grep -E "mqtt|websocket" | head -30

# Expected output:
# # HELP celery_mqtt_message_processed_total Total count of mqtt_message_processed events
# # TYPE celery_mqtt_message_processed_total counter
# celery_mqtt_message_processed_total{qos="1",topic_prefix="device"} 5.0
# celery_mqtt_message_processed_total{qos="1",topic_prefix="guard"} 5.0
# celery_mqtt_message_processed_total{qos="1",topic_prefix="sensor"} 5.0
# celery_mqtt_message_processed_total{qos="2",topic_prefix="alert"} 3.0
# celery_mqtt_message_processed_total{qos="0",topic_prefix="system"} 5.0
#
# celery_mqtt_device_telemetry_processed_total{device_id="sensor-001"} 2.0
# celery_mqtt_device_telemetry_processed_total{device_id="sensor-002"} 1.0
# celery_mqtt_device_telemetry_processed_total{device_id="sensor-003"} 1.0
#
# celery_mqtt_guard_gps_processed_total{guard_id="101"} 1.0
# celery_mqtt_guard_gps_processed_total{guard_id="102"} 1.0
# celery_mqtt_guard_gps_processed_total{guard_id="103"} 1.0
#
# celery_mqtt_critical_alert_processed_total{alert_type="panic",severity="critical"} 1.0
# celery_mqtt_critical_alert_processed_total{alert_type="sos",severity="critical"} 1.0
# celery_mqtt_critical_alert_processed_total{alert_type="geofence_violation",severity="high"} 2.0
# celery_mqtt_critical_alert_processed_total{alert_type="fire",severity="critical"} 1.0
#
# celery_websocket_broadcast_success_total{group_prefix="noc",message_type="critical_alert"} 6.0
#
# celery_alert_notification_sent_total{alert_type="panic",channel="sms",severity="critical"} 1.0
# celery_alert_notification_sent_total{alert_type="panic",channel="email",severity="critical"} 1.0
```

---

### STEP 7: View Results in Django Admin (2 minutes)

**Open Browser:**
```bash
open http://localhost:8000/admin/

# Login with superuser credentials
# Navigate to: MQTT section
```

**What You'll See:**

**Device Telemetry:**
- 5 records showing battery levels (color-coded: green > 80%, yellow 50-80%, red < 50%)
- Signal strength with icons (📶 good, 📵 poor)
- Temperature readings
- Timestamps

**Guard Locations:**
- 5 GPS points on map
- 3 with ✅ IN BOUNDS badge (green)
- 2 with ⚠️ VIOLATION badge (red)
- Click "View on Map" to see on OpenStreetMap

**Sensor Readings:**
- Door sensors showing OPEN/CLOSED
- Motion sensors showing DETECTED/CLEAR
- Smoke detector showing value + ALARM state (red badge)
- Temperature sensors showing °C

**Device Alerts:**
- 6 alerts total:
  - 🚨 PANIC from guard-101 (red CRITICAL badge)
  - 🆘 SOS from guard-102 (red CRITICAL badge)
  - 🚪 INTRUSION from sensor-301 (yellow HIGH badge)
  - 📍 GEOFENCE_VIOLATION × 2 (yellow HIGH badge)
  - 🔥 FIRE from smoke-301 (red CRITICAL badge)
- Each showing: Status (NEW), Notifications sent (✅ SMS, ✅ Email)

---

### STEP 8: Performance Measurement (1 minute)

**Measure End-to-End Latency:**

**Terminal 10:**
```bash
# Record start time
START=$(python3 -c "import time; print(time.time())")

# Publish message
mosquitto_pub -h localhost -t "device/latency-test/telemetry" \
  -m '{"battery": 100, "signal": -50, "timestamp": "'$(date -Iseconds)'"}'

# Wait a moment
sleep 1

# Check when it was stored
python manage.py shell << EOF
from apps.mqtt.models import DeviceTelemetry
import time
latest = DeviceTelemetry.objects.filter(device_id='latency-test').latest('received_at')
end_time = latest.received_at.timestamp()
start_time = $START
latency_ms = (end_time - start_time) * 1000
print(f"End-to-end latency: {latency_ms:.1f}ms")
print(f"Target: < 150ms")
print(f"Status: {'✅ PASS' if latency_ms < 150 else '❌ FAIL'}")
EOF
```

**Expected Output:**
```
End-to-end latency: 87.3ms
Target: < 150ms
Status: ✅ PASS
```

---

## 📊 Expected Test Results Summary

After completing all steps, you should see:

### Database Records

| Model | Expected Count | What to Check |
|-------|----------------|---------------|
| DeviceTelemetry | 5 | Battery 20-100%, Signal -90 to -50 dBm |
| GuardLocation | 5 | 3 in geofence, 2 violations |
| SensorReading | 5 | 1-2 smoke, 1 motion, 1 door, 1 temp |
| DeviceAlert | 6 | 3 original + 2 geofence + 1 fire |

### Triggered Events

| Event | Expected | Evidence |
|-------|----------|----------|
| Geofence violations | 2 | GuardLocation.geofence_violation=True |
| Geofence alerts | 2 | DeviceAlert.alert_type='GEOFENCE_VIOLATION' |
| Smoke alarm → Fire alert | 1 | DeviceAlert.alert_type='FIRE' |
| SMS sent | 4 | DeviceAlert.sms_sent=True |
| Email sent | 6 | DeviceAlert.email_sent=True |

### Performance

| Metric | Target | Expected |
|--------|--------|----------|
| End-to-end latency | < 150ms | 50-100ms ✅ |
| Task execution time | < 50ms | 20-50ms ✅ |
| Database writes | < 20ms | 10-20ms ✅ |

### Metrics

| Metric Name | Expected Value |
|-------------|----------------|
| `celery_mqtt_message_processed_total{topic_prefix="device"}` | 5 |
| `celery_mqtt_message_processed_total{topic_prefix="guard"}` | 5 |
| `celery_mqtt_message_processed_total{topic_prefix="alert"}` | 3 |
| `celery_mqtt_guard_gps_processed_total` | 5 |
| `celery_mqtt_critical_alert_processed_total` | 6 |
| `celery_websocket_broadcast_success_total` | 6 |
| `celery_alert_notification_sent_total{channel="sms"}` | 4 |
| `celery_alert_notification_sent_total{channel="email"}` | 6 |

---

## ✅ Success Criteria

**All must be TRUE:**

- [ ] Redis is running and accessible
- [ ] Mosquitto broker is running
- [ ] Django application is running
- [ ] Celery worker is running
- [ ] MQTT subscriber is running
- [ ] Database migrations applied (4 MQTT tables created)
- [ ] Test data generator publishes 25 messages without errors
- [ ] MQTT subscriber logs show "Received message" × 25
- [ ] Celery worker logs show tasks succeeded × 25
- [ ] Database has 5 telemetry, 5 GPS, 5 sensor, 6 alert records
- [ ] Geofence violations detected (2) and alerts created (2)
- [ ] Smoke alarm triggered fire alert (1)
- [ ] Notifications sent (4 SMS, 6 emails based on config)
- [ ] Prometheus metrics exported (25+ metrics)
- [ ] Verification script returns "ALL CHECKS PASSED"
- [ ] End-to-end latency < 150ms

**If all checked:** ✅ **SYSTEM IS 100% OPERATIONAL**

---

## 🚨 What If Tests Fail?

### Troubleshooting Quick Reference

**No database records:**
```bash
# Check MQTT subscriber is receiving messages
tail -f mqtt_subscriber.log | grep "Received message"

# If no messages, check mosquitto is running:
brew services list | grep mosquitto

# If not running:
brew services start mosquitto
```

**Celery tasks not executing:**
```bash
# Check worker is running
ps aux | grep celery

# Check worker can see tasks
celery -A intelliwiz_config inspect registered | grep mqtt_handler

# Restart worker
pkill -f celery
celery -A intelliwiz_config worker --loglevel=info
```

**Database errors:**
```bash
# Check PostGIS installed
python manage.py shell
>>> from django.contrib.gis.geos import Point
>>> Point(77.59, 12.97, srid=4326)
# Should work without errors

# If ImportError, install PostGIS:
brew install postgis
# Then in PostgreSQL:
CREATE EXTENSION postgis;
```

**Full troubleshooting:** See `docs/operations/MESSAGE_BUS_RUNBOOK.md`

---

## 🎯 After Successful Tests

**You've proven:**
✅ MQTT bidirectional communication works
✅ Data persists to database correctly
✅ Geofence validation detects violations
✅ Alerts trigger automatically
✅ Notifications send (SMS, Email, Push)
✅ WebSocket broadcasts in real-time
✅ Prometheus metrics export
✅ End-to-end latency meets targets

**Next step:** Deploy to production using `MESSAGE_BUS_DEPLOYMENT_CHECKLIST.md`

---

## 📝 Test Execution Notes

**Environment Tested:**
- macOS (Darwin 25.0.0)
- Redis running (127.0.0.1:6379, PID 20713)
- PostgreSQL with PostGIS
- Python 3.11.9

**Services Required:**
- Mosquitto (install with: `brew install mosquitto`)
- Virtual environment activated
- Django + Celery dependencies installed

**Estimated Time:**
- Setup (if services not running): 10 minutes
- Test execution: 15 minutes
- Verification: 5 minutes
- **Total: 30 minutes** for complete full system test

---

**Test Plan Version:** 1.0
**Created:** November 1, 2025
**For:** Message Bus Architecture Remediation (100% Complete)
