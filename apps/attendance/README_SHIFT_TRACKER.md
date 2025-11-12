# Shift Attendance Tracker

Real-time dashboard showing who's on time, late, or missing from scheduled shifts.

## Quick Access

**URL**: `/admin/attendance/shift-tracker/`

**User-Facing Name**: "Shift Attendance Tracker"

## What It Does

Compares scheduled shifts against actual clock-in/clock-out times to show:

- ✅ **On Time** - Clocked in within 15 min grace period
- ⚠️ **Late** - Arrived after grace period (shows minutes)
- 🔴 **No Show** - No clock-in record
- 🟠 **Early Exit** - Left before shift end
- 📊 **Coverage** - Overall shift fill rate

## Features

### Dashboard
- Real-time statistics with visual indicators
- Filter by date and site
- Tab navigation (All, Late, No Show, On Time)
- Auto-refresh every 5 minutes
- Responsive design

### Automated Monitoring
- Celery task runs every 10 minutes
- Auto-creates alerts for issues
- Optional manager notifications
- Comprehensive logging

### Analytics
- Coverage percentage
- On-time rate
- Late rate
- Absence rate

## Architecture

```
Service Layer:
  └─ ShiftAdherenceService
     ├─ calculate_adherence(date, site)
     ├─ get_coverage_stats(results)
     └─ auto_create_exceptions(results)

View Layer:
  └─ ShiftAdherenceDashboardView
     └─ Renders dashboard with filters

Background:
  └─ Celery Tasks
     ├─ update_shift_adherence (every 10 min)
     └─ notify_manager_no_show (on demand)
```

## Files

```
apps/attendance/
├── services/
│   └── shift_adherence_service.py      # Core logic
├── views/
│   └── shift_adherence_dashboard.py    # Dashboard view
├── tasks/
│   └── shift_monitoring.py             # Background tasks
└── urls.py                             # URL routing

templates/admin/attendance/
└── shift_adherence_dashboard.html      # UI template

scripts/
└── test_shift_adherence.py             # Validation script
```

## Usage

### Access Dashboard
```
1. Navigate to /admin/attendance/shift-tracker/
2. Select date (defaults to today)
3. Optionally filter by site
4. View statistics and tables
```

### Use Service Programmatically
```python
from apps.attendance.services.shift_adherence_service import ShiftAdherenceService
from datetime import date

service = ShiftAdherenceService()
adherence = service.calculate_adherence(date.today())
stats = service.get_coverage_stats(adherence)

for record in adherence:
    print(f"{record['shift'].shiftname}: {record['status']}")
```

### Trigger Monitoring Task
```python
from apps.attendance.tasks.shift_monitoring import update_shift_adherence
result = update_shift_adherence.delay()
```

## Configuration

### Grace Period
Default: 15 minutes

Change in `apps/attendance/services/shift_adherence_service.py`:
```python
class ShiftAdherenceService:
    GRACE_PERIOD_MINUTES = 15  # Adjust as needed
```

### Auto-Refresh Interval
Default: 5 minutes

Change in template:
```javascript
setInterval(() => location.reload(), 5 * 60 * 1000);
```

### Celery Schedule
Default: Every 10 minutes

Change in `intelliwiz_config/settings/attendance.py`:
```python
'update-shift-adherence': {
    'task': 'attendance.update_shift_adherence',
    'schedule': crontab(minute='*/10'),
}
```

## Testing

### Run Validation Script
```bash
python scripts/test_shift_adherence.py
```

### Manual Service Test
```python
python manage.py shell
>>> from apps.attendance.services.shift_adherence_service import ShiftAdherenceService
>>> from datetime import date
>>> service = ShiftAdherenceService()
>>> adherence = service.calculate_adherence(date.today())
>>> len(adherence)
```

### Test Celery Task
```bash
python manage.py shell
>>> from apps.attendance.tasks.shift_monitoring import update_shift_adherence
>>> result = update_shift_adherence()
>>> result
```

## Data Models

### Shift (client_onboarding.models.Shift)
- `starttime`, `endtime` - Scheduled times
- `bu` - Site/location
- `designation` - Role
- `enable` - Active status

### PeopleEventlog (attendance.models.PeopleEventlog)
- `pdate` - Attendance date
- `pstarttime` - Clock-in time
- `pendtime` - Clock-out time
- `post` - Assigned post (links to shift)

### AttendanceAlert (attendance.models.AttendanceAlert)
- Auto-created for issues
- Links to employee and post
- Tracks status and severity

## Troubleshooting

### No Data Showing
1. Check shifts are scheduled for date
2. Verify shifts have `enable=True`
3. Confirm attendance linked to posts

```python
from apps.client_onboarding.models import Shift
print(f"Active shifts: {Shift.objects.filter(enable=True).count()}")
```

### Wrong Status
1. Verify shift start/end times
2. Check attendance pdate matches
3. Confirm grace period setting

### Celery Not Running
```bash
# Check beat schedule
python manage.py shell
>>> from django.conf import settings
>>> settings.CELERY_BEAT_SCHEDULE['update-shift-adherence']

# Restart workers
./scripts/celery_workers.sh restart
```

## Security

- ✅ Login required (LoginRequiredMixin)
- ✅ Tenant-aware queries
- ✅ Input validation
- ✅ ORM only (no raw SQL)
- ✅ Template auto-escaping

## Performance

**Query Optimization**:
- Uses `select_related()` for joins
- Indexed field queries
- Service layer caching ready

**Expected Performance**:
- 100 shifts: <100ms
- 1000 shifts: <500ms
- 10000 shifts: Add caching

## Documentation

- **Quick Start**: `/SHIFT_ATTENDANCE_TRACKER_QUICK_START.md`
- **Implementation**: `/SHIFT_ATTENDANCE_TRACKER_IMPLEMENTATION.md`
- **This README**: Feature overview

## Support

**Logs**:
- Django: `/var/log/django/attendance.log`
- Celery: `/var/log/celery/worker.log`

**Issues**: Check diagnostics first, then create ticket

---

**Version**: 1.0  
**Status**: Production Ready  
**Created**: November 7, 2025
