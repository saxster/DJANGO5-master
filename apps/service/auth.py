"""
DEPRECATED: Legacy GraphQL authentication module with critical security bugs.

**Status**: Deprecated as of November 2025
**Removal**: Scheduled for March 2026
**Migration**: Use apps.peoples.services.authentication_service instead

**Known Security Issues**:
1. KeyError risk on missing bupreferences["validip"]/["validimei"] keys
2. Security bypass: allowAccess unconditionally reset to True (line 82)
   - IP validation is completely bypassed
   - Device validation is ignored
3. Inconsistent authentication logic between auth_check() and authenticate_user()

**Why Deprecated**:
- Never called in production (confirmed via codebase analysis Nov 2025)
- Contains exploitable security vulnerabilities
- Modern authentication available in apps.peoples.services.authentication_service
- Part of legacy GraphQL API being phased out

**Migration Path**:
Replace usage with apps.peoples.services.authentication_service:
    from apps.peoples.services.authentication_service import (
        authenticate_user_with_device,
        validate_user_access
    )

See: apps/service/DEPRECATION_NOTICE.md for complete migration guide

DO NOT USE THIS MODULE IN NEW CODE.
"""
from django.core.exceptions import ImproperlyConfigured

DEPRECATION_ERROR = (
    "apps.service.auth has been removed due to critical security issues. "
    "Use apps.peoples.services.authentication_service instead."
)


class Messages:
    AUTHFAILED = "Authentication Failed "
    AUTHSUCCESS = "Authentication Successfull"
    NOSITE = "Unable to find site!"
    INACTIVE = "Inactive client or people"
    NOCLIENTPEOPLE = "Unable to find client or People or User/Client are not verified"
    MULTIDEVICES = (
        "Cannot login on multiple devices, Please logout from the other device"
    )
    WRONGCREDS = "Incorrect Username or Password"
    NOTREGISTERED = "Device Not Registered"
    NOTBELONGSTOCLIENT = "UserNotInThisClient"


def _raise_deprecated_access(function_name: str):
    """Always raise ImproperlyConfigured to prevent accidental usage."""
    raise ImproperlyConfigured(
        f"{function_name} is no longer available. {DEPRECATION_ERROR}"
    )


def LoginUser(response, request):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function now raises ImproperlyConfigured immediately.
    """
    _raise_deprecated_access("LoginUser")


def LogOutUser(response, request):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function now raises ImproperlyConfigured immediately.
    """
    _raise_deprecated_access("LogOutUser")


def check_user_site(user):
    """Removed helper kept for backward compatibility."""
    _raise_deprecated_access("check_user_site")


def auth_check(info, input, returnUser, uclientip=None):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function now raises ImproperlyConfigured immediately to prevent
    the known security bypass from being executed.
    """
    _raise_deprecated_access("auth_check")


def authenticate_user(input, request, msg, returnUser):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function now raises ImproperlyConfigured immediately.
    """
    _raise_deprecated_access("authenticate_user")
