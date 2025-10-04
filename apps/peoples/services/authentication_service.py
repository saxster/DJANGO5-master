"""
Authentication Service

Extracts authentication business logic from views including:
- User authentication and validation
- Session management
- Role-based routing
- Multi-tenant authentication
- Security validation
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.services import BaseService, with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    AuthenticationError,
    WrongCredsError,
    PermissionDeniedError,
    SecurityException,
    EnhancedValidationException,
    UserManagementException
)
from apps.peoples.models import People
from apps.core import utils
import apps.peoples.utils as putils
from apps.peoples.services.login_throttling_service import login_throttle_service

logger = logging.getLogger(__name__)


class UserAccessType(Enum):
    """User access type enumeration."""
    WEB = "Web"
    MOBILE = "Mobile"
    BOTH = "Both"


class SiteCode(Enum):
    """Site code enumeration for routing."""
    SPSESIC = "SPSESIC"
    SPSPAYROLL = "SPSPAYROLL"
    SPSOPS = "SPSOPS"
    SPSOPERATION = "SPSOPERATION"
    SPSHR = "SPSHR"


@dataclass
class AuthenticationResult:
    """Authentication result data structure."""
    success: bool
    user: Optional[People] = None
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    session_data: Optional[Dict[str, Any]] = None


@dataclass
class UserContext:
    """User context for authentication decisions."""
    user: People
    bu_id: Optional[int] = None
    sitecode: Optional[str] = None
    client_name: Optional[str] = None
    has_wizard_data: bool = False
    access_type: Optional[str] = None


class AuthenticationService(BaseService):
    """
    Service for handling authentication business logic.

    Extracted from peoples/views.py to separate concerns and improve testability.
    """

    def __init__(self):
        super().__init__()
        self.error_messages = {
            "auth-error": "Authentication failed",
            "unauthorized-User": "User is not authorized for this platform",
            "invalid-details": "Invalid login details provided",
            "invalid-form": "Invalid form data submitted",
            "no-site-access": "User does not have site access permissions"
        }

    @BaseService.monitor_performance("authenticate_user")
    @with_transaction()
    def authenticate_user(
        self,
        loginid: str,
        password: str,
        access_type: str = UserAccessType.WEB.value,
        ip_address: str = None
    ) -> AuthenticationResult:
        """
        Authenticate a user with comprehensive validation and throttling.

        Args:
            loginid: User login ID
            password: User password
            access_type: Access type (Web, Mobile, Both)
            ip_address: Client IP address for throttling (optional)

        Returns:
            AuthenticationResult with success status and context

        Security:
            - Rate limiting per IP and username
            - Exponential backoff on failed attempts
            - Automatic lockout after threshold
        """
        try:
            # Step 0: Check throttling BEFORE any authentication attempts
            if ip_address:
                # Check IP-based throttling
                ip_throttle = login_throttle_service.check_ip_throttle(ip_address)
                if not ip_throttle.allowed:
                    self.logger.warning(
                        f"IP throttled: {ip_address} - {ip_throttle.reason}",
                        extra={
                            'ip_address': ip_address,
                            'wait_seconds': ip_throttle.wait_seconds,
                            'security_event': 'ip_throttled'
                        }
                    )
                    return AuthenticationResult(
                        success=False,
                        error_message=f"Too many login attempts. Please try again in {ip_throttle.wait_seconds} seconds.",
                        session_data={'lockout_until': ip_throttle.lockout_until}
                    )

                # Check username-based throttling
                username_throttle = login_throttle_service.check_username_throttle(loginid)
                if not username_throttle.allowed:
                    self.logger.warning(
                        f"Username throttled: {loginid} - {username_throttle.reason}",
                        extra={
                            'username': loginid,
                            'wait_seconds': username_throttle.wait_seconds,
                            'security_event': 'username_throttled'
                        }
                    )
                    return AuthenticationResult(
                        success=False,
                        error_message=f"Account temporarily locked. Please try again in {username_throttle.wait_seconds} seconds.",
                        session_data={'lockout_until': username_throttle.lockout_until}
                    )

            # Step 1: Validate user exists and access type
            user_validation = self._validate_user_access(loginid, access_type)
            if not user_validation.success:
                # Record failed attempt for non-existent users
                if ip_address:
                    login_throttle_service.record_failed_attempt(
                        ip_address,
                        loginid,
                        reason="user_not_found"
                    )
                return user_validation

            # Step 2: Authenticate credentials
            user = self._authenticate_credentials(loginid, password)
            if not user:
                # Record failed attempt for invalid credentials
                if ip_address:
                    login_throttle_service.record_failed_attempt(
                        ip_address,
                        loginid,
                        reason="invalid_credentials"
                    )
                return AuthenticationResult(
                    success=False,
                    error_message=self.error_messages["invalid-details"]
                )

            # Step 3: Build user context
            user_context = self._build_user_context(user)

            # Step 4: Validate site access
            site_validation = self._validate_site_access(user_context)
            if not site_validation.success:
                return site_validation

            # Step 5: Determine redirect URL
            redirect_url = self._determine_redirect_url(user_context)

            # Step 6: Prepare session data
            session_data = self._prepare_session_data(user_context)

            # Step 7: Record successful login and clear throttles
            if ip_address:
                login_throttle_service.record_successful_attempt(ip_address, loginid)

            self.logger.info(
                f'Authentication successful for user "{user.peoplename}" '
                f'with loginid "{user.loginid}" '
                f'client "{user_context.client_name}" '
                f'site "{user_context.sitecode}"'
            )

            return AuthenticationResult(
                success=True,
                user=user,
                redirect_url=redirect_url,
                session_data=session_data
            )

        except (AuthenticationError, WrongCredsError, ValidationError, PermissionDeniedError) as e:
            # Record failed attempt on exception
            if ip_address:
                login_throttle_service.record_failed_attempt(
                    ip_address,
                    loginid,
                    reason="authentication_exception"
                )

            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'user_authentication',
                    'loginid': loginid,
                    'access_type': access_type,
                    'ip_address': ip_address
                },
                level='error'
            )

            return AuthenticationResult(
                success=False,
                error_message="Authentication service error",
                correlation_id=correlation_id
            )
        except (ValidationError, IntegrityError) as e:
            self.logger.error(f"Database validation error during authentication: {str(e)}")
            return AuthenticationResult(
                success=False,
                error_message="User validation error"
            )

    def _validate_user_access(self, loginid: str, access_type: str) -> AuthenticationResult:
        """
        Validate user exists and has correct access type.

        Args:
            loginid: User login ID
            access_type: Required access type

        Returns:
            AuthenticationResult with validation status
        """
        try:
            user_query = People.objects.filter(loginid=loginid).values(
                "people_extras__userfor"
            )

            if not user_query.exists():
                self.logger.warning(f"User not found: {loginid}")
                return AuthenticationResult(
                    success=False,
                    error_message="User not found"
                )

            user_access_type = user_query[0]["people_extras__userfor"]

            # Validate access type
            if access_type == UserAccessType.WEB.value:
                if user_access_type not in [UserAccessType.WEB.value, UserAccessType.BOTH.value]:
                    self.logger.warning(f"User {loginid} not authorized for web access")
                    return AuthenticationResult(
                        success=False,
                        error_message=self.error_messages["unauthorized-User"]
                    )

            return AuthenticationResult(success=True)

        except (ValidationError, People.DoesNotExist) as e:
            self.logger.error(f"User access validation failed: {str(e)}")
            raise UserManagementException(
                "User access validation failed",
                original_exception=e
            ) from e
        except IntegrityError as e:
            self.logger.error(f"Database integrity error during user validation: {str(e)}")
            raise UserManagementException(
                "Database error during user validation",
                original_exception=e
            ) from e

    def _authenticate_credentials(self, loginid: str, password: str) -> Optional[People]:
        """
        Authenticate user credentials.

        Args:
            loginid: User login ID
            password: User password

        Returns:
            Authenticated user or None
        """
        try:
            user = authenticate(username=loginid, password=password)
            if user and user.is_authenticated:
                return user

            self.logger.warning(f"Invalid credentials for user: {loginid}")
            return None

        except (AuthenticationError, ValidationError) as e:
            self.logger.error(f"Credential authentication failed: {str(e)}")
            raise AuthenticationError(
                "Credential authentication failed",
                original_exception=e
            ) from e
        except AttributeError as e:
            self.logger.error(f"Invalid user object during authentication: {str(e)}")
            raise AuthenticationError(
                "Invalid user object",
                original_exception=e
            ) from e

    def _build_user_context(self, user: People) -> UserContext:
        """
        Build comprehensive user context for decision making.

        Args:
            user: Authenticated user

        Returns:
            UserContext with user information
        """
        return UserContext(
            user=user,
            bu_id=getattr(user.bu, 'id', None) if user.bu else None,
            sitecode=getattr(user.bu, 'bucode', None) if user.bu else None,
            client_name=getattr(user.client, 'buname', None) if user.client else None,
            access_type=getattr(user.people_extras, 'userfor', None) if hasattr(user, 'people_extras') else None
        )

    def _validate_site_access(self, user_context: UserContext) -> AuthenticationResult:
        """
        Validate user has appropriate site access.

        Args:
            user_context: User context information

        Returns:
            AuthenticationResult with validation status
        """
        # Check if user has no site or invalid site
        if user_context.bu_id in [1, None]:
            return AuthenticationResult(
                success=False,
                redirect_url='peoples:no_site',
                error_message=self.error_messages["no-site-access"]
            )

        return AuthenticationResult(success=True)

    def _determine_redirect_url(self, user_context: UserContext) -> str:
        """
        Determine post-authentication redirect URL based on user context.

        Args:
            user_context: User context information

        Returns:
            Redirect URL string
        """
        sitecode = user_context.sitecode

        # Define site-specific routing rules
        site_routing = {
            SiteCode.SPSOPS.value: 'reports:generateattendance',
            SiteCode.SPSHR.value: 'employee_creation:employee_creation',
            SiteCode.SPSOPERATION.value: 'reports:generate_declaration_form'
        }

        # Check if user has valid site codes
        valid_sites = [code.value for code in SiteCode]

        if sitecode not in valid_sites:
            # Handle wizard data or default redirect
            if user_context.has_wizard_data:
                return 'onboarding:wizard_delete'
            else:
                return 'onboarding:rp_dashboard'

        # Return site-specific redirect or default
        return site_routing.get(sitecode, 'reports:generatepdf')

    def _prepare_session_data(self, user_context: UserContext) -> Dict[str, Any]:
        """
        Prepare session data for authenticated user.

        Args:
            user_context: User context information

        Returns:
            Dictionary of session data
        """
        return {
            'user_id': user_context.user.id,
            'peoplecode': user_context.user.peoplecode,
            'bu_id': user_context.bu_id,
            'sitecode': user_context.sitecode,
            'client_name': user_context.client_name,
            'access_type': user_context.access_type,
            'login_timestamp': utils.get_current_timestamp() if hasattr(utils, 'get_current_timestamp') else None
        }

    @BaseService.monitor_performance("logout_user")
    def logout_user(self, request: HttpRequest) -> AuthenticationResult:
        """
        Handle user logout with session cleanup.

        Args:
            request: HTTP request object

        Returns:
            AuthenticationResult with logout status
        """
        try:
            user = request.user
            if user.is_authenticated:
                self.logger.info(f"User logout: {user.peoplecode}")
                logout(request)

            return AuthenticationResult(
                success=True,
                redirect_url='peoples:login'
            )

        except (AttributeError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'user_logout'},
                level='warning'
            )

            return AuthenticationResult(
                success=False,
                error_message="Logout failed",
                correlation_id=correlation_id
            )

    @BaseService.monitor_performance("validate_session")
    def validate_session(self, request: HttpRequest) -> bool:
        """
        Validate user session is still valid.

        Args:
            request: HTTP request object

        Returns:
            True if session is valid
        """
        try:
            if not request.user.is_authenticated:
                return False

            # Additional session validation can be added here
            # e.g., checking session timeout, user status, etc.

            return True

        except (AttributeError, ValueError) as e:
            self.logger.warning(f"Session validation failed: {str(e)}")
            return False

    @BaseService.monitor_performance("get_user_permissions")
    def get_user_permissions(self, user: People) -> Dict[str, Any]:
        """
        Get comprehensive user permissions and capabilities.

        Args:
            user: User object

        Returns:
            Dictionary of user permissions
        """
        try:
            permissions = {
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'is_active': user.is_active,
                'bu_id': getattr(user.bu, 'id', None) if user.bu else None,
                'client_id': getattr(user.client, 'id', None) if user.client else None,
                'access_type': getattr(user.people_extras, 'userfor', None) if hasattr(user, 'people_extras') else None,
                'groups': list(user.groups.values_list('name', flat=True)),
                'user_permissions': list(user.user_permissions.values_list('codename', flat=True))
            }

            return permissions

        except (AttributeError, People.DoesNotExist) as e:
            self.logger.error(f"Failed to get user permissions: {str(e)}")
            return {}

    @BaseService.monitor_performance("rotate_session")
    def rotate_session(
        self,
        request: HttpRequest,
        reason: str = "privilege_change"
    ) -> bool:
        """
        Rotate session key to prevent session fixation.

        Implements Rule #10: Session rotation on privilege changes.

        Args:
            request: HTTP request with active session
            reason: Reason for rotation (for audit logging)

        Returns:
            True if rotation successful
        """
        try:
            if not hasattr(request, 'session'):
                self.logger.warning("Cannot rotate session: no session available")
                return False

            old_session_key = request.session.session_key
            request.session.cycle_key()
            new_session_key = request.session.session_key

            correlation_id = getattr(request, 'correlation_id', 'unknown')

            self.logger.info(
                f"Session rotated: {reason}",
                extra={
                    'correlation_id': correlation_id,
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'old_session_key': old_session_key[:8] + '...' if old_session_key else 'none',
                    'new_session_key': new_session_key[:8] + '...' if new_session_key else 'none',
                    'rotation_reason': reason,
                    'timestamp': timezone.now().isoformat() if hasattr(timezone, 'now') else None
                }
            )

            return True

        except (AttributeError, ValueError) as e:
            self.logger.error(f"Session rotation failed: {str(e)}")
            return False

    @BaseService.monitor_performance("rotate_session_on_privilege_change")
    def rotate_session_on_privilege_change(
        self,
        request: HttpRequest,
        user: People,
        old_privileges: Dict[str, bool],
        new_privileges: Dict[str, bool]
    ) -> bool:
        """
        Rotate session when user privileges are elevated.

        Implements Rule #10: Session Security Standards.

        Args:
            request: HTTP request
            user: User whose privileges changed
            old_privileges: Previous privilege state
            new_privileges: New privilege state

        Returns:
            True if rotation performed
        """
        try:
            privilege_escalated = self._detect_privilege_escalation(
                old_privileges,
                new_privileges
            )

            if privilege_escalated:
                escalation_details = self._get_escalation_details(
                    old_privileges,
                    new_privileges
                )

                self.logger.warning(
                    f"Privilege escalation detected for user {user.peoplecode}: {escalation_details}",
                    extra={
                        'user_id': user.id,
                        'peoplecode': user.peoplecode,
                        'escalation_details': escalation_details,
                        'old_privileges': old_privileges,
                        'new_privileges': new_privileges
                    }
                )

                return self.rotate_session(
                    request,
                    reason=f"privilege_escalation:{escalation_details}"
                )

            return False

        except (AttributeError, ValueError, TypeError) as e:
            self.logger.error(f"Privilege change rotation failed: {str(e)}")
            return False

    def _detect_privilege_escalation(
        self,
        old_privileges: Dict[str, bool],
        new_privileges: Dict[str, bool]
    ) -> bool:
        """
        Detect if privileges were escalated.

        Args:
            old_privileges: Previous privilege state
            new_privileges: New privilege state

        Returns:
            True if escalation detected
        """
        escalation_keys = ['is_superuser', 'is_staff', 'isadmin']

        for key in escalation_keys:
            old_value = old_privileges.get(key, False)
            new_value = new_privileges.get(key, False)

            if not old_value and new_value:
                return True

        return False

    def _get_escalation_details(
        self,
        old_privileges: Dict[str, bool],
        new_privileges: Dict[str, bool]
    ) -> str:
        """
        Get human-readable escalation details.

        Args:
            old_privileges: Previous privilege state
            new_privileges: New privilege state

        Returns:
            Comma-separated list of escalated privileges
        """
        escalations = []
        escalation_keys = ['is_superuser', 'is_staff', 'isadmin']

        for key in escalation_keys:
            if not old_privileges.get(key, False) and new_privileges.get(key, False):
                escalations.append(key)

        return ','.join(escalations) if escalations else 'unknown'

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "AuthenticationService"