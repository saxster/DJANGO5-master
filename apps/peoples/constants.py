"""
Constants and default values for the peoples app.

This module contains default factory functions and constant values
extracted from models to maintain code organization and comply with
complexity limits per .claude/rules.md Rule #7.
"""


def peoplejson():
    """
    Default JSON structure for people_extras field.

    This function provides the default configuration for legacy user
    capabilities and preferences stored in the people_extras JSON field.

    Returns:
        dict: Default configuration for user capabilities and preferences
    """
    return {
        "andriodversion": "",
        "appversion": "",
        "mobilecapability": [],
        "portletcapability": [],
        "reportcapability": [],
        "webcapability": [],
        "noccapability": [],
        "loacationtracking": False,
        "capturemlog": False,
        "showalltemplates": False,
        "debug": False,
        "showtemplatebasedonfilter": False,
        "blacklist": False,
        "assignsitegroup": [],
        "tempincludes": [],
        "mlogsendsto": "",
        "user_type": "",
        "secondaryemails": [],
        "secondarymobno": [],
        "isemergencycontact": False,
        "alertmails": False,
        "currentaddress": "",
        "permanentaddress": "",
        "isworkpermit_approver": False,
        "userfor": "",
        'enable_gps': False,
        'noc_user': False
    }


def default_capabilities():
    """
    Default JSON structure for capabilities field.

    This function provides the default configuration for modern
    AI-powered user capabilities.

    Returns:
        dict: Default AI capabilities configuration with all 13 flags
    """
    return {
        # Module access capabilities
        'canAccessPeople': True,
        'canAccessAttendance': True,
        'canAccessOperations': True,
        'canAccessHelpdesk': True,
        'canAccessJournal': True,
        'canAccessReports': False,
        'canAccessCalendar': True,

        # Onboarding and voice capabilities (default OFF for security)
        'canAccessOnboarding': False,
        'canUseVoiceFeatures': False,
        'canUseVoiceBiometrics': False,

        # Workflow capabilities
        'canApproveJobs': False,
        'canManageTeam': False,
        'canViewAnalytics': False,
    }


def get_admin_capabilities() -> dict:
    """
    Full capabilities for admin/staff users.

    Admin users have all features enabled by default.

    Returns:
        dict: Admin capabilities with all features enabled
    """
    caps = default_capabilities()
    caps.update({
        'canAccessReports': True,
        'canAccessOnboarding': True,
        'canUseVoiceFeatures': True,
        'canUseVoiceBiometrics': True,
        'canApproveJobs': True,
        'canManageTeam': True,
        'canViewAnalytics': True,
    })
    return caps


def default_device_id():
    """
    Default device ID for users without registered devices.

    Returns:
        str: Default device ID value
    """
    return "-1"


GENDER_CHOICES = [
    ("M", "Male"),
    ("F", "Female"),
    ("O", "Others"),
]

DEFAULT_PROFILE_IMAGE = "master/people/blank.png"