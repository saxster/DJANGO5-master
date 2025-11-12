# Attendance App

**Purpose:** Employee attendance tracking with GPS validation, facial recognition, and shift management

**Owner:** HR & Operations Team  
**Status:** Production  
**Django Version:** 5.2.1

---

## Overview

The Attendance app provides comprehensive employee attendance tracking with GPS validation, facial recognition for identity verification, shift management, and timesheet generation. Built for security and facility management with mobile-first design.

### Key Features

- **Check-in/Check-out** - GPS-validated attendance
- **Facial Recognition** - Identity verification
- **Shift Management** - Automated shift tracking
- **GPS Validation** - Location-based validation
- **Timesheet Generation** - Automated reports
- **Leave Management** - Absence tracking
- **Overtime Calculation** - Automatic OT computation

---

## Architecture

### Models (Refactored - Phase 2)

**Attendance Models** (`models/attendance_models.py`):
- `AttendanceEntry` - Individual check-in/out record
- `AttendancePhoto` - Facial recognition photos
- `AttendanceApproval` - Manager approval workflow

**Shift Models** (`models/shift_models.py`):
- `Shift` - Shift definitions
- `ShiftAssignment` - User-shift assignments
- `ShiftSwapRequest` - Shift trading

**Leave Models** (`models/leave_models.py`):
- `LeaveRequest` - Time-off requests
- `LeaveBalance` - Accrued leave balances
- `LeavePolicy` - Organization policies

**Managers** (`models/managers.py`):
- `AttendanceQuerySet` - Optimized queries
- `ShiftQuerySet` - Shift-specific queries

**See:** [apps/attendance/models/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/models/)

### Services (Phase 2 Refactoring)

**Service Layer:**
- `AttendanceService` - Check-in/out logic
- `GPSValidationService` - Location verification
- `FacialRecognitionService` - Face matching
- `ShiftService` - Shift assignment and validation
- `TimesheetService` - Report generation
- `LeaveService` - Leave request processing

**See:** [apps/attendance/services/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/services/)

### Views (Modularized - Phase 2)

**Organized by domain:**
- `views/attendance_views.py` - Check-in/out endpoints
- `views/shift_views.py` - Shift management
- `views/leave_views.py` - Leave requests
- `views/report_views.py` - Timesheet reports

---

## API Endpoints

### Attendance

```
POST   /people/attendance/checkin/                    # Check in
POST   /people/attendance/checkout/                   # Check out
GET    /people/attendance/my_records/                 # User's records
GET    /people/attendance/team_records/               # Team records (managers)
POST   /people/attendance/{id}/approve/               # Approve record
```

### Shifts

```
GET    /people/shifts/                                # List shifts
GET    /people/shifts/my_shifts/                      # User's shifts
POST   /people/shifts/{id}/swap_request/              # Request shift swap
POST   /people/shifts/swap/{id}/approve/              # Approve swap
```

### Leave

```
GET    /people/leave/                                 # List leave requests
POST   /people/leave/                                 # Create leave request
GET    /people/leave/balance/                         # View leave balance
POST   /people/leave/{id}/approve/                    # Approve leave
```

### API v2 (Type-Safe)

```
POST   /api/v2/attendance/entries/                    # Pydantic validated
GET    /api/v2/attendance/reports/timesheet/          # Generate timesheet
```

---

## Usage Examples

### Check-In (Mobile App)

```python
from apps.attendance.services import AttendanceService

entry = AttendanceService.check_in(
    user=current_user,
    latitude=1.290270,
    longitude=103.851959,
    photo=face_photo,
    device_info={
        'device_id': 'ABC123',
        'device_type': 'android',
        'app_version': '2.1.0'
    }
)
```

### GPS Validation

```python
from apps.attendance.services import GPSValidationService

is_valid = GPSValidationService.validate_location(
    user=user,
    latitude=1.290270,
    longitude=103.851959,
    assigned_site=site,
    radius_meters=100
)
```

### Facial Recognition

```python
from apps.attendance.services import FacialRecognitionService

is_match = FacialRecognitionService.verify_face(
    user=user,
    uploaded_photo=photo,
    confidence_threshold=0.85
)
```

### Generate Timesheet

```python
from apps.attendance.services import TimesheetService

timesheet = TimesheetService.generate_timesheet(
    user=user,
    start_date=date(2025, 11, 1),
    end_date=date(2025, 11, 30),
    include_overtime=True
)
```

---

## Mobile Integration

### Kotlin SDK

```kotlin
// Check in with GPS and photo
val attendanceClient = IntelliwizSDK.attendance()

val result = attendanceClient.checkIn(
    latitude = location.latitude,
    longitude = location.longitude,
    photo = capturedPhoto,
    deviceInfo = DeviceInfo.current()
)

when (result) {
    is Success -> showSuccess("Checked in successfully")
    is Error -> showError(result.message)
}
```

### Swift SDK

```swift
// Check in (iOS)
let attendanceService = IntelliwizSDK.shared.attendance

attendanceService.checkIn(
    latitude: location.coordinate.latitude,
    longitude: location.coordinate.longitude,
    photo: facePhoto,
    deviceInfo: DeviceInfo.current
) { result in
    switch result {
    case .success(let entry):
        print("Checked in at \\(entry.timestamp)")
    case .failure(let error):
        print("Error: \\(error.localizedDescription)")
    }
}
```

---

## Database Schema

### Key Relationships

```
AttendanceEntry
  ├─ user (FK → People)
  ├─ shift (FK → Shift)
  ├─ site (FK → BusinessUnit)
  ├─ approved_by (FK → People)
  └─ photo (FK → AttendancePhoto)

Shift
  ├─ assignments (FK → ShiftAssignment)
  ├─ site (FK → BusinessUnit)
  └─ created_by (FK → People)

LeaveRequest
  ├─ user (FK → People)
  ├─ leave_type (FK → LeaveType)
  └─ approved_by (FK → People)
```

### Indexes (Optimized)

```python
class Meta:
    indexes = [
        models.Index(fields=['user', 'checkin_time']),
        models.Index(fields=['shift', 'status']),
        models.Index(fields=['site', 'checkin_time']),
        models.Index(fields=['approved_by', 'approval_status']),
    ]
```

---

## Business Logic

### Check-In Validation Rules

1. **GPS Validation**
   - Must be within radius of assigned site
   - Configurable radius (default: 100m)
   - Requires location permissions

2. **Facial Recognition**
   - Minimum 85% confidence score
   - Photo quality validation
   - Anti-spoofing checks

3. **Shift Validation**
   - Must have assigned shift
   - Within shift time window (+/- 15 min grace period)
   - No duplicate check-ins

4. **Duplicate Prevention**
   - No check-in if already checked in
   - Must check out before next check-in

### Overtime Calculation

```python
# Automatic OT calculation
def calculate_overtime(entry):
    """
    OT Rules:
    - First 2 hours: 1.5x
    - After 2 hours: 2.0x
    - Weekends: 2.0x from start
    - Holidays: 3.0x
    """
    hours_worked = entry.hours_worked
    shift_hours = entry.shift.duration_hours
    
    if hours_worked > shift_hours:
        ot_hours = hours_worked - shift_hours
        return calculate_ot_pay(ot_hours, entry.day_type)
```

---

## Testing

### Running Tests

```bash
# All attendance tests
pytest apps/attendance/tests/ -v

# GPS validation tests
pytest apps/attendance/tests/test_gps_validation.py -v

# Facial recognition tests
pytest apps/attendance/tests/test_facial_recognition.py -v

# With coverage
pytest apps/attendance/tests/ --cov=apps/attendance --cov-report=html
```

### Test Coverage

```
Attendance Models: 94%
Services: 89%
Views: 87%
Overall: 90.1%
```

### Key Test Files

- `test_attendance_service.py` - Check-in/out logic
- `test_gps_validation.py` - Location validation
- `test_facial_recognition.py` - Face matching
- `test_shift_service.py` - Shift assignment
- `test_security.py` - IDOR, multi-tenant isolation

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/attendance.py

ATTENDANCE_SETTINGS = {
    # GPS Validation
    'GPS_VALIDATION_ENABLED': True,
    'GPS_RADIUS_METERS': 100,
    'GPS_ACCURACY_THRESHOLD': 50,  # meters
    
    # Facial Recognition
    'FACE_RECOGNITION_ENABLED': True,
    'FACE_CONFIDENCE_THRESHOLD': 0.85,
    'FACE_PHOTO_MAX_SIZE_MB': 5,
    
    # Shift Validation
    'SHIFT_GRACE_PERIOD_MINUTES': 15,
    'ALLOW_EARLY_CHECKIN_MINUTES': 30,
    'ALLOW_LATE_CHECKOUT_MINUTES': 30,
    
    # Overtime
    'OT_TIER1_MULTIPLIER': 1.5,  # First 2 hours
    'OT_TIER2_MULTIPLIER': 2.0,  # After 2 hours
    'WEEKEND_MULTIPLIER': 2.0,
    'HOLIDAY_MULTIPLIER': 3.0,
}
```

### Celery Tasks

```python
@shared_task
def process_pending_approvals():
    """Auto-approve entries after 24 hours."""
    
@shared_task
def generate_daily_timesheets():
    """Generate timesheets at end of day."""
    
@shared_task
def send_late_checkin_notifications():
    """Notify managers of late check-ins."""
```

---

## Troubleshooting

### Common Issues

**Issue:** GPS validation failing  
**Solution:** 
- Check location permissions on device
- Verify GPS accuracy < 50m
- Ensure site coordinates are correct
- Increase `GPS_RADIUS_METERS` if needed

**Issue:** Facial recognition rejecting valid faces  
**Solution:**
- Ensure good lighting conditions
- Update user's reference photo
- Lower `FACE_CONFIDENCE_THRESHOLD` (carefully)
- Check photo quality/resolution

**Issue:** Check-in blocked - "Already checked in"  
**Solution:**
- Check for open attendance entry
- Force checkout if stuck
- Review last checkout timestamp

**Issue:** Overtime not calculated correctly  
**Solution:**
- Verify shift duration settings
- Check day type (weekday/weekend/holiday)
- Review OT tier multipliers

### Debug Mode

```python
# Enable attendance debug logging
import logging
logger = logging.getLogger('apps.attendance')
logger.setLevel(logging.DEBUG)

# GPS validation debug
logger.debug(f"GPS validation: user={user}, distance={distance}m, threshold={threshold}m")
```

---

## Security

### GPS Privacy & Consent

```python
# Users must consent to GPS tracking
class AttendanceEntry(models.Model):
    gps_consent_given = models.BooleanField(default=False)
    gps_consent_timestamp = models.DateTimeField(null=True)
```

### Face Photo Privacy

- Photos encrypted at rest
- Deleted after 90 days
- PII redaction in logs
- GDPR-compliant data handling

### Multi-Tenancy

```python
# Automatic tenant filtering
entries = AttendanceEntry.objects.all()  # Auto-filtered by middleware
```

---

## Performance

### Query Optimization

```python
# Optimized queryset with select_related/prefetch_related
entries = AttendanceEntry.objects.select_related(
    'user',
    'shift',
    'site',
    'approved_by'
).prefetch_related(
    'user__peopleprofile',
    'shift__shifttype'
)
```

### Caching

```python
# Cache user's recent entries
@cached(timeout=300, key='attendance_recent_{user_id}')
def get_recent_entries(user_id):
    return AttendanceEntry.objects.filter(
        user_id=user_id
    ).order_by('-checkin_time')[:10]
```

---

## Reporting

### Available Reports

1. **Timesheet Report** - Daily/weekly/monthly timesheets
2. **Attendance Summary** - Attendance percentage by user/team
3. **Overtime Report** - OT hours and costs
4. **Late Check-in Report** - Tardiness tracking
5. **Leave Balance Report** - Accrued and used leave

### Generating Reports

```python
from apps.attendance.services import TimesheetService

# Generate monthly timesheet
report = TimesheetService.generate_report(
    report_type='timesheet',
    user=user,
    start_date=date(2025, 11, 1),
    end_date=date(2025, 11, 30),
    format='pdf'
)
```

---

## Related Documentation

- [Activity App](../activity/README.md) - Shift assignment integration
- [Peoples App](../peoples/README.md) - User management
- [Face Recognition](../face_recognition/README.md) - Facial recognition service

---

**Last Updated:** November 6, 2025  
**Maintainers:** HR & Operations Team  
**Contact:** dev-team@example.com
