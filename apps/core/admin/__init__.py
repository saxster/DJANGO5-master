"""
Core Admin Module

Provides base admin classes and utilities for all IntelliWiz admin interfaces.

Exports:
- IntelliWizModelAdmin: Base admin class with Unfold theme
- ReadOnlyModelAdmin: For audit logs and system data
- ImportExportModelAdminMixin: For models with import/export
- BulkActionsMixin: Common bulk actions (enable/disable/export)
- TenantAwareBulkActions: Tenant-specific bulk actions
- ApprovalWorkflowActions: Approval workflow actions

Lazy imports to prevent circular dependency during app loading.
"""

__all__ = [
    # Base classes
    'IntelliWizModelAdmin',
    'ReadOnlyModelAdmin',
    'ImportExportModelAdminMixin',
    # Bulk actions
    'BulkActionsMixin',
    'TenantAwareBulkActions',
    'ApprovalWorkflowActions',
]


def __getattr__(name):
    """
    Lazy import admin classes to prevent circular import during app loading.

    This allows Django to load apps without importing admin classes,
    which depend on unfold.admin and ContentType being ready.
    """
    if name == 'IntelliWizModelAdmin':
        from .base_admin import IntelliWizModelAdmin
        return IntelliWizModelAdmin
    elif name == 'ReadOnlyModelAdmin':
        from .base_admin import ReadOnlyModelAdmin
        return ReadOnlyModelAdmin
    elif name == 'ImportExportModelAdminMixin':
        from .base_admin import ImportExportModelAdminMixin
        return ImportExportModelAdminMixin
    elif name == 'BulkActionsMixin':
        from .bulk_actions import BulkActionsMixin
        return BulkActionsMixin
    elif name == 'TenantAwareBulkActions':
        from .bulk_actions import TenantAwareBulkActions
        return TenantAwareBulkActions
    elif name == 'ApprovalWorkflowActions':
        from .bulk_actions import ApprovalWorkflowActions
        return ApprovalWorkflowActions
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Note: Specific admin classes (APIDeprecationAdmin, UserScopeAdmin, etc.)
# are registered directly in their respective files using @admin.register()
# No need to export them from __init__.py
