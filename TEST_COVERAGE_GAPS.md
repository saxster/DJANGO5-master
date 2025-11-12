# Test Coverage Gaps - Technical Debt Documentation

> **Date**: November 11, 2025
> **Status**: 🟡 Technical Debt Identified
> **Priority**: HIGH for MQTT, MEDIUM for AI Testing

---

## Executive Summary

Two critical production apps have **zero test coverage** despite handling security-critical and ML-powered functionality:

1. **apps/mqtt** - IoT telemetry, GPS tracking, security alerts (HIGH priority)
2. **apps/ai_testing** - ML-powered test coverage analysis (MEDIUM priority)

Both apps are **active in INSTALLED_APPS** and process production data. This documentation serves as a roadmap for future test coverage implementation.

---

## 1. apps/mqtt - Security-Critical Test Coverage Gap

### App Overview
- **Purpose**: MQTT message persistence, IoT device telemetry, GPS geofence validation, facility security alerts
- **Models**: 4 critical models (478 lines total)
- **Status**: Active in production (line 85 of base_apps.py)
- **Test Coverage**: 0% (empty tests/ directory)

### Critical Functionality Without Tests

#### 1.1 Device Telemetry Model
**File**: `apps/mqtt/models.py` (DeviceTelemetry)
**Functionality**:
- Battery level monitoring (0-100%)
- Signal strength validation (0-31 range for GSM)
- Temperature monitoring (sensor health)
- Timestamp integrity (timezone-aware)

**Test Cases Needed** (Priority: MEDIUM):
- ✅ Test battery level validation (0-100% bounds)
- ✅ Test signal strength range validation
- ✅ Test temperature threshold alerts
- ✅ Test timestamp timezone handling
- ✅ Test tenant isolation (multi-tenant data)

#### 1.2 Guard Location Model (PostGIS)
**File**: `apps/mqtt/models.py` (GuardLocation)
**Functionality**:
- GPS coordinate validation (PostGIS PointField)
- Geofence containment checks
- Location accuracy tracking
- Movement history for safety compliance

**Test Cases Needed** (Priority: HIGH):
- ✅ Test geofence boundary validation (Point within Polygon)
- ✅ Test coordinate format validation (lat/lon ranges)
- ✅ Test accuracy_meters validation (GPS precision)
- ✅ Test location history queries (PostGIS spatial queries)
- ✅ Test cross-tenant geofence isolation (security critical)

#### 1.3 Sensor Reading Model
**File**: `apps/mqtt/models.py` (SensorReading)
**Functionality**:
- Motion detection (boolean flags)
- Door status monitoring (open/closed/forced)
- Smoke/fire detection (life safety)
- Intrusion detection (security)

**Test Cases Needed** (Priority: HIGH):
- ✅ Test sensor type validation (motion, door, smoke, intrusion)
- ✅ Test boolean flag combinations (door_open + door_forced edge cases)
- ✅ Test alert threshold triggering
- ✅ Test sensor data integrity (timestamp ordering)
- ✅ Test multi-tenant sensor isolation

#### 1.4 Device Alert Model (Life Safety)
**File**: `apps/mqtt/models.py` (DeviceAlert)
**Functionality**:
- **PANIC BUTTON** - Emergency response trigger
- **SOS** - Distress signal
- **FIRE** - Life safety alert
- **MEDICAL** - Health emergency
- Alert acknowledgment workflow

**Test Cases Needed** (Priority: CRITICAL):
- ✅ Test alert creation workflow (PANIC → acknowledged → resolved)
- ✅ Test alert priority escalation (PANIC > FIRE > MEDICAL)
- ✅ Test acknowledgment state machine (pending → ack → resolved)
- ✅ Test duplicate alert prevention (same device, same type, same minute)
- ✅ Test alert notification triggers (real-time WebSocket broadcast)
- ✅ Test tenant isolation (alerts don't leak across tenants)

### Recommended Test Structure

```bash
apps/mqtt/tests/
├── __init__.py (exists)
├── .gitkeep (created Nov 11, 2025)
├── test_device_telemetry.py (TODO)
│   ├── test_battery_level_validation
│   ├── test_signal_strength_validation
│   ├── test_temperature_monitoring
│   └── test_tenant_isolation
├── test_guard_location.py (TODO)
│   ├── test_geofence_validation (PostGIS)
│   ├── test_coordinate_validation
│   ├── test_spatial_queries
│   └── test_location_history
├── test_sensor_reading.py (TODO)
│   ├── test_sensor_type_validation
│   ├── test_boolean_combinations
│   ├── test_alert_thresholds
│   └── test_multi_tenant_isolation
└── test_device_alert.py (TODO - CRITICAL)
    ├── test_panic_button_workflow
    ├── test_alert_state_machine
    ├── test_alert_priority
    ├── test_duplicate_prevention
    ├── test_notification_triggers
    └── test_cross_tenant_isolation
```

### Estimated Effort
- **Test Files**: 4 files
- **Test Cases**: ~30 tests
- **Lines of Code**: ~800-1,000 lines
- **Time**: 8-12 hours (including PostGIS testing setup)

### Risk if Not Addressed
- **🔴 CRITICAL**: Panic button/SOS failures in production (life safety)
- **🔴 HIGH**: Geofence validation bugs (security compliance)
- **🟡 MEDIUM**: Sensor data integrity issues (false alarms)
- **🟡 MEDIUM**: Cross-tenant data leaks (privacy/security)

---

## 2. apps/ai_testing - ML Model Test Coverage Gap

### App Overview
- **Purpose**: ML-powered test coverage analysis, regression prediction, automated test generation
- **Models**: 5 ML models (significant ML codebase)
- **Status**: Active in production (line 92 of base_apps.py)
- **Test Coverage**: 0% (empty tests/ directory)

### Critical Functionality Without Tests

#### 2.1 Adaptive Threshold Model
**File**: `apps/ai_testing/models.py` (AdaptiveThreshold)
**Functionality**:
- ML-based threshold adjustment
- Historical performance tracking
- Automated threshold tuning

**Test Cases Needed** (Priority: MEDIUM):
- ✅ Test threshold adaptation logic
- ✅ Test historical data analysis
- ✅ Test threshold bounds validation
- ✅ Test performance metric tracking

#### 2.2 Test Coverage Gap Model
**File**: `apps/ai_testing/models/test_coverage_gaps.py` (444 lines)
**Functionality**:
- ML prediction of untested code paths
- Coverage gap prioritization
- Risk-based testing recommendations

**Test Cases Needed** (Priority: MEDIUM):
- ✅ Test gap detection algorithm
- ✅ Test priority calculation
- ✅ Test risk assessment logic
- ✅ Test recommendation generation

#### 2.3 Regression Prediction Model
**File**: `apps/ai_testing/models.py` (RegressionPrediction)
**Functionality**:
- Predict test regression likelihood
- Historical failure pattern analysis
- Proactive test recommendation

**Test Cases Needed** (Priority: MEDIUM):
- ✅ Test prediction accuracy validation
- ✅ Test historical pattern recognition
- ✅ Test regression threshold tuning
- ✅ Test false positive rates

#### 2.4 Management Commands (No Tests)
**Commands**:
- `ai_insights_report` - Generate ML insights
- `update_thresholds` - Auto-tune thresholds
- `analyze_patterns` - Pattern detection
- `generate_tests` - Auto-generate test code

**Test Cases Needed** (Priority: LOW):
- ✅ Test command argument parsing
- ✅ Test command output validation
- ✅ Test error handling in commands

### Recommended Test Structure

```bash
apps/ai_testing/tests/
├── __init__.py (create)
├── .gitkeep (created Nov 11, 2025)
├── test_adaptive_thresholds.py (TODO)
│   ├── test_threshold_adaptation
│   ├── test_historical_tracking
│   └── test_bounds_validation
├── test_coverage_gaps.py (TODO)
│   ├── test_gap_detection
│   ├── test_priority_calculation
│   └── test_recommendations
├── test_regression_prediction.py (TODO)
│   ├── test_prediction_accuracy
│   ├── test_pattern_recognition
│   └── test_false_positive_rate
└── test_commands.py (TODO)
    ├── test_ai_insights_report
    ├── test_update_thresholds
    ├── test_analyze_patterns
    └── test_generate_tests
```

### Estimated Effort
- **Test Files**: 4 files
- **Test Cases**: ~20 tests
- **Lines of Code**: ~600-800 lines
- **Time**: 6-8 hours (including ML model testing patterns)

### Risk if Not Addressed
- **🟡 MEDIUM**: ML predictions untested (model drift undetected)
- **🟡 MEDIUM**: Test gap detection inaccurate (false positives/negatives)
- **🟢 LOW**: Management commands fail silently

---

## Recommendations

### Immediate Actions (This Sprint)
1. **Document gaps** in ADR 004 (Testing Standards) ✅ (this file)
2. **Create .gitkeep files** to preserve test directories ✅ (completed)
3. **Prioritize MQTT tests** (security-critical, life safety)

### Short-Term (Next Sprint)
1. **Implement apps/mqtt/tests/** (HIGH priority)
   - Focus on alert workflow and geofence validation first
   - 8-12 hours estimated effort
2. **Add to backlog**: apps/ai_testing/tests/ (MEDIUM priority)

### Long-Term (Next Quarter)
1. **Comprehensive ML testing** for ai_testing app
2. **Integration tests** for MQTT + WebSocket pipeline
3. **Performance tests** for PostGIS spatial queries

---

## Acceptance Criteria for Test Completion

### apps/mqtt/tests/
- ✅ All 4 models have dedicated test files
- ✅ Security-critical workflows tested (panic button, SOS, alerts)
- ✅ PostGIS geofence validation tested
- ✅ Multi-tenant isolation verified
- ✅ Test coverage > 80% for alert state machine

### apps/ai_testing/tests/
- ✅ All 5 ML models have test files
- ✅ ML prediction accuracy validated
- ✅ Management commands tested
- ✅ Test coverage > 70% for core ML logic

---

## References

- **ADR 004**: Testing Standards (to be updated)
- **Technical Debt Tracker**: Add 2 items (MQTT tests, AI Testing tests)
- **Empty Directories**: Preserved with .gitkeep files
- **Priority Justification**:
  - MQTT = Life safety + security (panic buttons, intrusion detection)
  - AI Testing = ML model reliability (test predictions)

---

**Documented By**: Claude Code - Phase 7.2 Execution
**Next Action**: Create backlog items, schedule MQTT test implementation
**Timeline**: MQTT tests by end of Q4 2025, AI Testing tests by Q1 2026
