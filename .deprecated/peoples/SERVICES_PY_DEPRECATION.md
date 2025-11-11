# apps/peoples/services.py - Removed November 11, 2025

## Summary

Legacy authentication service file shadowed by modern `services/` package.
File was unreachable via normal imports and contained critical bugs.

## Why Removed

1. **Shadowed by Package Directory**: Python's import resolution prioritizes `services/` directory over `services.py` file
2. **Dead Code**: Zero production usage, zero test coverage
3. **Critical Bug**: Missing `from django.contrib.auth import authenticate` import (line 20)
   - Would cause `NameError` if code were executed
4. **Superseded**: Modern implementation at `apps/peoples/services/authentication_service.py`

## Issues Found

### Missing Import (Line 20)
```python
# Line 20 - NameError waiting to happen
people = authenticate(username=username, password=password)  # ❌ authenticate not imported
```

### Missing Features Compared to Modern Service
- ❌ No login throttling (security vulnerability)
- ❌ No device trust validation
- ❌ No session management
- ❌ No audit logging
- ❌ No rate limiting

## Migration Path

All code using:
```python
from apps.peoples.services import AuthenticationService
```

Automatically resolves to modern implementation at:
```python
apps/peoples/services/__init__.py
  → apps/peoples/services/authentication_service.py
```

**No code changes needed** - imports already point to modern service.

## Modern Service Comparison

| Feature | Legacy `services.py` | Modern `services/authentication_service.py` |
|---------|---------------------|---------------------------------------------|
| Size | 60 lines (1.9KB) | 800+ lines (32KB) |
| Login throttling | ❌ None | ✅ Redis-backed rate limiting |
| Device trust | ❌ None | ✅ Device fingerprinting |
| Session management | ❌ Basic dict | ✅ Secure rotation, revocation |
| Audit logging | ❌ None | ✅ Comprehensive correlation IDs |
| Test coverage | ❌ 0 tests | ✅ 40+ tests |
| `authenticate()` import | ❌ **Missing** | ✅ Present (line 19) |
| Signature | `username, password` | `loginid, password, access_type, ip_address` |

## Historical Context

- **Created**: Pre-Oct 2025 (legacy GraphQL authentication)
- **Last Modified**: 2025-09-28 (before refactoring)
- **Shadowed**: Oct-Nov 2025 (when `services/` package created)
- **Removed**: 2025-11-11 (Ultrathink Phase 6)

## Related Deprecations

- `apps/service/DEPRECATION_NOTICE.md` - Legacy GraphQL auth deprecated (Oct 2025)
- `apps/security_intelligence/` - Orphaned legacy shim deleted (Nov 11, 2025)

## Verification

After removal, the following commands confirm no breakage:

```bash
# Check for import errors
python manage.py check

# Verify authentication still works
python -c "
from apps.peoples.services import AuthenticationService
import inspect
print('Source:', inspect.getfile(AuthenticationService))
# Should print: .../apps/peoples/services/authentication_service.py
"

# Run authentication tests
python -m pytest apps/peoples/tests/test_authentication.py -v
```

All tests pass - modern service is fully operational.

## Archive Location

Original file archived at: `.deprecated/peoples/services_legacy_2025_09_28.py`

---

**Removal Date**: November 11, 2025
**Removed By**: Ultrathink Phase 6 Remediation
**Impact**: Zero (dead code, no production usage)
**Rollback**: Not needed (file was unreachable)
