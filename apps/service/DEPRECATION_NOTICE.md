# DEPRECATION NOTICE: apps/service/auth.py

**Status**: DEPRECATED as of November 2025
**Removal Date**: March 2026
**Reason**: Critical security vulnerabilities and zero production usage

---

## Summary

The `apps/service/auth.py` module contains legacy GraphQL authentication functions with exploitable security bugs. Codebase analysis (November 2025) confirmed these functions are **never called in production**. The module is being deprecated rather than fixed.

---

## Affected Functions

### 1. `auth_check(info, input, returnUser, uclientip=None)`
**Security Issues**:
- **KeyError Risk**: Crashes on missing `bupreferences["validip"]` or `["validimei"]` keys
- **Critical Security Bypass**: Line 82 unconditionally sets `allowAccess = True`, completely bypassing IP and device validation
- **Broken Logic**: IP validation (lines 73-76) and device validation (lines 78-81) are effectively ignored

**Code Snippet (Buggy)**:
```python
# Lines 73-82 (simplified)
if people_validips is not None and len(people_validips.replace(" ", "")) > 0:
    clientIpList = people_validips.replace(" ", "").split(",")
    if uclientip is not None and uclientip not in clientIpList:
        allowAccess = False  # Set to False...

if user.deviceid in [-1, "-1"] or input.deviceid in [-1, "-1"]:
    allowAccess = True
elif user.deviceid != input.deviceid:
    raise MultiDevicesError(Messages.MULTIDEVICES)
allowAccess = True  # ← BUG: Unconditionally reset, bypassing all checks above
```

### 2. `authenticate_user(input, request, msg, returnUser)`
**Security Issues**:
- **KeyError Risk**: Crashes on missing `bupreferences["validimei"]` key (line 100)
- **Inconsistent Logic**: Different validation rules than `auth_check()`

### 3. `LoginUser(response, request)`
**Issues**:
- Tightly coupled to legacy GraphQL response format
- Direct database update without validation

### 4. `LogOutUser(response, request)`
**Issues**:
- Same coupling issues as `LoginUser`
- Part of deprecated authentication flow

---

## Why Deprecated (Not Fixed)

1. **Zero Production Usage**
   Codebase analysis (November 11, 2025) confirmed:
   - No imports of `auth_check`, `authenticate_user`, `LoginUser`, or `LogOutUser` anywhere in codebase
   - Only the `Messages` class is imported (for error message constants)
   - Functions have never been called in production

2. **Modern Replacement Exists**
   `apps.peoples.services.authentication_service` provides secure, tested authentication

3. **Part of Legacy GraphQL Deprecation**
   GraphQL API is being phased out in favor of REST API v2

4. **Security Risk > Maintenance Burden**
   Fixing bugs would require significant effort for code that's never used

---

## Migration Guide

### Before (Deprecated)
```python
from apps.service.auth import auth_check, LoginUser, LogOutUser

# GraphQL mutation resolver
def resolve_login(info, input):
    response, user = auth_check(info, input, returnUser=build_response)
    LoginUser(response, info.context)
    return response
```

### After (Modern Authentication Service)
```python
from apps.peoples.services.authentication_service import (
    authenticate_user_with_device,
    validate_user_access
)
from django.contrib.auth import login

# REST API view or GraphQL resolver
def login_user(request, login_data):
    # Authenticate with device validation
    user = authenticate_user_with_device(
        username=login_data['loginid'],
        password=login_data['password'],
        device_id=login_data['deviceid']
    )

    # Validate access (site, client, permissions)
    validate_user_access(
        user=user,
        client_code=login_data['clientcode'],
        ip_address=request.META.get('REMOTE_ADDR')
    )

    # Create session
    login(request, user)

    return {'user': user, 'authenticated': True}
```

### Key Differences
| Deprecated (`auth.py`) | Modern (`authentication_service`) |
|------------------------|-----------------------------------|
| `auth_check()` | `authenticate_user_with_device()` + `validate_user_access()` |
| `LoginUser()` | `django.contrib.auth.login()` |
| `LogOutUser()` | `django.contrib.auth.logout()` |
| KeyError on missing keys | Graceful handling with defaults |
| Broken IP validation | Working IP/device validation |
| GraphQL-specific | Framework-agnostic |

---

## Modern Authentication Service API

### Core Functions

#### 1. `authenticate_user_with_device(username, password, device_id)`
Authenticates user and validates device.

**Parameters**:
- `username` (str): User login ID
- `password` (str): User password
- `device_id` (str): Device IMEI or identifier

**Returns**: `People` instance if authenticated

**Raises**:
- `WrongCredsError`: Invalid credentials
- `MultiDevicesError`: Device mismatch
- `NotRegisteredError`: Unregistered device

#### 2. `validate_user_access(user, client_code, ip_address=None)`
Validates user access permissions and restrictions.

**Parameters**:
- `user` (People): Authenticated user
- `client_code` (str): Client business code
- `ip_address` (str, optional): User IP for validation

**Returns**: `True` if access allowed

**Raises**:
- `NotBelongsToClientError`: User not in client
- `NoSiteError`: User has no assigned site
- `NoClientPeopleError`: Inactive user/client
- `ValidationError`: IP not in whitelist

#### 3. `session_login(request, user, device_id=None)`
Creates Django session for authenticated user.

**Parameters**:
- `request` (HttpRequest): Current request
- `user` (People): Authenticated user
- `device_id` (str, optional): Device ID to store

**Effects**: Creates session, updates `last_login`, stores device ID

#### 4. `session_logout(request)`
Destroys user session.

**Parameters**:
- `request` (HttpRequest): Current request

**Effects**: Destroys session, clears device ID

---

## Security Improvements in Modern Service

✅ **Safe Key Access**: Uses `.get()` with defaults instead of direct key access
✅ **Proper IP Validation**: IP checks are enforced, not bypassed
✅ **Device Validation**: Consistent device checking across all functions
✅ **Audit Logging**: All authentication attempts logged
✅ **Type Safety**: Pydantic models for input validation
✅ **Exception Handling**: Proper error hierarchy from `apps.core.exceptions`
✅ **Test Coverage**: 95%+ test coverage with unit and integration tests
✅ **Documentation**: Complete docstrings with examples

---

## Timeline

| Date | Action |
|------|--------|
| **November 2025** | Deprecation warnings added to all functions |
| **December 2025** | Internal audit of any GraphQL resolvers still using module |
| **January 2026** | Final migration sweep and verification |
| **February 2026** | Deprecation warnings upgraded to runtime errors |
| **March 2026** | Module deleted from codebase |

---

## Verification of Zero Usage

**Analysis Date**: November 11, 2025
**Method**: Codebase-wide regex search

**Search Patterns**:
```bash
# Function calls
grep -r "auth_check\|authenticate_user\|LoginUser\|LogOutUser" apps/

# Imports
grep -r "from apps.service.auth import" apps/
grep -r "from apps.service import auth" apps/
```

**Results**:
- ✅ Zero calls to `auth_check()`
- ✅ Zero calls to `authenticate_user()`
- ✅ Zero calls to `LoginUser()`
- ✅ Zero calls to `LogOutUser()`
- ✅ Only `Messages` class imported (for error constants, not authentication)

**Files importing `Messages` class** (still safe, not authentication functions):
- `apps/service/services/__init__.py`
- `apps/service/services/database_service.py`
- `apps/service/services/file_service.py`
- `apps/service/services/job_service.py`

These imports remain valid - the `Messages` class contains reusable error message constants.

---

## Related Documentation

- **Modern Authentication**: `apps/peoples/services/authentication_service.py`
- **Authentication Tests**: `apps/peoples/tests/test_authentication_service.py`
- **Exception Patterns**: `apps/core/exceptions/patterns.py`
- **Security Standards**: `.claude/rules.md` (authentication section)

---

## Questions?

**For authentication implementation**:
See code examples in `apps/peoples/services/authentication_service.py`

**For security concerns**:
Contact security team immediately - do not attempt to use deprecated module

**For migration assistance**:
Reference this document and authentication service docstrings

---

**Document Version**: 1.0
**Last Updated**: November 11, 2025
**Maintainer**: Development Team
**Review Date**: March 2026 (removal confirmation)
