"""
Approval Required Decorator
============================
Decorator for admin actions requiring approval.

Follows .claude/rules.md:
- Rule #5: Specific exception handling
- Rule #25: Security first
"""

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.auth.models import Group
from django.shortcuts import render

from apps.core.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)


def requires_approval(
    approval_group_name: str,
    callback_task_name: str,
    approvers_count: int = 1,
    expires_hours: int = 24
):
    """
    Decorator to require approval for admin actions.
    
    Args:
        approval_group_name: Name of group that can approve
        callback_task_name: Celery task to execute after approval
        approvers_count: Number of approvals needed
        expires_hours: Hours until request expires
        
    Usage:
        @requires_approval('SecurityLeads', 'apps.monitoring.tasks.disable_cameras_task')
        @admin.action(description='Disable selected cameras')
        def disable_cameras(modeladmin, request, queryset):
            queryset.update(is_active=False)
    """
    def decorator(action_func):
        @wraps(action_func)
        def wrapper(modeladmin, request, queryset):
            # Check if user can bypass approval
            if request.user.has_perm('core.bypass_approval'):
                logger.info(
                    f"User {request.user.username} bypassed approval for {action_func.__name__}"
                )
                return action_func(modeladmin, request, queryset)
            
            # Check if this is the confirmation step
            if request.POST.get('confirm_approval_request'):
                try:
                    # Get approver group
                    try:
                        approver_group = Group.objects.get(name=approval_group_name)
                    except Group.DoesNotExist:
                        modeladmin.message_user(
                            request,
                            f"❌ Approver group '{approval_group_name}' not found. "
                            "Please contact your administrator.",
                            messages.ERROR
                        )
                        return
                    
                    # Get reason from form
                    reason = request.POST.get('approval_reason', 'Not provided')
                    
                    # Create approval request
                    approval = ApprovalService.create_approval_request(
                        user=request.user,
                        action_type=getattr(action_func, 'short_description', action_func.__name__),
                        reason=reason,
                        target_model=f"{queryset.model._meta.app_label}.{queryset.model.__name__}",
                        target_ids=list(queryset.values_list('id', flat=True)),
                        callback_task=callback_task_name,
                        approver_group=approver_group,
                        expires_hours=expires_hours
                    )
                    
                    modeladmin.message_user(
                        request,
                        f"✅ Approval request #{approval.id} created. "
                        f"You'll be notified when it's approved by {approval_group_name}.",
                        messages.SUCCESS
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to create approval request: {e}", exc_info=True)
                    modeladmin.message_user(
                        request,
                        f"❌ Failed to create approval request: {str(e)}",
                        messages.ERROR
                    )
                
                return
            
            # Show confirmation form
            context = {
                'title': f'Request Approval: {getattr(action_func, "short_description", action_func.__name__)}',
                'action_description': getattr(action_func, 'short_description', action_func.__name__),
                'queryset': queryset,
                'queryset_count': queryset.count(),
                'approval_group_name': approval_group_name,
                'approvers_count': approvers_count,
                'expires_hours': expires_hours,
                'opts': modeladmin.model._meta,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            }
            
            return render(
                request,
                'admin/approval_request_form.html',
                context
            )
        
        return wrapper
    return decorator


__all__ = ['requires_approval']
