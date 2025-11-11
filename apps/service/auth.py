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
from apps.core.exceptions import (
    NoClientPeopleError,
    MultiDevicesError,
    NotRegisteredError,
    WrongCredsError,
    NoSiteError,
    NotBelongsToClientError,
)
from apps.peoples.models import People
from logging import getLogger
import warnings

log = getLogger("mobile_service_log")


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


def LoginUser(response, request):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function will be removed in March 2026.
    """
    warnings.warn(
        "LoginUser() is deprecated and will be removed in March 2026. "
        "Use apps.peoples.services.authentication_service instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if response["isauthenticated"]:
        People.objects.filter(id=response["user"].id).update(
            deviceid=response["authinput"].deviceid
        )


def LogOutUser(response, request):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function will be removed in March 2026.
    """
    warnings.warn(
        "LogOutUser() is deprecated and will be removed in March 2026. "
        "Use apps.peoples.services.authentication_service instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if response["isauthenticated"]:
        People.objects.filter(id=response["user"].id).update(deviceid=-1)


def check_user_site(user):
    return user.bu_id not in [1, None, "NONE", "None"]


def auth_check(info, input, returnUser, uclientip=None):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function contains security vulnerabilities and will be removed in March 2026.
    """
    warnings.warn(
        "auth_check() is deprecated and will be removed in March 2026. "
        "Use apps.peoples.services.authentication_service instead. "
        "This function contains known security bugs (KeyError risks, IP validation bypass).",
        DeprecationWarning,
        stacklevel=2
    )

    from django.contrib.auth import authenticate

    try:
        log.info(f"Authenticating {input.loginid} for {input.clientcode}")
        if (
            valid_user := People.objects.select_related("client")
            .filter(loginid=input.loginid, client__bucode=input.clientcode)
            .exists()
        ):
            user = authenticate(
                info.context, username=input.loginid, password=input.password
            )
            if not user:
                raise ValueError
        else:
            raise NotBelongsToClientError(Messages.NOTBELONGSTOCLIENT)
    except ValueError as e:
        raise WrongCredsError(Messages.WRONGCREDS) from e
    else:
        if not check_user_site(user):
            raise NoSiteError(Messages.NOSITE)
        allowAccess = isValidDevice = isUniqueDevice = True
        people_validips = user.client.bupreferences["validip"]
        people_validimeis = (
            user.client.bupreferences["validimei"].replace(" ", "").split(",")
        )

        if people_validips is not None and len(people_validips.replace(" ", "")) > 0:
            clientIpList = people_validips.replace(" ", "").split(",")
            if uclientip is not None and uclientip not in clientIpList:
                allowAccess = False

        if user.deviceid in [-1, "-1"] or input.deviceid in [-1, "-1"]:
            allowAccess = True
        elif user.deviceid != input.deviceid:
            raise MultiDevicesError(Messages.MULTIDEVICES)
        allowAccess = True
        if allowAccess:
            if user.client.enable and user.enable:
                return returnUser(user, info.context), user
            else:
                raise NoClientPeopleError(Messages.NOCLIENTPEOPLE)


def authenticate_user(input, request, msg, returnUser):
    """
    DEPRECATED: Use apps.peoples.services.authentication_service instead.

    This function contains security vulnerabilities and will be removed in March 2026.
    """
    warnings.warn(
        "authenticate_user() is deprecated and will be removed in March 2026. "
        "Use apps.peoples.services.authentication_service instead. "
        "This function contains known security bugs (KeyError risks).",
        DeprecationWarning,
        stacklevel=2
    )

    loginid = input.loginid
    password = input.password
    deviceid = input.deviceid

    from django.contrib.auth import authenticate

    user = authenticate(request, username=loginid, password=password)
    if not user:
        raise WrongCredsError(msg.WRONGCREDS)
    valid_imeis = user.client.bupreferences["validimei"].replace(" ", "").split(",")

    if deviceid != "-1" and user.deviceid == "-1":
        if all([user.client.enable, user.enable, user.isverified]):
            return returnUser(user, request), user
        raise NoClientPeopleError(msg.NOCLIENTPEOPLE)
    if deviceid not in valid_imeis:
        raise NotRegisteredError(msg.NOTREGISTERED)
    if deviceid != user.deviceid:
        raise MultiDevicesError(msg.MULTIDEVICES)
    return returnUser(user, request), user
