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
        dict: Default AI capabilities configuration
    """
    return {}


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