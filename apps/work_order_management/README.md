# Work Order Management App

## Purpose

Comprehensive work order and maintenance management system for planned preventive maintenance (PPM), reactive repairs, and vendor-managed work with multi-level approval workflows.

## Key Features

- **Work Order Lifecycle** - ASSIGNED → IN_PROGRESS → COMPLETED → CLOSED
- **Work Permits** - Required/not-required workflow with approval chains
- **Vendor Management** - External contractor coordination with token-based access
- **Multi-Level Approvals** - Configurable approver and verifier chains
- **SLA Tracking** - Planned vs. actual time monitoring with deadline alerts
- **Parent-Child Hierarchy** - Breakdown structures for complex maintenance
- **Quality Scoring** - Section weightage, overall score, uptime tracking
- **GPS Validation** - Location verification for field work
- **Inspection Checklists** - QuestionSet integration for quality control
- **State Machine** - Workflow enforcement with transition validation

---

## Architecture

### Models Overview

**Core Models:**
- `Wom` (Work Order Model) - Central work order entity
  - Work order metadata (title, description, identifier)
  - Status and workflow fields (workstatus, workpermit)
  - Time tracking (plandatetime, starttime, endtime, expirydatetime)
  - Priority and SLA management
  - Vendor assignment and coordination
  - Approval and verification chains
  - GPS location tracking
  - Quality scores and performance metrics
- `WomDetails` - Inspection checklist answers (1:M with Wom)
- `Vendor` - External contractor profiles
- `Approver` - Approval matrix configuration

**Enums:**
- `Workstatus` - Status transitions (ASSIGNED, INPROGRESS, COMPLETED, CLOSED, CANCELLED)
- `WorkPermitStatus` - Permit states (APPROVED, PENDING, REJECTED)
- `Priority` - Priority levels (HIGH, MEDIUM, LOW)
- `Identifier` - Type classification (WO, WP, SLA)

**See:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/models/` for complete model definitions

### Database Schema

```
Wom (Work Order)
  ├─ asset (FK → Asset)
  ├─ location (FK → Location)
  ├─ qset (FK → QuestionSet)
  ├─ vendor (FK → Vendor)
  ├─ parent (FK → Wom) - Self-referential
  ├─ client (FK → Bt)
  ├─ bu (FK → Bt)
  ├─ WomDetails (1:M) - Checklist answers
  └─ approvers, verifiers (ArrayField) - People IDs

Vendor
  ├─ vendortype (FK → TypeAssist)
  └─ Wom (1:M) - Assigned work orders

Approver
  ├─ assignedperson (FK → People)
  ├─ assignedgroup (FK → Pgroup)
  └─ job (FK → Job)
```

### Workflow State Machine

```python
# State transitions
ASSIGNED → INPROGRESS → COMPLETED → CLOSED
         ↓                        ↓
     RE_ASSIGNED             CANCELLED

# Transition rules
- ASSIGNED → INPROGRESS: Vendor starts work
- INPROGRESS → COMPLETED: Work finished, pending verification
- COMPLETED → CLOSED: Verified and approved
- Any state → CANCELLED: Work order cancelled
- COMPLETED → RE_ASSIGNED: Verification failed, reassign
```

---

## API Endpoints

### Work Orders

```
GET    /api/v2/work-orders/                   # List work orders
POST   /api/v2/work-orders/                   # Create work order
GET    /api/v2/work-orders/{id}/              # Work order details
PATCH  /api/v2/work-orders/{id}/              # Update work order
DELETE /api/v2/work-orders/{id}/              # Cancel work order
POST   /api/v2/work-orders/{id}/start/        # Start work
POST   /api/v2/work-orders/{id}/complete/     # Mark completed
POST   /api/v2/work-orders/{id}/verify/       # Verify completion
POST   /api/v2/work-orders/{id}/close/        # Close work order
```

### Work Permits

```
GET    /api/v2/work-permits/                  # List work permits
POST   /api/v2/work-permits/                  # Create permit
GET    /api/v2/work-permits/{id}/             # Permit details
POST   /api/v2/work-permits/{id}/approve/     # Approve permit
POST   /api/v2/work-permits/{id}/reject/      # Reject permit
```

### Vendors

```
GET    /api/v2/vendors/                       # List vendors
POST   /api/v2/vendors/                       # Create vendor
GET    /api/v2/vendors/{id}/                  # Vendor details
GET    /api/v2/vendors/{id}/work-orders/      # Vendor's work orders
GET    /api/v2/vendors/{id}/performance/      # Performance metrics
```

### Vendor Portal (Token-Based)

```
GET    /vendor/{token}/work-orders/           # Vendor's assigned WOs
POST   /vendor/{token}/work-orders/{id}/update/ # Update status
POST   /vendor/{token}/work-orders/{id}/photos/ # Upload photos
```

---

## Usage Examples

### Creating a Work Order

```python
from apps.work_order_management.models import Wom
from apps.work_order_management.models.enums import Workstatus, Priority, Identifier

work_order = Wom.objects.create(
    workname="HVAC System Maintenance",
    description="Quarterly preventive maintenance for HVAC Unit 5",
    identifier=Identifier.WO,
    workstatus=Workstatus.ASSIGNED,
    priority=Priority.HIGH,

    # Asset and location
    asset=hvac_unit,
    location=building_5_floor_3,

    # Vendor assignment
    vendor=abc_hvac_services,

    # Scheduling
    plandatetime=datetime(2025, 11, 15, 9, 0),
    expirydatetime=datetime(2025, 11, 15, 17, 0),

    # Inspection checklist
    qset=hvac_maintenance_checklist,

    # Approval chain
    approvers=[manager_1_id, manager_2_id],
    verifiers=[supervisor_id],

    # Tenant
    client=tenant,
    bu=business_unit,
    tenant=tenant
)
```

### Work Order Lifecycle

```python
# 1. Start work
work_order.workstatus = Workstatus.INPROGRESS
work_order.starttime = timezone.now()
work_order.save()

# 2. Complete checklist (WomDetails)
from apps.work_order_management.models import WomDetails

WomDetails.objects.create(
    wom=work_order,
    question_id=1,
    answer="Filters replaced",
    passed=True
)

# 3. Mark completed
work_order.workstatus = Workstatus.COMPLETED
work_order.endtime = timezone.now()
work_order.actualenddatetime = timezone.now()
work_order.save()

# 4. Verification
work_order.workstatus = Workstatus.CLOSED
work_order.verified_by = supervisor
work_order.verified_at = timezone.now()
work_order.save()
```

### Vendor Token Access

```python
# Generate vendor access token
from apps.work_order_management.services import VendorAccessService

token = VendorAccessService.generate_token(
    vendor=vendor,
    work_order=work_order,
    expiration_minutes=480  # 8 hours
)

# Vendor uses token to access
vendor_url = f"https://portal.example.com/vendor/{token}/work-orders/"
```

### Approval Workflow

```python
# Create work permit requiring approval
work_permit = Wom.objects.create(
    workname="Hot Work - Welding",
    identifier=Identifier.WP,
    workpermit=WorkPermitStatus.PENDING,
    approvers=[safety_officer_id, operations_manager_id],
    # ... other fields
)

# Approve permit
from apps.work_order_management.services import ApprovalService

ApprovalService.approve_permit(
    work_permit=work_permit,
    approver=safety_officer,
    comments="Safety measures verified"
)

# Auto-promote to APPROVED when all approvers sign off
if work_permit.all_approvals_received():
    work_permit.workpermit = WorkPermitStatus.APPROVED
    work_permit.save()
```

### SLA Monitoring

```python
# Check overdue work orders
from apps.work_order_management.services import SLAMonitoringService

overdue = SLAMonitoringService.get_overdue_work_orders(
    tenant=tenant,
    business_unit=business_unit
)

# Calculate SLA breach percentage
sla_stats = SLAMonitoringService.calculate_sla_compliance(
    tenant=tenant,
    start_date=datetime(2025, 11, 1),
    end_date=datetime(2025, 11, 30)
)

print(f"On-time completion: {sla_stats['on_time_percentage']}%")
print(f"Average delay: {sla_stats['average_delay_hours']} hours")
```

---

## Quality Scoring System

### Score Calculation

```python
# Work order quality metrics stored in other_data JSON
{
    "section_weightage": {
        "mechanical": 0.4,
        "electrical": 0.3,
        "safety": 0.3
    },
    "section_scores": {
        "mechanical": 95,
        "electrical": 88,
        "safety": 100
    },
    "overall_score": 94.1,  # Weighted average
    "uptime_score": 99.5,   # Equipment availability
    "quality_grade": "A"
}
```

### Vendor Performance

```python
# Track vendor performance
vendor_stats = vendor.calculate_performance_metrics(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 11, 30)
)

# Metrics
print(f"Completion rate: {vendor_stats['completion_rate']}%")
print(f"Average quality score: {vendor_stats['avg_quality_score']}")
print(f"On-time delivery: {vendor_stats['on_time_percentage']}%")
print(f"Rework rate: {vendor_stats['rework_rate']}%")
```

---

## Parent-Child Hierarchy

### Breakdown Structures

```python
# Create parent work order
parent_wo = Wom.objects.create(
    workname="Annual Building Maintenance",
    identifier=Identifier.WO,
    # ... other fields
)

# Create child work orders for phases
hvac_wo = Wom.objects.create(
    workname="HVAC Maintenance - Phase 1",
    parent=parent_wo,
    # ... other fields
)

electrical_wo = Wom.objects.create(
    workname="Electrical Inspection - Phase 2",
    parent=parent_wo,
    # ... other fields
)

# Query children
children = parent_wo.wom_children.all()

# Calculate parent completion
parent_progress = sum(c.completion_percentage for c in children) / children.count()
```

---

## Testing

### Running Tests

```bash
# All work order tests
pytest apps/work_order_management/tests/ -v

# Specific test module
pytest apps/work_order_management/tests/test_workflow.py -v

# With coverage
pytest apps/work_order_management/tests/ --cov=apps/work_order_management --cov-report=html
```

### Test Factories

```python
from apps/work_order_management.tests.factories import (
    WomFactory,
    VendorFactory,
    ApproverFactory
)

# Create work order
wo = WomFactory.create(
    workstatus=Workstatus.ASSIGNED,
    priority=Priority.HIGH,
    vendor=VendorFactory.create()
)
```

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/work_order.py

WORK_ORDER_SETTINGS = {
    'VENDOR_TOKEN_EXPIRATION_HOURS': 8,
    'SLA_ALERT_HOURS_BEFORE_DUE': 4,
    'MAX_APPROVAL_LEVELS': 5,
    'PHOTO_UPLOAD_MAX_SIZE_MB': 10,
    'GPS_VALIDATION_TOLERANCE_METERS': 50,
}

# Celery tasks
CELERY_BEAT_SCHEDULE = {
    'check-overdue-work-orders': {
        'task': 'apps.work_order_management.tasks.check_overdue',
        'schedule': crontab(hour='*/1'),  # Every hour
    },
    'send-sla-alerts': {
        'task': 'apps.work_order_management.tasks.send_sla_alerts',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
}
```

---

## State Machine Integration

### Transition Validation

```python
from apps.work_order_management.state_machines import WorkOrderStateMachine

# Validate transition
can_transition = WorkOrderStateMachine.can_transition(
    work_order,
    from_state=Workstatus.ASSIGNED,
    to_state=Workstatus.INPROGRESS
)

# Execute transition with validation
WorkOrderStateMachine.transition(
    work_order,
    new_state=Workstatus.INPROGRESS,
    user=current_user,
    comments="Starting work on schedule"
)
```

---

## Related Apps

- [activity](../activity/README.md) - Asset and location management
- [scheduler](../scheduler/README.md) - PPM schedule generation
- [inventory](../inventory/README.md) - Spare parts tracking
- [peoples](../peoples/README.md) - Approver and verifier management

---

## Troubleshooting

### Common Issues

**Issue:** Work order creation fails with tenant constraint error
**Solution:** Ensure client, bu, and tenant fields all reference the same tenant

**Issue:** Vendor token access denied
**Solution:** Check token expiration in other_data.token_expiration

**Issue:** Approval workflow stuck
**Solution:** Verify all approvers in approvers ArrayField are valid user IDs

**Issue:** GPS validation failing
**Solution:** Check gpslocation matches asset.gpslocation within tolerance

**Issue:** State transition rejected
**Solution:** Review WorkOrderStateMachine allowed transitions

---

**Last Updated:** November 12, 2025
**Maintainers:** Operations Team
**Contact:** operations-team@example.com
