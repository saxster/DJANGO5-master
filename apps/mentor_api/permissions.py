"""
Enhanced permission classes for AI Mentor API.
"""

from rest_framework import permissions
from apps.mentor.security.access_control import MentorPermission, get_access_control


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