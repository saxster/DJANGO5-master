# GPS Data Retention Policy

**Version**: 1.0
**Effective Date**: November 3, 2025
**Last Updated**: November 3, 2025
**Owner**: Security & Privacy Team

---

## Table of Contents

1. [Overview](#overview)
2. [Data Classification](#data-classification)
3. [Retention Periods](#retention-periods)
4. [Privacy Compliance](#privacy-compliance)
5. [Data Minimization](#data-minimization)
6. [Automated Cleanup](#automated-cleanup)
7. [User Rights](#user-rights)
8. [Technical Implementation](#technical-implementation)
9. [Audit & Logging](#audit--logging)

---

## Overview

This policy defines data retention requirements for GPS location data collected through the attendance tracking system. It ensures compliance with privacy regulations (GDPR, CCPA) while maintaining operational and legal requirements for attendance records.

### Scope

This policy applies to all GPS location data stored in:
- `PeopleEventlog` table (`startlocation`, `endlocation`, `journeypath`, `accuracy`)
- `Tracking` table (temporary GPS logging)
- `GPSValidationLog` table (fraud detection logs)
- Geofence validation logs

---

## Data Classification

### Sensitive Personal Data

GPS location data is classified as **Sensitive Personal Data** under GDPR Article 9 and requires:
- **Explicit consent** from users
- **Purpose limitation** (cannot be repurposed without renewed consent)
- **Storage limitation** (retain only as long as necessary)
- **Transparency** (users must be informed of data practices)

### Data Categories

| Data Type | Classification | Retention | Justification |
|-----------|---------------|-----------|---------------|
| GPS Coordinates (lat/lng) | Sensitive PII | 90 days | Fraud detection, dispute resolution |
| GPS Accuracy | Technical metadata | 90 days | Quality assurance, fraud detection |
| Device ID | Pseudonymized PII | 1 year | Device tracking, fraud prevention |
| Attendance Metadata | Business record | 7 years | Legal requirement (employment records) |
| Geofence Validation Results | Business data | 1 year | Audit trail, compliance |
| GPS Fraud Logs | Security data | 2 years | Fraud investigation, legal evidence |

---

## Retention Periods

### Primary GPS Data (Attendance)

**Retention Period**: **90 days** from capture date

**Rationale**:
- Sufficient for fraud detection (30-60 day patterns)
- Dispute resolution window (employment disputes typically <90 days)
- Minimizes privacy risk by limiting long-term location tracking
- Balances operational needs with data minimization principles

**After 90 Days**:
- GPS coordinates (`startlocation`, `endlocation`) → **NULLIFIED**
- GPS accuracy → **NULLIFIED**
- Device ID → **RETAINED** (for fraud pattern analysis)
- Attendance metadata (date, time, person, event type) → **RETAINED** (7 years)

### GPS Fraud Detection Logs

**Retention Period**: **2 years** from detection date

**Rationale**:
- Fraud investigations may take 6-12 months
- Legal evidence preservation (statute of limitations)
- Pattern analysis for security improvements

**Data Stored**:
- `GPSValidationLog` table: GPS coordinates, accuracy, validation results, fraud scores
- Auto-purge after 2 years

### Geofence Definitions

**Retention Period**: **Indefinite** (while geofence is active)

**Rationale**:
- Operational requirement for attendance validation
- Not PII (business location boundaries)

**On Deactivation**:
- Geofence marked `is_active=False`
- Historical validation results retained per schedule above

### Temporary GPS Tracking

**Retention Period**: **7 days** from capture date

**Rationale**:
- Used for real-time tracking (tours, conveyance)
- Short-term operational need only

**Data Stored**:
- `Tracking` table: GPS location for active sessions
- Auto-purge after 7 days

---

## Privacy Compliance

### GDPR Requirements (EU Operations)

#### Explicit Consent

**Required Elements**:
1. **Informed Consent**: Users must be informed of:
   - What GPS data is collected (coordinates, accuracy, device ID)
   - Why it's collected (attendance verification, fraud prevention)
   - How long it's stored (90 days for GPS, 7 years for metadata)
   - Who it's shared with (tenant admins, security team)
2. **Opt-In Mechanism**: Users must actively consent (no pre-checked boxes)
3. **Withdrawal Right**: Users can withdraw consent (degrades to manual attendance)

**Implementation Status**: ⚠️ **NOT YET IMPLEMENTED** (see Technical Implementation)

#### Right to Erasure

Users can request deletion of their GPS data:
- GPS coordinates deleted within **30 days** of request
- Attendance metadata retained (legal requirement: 7 years for employment records)
- Exception: Fraud investigation (data retention extended)

#### Data Portability

Users can request export of their GPS data in machine-readable format (CSV/JSON).

### CCPA Requirements (California Operations)

- **Right to Know**: Disclose GPS data collection in privacy policy
- **Right to Delete**: Honor deletion requests within 45 days
- **Right to Opt-Out**: Provide opt-out mechanism (manual attendance)

---

## Data Minimization

### Coordinate Precision Reduction

**Current**: 6 decimal places (~10cm accuracy)
**Recommended**: **4-5 decimal places** (~1-10m accuracy)

**Rationale**:
- 4 decimal places = ~11 meters (sufficient for geofence validation)
- Reduces location tracking precision for privacy
- Still adequate for fraud detection

**Implementation**:
```python
# In serializers.py or save methods
def reduce_precision(lat, lng, precision=4):
    return round(lat, precision), round(lng, precision)
```

### Device ID Hashing

**Current**: Plain device ID stored
**Recommended**: **Hashed device ID** (SHA-256)

**Rationale**:
- Prevents direct device identification
- Maintains fraud detection capability
- Enhances privacy

**Implementation**:
```python
import hashlib

def hash_device_id(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()[:16]
```

---

## Automated Cleanup

### Celery Periodic Tasks

#### GPS Data Cleanup (Daily)

**Schedule**: Every day at 2:00 AM
**Task**: `apps.attendance.tasks.cleanup_expired_gps_data`

```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog, Tracking
from apps.noc.security_intelligence.models import GPSValidationLog

@shared_task
def cleanup_expired_gps_data():
    """
    Anonymize GPS coordinates older than retention period.

    Retention Periods:
    - PeopleEventlog: 90 days (nullify coordinates, keep metadata)
    - Tracking: 7 days (delete records)
    - GPSValidationLog: 2 years (delete records)
    """
    # PeopleEventlog: Nullify GPS coordinates (90 days)
    cutoff_date_attendance = timezone.now() - timedelta(days=90)
    updated_count = PeopleEventlog.objects.filter(
        created_at__lt=cutoff_date_attendance
    ).exclude(
        startlocation__isnull=True
    ).update(
        startlocation=None,
        endlocation=None,
        journeypath=None,
        accuracy=None
        # device_id retained for fraud analysis
    )

    # Tracking: Delete old records (7 days)
    cutoff_date_tracking = timezone.now() - timedelta(days=7)
    deleted_tracking = Tracking.objects.filter(
        created_at__lt=cutoff_date_tracking
    ).delete()

    # GPSValidationLog: Delete old fraud logs (2 years)
    cutoff_date_fraud = timezone.now() - timedelta(days=730)  # 2 years
    deleted_fraud = GPSValidationLog.objects.filter(
        created_at__lt=cutoff_date_fraud
    ).delete()

    return {
        'attendance_anonymized': updated_count,
        'tracking_deleted': deleted_tracking[0] if deleted_tracking else 0,
        'fraud_logs_deleted': deleted_fraud[0] if deleted_fraud else 0,
        'timestamp': timezone.now().isoformat()
    }
```

**Configuration** (`celerybeat_schedule` in settings):
```python
CELERYBEAT_SCHEDULE = {
    'cleanup-gps-data': {
        'task': 'apps.attendance.tasks.cleanup_expired_gps_data',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

---

## User Rights

### Right to Access

Users can view their GPS data via:
- **Mobile App**: "My Location History" screen (last 90 days)
- **Web Portal**: Attendance history with map view
- **API**: `GET /api/v1/attendance/history/?person_id={id}`

### Right to Deletion

Users can request GPS data deletion:
1. Submit deletion request via mobile app or web portal
2. System anonymizes GPS coordinates within 30 days
3. Attendance metadata retained (legal requirement)

**Implementation**: `apps.attendance.services.gdpr_service.delete_user_gps_data(user_id)`

### Right to Data Portability

Users can export their GPS data:
- **Format**: CSV or JSON
- **Scope**: All GPS data within retention period
- **Delivery**: Email download link (expires in 7 days)

**Implementation**: `apps.attendance.services.gdpr_service.export_user_gps_data(user_id, format='csv')`

---

## Technical Implementation

### Phase 1: Critical Fixes (Completed)

✅ Server-side timestamp validation (prevent replay attacks)
✅ GPS spoofing detection ((0,0) coordinate blocking)
✅ Rate limiting (30 clock events/hour)
✅ Exception handling (specific exceptions, not generic)
✅ Spatial indexes (GIST on geofence boundaries)

### Phase 2: Privacy Compliance (To Be Implemented)

#### User Consent Flow

**Mobile App**:
1. First launch: Show GPS consent dialog
2. Explain data collection, usage, retention
3. Require explicit opt-in (tap "Accept")
4. Store consent timestamp in `People.gps_consent_date`

**Database**:
```sql
ALTER TABLE people ADD COLUMN gps_consent_date TIMESTAMP NULL;
ALTER TABLE people ADD COLUMN gps_consent_version VARCHAR(10) NULL;
```

**API Validation**:
```python
# In clock-in/out endpoints
if not request.user.gps_consent_date:
    return Response(
        {'error': 'GPS consent required. Please accept location tracking in app settings.'},
        status=status.HTTP_403_FORBIDDEN
    )
```

#### Automated Cleanup Task

**File**: `apps/attendance/tasks.py`
**Function**: `cleanup_expired_gps_data()` (see Automated Cleanup section)

**Celery Beat Schedule**: Add to `settings/celery.py`

#### Privacy Policy Documentation

**File**: `docs/policies/PRIVACY_POLICY.md`
**Sections**:
- GPS data collection disclosure
- Purpose limitation
- Retention periods
- User rights (access, deletion, portability)
- Third-party sharing (none)

---

## Audit & Logging

### Retention Policy Compliance Audit

**Frequency**: Quarterly
**Report**: `apps.attendance.reports.gps_retention_audit`

**Metrics**:
- GPS records older than 90 days (should be 0)
- Tracking records older than 7 days (should be 0)
- Fraud logs older than 2 years (should be 0)
- Failed cleanup tasks (investigate)

### User Data Access Logging

All GPS data access logged in audit trail:
```python
{
    "event": "gps_data_access",
    "user_id": 123,
    "accessor_id": 456,
    "access_type": "view|export|delete",
    "timestamp": "2025-11-03T10:30:00Z",
    "ip_address": "192.168.1.1",
    "correlation_id": "abc-123"
}
```

---

## Compliance Summary

| Requirement | Status | Notes |
|-------------|--------|-------|
| GDPR Article 9 (Explicit Consent) | ⚠️ **To Be Implemented** | User consent flow needed |
| GDPR Right to Erasure | ⚠️ **Partial** | Manual process, needs automation |
| GDPR Right to Data Portability | ⚠️ **To Be Implemented** | Export function needed |
| CCPA Right to Know | ✅ **Compliant** | Privacy policy documented |
| Data Minimization | ⚠️ **Partial** | Reduce coordinate precision to 4-5 decimal places |
| Automated Cleanup | ⚠️ **To Be Implemented** | Celery task needed |
| Audit Trail | ✅ **Compliant** | Access logging implemented |

---

## Next Steps (Priority Order)

### Immediate (Week 1)
1. ✅ Implement timestamp validation (completed)
2. ✅ Add rate limiting (completed)
3. ✅ Block spoofed coordinates (completed)

### Short-Term (Month 1)
4. ⚠️ Create GPS consent flow in mobile app
5. ⚠️ Implement automated cleanup Celery task
6. ⚠️ Add GDPR deletion endpoint

### Medium-Term (Quarter 1)
7. ⚠️ Reduce coordinate precision to 4-5 decimal places
8. ⚠️ Implement data portability (CSV/JSON export)
9. ⚠️ Create privacy policy documentation

### Long-Term (Quarter 2)
10. ⚠️ Hash device IDs (SHA-256)
11. ⚠️ Implement consent versioning
12. ⚠️ Quarterly compliance audit report

---

## Contact

**Policy Owner**: Security & Privacy Team
**Technical Contact**: Backend Engineering Team
**Legal Contact**: Legal & Compliance Team

For questions or concerns about GPS data retention, contact: privacy@company.com

---

**Document History**:
- 2025-11-03: v1.0 - Initial policy created (GPS security review)
