# 🚀 Stream Testbench Quick Start Guide

Get up and running with Stream Testbench in 10 minutes!

## ⚡ Prerequisites

- Django 5.2.1+ with PostgreSQL
- Redis server running
- Python 3.11+
- Java 17+ (for Kotlin generator)

## 🎯 5-Minute Setup

### 1. Install Dependencies (2 minutes)

```bash
# Install Python packages
pip install -r requirements/base.txt

# The following packages are now included:
# - channels==4.1.0
# - channels-redis==4.2.0
# - daphne==4.1.2
```

### 2. Configure Django (1 minute)

The following apps are automatically configured in `settings.py`:
- ✅ `channels` and `daphne` - WebSocket support
- ✅ `apps.streamlab` - Stream testing core
- ✅ `apps.issue_tracker` - Anomaly detection

Redis Channel Layer is configured on DB 2 for isolation from cache.

### 3. Run Migrations (1 minute)

```bash
python manage.py migrate
```

This creates all necessary tables:
- `streamlab_*` - Test scenarios, runs, events
- `issue_tracker_*` - Anomaly signatures, occurrences, fixes

### 4. Start Services (1 minute)

```bash
# Start Django with ASGI (WebSocket support)
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# In another terminal, verify WebSocket is working
curl http://localhost:8000/health/
```

## 🧪 First Test (5 minutes)

### 1. Create Test Scenario

```bash
python manage.py shell << 'EOF'
from apps.streamlab.models import TestScenario
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first() or User.objects.create_superuser(
    'admin', 'admin@example.com', 'admin123'
)

scenario = TestScenario.objects.create(
    name="Quick WebSocket Test",
    description="5-minute WebSocket connectivity and performance test",
    protocol="websocket",
    endpoint="ws://localhost:8000/ws/mobile/sync/",
    config={
        "duration_seconds": 60,
        "connections": 5,
        "messages_per_second": 2
    },
    expected_p95_latency_ms=200,
    expected_error_rate=0.1,
    created_by=user
)

print(f"✅ Created scenario: {scenario.name} (ID: {scenario.id})")
EOF
```

### 2. Build Kotlin Generator

```bash
cd intelliwiz_kotlin
./gradlew fatJar

echo "✅ Kotlin generator built"
```

### 3. Run Test

```bash
# Quick test with Kotlin generator
java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar run \
  --protocol websocket \
  --endpoint localhost:8000/ws/mobile/sync/ \
  --duration 30 \
  --connections 3 \
  --rate 1 \
  --output first_test_results.json

echo "✅ Test completed - check first_test_results.json"
```

### 4. View Results

```bash
# View test results
cat first_test_results.json | jq '{
  scenarioName,
  totalMessages,
  successfulMessages,
  errorRate,
  averageLatencyMs,
  throughputQps
}'

# View in dashboard
open http://localhost:8000/streamlab/
```

## 📊 Dashboard Tour (2 minutes)

### 1. Main Dashboard
```bash
open http://localhost:8000/streamlab/
```

**What you'll see:**
- 📈 **Live Metrics**: Real-time performance charts
- 🏃‍♂️ **Active Runs**: Currently running tests
- 📋 **Recent Runs**: Test history with results
- 🚨 **Recent Anomalies**: Detected issues

### 2. Anomaly Detection
```bash
open http://localhost:8000/streamlab/anomalies/
```

**Features:**
- 🎯 **Active Signatures**: Recurring issue patterns
- ⏰ **Timeline**: Recent anomaly occurrences
- 💡 **Fix Suggestions**: AI-generated solutions

### 3. Admin Interface
```bash
open http://localhost:8000/admin/streamlab/
```

**Management:**
- 🎛️ **Test Scenarios**: Create and configure tests
- 📊 **Test Runs**: View detailed results
- 🔍 **Stream Events**: Individual event inspection

## 🎪 Advanced Examples (10 minutes)

### Example 1: High-Load WebSocket Test

```bash
# Create comprehensive scenario file
cat > advanced_websocket_test.json << 'EOF'
{
  "name": "Advanced WebSocket Load Test",
  "protocol": "WEBSOCKET",
  "endpoint": "localhost:8000/ws/mobile/sync/",
  "duration_seconds": 300,
  "connections": 25,
  "rates": {
    "messagesPerSecond": 8.0,
    "burstMultiplier": 2.0,
    "rampUpSeconds": 30,
    "rampDownSeconds": 30
  },
  "payloads": ["VOICE_DATA", "BEHAVIORAL_DATA", "SESSION_DATA"],
  "failureInjection": {
    "enabled": true,
    "networkDelays": {
      "enabled": true,
      "rangeMs": {"start": 10, "endInclusive": 200},
      "probability": 0.03
    },
    "duplicateMessages": {
      "probability": 0.01
    }
  },
  "validation": {
    "validateResponses": true,
    "maxLatencyMs": 1000
  }
}
EOF

# Run advanced test
java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar \
  run --scenario advanced_websocket_test.json --output advanced_results.json

# Check SLOs
python testing/stream_load_testing/check_slos.py advanced_results.json
```

### Example 2: MQTT GraphQL Processing

```bash
# Create MQTT scenario
cat > mqtt_graphql_test.json << 'EOF'
{
  "name": "MQTT GraphQL Processing Test",
  "protocol": "MQTT",
  "endpoint": "localhost:1883",
  "duration_seconds": 120,
  "connections": 10,
  "rates": {
    "messagesPerSecond": 3.0,
    "burstMultiplier": 1.5
  },
  "payloads": ["BEHAVIORAL_DATA", "METRICS"],
  "failureInjection": {
    "enabled": true,
    "duplicateMessages": {"probability": 0.02}
  }
}
EOF

# Run MQTT test (requires MQTT broker)
java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar \
  run --scenario mqtt_graphql_test.json --output mqtt_results.json
```

### Example 3: Mixed Protocol Chaos Test

```bash
# Generate chaos scenario
java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar \
  generate --type mixed --output chaos_scenarios/

# Run chaos test
java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar \
  run --scenario chaos_scenarios/mixed_protocol_stress.json
```

## 🔧 Troubleshooting Quick Fixes

### Issue: "No module named 'channels'"
```bash
pip install channels channels-redis daphne
```

### Issue: "Connection refused" on WebSocket
```bash
# Check if server is running ASGI
ps aux | grep daphne

# If not running, start with:
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

### Issue: "Redis connection failed"
```bash
# Check Redis status
redis-cli ping

# If not running:
redis-server --daemonize yes

# Check Redis DB 2 (Channel Layer)
redis-cli -n 2 ping
```

### Issue: "MQTT connection failed"
```bash
# Install and start Mosquitto
# Ubuntu/Debian:
sudo apt-get install mosquitto
sudo systemctl start mosquitto

# macOS:
brew install mosquitto
brew services start mosquitto

# Test connection:
mosquitto_pub -h localhost -p 1883 -t test -m "hello"
```

### Issue: Migration errors
```bash
# Reset migrations if needed (DEVELOPMENT ONLY)
python manage.py migrate streamlab zero
python manage.py migrate issue_tracker zero
rm apps/streamlab/migrations/0*.py
rm apps/issue_tracker/migrations/0*.py

# Recreate migrations
python manage.py makemigrations streamlab
python manage.py makemigrations issue_tracker
python manage.py migrate
```

## 🎯 Next Steps

### 1. Explore Dashboard Features
- **Live Monitoring**: Watch real-time metrics during tests
- **Anomaly Analysis**: Review detected patterns and fix suggestions
- **Historical Data**: Analyze performance trends over time

### 2. Create Custom Scenarios
- **Business-Specific Tests**: Model your actual usage patterns
- **Failure Scenarios**: Test resilience with chaos engineering
- **Performance Baselines**: Establish SLOs for your environment

### 3. Set Up Monitoring
- **Alerts**: Configure Slack/Teams/email notifications
- **SLO Tracking**: Define and monitor service level objectives
- **Trend Analysis**: Set up weekly performance reviews

### 4. Integrate with CI/CD
- **PR Gates**: Add performance validation to pull requests
- **Nightly Tests**: Schedule long-running stability tests
- **Regression Detection**: Catch performance regressions early

## 📚 What's Next?

### Learn More
- 📖 **Full Documentation**: `STREAM_TESTBENCH_DOCUMENTATION.md`
- 🛠️ **Operations Guide**: `STREAM_TESTBENCH_OPERATIONS_RUNBOOK.md`
- 🔒 **Security Guide**: Review PII protection and access controls
- ⚡ **Performance Tuning**: Optimize for your specific workloads

### Advanced Features
- 🤖 **Custom Anomaly Rules**: Create business-specific detection rules
- 🎨 **Dashboard Customization**: Add custom metrics and visualizations
- 🔄 **Auto-Fix Integration**: Set up automated fix application
- 📈 **Business Metrics**: Track business KPIs alongside technical metrics

### Community
- 🐛 **Report Issues**: Use GitHub issues for bugs and feature requests
- 💡 **Feature Requests**: Share ideas for improvements
- 🤝 **Contribute**: Submit pull requests with improvements
- 📣 **Share Results**: Share your testing results and insights

---

**🎉 Congratulations!** You now have a fully functional Stream Testbench system for comprehensive real-time stream testing, monitoring, and anomaly detection!

For detailed information on any topic, refer to the complete documentation or operations runbook.