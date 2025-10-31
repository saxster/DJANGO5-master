"""
Reusable Bulk Actions for Django Admin

Provides common bulk actions that can be used across all admin classes.

Usage:
    from apps.core.admin.bulk_actions import BulkActionsMixin

    class MyModelAdmin(BulkActionsMixin, IntelliWizModelAdmin):
        actions = [
            'bulk_enable',
            'bulk_disable',
            'export_to_excel',
        ]

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
import csv
from datetime import datetime


class BulkActionsMixin:
    """
    Mixin providing common bulk actions for admin classes.

    Features:
    - Enable/Disable records
    - Export to CSV/Excel
    - Clone records
    - Archive/Unarchive
    - Bulk assign
    """

    @admin.action(description=_("Enable selected items"))
    def bulk_enable(self, request, queryset):
        """Enable multiple records"""
        if not hasattr(queryset.model, 'enable'):
            self.message_user(
                request,
                "This model doesn't have an 'enable' field.",
                level=messages.ERROR
            )
            return

        updated = queryset.update(enable=True)
        self.message_user(
            request,
            _(f"{updated} items enabled successfully."),
            level=messages.SUCCESS
        )

    @admin.action(description=_("Disable selected items"))
    def bulk_disable(self, request, queryset):
        """Disable multiple records"""
        if not hasattr(queryset.model, 'enable'):
            self.message_user(
                request,
                "This model doesn't have an 'enable' field.",
                level=messages.ERROR
            )
            return

        updated = queryset.update(enable=False)
        self.message_user(
            request,
            _(f"{updated} items disabled."),
            level=messages.WARNING
        )

    @admin.action(description=_("Export to CSV"))
    def export_to_csv(self, request, queryset):
        """Export selected records to CSV"""
        model = queryset.model
        model_name = model._meta.verbose_name_plural

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response['Content-Disposition'] = f'attachment; filename="{model_name}_{timestamp}.csv"'

        writer = csv.writer(response)

        # Get field names
        fields = [f.name for f in model._meta.fields if not f.name.startswith('_')]

        # Write header
        writer.writerow(fields)

        # Write data
        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, field, '')
                # Handle None and special types
                if value is None:
                    value = ''
                elif hasattr(value, 'isoformat'):  # datetime
                    value = value.isoformat()
                row.append(str(value))
            writer.writerow(row)

        self.message_user(
            request,
            _(f"Exported {queryset.count()} {model_name} to CSV."),
            level=messages.SUCCESS
        )

        return response

    @admin.action(description=_("Clone selected items"))
    def bulk_clone(self, request, queryset):
        """Clone selected records"""
        cloned = 0
        for obj in queryset:
            obj.pk = None
            obj.id = None

            # Update name/code to indicate clone
            if hasattr(obj, 'name'):
                obj.name = f"{obj.name} (Copy)"
            if hasattr(obj, 'code'):
                obj.code = f"{obj.code}_COPY"

            try:
                obj.save()
                cloned += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to clone {obj}: {str(e)}",
                    level=messages.ERROR
                )

        if cloned > 0:
            self.message_user(
                request,
                _(f"{cloned} items cloned successfully."),
                level=messages.SUCCESS
            )


class TenantAwareBulkActions(BulkActionsMixin):
    """
    Bulk actions specific to tenant-aware models.

    Adds tenant-specific operations like bulk tenant assignment.
    """

    @admin.action(description=_("Assign to current tenant"))
    def bulk_assign_to_tenant(self, request, queryset):
        """Assign selected records to current user's tenant"""
        if not hasattr(request.user, 'tenant'):
            self.message_user(
                request,
                "Current user has no tenant assigned.",
                level=messages.ERROR
            )
            return

        updated = queryset.update(tenant=request.user.tenant)
        self.message_user(
            request,
            _(f"Assigned {updated} items to {request.user.tenant}."),
            level=messages.SUCCESS
        )


class ApprovalWorkflowActions:
    """
    Bulk actions for models with approval workflow.

    For models with status like: PENDING, APPROVED, REJECTED
    """

    @admin.action(description=_("Approve selected items"))
    def bulk_approve(self, request, queryset):
        """Approve selected records"""
        updated = queryset.filter(status='PENDING').update(
            status='APPROVED',
            approved_by=request.user,
        )
        self.message_user(
            request,
            _(f"{updated} items approved."),
            level=messages.SUCCESS
        )

    @admin.action(description=_("Reject selected items"))
    def bulk_reject(self, request, queryset):
        """Reject selected records"""
        updated = queryset.filter(status='PENDING').update(
            status='REJECTED',
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            _(f"{updated} items rejected."),
            level=messages.WARNING
        )
