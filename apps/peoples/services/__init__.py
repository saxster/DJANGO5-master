"""
Peoples Services Package

This package contains service classes for managing People model operations
in a secure, maintainable way following separation of concerns principles.

Service Classes:
- AuthenticationService: User authentication, session management, and routing
- PeopleManagementService: CRUD operations for People model
- CapabilityManagementService: Capability management operations
- GroupManagementService: People group management
- SiteGroupManagementService: Site group and assignment management
- PasswordManagementService: Password change and validation
- EmailVerificationService: Email verification workflow
- UserDefaultsService: Handles default field values and initialization
- UserCapabilityService: Manages user capabilities and permissions
- FileUploadService: Secure file upload handling with comprehensive validation
"""

from .authentication_service import (
    AuthenticationService,
    AuthenticationResult,
    UserContext
)
from .people_management_service import (
    PeopleManagementService,
    PeopleListResult,
    PeopleOperationResult
)
from .capability_management_service import (
    CapabilityManagementService,
    CapabilityOperationResult
)
from .group_management_service import (
    GroupManagementService,
    GroupOperationResult
)
from .site_group_management_service import (
    SiteGroupManagementService,
    SiteGroupOperationResult
)
from .password_management_service import (
    PasswordManagementService,
    PasswordOperationResult
)
from .email_verification_service import (
    EmailVerificationService,
    EmailVerificationResult
)

__all__ = [
    'AuthenticationService',
    'AuthenticationResult',
    'UserContext',
    'PeopleManagementService',
    'PeopleListResult',
    'PeopleOperationResult',
    'CapabilityManagementService',
    'CapabilityOperationResult',
    'GroupManagementService',
    'GroupOperationResult',
    'SiteGroupManagementService',
    'SiteGroupOperationResult',
    'PasswordManagementService',
    'PasswordOperationResult',
    'EmailVerificationService',
    'EmailVerificationResult',
]