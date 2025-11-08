# Alternative MQTT Setup Options (No Global Install)

**Problem:** Don't want to install Mosquitto globally
**Solution:** 3 alternatives that work without global installation

---

## ✅ Option 1: Docker (BEST - Recommended)

**Advantages:**
- No global installation
- Professional-grade broker
- Easy to start/stop
- Works identically to production

### Quick Setup (30 seconds)

```bash
# Start Mosquitto in Docker
docker run -d \
  --name mosquitto-test \
  -p 1883:1883 \
  eclipse-mosquitto:latest

# Verify it's running
docker ps | grep mosquitto

# Test connection
docker exec mosquitto-test mosquitto_sub -t "test" -C 1 &
sleep 1
docker exec mosquitto-test mosquitto_pub -t "test" -m "Hello"

# Should print: Hello
```

### Use with Tests

```bash
# With Docker mosquitto running, just run tests normally:
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5
python scripts/testing/verify_mqtt_pipeline.py

# Stop when done
docker stop mosquitto-test
docker rm mosquitto-test
```

**That's it!** Works perfectly with all our test scripts.

---

## ✅ Option 2: Python MQTT Broker (Lightweight)

**Use `hbmqtt` - Pure Python MQTT broker** (can install in venv)

### Setup

```bash
# Install in your venv
pip install hbmqtt

# Create simple config
cat > /tmp/mqtt_broker_config.yaml << 'EOF'
listeners:
  default:
    type: tcp
    bind: localhost:1883
auth:
  allow-anonymous: true
EOF

# Start broker (Terminal 1)
hbmqtt --config /tmp/mqtt_broker_config.yaml

# Expected output:
# [INFO] HBMQTT broker running on localhost:1883
```

### Use with Tests

```bash
# In another terminal (Terminal 2):
source venv/bin/activate
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

# Verify
python scripts/testing/verify_mqtt_pipeline.py
```

**Advantages:**
- ✅ Installs in venv (pip install)
- ✅ Pure Python (no C compilation)
- ✅ Works with our test scripts

**Disadvantages:**
- ⚠️ Not production-grade
- ⚠️ Slower than mosquitto
- ⚠️ Less battle-tested

---

## ✅ Option 3: Skip MQTT Broker (Direct Task Testing)

**Test Celery tasks directly** without going through MQTT:

### Direct Task Testing

```bash
# Activate venv
source venv/bin/activate

# Run migrations first
python manage.py makemigrations mqtt
python manage.py migrate mqtt

# Start Django
python manage.py shell
```

**In Django shell:**
```python
from background_tasks.mqtt_handler_tasks import (
    process_device_telemetry,
    process_guard_gps,
    process_sensor_data,
    process_device_alert
)
from datetime import datetime

# Test device telemetry directly (bypass MQTT)
topic = "device/test-sensor/telemetry"
data = {
    'battery': 85,
    'signal': -65,
    'temperature': 24.5,
    'timestamp': datetime.now().isoformat(),
    '_mqtt_metadata': {'topic': topic, 'qos': 1}
}

# Call task directly (synchronous - no Celery needed for testing)
process_device_telemetry(topic, data)
# Should print: INFO - Device test-sensor telemetry stored (ID: 1): battery=85%...

# Verify in database
from apps.mqtt.models import DeviceTelemetry
telemetry = DeviceTelemetry.objects.latest('received_at')
print(f"✅ Stored: Device {telemetry.device_id}, Battery {telemetry.battery_level}%")

# Test guard GPS with geofence
topic = "guard/guard-123/gps"
data = {
    'lat': 12.9716,
    'lon': 77.5946,
    'accuracy': 10.5,
    'guard_id': 1,  # Must exist in database
    'client_id': 1,
    'timestamp': datetime.now().isoformat(),
    '_mqtt_metadata': {'topic': topic, 'qos': 1}
}

process_guard_gps(topic, data)
# Should print: INFO - GPS location stored for guard 1...

# Verify
from apps.mqtt.models import GuardLocation
gps = GuardLocation.objects.latest('received_at')
print(f"✅ GPS stored: ({gps.location.y}, {gps.location.x}), In geofence: {gps.in_geofence}")

# Test critical alert
topic = "alert/panic/guard-123"
data = {
    'source_id': 'guard-123',
    'alert_type': 'panic',
    'severity': 'critical',
    'message': 'Test panic button',
    'location': {'lat': 12.9716, 'lon': 77.5946},
    'timestamp': datetime.now().isoformat(),
    '_mqtt_metadata': {'topic': topic, 'qos': 2}
}

process_device_alert(topic, data)
# Should print: CRITICAL - Device alert stored...
# Should print: INFO - Notifications sent for alert X...

# Verify
from apps.mqtt.models import DeviceAlert
alert = DeviceAlert.objects.latest('received_at')
print(f"✅ Alert stored: {alert.alert_type}, SMS sent: {alert.sms_sent}, Email sent: {alert.email_sent}")
```

**Advantages:**
- ✅ No MQTT broker needed at all
- ✅ No Docker needed
- ✅ Tests core logic (data persistence, geofence, notifications)
- ✅ Fast (synchronous execution)

**Disadvantages:**
- ⚠️ Doesn't test MQTT subscriber
- ⚠️ Doesn't test MQTT routing
- ⚠️ Not end-to-end

---

## 📊 Comparison

| Option | Installation | Complexity | Coverage | Production-Like |
|--------|--------------|------------|----------|-----------------|
| **Docker mosquitto** | `docker run` | Low | 100% | ✅ Yes |
| **hbmqtt (Python)** | `pip install` | Low | 100% | ⚠️ Testing only |
| **Direct task test** | None | Very low | 70% | ⚠️ Skips MQTT layer |
| **Global mosquitto** | `brew install` | Low | 100% | ✅ Yes |

---

## 🎯 My Recommendation

**For Testing:** Use **Docker** (Option 1)
```bash
# One command to start
docker run -d -p 1883:1883 --name mqtt-test eclipse-mosquitto

# Run all tests
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5
python scripts/testing/verify_mqtt_pipeline.py

# One command to stop
docker stop mqtt-test && docker rm mqtt-test
```

**For Quick Validation:** Use **Direct Task Testing** (Option 3)
- No installation needed
- Proves core logic works
- 5 minutes total

**For Production:** Install **mosquitto globally**
- Most robust
- Best performance
- What you'll use in production anyway

---

## 🚀 Quickest Path to Test Right Now

**If you have Docker:**
```bash
# Start mosquitto (1 command)
docker run -d -p 1883:1883 eclipse-mosquitto

# Run tests (2 commands)
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5
python scripts/testing/verify_mqtt_pipeline.py
```

**If you don't have Docker:**
```bash
# Test core logic directly (no broker needed)
python manage.py shell

# Run the code from Option 3 above
# Tests: Data persistence, geofence, notifications
# Takes 5 minutes
```

**Want me to create a script for Option 3 (direct testing without MQTT broker)?**