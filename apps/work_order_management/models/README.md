# Work Order Management Models - Quick Reference

**Refactored**: November 4, 2025
**Pattern**: Wellness/Journal modular architecture
**Status**: ✅ Production Ready

---

## Module Structure

```
models/
├── __init__.py          - Backward compatibility exports
├── enums.py             - All TextChoices enumerations
├── helpers.py           - JSONField default functions
├── vendor.py            - Vendor/contractor model
├── work_order.py        - Wom (Work Order) model + @ontology
├── wom_details.py       - WomDetails checklist model
└── approver.py          - Approver/Verifier model
```

---

## Import Examples

### Models

```python
# All imports remain unchanged
from apps.work_order_management.models import Wom, Vendor, WomDetails, Approver

# Relative imports work
from .models import Wom, WomDetails

# Module-level import
from apps.work_order_management import models as wom
```

### Enumerations

```python
# Direct enum import
from apps.work_order_management.models import Workstatus, Priority, AnswerType

# Nested access (backward compatible)
Wom.Workstatus.ASSIGNED
Wom.WorkPermitStatus.APPROVED
Wom.Priority.HIGH
WomDetails.AnswerType.CHECKBOX
Approver.Identifier.APPROVER
```

---

## Models Overview

### Vendor
Vendor/contractor management for work order assignment.
- Contact information, GPS location
- Site-specific or global availability
- Multi-tenant isolation

### Wom (Work Order Management)
Central work order model with approval flows and SLA tracking.
- Lifecycle states: ASSIGNED → INPROGRESS → COMPLETED → CLOSED
- Multi-level approval flows (approvers/verifiers)
- Vendor coordination with tokens
- Quality scoring and GPS validation
- Complete @ontology documentation

### WomDetails
Checklist question/answer pairs for work order verification.
- Multiple answer types (checkbox, dropdown, numeric, rating, etc.)
- Attachment support (photo, audio, video)
- Min/max validation

### Approver
Approver/Verifier permissions configuration.
- Role distinction (APPROVER vs VERIFIER)
- Site-specific or global permissions
- Category-based approval scope

---

## Enumerations

### Workstatus
`ASSIGNED`, `RE_ASSIGNED`, `INPROGRESS`, `COMPLETED`, `CANCELLED`, `CLOSED`

### WorkPermitStatus
`NOT_REQUIRED`, `APPROVED`, `REJECTED`, `PENDING`

### Priority
`HIGH`, `MEDIUM`, `LOW`

### Identifier
`WO` (Work Order), `WP` (Work Permit), `SLA` (Service Level Agreement)

### AnswerType
`CHECKBOX`, `DATE`, `DROPDOWN`, `NUMERIC`, `RATING`, `BACKCAMERA`, `FRONTCAMERA`, etc.

---

## Key Features

### Multi-Tenant Security
- All queries filtered by tenant
- Unique constraints include tenant field
- Token-based vendor access

### Optimistic Locking
- `VersionField` on Wom, WomDetails, Approver
- Prevents lost updates

### PostGIS Integration
- GPS location tracking (PointField)
- Spatial indexes for proximity queries

### Approval Workflows
- Multi-level approval (approvers + verifiers)
- Work permit requirements
- History tracking in JSONField

---

## Database Indexes

### Wom
- `(tenant, cdtz)` - Date filtering
- `(tenant, workstatus)` - Status queries
- `(tenant, workpermit)` - Permit filtering

### Vendor
- `(tenant, cdtz)` - Date filtering
- `(tenant, enable)` - Active vendors

### WomDetails
- `(tenant, wom)` - Work order details
- `(tenant, question)` - Question lookups

### Approver
- `(tenant, people)` - People lookups
- `(tenant, identifier)` - Role filtering

---

## Usage Examples

### Create Work Order

```python
from apps.work_order_management.models import Wom
from django.contrib.gis.geos import Point

wo = Wom.objects.create(
    description='HVAC Maintenance',
    priority=Wom.Priority.HIGH,
    workstatus=Wom.Workstatus.ASSIGNED,
    asset=asset_obj,
    vendor=vendor_obj,
    gpslocation=Point(77.5946, 12.9716, srid=4326),
    tenant=tenant_obj
)
```

### Query Overdue Work Orders

```python
from django.utils import timezone

overdue = Wom.objects.filter(
    workstatus=Wom.Workstatus.ASSIGNED,
    expirydatetime__lt=timezone.now(),
    tenant=request.user.tenant
).select_related('asset', 'vendor')
```

### Approve Work Permit

```python
wo = Wom.objects.get(pk=wo_id)
wo.workpermit = Wom.WorkPermitStatus.APPROVED
wo.add_history()  # Track state change
wo.save()
```

---

## Related Documentation

- **Complete Report**: `/WORK_ORDER_REFACTORING_COMPLETE.md`
- **Architecture Guide**: `/CLAUDE.md`
- **Ontology Details**: See `@ontology` decorator in `work_order.py`

---

## Backward Compatibility

✅ **Zero Breaking Changes**
- All existing imports work unchanged
- Nested enum classes maintained
- No migration required
- Original file archived as `models_deprecated.py`

---

**Questions?** See `/WORK_ORDER_REFACTORING_COMPLETE.md` for detailed information.
