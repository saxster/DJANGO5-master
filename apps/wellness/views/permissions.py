"""
Wellness Permissions - Custom permission classes for wellness system

This module contains permission classes extracted from views.py
"""

from rest_framework import permissions

from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction


class WellnessPermission(permissions.BasePermission):
    """Custom permission for wellness system"""

    def has_permission(self, request, view):
        """Check if user has permission to access wellness system"""
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can access specific wellness object"""
        if isinstance(obj, WellnessContent):
            return obj.is_active  # Content must be active
        elif isinstance(obj, WellnessUserProgress):
            return obj.user == request.user or request.user.is_superuser
        elif isinstance(obj, WellnessContentInteraction):
            return obj.user == request.user or request.user.is_superuser

        return False
