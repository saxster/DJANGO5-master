"""
Peoples forms module - split for maintainability.

Exports all forms for backward compatibility.
"""

from .authentication_forms import LoginForm
from .user_forms import PeopleForm
from .group_forms import (
    PgroupForm,
    SiteGroupForm,
    PeopleGroupForm,
    PgbelongingForm,
    CapabilityForm,
)
from .extras_forms import PeopleExtrasForm, NoSiteForm

__all__ = [
    'LoginForm',
    'PeopleForm',
    'PgroupForm',
    'SiteGroupForm',
    'PeopleGroupForm',
    'PgbelongingForm',
    'CapabilityForm',
    'PeopleExtrasForm',
    'NoSiteForm',
]
