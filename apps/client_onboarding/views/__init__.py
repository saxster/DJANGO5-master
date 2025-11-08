"""
Client Onboarding Views Module

Refactored into focused modules (Nov 2025):
- configuration_views.py - Configuration/setup (SuperTypeAssist, TypeAssist, capabilities)
- site_views.py - Site management (GetAllSites, GetAssignedSites, SwitchSite)
- people_views.py - People onboarding (get_list_of_peoples)
- subscription_views.py - Subscription management (LicenseSubscriptionView)
"""

from .configuration_views import (
    get_caps,
    handle_pop_forms,
    SuperTypeAssist,
)
from .site_views import (
    GetAllSites,
    GetAssignedSites,
    SwitchSite,
)
from .people_views import (
    get_list_of_peoples,
)
from .subscription_views import (
    LicenseSubscriptionView,
)

__all__ = [
    # Configuration views
    "get_caps",
    "handle_pop_forms",
    "SuperTypeAssist",
    # Site views
    "GetAllSites",
    "GetAssignedSites",
    "SwitchSite",
    # People views
    "get_list_of_peoples",
    # Subscription views
    "LicenseSubscriptionView",
]
