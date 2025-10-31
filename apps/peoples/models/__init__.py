"""
Models package for the peoples app.

This package provides a refactored, secure, and maintainable model architecture
that complies with .claude/rules.md Rule #7 and follows SOLID principles.

Architecture Summary:
- Split from monolithic model into focused modules
- Each model file under complexity limits (< 180 lines)
- Enhanced security with battle-tested encryption
- Service layer delegation for business logic
- Backward compatibility via property accessors

File Structure:
- base_model.py: Common audit fields and utilities (88 lines)
- user_model.py: Core People authentication model (178 lines)
- profile_model.py: Personal/profile information (117 lines)
- organizational_model.py: Organizational relationships (177 lines)
- group_model.py: Group management models (164 lines)
- membership_model.py: Group membership relationships (120 lines)
- capability_model.py: Hierarchical capabilities (113 lines)
- device_registry.py: Device trust & biometric security (145 lines) [Sprint 1]

Security Improvements:
- Enhanced field encryption with Fernet
- Secure file upload service with comprehensive validation
- Enhanced input validation and sanitization
- Comprehensive audit logging

Performance Optimizations:
- Added database indexes for common queries
- Query optimization with select_related/prefetch_related patterns
- Efficient capability and permission resolution
"""

from .base_model import BaseModel
from .user_model import People
from .profile_model import PeopleProfile
from .organizational_model import PeopleOrganizational
from .group_model import PermissionGroup, Pgroup
from .membership_model import Pgbelonging
from .capability_model import Capability
from .device_registry import DeviceRegistration, DeviceRiskEvent

__all__ = [
    # Base classes
    'BaseModel',

    # User management
    'People',
    'PeopleProfile',
    'PeopleOrganizational',

    # Group management
    'PermissionGroup',
    'Pgroup',
    'Pgbelonging',

    # Capabilities
    'Capability',

    # Device Trust & Security (Sprint 1)
    'DeviceRegistration',
    'DeviceRiskEvent',
]