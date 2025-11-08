# Attendance Models - Quick Reference

**Last Updated**: November 4, 2025
**Status**: Refactored into modular package

---

## Package Structure

```
apps/attendance/models/
├── __init__.py                        # Central exports (backward compatibility)
├── people_eventlog.py                 # Main attendance tracking
├── geofence.py                        # Geographic boundaries
├── tracking.py                        # GPS tracking (temporary)
├── test_geo.py                        # PostGIS testing
├── audit_log.py                       # Audit & compliance
├── consent.py                         # Consent management
├── post.py                            # Duty station definitions
├── post_assignment.py                 # Roster management
├── post_order_acknowledgement.py      # Digital post orders
├── approval_workflow.py               # Approval workflow
├── alert_monitoring.py                # Alert & monitoring
├── fraud_alert.py                     # Fraud detection alerts
├── user_behavior_profile.py           # Behavioral analytics
├── attendance_photo.py                # Photo capture
└── sync_conflict.py                   # Conflict resolution
```

---

## Import Guide

### Core Attendance Models

```python
from apps.attendance.models import PeopleEventlog, Geofence, Tracking, TestGeo
```

**PeopleEventlog** - Main attendance tracking model
- Check-in/check-out events
- Geospatial validation (GPS coordinates, geofences)
- Biometric verification (face recognition)
- Post assignment tracking
- Fraud detection scoring
- Data retention compliance

**Geofence** - Geographic boundary definitions
- Polygon and circle geofence types
- PostGIS integration
- Configurable hysteresis buffer

**Tracking** - Temporary GPS tracking table
- Real-time location tracking
- Conveyance, tours, site visits

**TestGeo** - PostGIS testing model
- Test model for geospatial functionality

### Helper Types & Functions

```python
from apps.attendance.models import (
    PEventLogExtras,     # TypedDict for peventlogextras JSON
    PELGeoJson,          # TypedDict for GeoJSON structure
    peventlog_json,      # Default JSON factory
    pel_geojson,         # Default GeoJSON factory
)
```

### Audit & Compliance

```python
from apps.attendance.models import (
    AttendanceAccessLog,      # Audit trail for data access
    AuditLogRetentionPolicy,  # Retention policy configuration
)
```

### Consent Management

```python
from apps.attendance.models import (
    ConsentPolicy,         # Policy templates (GPS, biometric)
    EmployeeConsentLog,    # Employee consent records
    ConsentRequirement,    # Jurisdiction-specific requirements
)
```

### Post Assignment (Phase 2)

```python
from apps.attendance.models import (
    Post,                       # Duty station definitions
    PostAssignment,             # Roster/schedule assignments
    PostOrderAcknowledgement,   # Digital post order compliance
)
```

### Approval Workflow (Phase 4)

```python
from apps.attendance.models import (
    ApprovalRequest,     # Approval requests (overtime, emergency)
    ApprovalAction,      # Approval decision records
    AutoApprovalRule,    # Automated approval rules
)
```

### Alert & Monitoring (Phase 5)

```python
from apps.attendance.models import (
    AlertRule,           # Alert configuration
    AttendanceAlert,     # Alert instances
    AlertEscalation,     # Escalation tracking
)
```

### Fraud Detection

```python
from apps.attendance.models import (
    FraudAlert,              # ML-detected fraud alerts
    UserBehaviorProfile,     # Behavioral baseline profiles
)
```

### Photo Capture (Phase 1.4)

```python
from apps.attendance.models import AttendancePhoto
```

### Conflict Resolution

```python
from apps.attendance.models import SyncConflict
```

---

## Model Relationships

### PeopleEventlog Dependencies
- **ForeignKey**: People (AUTH_USER_MODEL), Bt (client/bu), Shift, GeofenceMaster, TypeAssist
- **ForeignKey (Phase 2)**: Post, PostAssignment, AttendancePhoto

### Post Assignment Chain
```
Post ← PostAssignment ← PeopleEventlog
                     ↓
          PostOrderAcknowledgement
```

### Approval Workflow
```
ApprovalRequest → ApprovalAction
              ↓
        AutoApprovalRule
```

### Alert Flow
```
AlertRule → AttendanceAlert → AlertEscalation
```

### Fraud Detection
```
PeopleEventlog → FraudAlert
              ↓
      UserBehaviorProfile
```

---

## Database Tables

| Model | Table Name | Key Indexes |
|-------|-----------|-------------|
| PeopleEventlog | peopleeventlog | tenant+datefor, tenant+people, fraud_score |
| Geofence | geofence | tenant+is_active, tenant+bu |
| Tracking | tracking | - |
| Post | attendance_post | tenant+site, post_code |
| PostAssignment | attendance_post_assignment | tenant+date+shift, worker_id |

---

## Common Queries

### Get attendance for date range
```python
from apps.attendance.models import PeopleEventlog

records = PeopleEventlog.objects.filter(
    tenant='default',
    datefor__gte=start_date,
    datefor__lte=end_date
)
```

### Get active geofences
```python
from apps.attendance.models import Geofence

geofences = Geofence.objects.filter(
    tenant='default',
    is_active=True
)
```

### Get post assignments for date
```python
from apps.attendance.models import PostAssignment

assignments = PostAssignment.objects.filter(
    tenant='default',
    assignment_date=date
).select_related('post', 'worker')
```

---

## Migration Notes

✅ **NO MIGRATIONS REQUIRED**

This refactoring is code organization only:
- Models retain same table names
- Fields unchanged
- Indexes unchanged
- Relationships unchanged

---

## Backward Compatibility

✅ **100% BACKWARD COMPATIBLE**

All existing imports continue to work:
```python
# Old import pattern (still works)
from apps.attendance.models import PeopleEventlog

# Multi-model imports (still works)
from apps.attendance.models import (
    Post,
    PostAssignment,
    PeopleEventlog,
)
```

The `__init__.py` file in the models package ensures all models are accessible at the package level.

---

## Deprecation Notice

⚠️ **`models_deprecated.py` will be deleted after verification**

The original monolithic `models.py` has been renamed to `models_deprecated.py` with a deprecation notice. It will be deleted once all imports are verified to work correctly with the new package structure.

---

## References

- **Complete Documentation**: `ATTENDANCE_MODELS_REFACTORING_COMPLETE.md`
- **Verification Script**: `scripts/verify_attendance_models_refactoring.py`
- **Architecture Rules**: `.claude/rules.md`

---

**Maintainer**: Development Team
**Review Cycle**: Quarterly or on model structure changes
