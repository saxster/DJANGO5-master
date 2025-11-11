# Deprecated Serializers Notice

## File: `serializers_fixed.py` (DEPRECATED)

**Deprecation Date**: November 11, 2025  
**Reason**: Duplicate implementation with no functional benefit  
**Replacement**: Use `serializers.py` instead

### Background

During a security review (Nov 6, 2025), an alternative serializer implementation was created using explicit `fields = [...]` lists instead of `exclude = [...]` patterns.

### Resolution

After validation:
- Both approaches are **equally secure**
- Both properly exclude sensitive fields (SSN, background checks, internal notes)
- The `exclude` pattern in `serializers.py` is more maintainable (DRYer)
- Zero imports found for `serializers_fixed.py` in the codebase

### Migration Guide

**No migration needed** - `serializers_fixed.py` was never imported/used.

If you were somehow using it:
```python
# OLD (unused)
from apps.people_onboarding.serializers_fixed import DocumentSubmissionSerializer

# NEW (active)
from apps.people_onboarding.serializers import DocumentSubmissionSerializer
```

### File Location

Archived to: `serializers_fixed.py.deprecated`

---

**Remediation**: Ultrathink Phase 3, Issue #2
