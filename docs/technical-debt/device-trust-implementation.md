# Device Trust Implementation TODO

## Status: STUBBED (Fail-Open Mode)

**Date**: 2025-11-11
**Priority**: P2 (Important but not blocking)
**Phase**: Sprint 6-10 (Design and Implementation)

## Background

Device Trust Service references `DeviceRegistration` and `DeviceRiskEvent` models that don't exist.
Temporarily stubbed to prevent ImportError while models are designed and implemented.

### Current Behavior

- `DeviceTrustService.validate_device()` always returns fail-open response (passed=True)
- Logs warning when called: "Device trust service called but models not available - failing open"
- All device registration and risk scoring disabled
- Helper methods (`_calculate_risk_score`, `_register_or_update_device`) stubbed with debug logging
- Voice biometric enrollment temporarily disabled until models implemented

## Required Implementation

### Models Needed

**File**: `apps/peoples/models/device_registry.py` (file exists, only 217 lines)

#### DeviceRegistration Model

```python
class DeviceRegistration(TenantAwareModel):
    """Tracks enrolled devices for biometric enrollment security."""

    # Core Fields
    device_id = models.CharField(unique=True, max_length=256, indexed=True)
    user = models.ForeignKey(People, on_delete=models.CASCADE)

    # Device Fingerprint
    device_fingerprint = models.JSONField()  # Canvas, WebGL, User-Agent hash
    user_agent = models.CharField(max_length=512)
    ip_address = models.GenericIPAddressField()

    # Trust Scoring
    trust_score = models.IntegerField(default=0)
    trust_factors = models.JSONField(default=dict)  # Individual factor scores
    is_trusted = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    biometric_enrolled = models.BooleanField(default=False)

    # Timestamps
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['user', 'device_id']),
            models.Index(fields=['user', 'is_trusted']),
            models.Index(fields=['is_blocked']),
        ]

    @staticmethod
    def generate_device_id(fingerprint_data: Dict[str, Any]) -> str:
        """Generate device ID from fingerprint data."""
        import hashlib
        import json
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
```

#### DeviceRiskEvent Model

```python
class DeviceRiskEvent(TenantAwareModel):
    """Security events associated with device registration."""

    # Reference
    device = models.ForeignKey(DeviceRegistration, on_delete=models.CASCADE, related_name='risk_events')

    # Event Details
    risk_score = models.IntegerField()  # 0-100
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('suspicious_login', 'Suspicious Login Attempt'),
            ('location_anomaly', 'Location Anomaly'),
            ('velocity_check_failed', 'Velocity Check Failed'),
            ('behavioral_anomaly', 'Behavioral Anomaly'),
            ('manual_flagged', 'Manually Flagged'),
        ]
    )

    # Resolution
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['device', 'detected_at']),
            models.Index(fields=['device', 'resolved']),
        ]
```

### Trust Scoring Algorithm

When both models are implemented, validation will use multi-factor scoring:

| Factor | Points | Condition |
|--------|--------|-----------|
| Known device | +50 | Device registered and not blocked |
| Corporate network | +30 | IP in corporate ranges |
| Biometric enrolled | +20 | Biometric already on device |
| Recent activity | +10 | Activity within 30 days |
| Low risk | +10 | Risk score < 20 |

**Enrollment Threshold**: 70 points (all factors aligned)

### Migration Strategy

**File**: Create `apps/peoples/migrations/0XXX_device_registry.py`

```python
# Two-step migration strategy:
# 1. CREATE: DeviceRegistration + DeviceRiskEvent tables
# 2. CREATE: Indexes on user_id, device_id, is_blocked, risk_score fields
# 3. Add data migration to generate device IDs for existing registrations
```

## Implementation Timeline

### Sprint 6: Design & Approval
- [ ] Design schema with security team review
- [ ] Define device fingerprinting algorithm
- [ ] Create ADR for device trust architecture

### Sprint 7: Models & Migrations
- [ ] Implement DeviceRegistration model
- [ ] Implement DeviceRiskEvent model
- [ ] Create database migrations
- [ ] Add indexes for performance
- [ ] Write model-level tests (100+ tests)

### Sprint 8: Service Implementation
- [ ] Implement full trust scoring algorithm
- [ ] Add device ID generation logic
- [ ] Add corporate network detection
- [ ] Add risk event calculation
- [ ] Write integration tests

### Sprint 9: Integration & Features
- [ ] Voice biometric enrollment integration
- [ ] Admin dashboard for device management
- [ ] Device blocking functionality
- [ ] Risk event investigation tools

### Sprint 10: Production Release
- [ ] Security review and hardening
- [ ] Load testing with 1000+ devices
- [ ] Production deployment
- [ ] Monitoring and alerting setup

## Risk Mitigation

### Fail-Open Strategy
- Currently returns `passed=True` to prevent blocking legitimate users
- All device trust features disabled until models implemented
- Warning logged every time service called
- Can be toggled via feature flag if needed

### Security Considerations
- Device fingerprinting vulnerable to spoofing (will add WebGL + Canvas hash)
- IP-based validation can be bypassed (will add behavioral analysis)
- Risk event model needs audit logging (will use AuditLog service)
- Biometric data must be encrypted at rest (will use Django-Cryptography)

## Testing Requirements

### Unit Tests (30+ required)
- Device ID generation consistency
- Trust score calculation with various factors
- Corporate network detection (valid + invalid IPs)
- Risk event aggregation

### Integration Tests (50+ required)
- Full enrollment flow with known device
- Unknown device from external IP rejection
- Device blocking and re-enablement
- Concurrent device registrations

### Load Tests (before production)
- 1000 concurrent device enrollments
- Device lookup performance (< 100ms)
- Risk event aggregation on 10k+ events

## Rollback Plan

If models fail in production:
1. Set `DeviceTrustService.FAIL_OPEN = True` (already default)
2. Deployment rollback to previous version
3. Database rollback using migration
4. Monitor user impact in logs

## References

- **ADR**: Architecture Decision Records (TBD)
- **Security Review**: Required before Sprint 6 (TBD)
- **Threat Model**: Device spoofing, IP spoofing, behavioral attacks (TBD)
- **Performance Baseline**: Device lookup < 100ms, trust scoring < 50ms (TBD)

## Notes

- Do NOT remove stub status until both models are fully implemented and tested
- Ensure all helper methods have comprehensive error handling
- Add metrics/telemetry for device trust decisions (for monitoring)
- Document device fingerprinting algorithm (privacy implications)
