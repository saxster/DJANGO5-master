"""
Enhanced permission classes for AI Mentor API.
"""

import logging
from enum import Enum

from rest_framework import permissions


logger = logging.getLogger(__name__)


class MentorPermission(str, Enum):
    """Enumerated mentor permissions for access control checks."""

    VIEW_MENTOR = "view_mentor"
    USE_PLAN_GENERATOR = "use_plan_generator"
    USE_PATCH_GENERATOR = "use_patch_generator"
    APPLY_PATCHES = "apply_patches"
    USE_TEST_RUNNER = "use_test_runner"
    VIEW_SENSITIVE_CODE = "view_sensitive_code"
    ADMIN_MENTOR = "admin_mentor"


class MentorAccessControl:
    """Lightweight access control layer for mentor APIs."""

    def __init__(self):
        self._permission_checks = {
            MentorPermission.ADMIN_MENTOR: self._is_superuser,
            MentorPermission.VIEW_SENSITIVE_CODE: self._is_staff_or_superuser,
            MentorPermission.APPLY_PATCHES: self._is_staff_or_superuser,
            MentorPermission.USE_PATCH_GENERATOR: self._is_staff_or_superuser,
            MentorPermission.USE_TEST_RUNNER: self._is_staff_or_superuser,
        }

    def check_access(self, user, permission, request_ip=None, endpoint=None):
        """
        Evaluate access for a given permission.

        Falls back to authenticated user requirement when no specific rule exists.
        """
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        check = self._permission_checks.get(permission, self._is_authenticated)
        try:
            return check(user)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Mentor access control check failed",
                extra={
                    "permission": permission,
                    "user_id": getattr(user, "id", None),
                    "endpoint": endpoint,
                    "request_ip": request_ip,
                    "error": str(exc),
                },
            )
            return False

    @staticmethod
    def _is_superuser(user):
        return bool(user.is_superuser)

    @staticmethod
    def _is_staff_or_superuser(user):
        return bool(user.is_staff or user.is_superuser)

    @staticmethod
    def _is_authenticated(user):
        return bool(user.is_authenticated)


_access_control_singleton = MentorAccessControl()


def get_access_control():
    """Return shared access control instance."""
    return _access_control_singleton


class MentorBasePermission(permissions.BasePermission):
    """Base permission class for mentor API endpoints."""

    required_permission = MentorPermission.VIEW_MENTOR

    def has_permission(self, request, view):
        """Check if user has required mentor permission."""
        if not request.user or not request.user.is_authenticated:
            return False

        access_control = get_access_control()
        return access_control.check_access(
            user=request.user,
            permission=self.required_permission,
            request_ip=self.get_client_ip(request),
            endpoint=request.path
        )

    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', 'unknown')


class CanUsePlanGenerator(MentorBasePermission):
    """Permission for plan generation."""
    required_permission = MentorPermission.USE_PLAN_GENERATOR


class CanUsePatchGenerator(MentorBasePermission):
    """Permission for patch generation."""
    required_permission = MentorPermission.USE_PATCH_GENERATOR


class CanApplyPatches(MentorBasePermission):
    """Permission for applying patches."""
    required_permission = MentorPermission.APPLY_PATCHES


class CanUseTestRunner(MentorBasePermission):
    """Permission for test execution."""
    required_permission = MentorPermission.USE_TEST_RUNNER


class CanViewSensitiveCode(MentorBasePermission):
    """Permission for viewing sensitive code."""
    required_permission = MentorPermission.VIEW_SENSITIVE_CODE


class CanAdminMentor(MentorBasePermission):
    """Permission for mentor administration."""
    required_permission = MentorPermission.ADMIN_MENTOR
