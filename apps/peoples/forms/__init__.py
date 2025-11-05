"""
Peoples forms - Refactored modular structure with backward compatibility.

This package provides all forms for the peoples app, organized by functionality:
- authentication_forms: LoginForm
- profile_forms: PeopleForm
- extras_forms: PeopleExtrasForm
- organizational_forms: Group and capability forms

All imports are re-exported here for 100% backward compatibility with the original
monolithic forms.py file (703 lines -> 4 focused modules, ~580 lines).
"""

# Authentication
from .authentication_forms import LoginForm

# Profile management
from .profile_forms import PeopleForm

# User capabilities and access
from .extras_forms import PeopleExtrasForm

# Organizational structures
from .organizational_forms import (
    PgroupForm,
    SiteGroupForm,
    PeopleGroupForm,
    PgbelongingForm,
    CapabilityForm,
    PeopleGrpAllocation,
    NoSiteForm,
)

__all__ = [
    # Authentication
    "LoginForm",
    # Profile
    "PeopleForm",
    # Capabilities
    "PeopleExtrasForm",
    # Organizational
    "PgroupForm",
    "SiteGroupForm",
    "PeopleGroupForm",
    "PgbelongingForm",
    "CapabilityForm",
    "PeopleGrpAllocation",
    "NoSiteForm",
]
