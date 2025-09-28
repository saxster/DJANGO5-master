"""
Mixins package for peoples app.

This package contains mixin classes that provide reusable functionality
for the People model while maintaining backward compatibility and
keeping model files under 150-line limit (Rule #7 compliance).

Available Mixins:
- PeopleCompatibilityMixin: Backward compatibility for split People model
- PeopleCapabilityMixin: Capability management methods (extracted from user_model)
- OrganizationalQueryMixin: Organizational relationship helpers (for organizational_model)
"""

from .compatibility_mixin import PeopleCompatibilityMixin
from .capability_mixin import PeopleCapabilityMixin
from .organizational_mixin import OrganizationalQueryMixin

__all__ = [
    'PeopleCompatibilityMixin',
    'PeopleCapabilityMixin',
    'OrganizationalQueryMixin',
]