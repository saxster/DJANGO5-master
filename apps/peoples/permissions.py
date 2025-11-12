"""
DRF permission classes for capability-based access control.

These permissions enforce that users must have specific capability flags
set to True in their capabilities JSON field.

Usage:
    class MyView(APIView):
        permission_classes = [IsAuthenticated, HasOnboardingAccess]
"""
from rest_framework import permissions


class HasOnboardingAccess(permissions.BasePermission):
    """
    Permission: User must have canAccessOnboarding capability.

    Returns 403 if user lacks this capability.
    Used for: All onboarding-related endpoints.
    """

    message = 'You do not have permission to access onboarding features.'

    def has_permission(self, request, view):
        """Check if user has onboarding capability."""
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_all_capabilities()
        return capabilities.get('canAccessOnboarding', False)


class HasVoiceFeatureAccess(permissions.BasePermission):
    """
    Permission: User must have canUseVoiceFeatures capability.

    Returns 403 if user lacks this capability.
    Used for: Voice notes, voice input (non-biometric).
    """

    message = 'You do not have permission to use voice features.'

    def has_permission(self, request, view):
        """Check if user has voice feature capability."""
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_all_capabilities()
        return capabilities.get('canUseVoiceFeatures', False)


class HasVoiceBiometricAccess(permissions.BasePermission):
    """
    Permission: User must have canUseVoiceBiometrics capability.

    Returns 403 if user lacks this capability.
    Used for: Voice biometric enrollment, voice-based check-in.
    """

    message = 'You do not have permission to use voice biometric features.'

    def has_permission(self, request, view):
        """Check if user has voice biometric capability."""
        if not request.user or not request.user.is_authenticated:
            return False

        capabilities = request.user.get_all_capabilities()
        return capabilities.get('canUseVoiceBiometrics', False)
