# MQTT Test Suite

## Quick Start

```bash
# Set environment variables
export SECRET_KEY="test-secret-key"
export DJANGO_SETTINGS_MODULE="intelliwiz_config.settings.test"

# Run all MQTT tests
pytest apps/mqtt/tests/ -v

# Run with coverage report
pytest apps/mqtt/tests/ --cov=apps/mqtt --cov-report=html:coverage_reports/mqtt_coverage --cov-report=term-missing -v
```

## Test Suites

### 1. Panic Button Security (CRITICAL)
**File**: `test_panic_button_security.py` (28 tests)
```bash
pytest apps/mqtt/tests/test_panic_button_security.py -v
```

### 2. Geofence Validation
**File**: `test_geofence_validation.py` (19 tests)
```bash
pytest apps/mqtt/tests/test_geofence_validation.py -v
```

### 3. Message Processing
**File**: `test_mqtt_message_processing.py` (25 tests)
```bash
pytest apps/mqtt/tests/test_mqtt_message_processing.py -v
```

### 4. Device Security
**File**: `test_device_security.py` (20 tests)
```bash
pytest apps/mqtt/tests/test_device_security.py -v
```

## Run Specific Test

```bash
pytest apps/mqtt/tests/test_panic_button_security.py::TestPanicButtonAlertCreation::test_panic_button_creates_critical_alert -xvs
```

## Total Tests: 79

## Test Coverage

See `TEST_COVERAGE_SUMMARY.md` for detailed coverage report.

**Priority**: CRITICAL (Safety-critical features)
