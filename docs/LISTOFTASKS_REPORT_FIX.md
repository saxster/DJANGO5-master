# List of Tasks Report Fix

## Issue Fixed ✅

**Error was:**
```
Error generating report: name 'CharField' is not defined
```

## Root Cause:
The `listoftasks_report` method in `apps/core/queries.py` was using `CharField()` as an `output_field` but `CharField` wasn't imported.

**Problem code (line 1007):**
```python
assigned_to=Case(
    When(~Q(people_id=1), then=F('people__peoplename')),
    When(~Q(pgroup_id=1), then=F('pgroup__groupname')),
    default=Value('NONE'),
    output_field=CharField()  # ← CharField not imported
),
```

## Fix Applied:
Added `CharField` to the imports in `apps/core/queries.py`:

**Before:**
```python
from django.db.models import (
    Q, F, Count, Case, When, Value, IntegerField, FloatField,
    Window, ExpressionWrapper, Max, Sum, TextField
)
```

**After:**
```python
from django.db.models import (
    Q, F, Count, Case, When, Value, IntegerField, FloatField,
    Window, ExpressionWrapper, Max, Sum, TextField, CharField
)
```

## Verification:
- ✅ `CharField` now imported
- ✅ `ReportQueryRepository.listoftasks_report` method available
- ✅ All other field types (`IntegerField`, `FloatField`, `TextField`) already imported
- ✅ Method signature confirmed: `(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]`

## Testing:
Now try generating the "List of Tasks" report again - it should work without the `CharField` error.

## Related:
This report uses the new Django ORM implementation and replaces the raw SQL from the original migration.