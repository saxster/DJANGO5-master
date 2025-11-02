# Mosquitto MQTT Broker - Setup Guide for macOS

**For:** Message Bus Testing
**Platform:** macOS (Darwin 25.0.0)
**Installation Time:** 5 minutes

---

## Quick Install (Recommended)

```bash
# Install via Homebrew (easiest)
brew install mosquitto

# Start mosquitto as a service
brew services start mosquitto

# Verify it's running
brew services list | grep mosquitto
# Should show: mosquitto started

# Test connection
mosquitto_sub -h localhost -t test/topic -C 1 &
sleep 1
mosquitto_pub -h localhost -t test/topic -m "Hello MQTT"
# Should print: Hello MQTT
```

**That's it!** Mosquitto is now running on `localhost:1883`

---

## Configuration (Optional)

**Default config location:** `/opt/homebrew/etc/mosquitto/mosquitto.conf`

**View current config:**
```bash
cat /opt/homebrew/etc/mosquitto/mosquitto.conf
```

**For testing (no authentication needed):**
```bash
# Edit config
nano /opt/homebrew/etc/mosquitto/mosquitto.conf

# Add these lines for development:
listener 1883
allow_anonymous true

# Restart
brew services restart mosquitto
```

---

## Verify Installation

```bash
# Check mosquitto is running
ps aux | grep mosquitto

# Check port is listening
lsof -i :1883
# Should show mosquitto listening on port 1883

# Test publish/subscribe
# Terminal 1:
mosquitto_sub -h localhost -t "test/#" -v

# Terminal 2:
mosquitto_pub -h localhost -t "test/message" -m "Test successful"

# Terminal 1 should print:
# test/message Test successful
```

---

## Integration with Project

**Configuration already set in project:**
```python
# intelliwiz_config/settings/integrations.py
MQTT_CONFIG = {
    "BROKER_ADDRESS": env("MQTT_BROKER_ADDRESS", default="localhost"),
    "broker_port": env.int("MQTT_BROKER_PORT", default=1883),
    ...
}
```

**No code changes needed!** Just install mosquitto and it works.

---

## Start/Stop Commands

```bash
# Start
brew services start mosquitto

# Stop
brew services stop mosquitto

# Restart
brew services restart mosquitto

# Status
brew services list | grep mosquitto

# View logs
tail -f /opt/homebrew/var/log/mosquitto/mosquitto.log
```

---

## Now You Can Run Tests!

After installing mosquitto:

```bash
# Generate test data
python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

# Verify pipeline
python scripts/testing/verify_mqtt_pipeline.py --verbose

# Should see: 🎉 ALL CHECKS PASSED
```

---

**Setup Guide Version:** 1.0
**Installation Time:** 5 minutes
**Next Step:** Run full system tests!
