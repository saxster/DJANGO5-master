# Attendance Models - File Index

**Last Updated**: November 4, 2025  
**Total Files**: 16 model files + 1 deprecated file

---

## Directory Structure

```
apps/attendance/
├── models/
│   ├── __init__.py (125 lines)
│   ├── alert_monitoring.py (614 lines)
│   ├── approval_workflow.py (679 lines)
│   ├── attendance_photo.py (429 lines)
│   ├── audit_log.py (366 lines)
│   ├── consent.py (502 lines)
│   ├── fraud_alert.py (125 lines)
│   ├── geofence.py (61 lines) ⭐ NEW
│   ├── people_eventlog.py (476 lines) ⭐ NEW
│   ├── post_assignment.py (511 lines)
│   ├── post_order_acknowledgement.py (408 lines)
│   ├── post.py (420 lines)
│   ├── sync_conflict.py (89 lines)
│   ├── test_geo.py (26 lines) ⭐ NEW
│   ├── tracking.py (52 lines) ⭐ NEW
│   └── user_behavior_profile.py (349 lines)
└── models_deprecated.py (615 lines) ⚠️ TO BE DELETED
```

---

## File Purposes

### Core Attendance (4 files)

#### `people_eventlog.py` (476 lines) ⭐ NEW
**Models**: PeopleEventlog, PEventLogExtras, PELGeoJson  
**Purpose**: Main attendance tracking with check-in/check-out events  
**Features**:
- Geospatial validation (GPS, geofences)
- Biometric verification (face recognition)
- Post assignment tracking
- Fraud detection scoring
- Data retention compliance
- Encrypted biometric data storage

#### `geofence.py` (61 lines) ⭐ NEW
**Models**: Geofence  
**Purpose**: Geographic boundary definitions  
**Features**:
- Polygon and circle geofences
- PostGIS spatial validation
- Configurable hysteresis buffer
- Multi-tenant support

#### `tracking.py` (52 lines) ⭐ NEW
**Models**: Tracking  
**Purpose**: Temporary GPS tracking table  
**Features**:
- Real-time location tracking
- Conveyance tracking
- Tour tracking (internal/external)
- Site visit tracking

#### `test_geo.py` (26 lines) ⭐ NEW
**Models**: TestGeo  
**Purpose**: PostGIS testing model  
**Features**:
- Polygon, point, linestring fields
- Geospatial functionality testing

---

### Audit & Compliance (1 file)

#### `audit_log.py` (366 lines)
**Models**: AttendanceAccessLog, AuditLogRetentionPolicy  
**Purpose**: Audit trail and retention policies  
**Features**:
- Access logging for GDPR/CCPA compliance
- Configurable retention policies
- Automated data purging

---

### Consent Management (1 file)

#### `consent.py` (502 lines)
**Models**: ConsentPolicy, EmployeeConsentLog, ConsentRequirement  
**Purpose**: Employee consent management  
**Features**:
- Policy templates (GPS, biometric)
- Jurisdiction-specific requirements
- Consent expiration tracking
- Audit trail for consent changes

---

### Post Assignment (3 files)

#### `post.py` (420 lines)
**Models**: Post  
**Purpose**: Duty station/post definitions  
**Features**:
- Site association
- Geofence integration
- Equipment tracking
- Post types and requirements

#### `post_assignment.py` (511 lines)
**Models**: PostAssignment  
**Purpose**: Roster/schedule management  
**Features**:
- Worker-to-post assignments
- Shift scheduling
- Qualification validation
- Conflict detection

#### `post_order_acknowledgement.py` (408 lines)
**Models**: PostOrderAcknowledgement  
**Purpose**: Digital post orders and compliance tracking  
**Features**:
- Digital signature capture
- QR code generation
- Acknowledgement tracking
- Compliance verification

---

### Approval Workflow (1 file)

#### `approval_workflow.py` (679 lines)
**Models**: ApprovalRequest, ApprovalAction, AutoApprovalRule  
**Purpose**: Multi-level approval workflows  
**Features**:
- Overtime requests
- Emergency assignments
- Automated approval rules
- Escalation handling

---

### Alert & Monitoring (1 file)

#### `alert_monitoring.py` (614 lines)
**Models**: AlertRule, AttendanceAlert, AlertEscalation  
**Purpose**: Real-time alerting and escalation  
**Features**:
- Configurable alert rules
- Multi-channel notifications
- Escalation workflows
- Alert suppression

---

### Fraud Detection (2 files)

#### `fraud_alert.py` (125 lines)
**Models**: FraudAlert  
**Purpose**: ML-detected fraud alerts  
**Features**:
- Anomaly detection results
- Risk scoring
- Alert generation
- Investigation tracking

#### `user_behavior_profile.py` (349 lines)
**Models**: UserBehaviorProfile  
**Purpose**: Behavioral baseline profiles  
**Features**:
- Behavioral pattern learning
- Anomaly scoring
- Historical pattern tracking
- ML model integration

---

### Photo Capture (1 file)

#### `attendance_photo.py` (429 lines)
**Models**: AttendancePhoto  
**Purpose**: Photo capture for buddy punching prevention  
**Features**:
- Check-in/check-out photos
- Quality validation
- Secure storage
- Face recognition integration

---

### Conflict Resolution (1 file)

#### `sync_conflict.py` (89 lines)
**Models**: SyncConflict  
**Purpose**: Offline sync conflict resolution  
**Features**:
- Conflict detection
- Resolution strategies
- Manual override support
- Audit trail

---

### Package Configuration (1 file)

#### `__init__.py` (125 lines)
**Purpose**: Central import/export file  
**Features**:
- Backward compatibility for all imports
- Organized by domain
- Complete __all__ export list
- Documentation of model organization

---

## Statistics

| Category | Files | Total Lines |
|----------|-------|-------------|
| Core Attendance | 4 | 615 |
| Audit & Compliance | 1 | 366 |
| Consent Management | 1 | 502 |
| Post Assignment | 3 | 1,339 |
| Approval Workflow | 1 | 679 |
| Alert & Monitoring | 1 | 614 |
| Fraud Detection | 2 | 474 |
| Photo Capture | 1 | 429 |
| Conflict Resolution | 1 | 89 |
| Package Config | 1 | 125 |
| **TOTAL** | **16** | **5,232** |

---

## Import Patterns

All models can be imported from `apps.attendance.models`:

```python
# Core attendance
from apps.attendance.models import PeopleEventlog, Geofence, Tracking, TestGeo

# Audit & compliance
from apps.attendance.models import AttendanceAccessLog, AuditLogRetentionPolicy

# Consent management
from apps.attendance.models import ConsentPolicy, EmployeeConsentLog

# Post assignment
from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement

# Approval workflow
from apps.attendance.models import ApprovalRequest, ApprovalAction, AutoApprovalRule

# Alert & monitoring
from apps.attendance.models import AlertRule, AttendanceAlert, AlertEscalation

# Fraud detection
from apps.attendance.models import FraudAlert, UserBehaviorProfile

# Photo capture
from apps.attendance.models import AttendancePhoto

# Conflict resolution
from apps.attendance.models import SyncConflict
```

---

## Deprecated File

### `models_deprecated.py` (615 lines) ⚠️
**Status**: TO BE DELETED after verification  
**Original**: apps/attendance/models.py  
**Renamed**: November 4, 2025  
**Contains**: All models now in modular package  
**Deprecation Notice**: Included at top of file  

This file will be deleted after verifying all imports work correctly with the new package structure.

---

## References

- **Refactoring Report**: ATTENDANCE_MODELS_REFACTORING_COMPLETE.md
- **Quick Reference**: ATTENDANCE_MODELS_QUICK_REFERENCE.md
- **Verification Script**: scripts/verify_attendance_models_refactoring.py

---

**Maintainer**: Development Team  
**Last Refactor**: November 4, 2025  
**Review Cycle**: On model structure changes
