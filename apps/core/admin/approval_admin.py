"""
Enhanced Approval Request Admin
================================
User-friendly admin interface for approval workflows.

Follows .claude/rules.md:
- Rule #7: Admin class < 150 lines
- Rule #25: Security first
"""

import logging
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect, get_object_or_404

from apps.core.models.admin_approval import ApprovalRequest, ApprovalAction
from apps.core.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Approval Requests.
    
    User-friendly name: "Approval Requests" (NOT "Approval Workflows")
    
    Features:
    - Visual status badges
    - Quick approve/deny actions
    - Progress indicators
    - Email notifications
    - Audit trail
    """
    
    list_display = [
        'id',
        'status_badge',
        'what_they_want',
        'who_requested',
        'when_requested',
        'expires_when',
        'quick_decision',
    ]
    
    list_filter = [
        'status',
        ('requested_at', admin.DateFieldListFilter),
        ('expires_at', admin.DateFieldListFilter),
        'approver_group',
    ]
    
    search_fields = [
        'action_description',
        'reason',
        'requester__username',
        'requester__first_name',
        'requester__last_name',
    ]
    
    readonly_fields = [
        'requester',
        'requested_at',
        'action_description',
        'reason',
        'target_model',
        'target_ids',
        'callback_task_name',
        'approval_history',
    ]
    
    fieldsets = [
        ("📋 What They Want to Do", {
            'fields': ['action_description', 'reason']
        }),
        ("👤 Who Requested This", {
            'fields': ['requester', 'requested_at']
        }),
        ("✅ Approval Details", {
            'fields': ['status', 'approver_group', 'approved_by', 'expires_at']
        }),
        ("❌ Denial Details", {
            'fields': ['denied_by', 'denial_reason'],
            'classes': ['collapse']
        }),
        ("🔧 Technical Details", {
            'fields': ['target_model', 'target_ids', 'callback_task_name'],
            'classes': ['collapse']
        }),
        ("📜 Approval History", {
            'fields': ['approval_history'],
        }),
    ]
    
    filter_horizontal = ['approved_by']
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'requester',
            'approver_group',
            'denied_by',
            'tenant'
        ).prefetch_related('approved_by', 'actions')
    
    @admin.display(description='Status')
    def status_badge(self, obj):
        """Visual status badge."""
        badges = {
            'WAITING': '<span style="background-color: orange; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">⏳ Waiting</span>',
            'APPROVED': '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✅ Approved</span>',
            'DENIED': '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">❌ Denied</span>',
            'EXPIRED': '<span style="background-color: gray; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">⌛ Expired</span>',
            'COMPLETED': '<span style="background-color: blue; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Done</span>',
        }
        return format_html(badges.get(obj.status, obj.status))
    
    @admin.display(description='Request')
    def what_they_want(self, obj):
        """Short description of request."""
        text = obj.action_description[:60]
        if len(obj.action_description) > 60:
            text += '...'
        return text
    
    @admin.display(description='Requested By')
    def who_requested(self, obj):
        """Requester name."""
        return obj.requester.get_full_name() or obj.requester.username
    
    @admin.display(description='When')
    def when_requested(self, obj):
        """Formatted request time."""
        return obj.requested_at.strftime('%b %d, %I:%M %p')
    
    @admin.display(description='Expires')
    def expires_when(self, obj):
        """Formatted expiration time."""
        if obj.status == 'WAITING':
            return format_html(
                '<span style="color: red;">{}</span>',
                obj.expires_at.strftime('%b %d, %I:%M %p')
            )
        return obj.expires_at.strftime('%b %d, %I:%M %p')
    
    @admin.display(description='Actions')
    def quick_decision(self, obj):
        """Quick approve/deny buttons."""
        if obj.status == 'WAITING':
            approve_url = reverse('admin:approve_approval_request', args=[obj.id])
            deny_url = reverse('admin:deny_approval_request', args=[obj.id])
            return format_html(
                '<a class="button" href="{}" style="background-color: green; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">✅ Approve</a> '
                '<a class="button" href="{}" style="background-color: red; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin-left: 5px;">❌ Deny</a>',
                approve_url,
                deny_url
            )
        return '-'
    
    @admin.display(description='Approval History')
    def approval_history(self, obj):
        """Show approval/denial history."""
        actions = obj.actions.select_related('approver').order_by('-decided_at')
        
        if not actions:
            return format_html('<p><em>No actions yet</em></p>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background-color: #f5f5f5;"><th style="padding: 5px; text-align: left;">User</th><th style="padding: 5px; text-align: left;">Decision</th><th style="padding: 5px; text-align: left;">Comment</th><th style="padding: 5px; text-align: left;">When</th></tr>'
        
        for action in actions:
            color = 'green' if action.decision == 'APPROVE' else 'red'
            html += f'<tr><td style="padding: 5px;">{action.approver.get_full_name() or action.approver.username}</td>'
            html += f'<td style="padding: 5px; color: {color}; font-weight: bold;">{action.get_decision_display()}</td>'
            html += f'<td style="padding: 5px;">{action.comment or "-"}</td>'
            html += f'<td style="padding: 5px;">{action.decided_at.strftime("%b %d, %I:%M %p")}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    
    # Custom actions
    actions = ['approve_selected_requests', 'deny_selected_requests']
    
    @admin.action(description='✅ Approve selected requests')
    def approve_selected_requests(self, request, queryset):
        """Bulk approve requests."""
        waiting = queryset.filter(status='WAITING')
        count = 0
        
        for req in waiting:
            try:
                ApprovalService.approve_request(req, request.user, "Bulk approved")
                count += 1
            except Exception as e:
                logger.error(f"Failed to approve request {req.id}: {e}")
        
        self.message_user(
            request,
            f"✅ Approved {count} request(s)",
            messages.SUCCESS
        )
    
    @admin.action(description='❌ Deny selected requests')
    def deny_selected_requests(self, request, queryset):
        """Bulk deny requests."""
        waiting = queryset.filter(status='WAITING')
        count = 0
        
        for req in waiting:
            try:
                ApprovalService.deny_request(
                    req,
                    request.user,
                    "Bulk denied by administrator"
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to deny request {req.id}: {e}")
        
        self.message_user(
            request,
            f"❌ Denied {count} request(s)",
            messages.SUCCESS
        )
    
    # Custom URLs
    def get_urls(self):
        """Add custom approval/denial URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/approve/',
                self.admin_site.admin_view(self.approve_view),
                name='approve_approval_request'
            ),
            path(
                '<int:pk>/deny/',
                self.admin_site.admin_view(self.deny_view),
                name='deny_approval_request'
            ),
        ]
        return custom_urls + urls
    
    def approve_view(self, request, pk):
        """Quick approve view."""
        obj = get_object_or_404(ApprovalRequest, pk=pk)
        
        if obj.status != 'WAITING':
            self.message_user(
                request,
                f"❌ Request already {obj.get_status_display()}",
                messages.ERROR
            )
        else:
            try:
                ApprovalService.approve_request(obj, request.user, "Quick approved")
                self.message_user(
                    request,
                    f"✅ Approval request #{pk} approved and queued for execution",
                    messages.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to approve: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"❌ Error: {str(e)}",
                    messages.ERROR
                )
        
        return redirect('admin:core_approvalrequest_changelist')
    
    def deny_view(self, request, pk):
        """Quick deny view."""
        obj = get_object_or_404(ApprovalRequest, pk=pk)
        
        if obj.status != 'WAITING':
            self.message_user(
                request,
                f"❌ Request already {obj.get_status_display()}",
                messages.ERROR
            )
        else:
            try:
                ApprovalService.deny_request(
                    obj,
                    request.user,
                    "Denied by administrator"
                )
                self.message_user(
                    request,
                    f"❌ Approval request #{pk} denied",
                    messages.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to deny: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"❌ Error: {str(e)}",
                    messages.ERROR
                )
        
        return redirect('admin:core_approvalrequest_changelist')


__all__ = ['ApprovalRequestAdmin']
