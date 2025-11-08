# MQTT Pipeline - Quick Start Testing Guide

**Ready to test in:** 5 minutes
**Complete test:** 15 minutes

---

## ⚡ Ultra-Quick Test (2 minutes)

```bash
# 1. Generate test messages
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

# 2. Verify they were stored
python scripts/testing/verify_mqtt_pipeline.py

# Expected:
# 🎉 ALL CHECKS PASSED - Pipeline is working correctly!
```

**That's it!** If you see "ALL CHECKS PASSED", the entire pipeline works.

---

## 📋 What Just Happened

When you ran those 2 commands, here's what happened:

### Generate Script (`generate_mqtt_test_data.py`)

**Published 25 MQTT messages:**
- ✅ 5 device telemetry (battery, signal, temperature)
- ✅ 5 guard GPS locations (some in geofence, some violations)
- ✅ 5 sensor readings (doors, motion, smoke)
- ✅ 3 critical alerts (panic button, SOS, intrusion)
- ✅ 5 system health (edge server metrics)

**To:** `mqtt://localhost:1883`

---

### Verification Script (`verify_mqtt_pipeline.py`)

**Checked database for:**
- ✅ DeviceTelemetry records (should find 5)
- ✅ GuardLocation records (should find 5, some with geofence_violation=True)
- ✅ SensorReading records (should find 5)
- ✅ DeviceAlert records (should find 3-8, including geofence violations)
- ✅ Prometheus metrics exported

**Verified:**
- ✅ MQTT → Celery routing works
- ✅ Celery → Database persistence works
- ✅ Geofence validation works (auto-creates alerts)
- ✅ Smoke detection → Fire alert works
- ✅ Metrics collection works

---

## 🔍 See The Results

### View in Django Admin

```
Open: http://localhost:8000/admin/

Navigate to:
- MQTT → Device Telemetry (see battery, signal, temperature)
- MQTT → Guard Locations (see GPS points with geofence status)
- MQTT → Sensor Readings (see facility sensors)
- MQTT → Device Alerts (see panic, SOS, geofence violations)

Each view has:
- Color-coded badges (battery green/yellow/red)
- Map links for GPS locations
- Alert severity indicators
```

---

### View in Grafana

```
Open: http://localhost:3000/d/message-bus-unified

See:
- MQTT messages received (graph showing 25 messages)
- Critical alerts processed (table with details)
- Guard GPS locations tracked (counter)
- Geofence violations (if any)
- WebSocket broadcasts sent
```

---

### View Prometheus Metrics

```bash
curl http://localhost:8000/metrics/export/ | grep mqtt

# Output:
# celery_mqtt_message_processed_total{topic_prefix="device"} 5
# celery_mqtt_message_processed_total{topic_prefix="guard"} 5
# celery_mqtt_message_processed_total{topic_prefix="sensor"} 5
# celery_mqtt_message_processed_total{topic_prefix="alert"} 3
# celery_mqtt_device_telemetry_processed_total{device_id="sensor-001"} 2
# celery_mqtt_guard_gps_processed_total{guard_id="101"} 1
# celery_mqtt_critical_alert_processed_total{alert_type="panic"} 1
```

---

## 🎯 Specific Test Cases

### Test Case 1: Verify Panic Button Works

```bash
# Publish panic button message
mosquitto_pub -h localhost -t "alert/panic/guard-999" -m '{
  "alert_type": "panic",
  "severity": "critical",
  "message": "TEST: Panic button pressed",
  "location": {"lat": 12.9716, "lon": 77.5946},
  "timestamp": "'$(date -Iseconds)'"
}'

# Wait 2 seconds
sleep 2

# Check database
python manage.py shell
>>> from apps.mqtt.models import DeviceAlert
>>> alert = DeviceAlert.objects.filter(source_id__contains='999').latest('received_at')
>>> print(f"Alert: {alert.alert_type}")
>>> print(f"Severity: {alert.severity}")
>>> print(f"Status: {alert.status}")
>>> print(f"SMS sent: {alert.sms_sent}")
>>> print(f"Email sent: {alert.email_sent}")

# Expected:
# Alert: PANIC
# Severity: CRITICAL
# Status: NEW
# SMS sent: True (if Twilio configured)
# Email sent: True
```

---

### Test Case 2: Verify Geofence Violation Detection

```bash
# Publish GPS OUTSIDE geofence (far from 12.9716, 77.5946)
mosquitto_pub -h localhost -t "guard/guard-888/gps" -m '{
  "lat": 13.0716,
  "lon": 78.5946,
  "accuracy": 10.0,
  "guard_id": 1,
  "client_id": 1,
  "timestamp": "'$(date -Iseconds)'"
}'

# Wait 3 seconds
sleep 3

# Check database
python manage.py shell
>>> from apps.mqtt.models import GuardLocation, DeviceAlert
>>>
>>> # Check GPS stored
>>> gps = GuardLocation.objects.filter(guard_id=1).latest('received_at')
>>> print(f"GPS stored: {gps.location}")
>>> print(f"In geofence: {gps.in_geofence}")
>>> print(f"Violation: {gps.geofence_violation}")
>>>
>>> # If violation, check alert created
>>> if gps.geofence_violation:
...     alert = DeviceAlert.objects.filter(alert_type='GEOFENCE_VIOLATION').latest('received_at')
...     print(f"✅ Geofence alert created: {alert.message}")
```

---

### Test Case 3: Verify WebSocket Real-Time Updates

**Terminal 1: Subscribe to WebSocket**
```bash
wscat -c "ws://localhost:8000/ws/noc/dashboard/"

# Wait for connection:
# < {"type": "connected", "tenant_id": 1}
```

**Terminal 2: Publish Critical Alert**
```bash
python scripts/testing/generate_mqtt_test_data.py --scenario critical_alerts --count 1
```

**Terminal 1: Should receive** (within 1-2 seconds):
```json
< {
  "type": "critical_alert",
  "data": {
    "source_id": "guard-101",
    "alert_type": "PANIC",
    "severity": "CRITICAL",
    "message": "Panic button pressed by guard"
  },
  "priority": "critical",
  "timestamp": "2025-11-01T10:50:12Z"
}
```

**Result:** ✅ Real-time update confirmed (MQTT → WebSocket in < 2 seconds)

---

## 📊 Sample Test Report

After running tests, you should see:

```
============================================================
MQTT Pipeline Verification (Last 5 minutes)
============================================================

============================================================
  Device Telemetry Verification
============================================================
✅ Device telemetry records created
   Found 5 records in last 5 minutes
✅ Telemetry has battery data
✅ Telemetry has signal data
✅ Telemetry has raw MQTT payload

============================================================
  Guard GPS Tracking Verification
============================================================
✅ Guard GPS records created
   Found 5 records in last 5 minutes
✅ GPS has PostGIS Point data
✅ Geofence validation ran
   ⚠️  2 geofence violations detected
✅ Geofence violations triggered alerts
   Found 2 geofence violation alerts

============================================================
  Sensor Readings Verification
============================================================
✅ Sensor reading records created
   Found 5 records in last 5 minutes
   🔥 1 smoke alarms detected
✅ Smoke alarms triggered fire alerts
   Found 1 fire alerts

============================================================
  Device Alerts Verification
============================================================
✅ Device alert records created
   Found 6 alerts in last 5 minutes

   📧 Notifications sent:
   - SMS: 3
   - Email: 6
   - Push: 0

============================================================
  Metrics Verification
============================================================
✅ MQTT metrics being collected
   Found 15 MQTT metric keys in cache
✅ WebSocket metrics being collected
   Found 8 WebSocket metric keys in cache

============================================================
  Prometheus Export Verification
============================================================
✅ Prometheus /metrics/export/ accessible
   Status code: 200
✅ Celery metrics exported
✅ MQTT metrics exported
✅ WebSocket metrics exported

============================================================
  Verification Summary
============================================================

✅ Passed: 20
❌ Failed: 0
📊 Success Rate: 100.0%

🎉 ALL CHECKS PASSED - Pipeline is working correctly!
```

---

## 🚀 Ready for Production?

If you see **100% success rate** after running tests:

✅ **YES** - Pipeline is fully operational and ready for production deployment

**Next steps:**
1. Review deployment checklist: `MESSAGE_BUS_DEPLOYMENT_CHECKLIST.md`
2. Deploy to staging environment first
3. Run tests in staging
4. Deploy to production
5. Monitor for 24 hours

---

**Quick Start Version:** 1.0
**For Full Details:** See `MQTT_PIPELINE_TESTING_GUIDE.md`
