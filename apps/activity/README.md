# Activity App

**Purpose:** Task management, tours, work orders, and field operations tracking

**Owner:** Operations Team  
**Status:** Production  
**Django Version:** 5.2.1

---

## Overview

The Activity app manages operational tasks, scheduled tours, work orders, and field operations for security and facility management. It provides comprehensive tracking of guard activities, patrol routes, and maintenance tasks.

### Key Features

- **Task Management** - Create, assign, and track tasks
- **Tour Management** - Schedule and monitor guard tours with checkpoints
- **Work Orders** - Preventive and reactive maintenance
- **Shift Management** - Staff scheduling and assignment
- **Mobile Integration** - Kotlin SDK for field staff
- **Real-time Updates** - WebSocket support for live status

---

## Architecture

### Models

**Core Models:**
- `Activity` - Base task/activity model
- `Tour` - Guard tour routes with checkpoints
- `TourCheckpoint` - Individual checkpoints in a tour
- `TourLog` - Completed tour records
- `Shift` - Work shifts and assignments
- `ShiftAssignment` - Personnel assignments to shifts

**See:** [apps/activity/models/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/models/) for complete model definitions

### Services

**Service Layer** (ADR 003 compliant):
- `ActivityService` - Task creation, assignment, completion
- `TourService` - Tour scheduling, checkpoint validation
- `ShiftService` - Shift management, conflict detection
- `NotificationService` - Real-time notifications for tasks

**See:** [apps/activity/services/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/services/)

### Views

**Organized by domain:**
- `apps/activity/views/task_views.py` - Task CRUD operations
- `apps/activity/views/tour_views.py` - Tour management
- `apps/activity/views/shift_views.py` - Shift scheduling

---

## API Endpoints

### Tasks

```
GET    /operations/tasks/                     # List all tasks
POST   /operations/tasks/                     # Create task
GET    /operations/tasks/{id}/                # Task details
PATCH  /operations/tasks/{id}/                # Update task
POST   /operations/tasks/{id}/assign/         # Assign to user
POST   /operations/tasks/{id}/complete/       # Mark complete
```

### Tours

```
GET    /operations/tours/                     # List tours
POST   /operations/tours/                     # Create tour
GET    /operations/tours/{id}/                # Tour details
POST   /operations/tours/{id}/start/          # Start tour
POST   /operations/tours/{id}/checkpoint/     # Log checkpoint
POST   /operations/tours/{id}/complete/       # Complete tour
```

### API v2 (Type-Safe)

```
GET    /api/v2/operations/tasks/              # Pydantic validated
POST   /api/v2/operations/tasks/              # Auto-serialization
```

---

## Usage Examples

### Creating a Task

```python
from apps.activity.services import ActivityService

task = ActivityService.create_task(
    title="Check fire extinguishers",
    description="Monthly inspection of all fire extinguishers",
    assigned_to=user,
    due_date=datetime(2025, 11, 15),
    priority="high",
    client=tenant
)
```

### Starting a Tour

```python
from apps.activity.services import TourService

tour_log = TourService.start_tour(
    tour_id=tour.id,
    guard_id=guard.id,
    start_location={"lat": 1.234, "lng": 103.456}
)
```

### Logging a Checkpoint

```python
TourService.log_checkpoint(
    tour_log_id=tour_log.id,
    checkpoint_id=checkpoint.id,
    timestamp=timezone.now(),
    location={"lat": 1.234, "lng": 103.456},
    photo=uploaded_file  # Optional proof
)
```

---

## Mobile Integration

### Kotlin SDK

```kotlin
// Initialize
val activityClient = IntelliwizSDK.activity()

// Fetch assigned tasks
val tasks = activityClient.getTasks(
    assignedTo = currentUser.id,
    status = "pending"
)

// Complete task
activityClient.completeTask(
    taskId = task.id,
    notes = "All extinguishers checked",
    photos = listOf(photoFile)
)
```

**See:** [intelliwiz_kotlin_sdk/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/intelliwiz_kotlin_sdk/) for complete SDK

---

## Database Schema

### Key Relationships

```
Activity
  ├─ assigned_to (FK → People)
  ├─ created_by (FK → People)
  ├─ client (FK → Tenant)
  └─ bu (FK → BusinessUnit)

Tour
  ├─ checkpoints (M2M → TourCheckpoint)
  ├─ assigned_guards (M2M → People)
  └─ site (FK → BusinessUnit)

TourLog
  ├─ tour (FK → Tour)
  ├─ guard (FK → People)
  └─ checkpoint_logs (FK → TourCheckpointLog)
```

### Indexes

```python
class Meta:
    indexes = [
        models.Index(fields=['assigned_to', 'status']),
        models.Index(fields=['due_date', 'priority']),
        models.Index(fields=['client', 'created_at']),
    ]
```

---

## Business Logic

### Task Assignment Rules

1. **Availability Check** - User must be on-duty
2. **Skill Matching** - User has required skills
3. **Workload Balancing** - Even distribution across team
4. **Geographic Proximity** - Assign to nearest available guard

### Tour Validation

1. **Checkpoint Order** - Must visit in sequence
2. **Time Windows** - Must complete within schedule
3. **GPS Verification** - Location must be within radius
4. **Photo Requirements** - Some checkpoints require proof

---

## Testing

### Running Tests

```bash
# All activity tests
pytest apps/activity/tests/ -v

# Specific test module
pytest apps/activity/tests/test_tour_service.py -v

# With coverage
pytest apps/activity/tests/ --cov=apps/activity --cov-report=html
```

### Test Coverage

```
Activities: 95%
Tours: 92%
Shifts: 88%
Overall: 91.7%
```

### Key Test Files

- `test_activity_service.py` - Task creation, assignment
- `test_tour_service.py` - Tour logic, checkpoints
- `test_shift_service.py` - Shift scheduling, conflicts
- `test_security.py` - IDOR, multi-tenant isolation

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/activity.py

ACTIVITY_SETTINGS = {
    'MAX_ASSIGNMENTS_PER_USER': 10,
    'TOUR_GPS_RADIUS_METERS': 50,
    'CHECKPOINT_PHOTO_REQUIRED': True,
    'LATE_TASK_NOTIFICATION_HOURS': 2,
}
```

### Celery Tasks

```python
# Background processing
@shared_task
def send_overdue_task_notifications():
    """Notify managers of overdue tasks."""
    
@shared_task
def generate_tour_reports():
    """Generate daily tour completion reports."""
```

---

## Troubleshooting

### Common Issues

**Issue:** Tasks not appearing for assigned user  
**Solution:** Check `assigned_to` field and user's tenant assignment

**Issue:** GPS checkpoint validation failing  
**Solution:** Verify `GPS_RADIUS_METERS` setting and coordinate accuracy

**Issue:** Tour completion blocked  
**Solution:** Ensure all required checkpoints are logged

### Debug Logging

```python
import logging
logger = logging.getLogger('apps.activity')
logger.setLevel(logging.DEBUG)
```

---

## Security

### Multi-Tenancy

All queries automatically filtered by user's tenant:

```python
# Middleware handles tenant isolation
tasks = Activity.objects.all()  # Auto-filtered to user's tenant
```

### Permissions

```python
# View-level permissions
@permission_required('activity.view_task')
def task_list(request):
    ...

# Object-level permissions
def can_edit_task(user, task):
    return task.assigned_to == user or user.is_manager
```

---

## Performance

### Query Optimization

```python
# N+1 prevention
tasks = Activity.objects.select_related(
    'assigned_to',
    'created_by',
    'client'
).prefetch_related(
    'attachments',
    'comments'
)
```

### Caching

```python
# Tour templates cached for 1 hour
@cached(timeout=3600, key='tour_templates_{site_id}')
def get_tour_templates(site_id):
    return Tour.objects.filter(site_id=site_id, is_template=True)
```

---

## Related Documentation

- [Work Order Management](../work_order_management/README.md) - Work order integration
- [Attendance](../attendance/README.md) - Shift and attendance integration
- [NOC](../noc/README.md) - Alert integration for facility issues

---

**Last Updated:** November 6, 2025  
**Maintainers:** Operations Team  
**Contact:** dev-team@example.com
