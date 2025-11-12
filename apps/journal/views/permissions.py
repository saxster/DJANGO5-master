"""
Journal Permission Classes

Custom permissions for journal entries with privacy enforcement.
Extracted from views.py for reusability across view modules.
"""

from rest_framework import permissions

from apps.journal.models import JournalEntry, JournalMediaAttachment, JournalPrivacySettings


class JournalPermission(permissions.BasePermission):
    """Custom permission for journal entries with privacy enforcement"""

    def has_permission(self, request, view):
        """Check if user has permission to access journal system"""
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can access specific journal entry"""
        if isinstance(obj, JournalEntry):
            return obj.can_user_access(request.user)
        elif isinstance(obj, JournalMediaAttachment):
            return obj.journal_entry.can_user_access(request.user)
        elif isinstance(obj, JournalPrivacySettings):
            return obj.user == request.user or request.user.is_superuser

        return False
