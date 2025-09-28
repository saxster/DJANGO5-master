# People Model Migration Guide

## Overview

This guide explains the refactoring of `apps/peoples/models.py` from a monolithic 660-line file into a modular, maintainable architecture that complies with `.claude/rules.md` Rule #7.

## What Changed

### Before (Old Structure)
```
apps/peoples/
├── models.py (660 lines - ❌ VIOLATION)
│   ├── upload_peopleimg() function (146 lines)
│   ├── People model (235 lines)
│   ├── Pgroup, Pgbelonging models
│   └── Capability model
```

###After (New Structure)
```
apps/peoples/
├── models.py (163 lines - ✅ Compatibility shim)
├── models/
│   ├── __init__.py (exports all models)
│   ├── base_model.py (88 lines - ✅)
│   ├── user_model.py (152 lines - ✅)
│   ├── profile_model.py (117 lines - ✅)
│   ├── organizational_model.py (178 lines - ✅)
│   ├── group_model.py (164 lines - ✅)
│   ├── membership_model.py (120 lines - ✅)
│   └── capability_model.py (113 lines - ✅)
├── mixins/
│   ├── capability_mixin.py (provides capability methods)
│   ├── organizational_mixin.py (query helpers)
│   └── compatibility_mixin.py (backward compatibility)
└── services/
    └── file_upload_service.py (SecureFileUploadService)
```

## Migration Steps

### For Existing Code (No Changes Required)

**✅ Your existing code continues to work without modification:**

```python
# OLD CODE - Still works!
from apps.peoples.models import People, Pgroup, Capability

user = People.objects.get(loginid="john")
```

The old `models.py` is now a **compatibility shim** that imports from the new structure.

### For New Code (Recommended)

**Option 1: Continue using old import path** (easiest, works forever):
```python
from apps.peoples.models import People
```

**Option 2: Use explicit imports** (more explicit, recommended for new code):
```python
from apps.peoples.models.user_model import People
from apps.peoples.models.profile_model import PeopleProfile
```

## Deprecated Functions

Three utility functions are deprecated but still work with warnings:

### 1. `upload_peopleimg()`

**OLD (Deprecated):**
```python
from apps.peoples.models import upload_peopleimg

class People(models.Model):
    peopleimg = models.ImageField(upload_to=upload_peopleimg)
```

**NEW (Recommended):**
```python
from apps.peoples.services import SecureFileUploadService

class People(models.Model):
    peopleimg = models.ImageField(
        upload_to=SecureFileUploadService.generate_secure_upload_path
    )
```

**Benefits:**
- ✅ Better security (comprehensive validation)
- ✅ Complies with Rule #14 (<50 line functions)
- ✅ Easier to test and maintain

### 2. `peoplejson()`

**OLD (Deprecated):**
```python
from apps.peoples.models import peoplejson

defaults = peoplejson()
```

**NEW (Recommended):**
```python
from apps.peoples.constants import default_people_extras

defaults = default_people_extras
```

### 3. `now()`

**OLD (Deprecated):**
```python
from apps.peoples.models import now

current_time = now()
```

**NEW (Recommended):**
```python
from django.utils import timezone

current_time = timezone.now().replace(microsecond=0)
```

## New Features

### 1. Capability Management (via Mixin)

```python
from apps.peoples.models import People

user = People.objects.get(loginid="john")

# Check capabilities
if user.has_capability('can_approve_workorders'):
    # Approve work orders

# Add capabilities
user.add_capability('can_manage_knowledge_base', True)

# Set AI capabilities
user.set_ai_capabilities(
    can_approve=True,
    can_manage_kb=True,
    is_approver=True
)

# Get all capabilities
capabilities = user.get_all_capabilities()

# Get effective permissions
permissions = user.get_effective_permissions()
```

### 2. Organizational Query Helpers (via Mixin)

```python
from apps.peoples.models import People

manager = People.objects.get(loginid="manager")

# Get direct reports
team = manager.get_team_members()

# Get department colleagues
colleagues = manager.get_department_colleagues()

# Get location colleagues
local_team = manager.get_location_colleagues()

# Check same business unit
if user1.is_in_same_business_unit(user2):
    # They can collaborate

# Get reporting chain
chain = employee.get_reporting_chain()
# Returns: [employee, supervisor, manager, director, ...]

# Get organizational summary
summary = user.get_organizational_summary()
# {
#     'department': 'Engineering',
#     'designation': 'Senior Developer',
#     'location': 'Building A',
#     'business_unit': 'Tech Solutions',
#     'reports_to': 'John Manager',
#     'team_size': 5
# }
```

## Testing

Run the compatibility test suite to verify your code works:

```bash
# Test backward compatibility
python -m pytest apps/peoples/tests/test_models/test_models_backward_compatibility.py -v

# Test file upload integration
python -m pytest apps/peoples/tests/test_models/test_file_upload_integration.py -v

# Test model complexity compliance
python -m pytest apps/peoples/tests/test_models/test_model_complexity_compliance.py -v

# Run all people tests
python -m pytest apps/peoples/tests/ -v
```

## Timeline

- **Now - March 2026**: Compatibility shim maintained (6 months)
- **After March 2026**: Compatibility shim may be removed
  - Direct imports from `models/` subdirectory will be required
  - Deprecated functions will be removed

## Benefits

### 1. Code Quality
- ✅ All model files < 200 lines (most < 150)
- ✅ Utility functions < 50 lines
- ✅ Complies with `.claude/rules.md` Rule #7

### 2. Maintainability
- ✅ Single Responsibility Principle
- ✅ Easier to locate and modify code
- ✅ Better separation of concerns

### 3. Security
- ✅ Secure file upload service (Rule #14)
- ✅ Comprehensive input validation
- ✅ Path traversal prevention

### 4. Performance
- ✅ New query optimization helpers
- ✅ Better database index utilization
- ✅ Reduced import overhead

### 5. Extensibility
- ✅ Mixin-based architecture
- ✅ Service layer pattern
- ✅ Easy to add new functionality

## Troubleshooting

### Import Errors

**Problem:** `ImportError: cannot import name 'People' from 'apps.peoples.models'`

**Solution:** Ensure you're importing from the correct path:
```python
# Works
from apps.peoples.models import People

# Also works
from apps.peoples.models.user_model import People
```

### Deprecation Warnings

**Problem:** Seeing `DeprecationWarning` messages

**Solution:** This is expected! Update your code to use the new recommended patterns shown above.

To suppress warnings temporarily:
```python
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
```

### Missing Methods

**Problem:** `AttributeError: 'People' object has no attribute 'has_capability'`

**Solution:** Ensure the mixin is properly included. This should work automatically via the compatibility shim.

### Test Failures

**Problem:** Tests failing after migration

**Solution:**
1. Verify imports are correct
2. Check that fixtures create required related models (Profile, Organizational)
3. Run compatibility tests to identify specific issues:
   ```bash
   python -m pytest apps/peoples/tests/test_models/test_models_backward_compatibility.py -v
   ```

## FAQ

**Q: Do I need to change my existing code?**
A: No! Existing code continues to work via the compatibility shim.

**Q: Should I update to the new patterns?**
A: Recommended for new code, but not required for existing code.

**Q: When will the compatibility shim be removed?**
A: Planned for March 2026 (6 months from now).

**Q: Will my database migrations be affected?**
A: No, database table structures remain unchanged.

**Q: How do I report issues?**
A: Create an issue in the project repository with:
- Code that's not working
- Error messages
- Expected vs actual behavior

## Additional Resources

- `.claude/rules.md` - Code quality rules
- `apps/peoples/models/__init__.py` - Model exports
- `apps/peoples/services/` - Service layer documentation
- `apps/peoples/tests/` - Comprehensive test suite

---

**Last Updated:** September 27, 2025
**Compatibility Shim Valid Until:** March 27, 2026