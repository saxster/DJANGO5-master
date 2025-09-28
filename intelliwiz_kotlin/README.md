# Stream Testbench - Kotlin Load Generator

High-performance load generator for WebSocket, MQTT, and HTTP protocols, specifically designed for testing Django Stream Testbench infrastructure.

## Features

- 🔌 **WebSocket Support**: Real-time bidirectional communication testing
- 📡 **MQTT Protocol**: Message queuing and pub/sub pattern testing
- 🌐 **HTTP REST API**: Traditional request/response testing
- 🎭 **Mixed Protocol**: Combined protocol scenarios
- 🧪 **Failure Injection**: Network delays, connection drops, schema drift
- 📊 **Real-time Metrics**: Latency, throughput, error rates
- 🔒 **Authentication**: Bearer tokens, API keys, basic auth
- ⚙️  **Configurable**: JSON-based scenario configuration

## Quick Start

### 1. Build the Project

```bash
cd intelliwiz_kotlin
./gradlew build
```

### 2. Generate Example Scenarios

```bash
./gradlew run --args="generate --type all --output scenarios/"
```

### 3. Run a Test

```bash
# Quick WebSocket test
./gradlew run --args="run --protocol websocket --endpoint localhost:8000/ws/mobile/sync/ --duration 60 --connections 10 --rate 5"

# Run from scenario file
./gradlew run --args="run --scenario scenarios/mobile_sync_stress.json --output results.json"
```

### 4. Build Standalone JAR

```bash
./gradlew fatJar
java -jar build/libs/intelliwiz_kotlin-1.0.0-fat.jar run --help
```

## Usage

### Command Line Interface

```bash
streamtestbench [OPTIONS] COMMAND [ARGS]...

Commands:
  run       Run a test scenario
  generate  Generate example scenario files
  validate  Validate scenario configuration files
```

### Run Command Options

```bash
streamtestbench run [OPTIONS]

Options:
  -s, --scenario FILE       JSON file containing scenario configuration
  -e, --endpoint TEXT       Override endpoint URL
  -d, --duration INT        Override test duration in seconds
  -p, --protocol CHOICE     Protocol to use (websocket, mqtt, http)
  -c, --connections INT     Number of concurrent connections
  -r, --rate DOUBLE         Messages per second
  -o, --output FILE         Output file for results
  -v, --verbose             Verbose logging
```

## Scenario Configuration

### Basic Structure

```json
{
  "name": "Test Scenario",
  "description": "Description of the test",
  "protocol": "WEBSOCKET",
  "endpoint": "localhost:8000/ws/mobile/sync/",
  "duration_seconds": 300,
  "connections": 50,
  "rates": {
    "messagesPerSecond": 10.0,
    "burstMultiplier": 2.0,
    "rampUpSeconds": 30,
    "rampDownSeconds": 30
  },
  "payloads": ["VOICE_DATA", "BEHAVIORAL_DATA", "METRICS"],
  "failureInjection": { ... },
  "authentication": { ... },
  "validation": { ... }
}
```

### Supported Protocols

- `WEBSOCKET`: Real-time WebSocket connections
- `MQTT`: MQTT pub/sub messaging
- `HTTP`: REST API calls (future)
- `MIXED`: Combined protocol testing

### Payload Types

- `VOICE_DATA`: Simulated voice recognition data
- `BEHAVIORAL_DATA`: User behavior analytics
- `SESSION_DATA`: Session management data
- `METRICS`: System performance metrics
- `HEARTBEAT`: Connection keep-alive messages
- `CUSTOM`: Custom test payloads

### Failure Injection

```json
"failureInjection": {
  "enabled": true,
  "networkDelays": {
    "enabled": true,
    "rangeMs": {"start": 50, "endInclusive": 500},
    "probability": 0.05
  },
  "duplicateMessages": {
    "probability": 0.01,
    "maxDuplicates": 3
  },
  "schemaDrift": {
    "probability": 0.001,
    "mutations": [
      {
        "type": "ADD_FIELD",
        "fieldPath": "extra_field",
        "newValue": "test_value"
      }
    ]
  },
  "connectionDrops": {
    "probability": 0.001,
    "reconnectDelayMs": 1000
  }
}
```

### Authentication

```json
"authentication": {
  "type": "BEARER_TOKEN",
  "credentials": {
    "token": "your_bearer_token"
  }
}
```

Supported auth types:
- `BEARER_TOKEN`: OAuth-style bearer tokens
- `BASIC_AUTH`: Username/password authentication
- `API_KEY`: API key authentication
- `NONE`: No authentication

## Example Scenarios

### WebSocket Mobile Sync

```json
{
  "name": "Mobile Sync Test",
  "protocol": "WEBSOCKET",
  "endpoint": "localhost:8000/ws/mobile/sync/",
  "duration_seconds": 300,
  "connections": 50,
  "rates": {
    "messagesPerSecond": 15.0,
    "burstMultiplier": 2.5
  },
  "payloads": ["VOICE_DATA", "BEHAVIORAL_DATA", "SESSION_DATA"]
}
```

### MQTT GraphQL Processing

```json
{
  "name": "MQTT GraphQL Load",
  "protocol": "MQTT",
  "endpoint": "localhost:1883",
  "duration_seconds": 180,
  "connections": 20,
  "rates": {
    "messagesPerSecond": 8.0
  },
  "payloads": ["BEHAVIORAL_DATA", "METRICS"]
}
```

## Output and Results

### JSON Results Format

```json
{
  "scenarioName": "Test Scenario",
  "startTime": 1645123456789,
  "endTime": 1645123756789,
  "totalMessages": 15000,
  "successfulMessages": 14850,
  "failedMessages": 150,
  "averageLatencyMs": 45.2,
  "p95LatencyMs": 89.5,
  "p99LatencyMs": 156.7,
  "throughputQps": 49.5,
  "errorRate": 0.01,
  "anomaliesDetected": 3,
  "connectionMetrics": { ... },
  "errors": [ ... ]
}
```

### Console Summary

```
📊 Stream Testbench Results Summary
==================================================

🎯 Scenario: Mobile Sync Test
   Duration: 300.0s
   Total Messages: 15000
   Successful: 14850
   Failed: 150
   Success Rate: 99.00%
   Throughput: 49.50 QPS
   Avg Latency: 45.20ms
   P95 Latency: 89.50ms
   P99 Latency: 156.70ms

🏆 Overall Summary:
   Total Messages: 15000
   Success Rate: 99.00%
   Average Throughput: 49.50 QPS
   Average Latency: 45.20ms
   Total Anomalies: 3
```

## Integration with Django

The generator is designed to work seamlessly with the Django Stream Testbench:

1. **WebSocket Endpoints**: Connects to Django Channels WebSocket consumers
2. **MQTT Topics**: Publishes to configured MQTT broker topics
3. **Authentication**: Supports Django authentication mechanisms
4. **Payload Format**: Generates payloads compatible with Django serializers
5. **Error Handling**: Reports errors in Django-compatible format

## Development

### Requirements

- Java 17+
- Kotlin 1.9.22+
- Gradle 8.0+

### Dependencies

- **Ktor**: WebSocket and HTTP client
- **Eclipse Paho**: MQTT client
- **Kotlinx Serialization**: JSON handling
- **Clikt**: Command line interface
- **Logback**: Logging

### Building

```bash
# Build project
./gradlew build

# Run tests
./gradlew test

# Create fat JAR
./gradlew fatJar
```

### Adding New Protocols

1. Create generator class in `generators/` package
2. Implement protocol-specific logic
3. Add to `ScenarioRunner.runScenario()`
4. Update CLI options and validation

## Best Practices

### Performance Testing

- Start with low rates and gradually increase
- Monitor system resources during testing
- Use realistic payload sizes and patterns
- Include ramp-up/ramp-down periods

### Scenario Design

- Model real user behavior patterns
- Include appropriate failure injection
- Validate responses when possible
- Use meaningful test names and descriptions

### CI/CD Integration

```bash
# Quick smoke test
java -jar streamtestbench.jar run --protocol websocket --duration 30 --connections 5 --rate 2

# Load test gate
java -jar streamtestbench.jar run --scenario ci/load_test.json --output results.json

# Validate results
if [ $(jq '.errorRate' results.json | cut -d. -f1) -gt 0 ]; then
  echo "Load test failed with high error rate"
  exit 1
fi
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Verify Django server is running and WebSocket routing is configured
2. **MQTT Connection Failed**: Check MQTT broker settings and authentication
3. **High Latency**: Monitor network conditions and server resources
4. **Memory Issues**: Reduce connection count or message rate

### Logging

Enable verbose logging for debugging:

```bash
java -jar streamtestbench.jar run --verbose --scenario test.json
```

### Performance Tuning

- Adjust JVM memory: `java -Xmx4g -jar streamtestbench.jar`
- Tune connection pools and timeouts
- Monitor GC performance for long-running tests
- Use multiple generator instances for extreme load

## Contributing

1. Follow Kotlin coding conventions
2. Add tests for new features
3. Update documentation
4. Ensure compatibility with Django integration