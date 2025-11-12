"""
Admin Panel Registrations for New Enhancement Models
=====================================================
User-friendly admin interfaces for the new models.

Follows .claude/rules.md:
- Rule #7: Admin registration with clear naming
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Runbook,
    RunbookExecution,
    ApprovalRequest,
    ApprovalAction,
    OperationsQueueItem,
    SLAPrediction,
)


@admin.register(Runbook)
class RunbookAdmin(admin.ModelAdmin):
    """Admin interface for Quick Action Templates."""

    list_display = [
        "name",
        "is_active",
        "usage_count",
        "last_used_at",
        "cdtz",
    ]
    list_filter = ["is_active", "cdtz"]
    search_fields = ["name", "description"]
    readonly_fields = ["usage_count", "last_used_at", "cdtz", "mdtz"]
    filter_horizontal = []

    fieldsets = (
        (_("Basic Information"), {
            "fields": ("name", "description", "is_active")
        }),
        (_("Triggers"), {
            "fields": ("trigger_types",)
        }),
        (_("Actions"), {
            "fields": ("automated_steps", "manual_steps")
        }),
        (_("Usage Statistics"), {
            "fields": ("usage_count", "last_used_at"),
            "classes": ("collapse",)
        }),
        (_("System Information"), {
            "fields": ("cdtz", "mdtz", "cuser", "tenant"),
            "classes": ("collapse",)
        }),
    )


@admin.register(RunbookExecution)
class RunbookExecutionAdmin(admin.ModelAdmin):
    """Admin interface for Quick Action Executions."""

    list_display = [
        "runbook",
        "target_type_and_id",
        "executed_by",
        "completed_at",
        "cdtz",
    ]
    list_filter = ["completed_at", "cdtz", "target_model"]
    search_fields = ["runbook__name", "executed_by__username"]
    readonly_fields = ["cdtz", "mdtz"]

    def target_type_and_id(self, obj):
        return f"{obj.target_model}#{obj.target_id}"
    target_type_and_id.short_description = "Target"


# ApprovalRequest admin is in apps/core/admin/approval_admin.py
# (Enhanced version with quick approve/deny actions)


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    """Admin interface for Approval Actions."""

    list_display = [
        "request",
        "approver",
        "decision",
        "decided_at",
    ]
    list_filter = ["decision", "decided_at"]
    search_fields = ["request__action_description", "approver__username", "comment"]
    readonly_fields = ["decided_at", "cdtz", "mdtz"]


@admin.register(OperationsQueueItem)
class OperationsQueueItemAdmin(admin.ModelAdmin):
    """
    Admin interface for Operations Queue (read-only view).
    
    ⚠️ This is a database view - no add/edit/delete operations allowed.
    """

    list_display = [
        "item_type",
        "title_short",
        "priority_badge",
        "breach_risk_badge",
        "assignee",
        "sla_due_at",
    ]
    list_filter = ["item_type", "breach_risk", "status"]
    search_fields = ["title", "description"]
    readonly_fields = [
        "item_type", "item_id", "title", "description",
        "priority_score", "breach_risk", "sla_due_at",
        "assignee", "status", "tenant", "created_at", "updated_at"
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def title_short(self, obj):
        return obj.title[:50] + ("..." if len(obj.title) > 50 else "")
    title_short.short_description = "Title"

    def priority_badge(self, obj):
        color = "red" if obj.priority_score >= 80 else "orange" if obj.priority_score >= 50 else "green"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.priority_score
        )
    priority_badge.short_description = "Priority"

    def breach_risk_badge(self, obj):
        colors = {
            "LOW": "green",
            "MEDIUM": "orange",
            "HIGH": "red",
            "CRITICAL": "darkred",
        }
        color = colors.get(obj.breach_risk, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_breach_risk_display()
        )
    breach_risk_badge.short_description = "SLA Risk"


@admin.register(SLAPrediction)
class SLAPredictionAdmin(admin.ModelAdmin):
    """Admin interface for Priority Alerts (SLA Predictions)."""

    list_display = [
        "item_type_and_id",
        "risk_badge",
        "confidence_level",
        "predicted_breach_time",
        "acknowledged_badge",
        "calculated_at",
    ]
    list_filter = ["risk_level", "is_acknowledged", "calculated_at"]
    search_fields = ["item_type", "item_id"]
    readonly_fields = ["calculated_at", "cdtz", "mdtz"]

    fieldsets = (
        (_("Item Information"), {
            "fields": ("item_type", "item_id")
        }),
        (_("Prediction"), {
            "fields": (
                "predicted_breach_time",
                "confidence_level",
                "risk_level",
            )
        }),
        (_("Analysis"), {
            "fields": ("risk_factors", "suggested_actions", "suggested_assignee")
        }),
        (_("Acknowledgment"), {
            "fields": ("is_acknowledged", "acknowledged_by", "acknowledged_at")
        }),
        (_("System Information"), {
            "fields": ("calculated_at", "cdtz", "mdtz"),
            "classes": ("collapse",)
        }),
    )

    def item_type_and_id(self, obj):
        return f"{obj.item_type}#{obj.item_id}"
    item_type_and_id.short_description = "Item"

    def risk_badge(self, obj):
        colors = {
            "LOW": "green",
            "MEDIUM": "orange",
            "HIGH": "red",
            "CRITICAL": "darkred",
        }
        color = colors.get(obj.risk_level, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_risk_level_display()
        )
    risk_badge.short_description = "Risk"

    def acknowledged_badge(self, obj):
        if obj.is_acknowledged:
            return format_html(
                '<span style="color: green;">✓ Acknowledged</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Not Acknowledged</span>'
        )
    acknowledged_badge.short_description = "Status"
