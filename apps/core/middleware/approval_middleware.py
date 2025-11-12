"""
Approval Required Middleware
=============================
Intercepts risky admin actions and requires approval.

Follows .claude/rules.md:
- Rule #5: Specific exception handling
- Rule #21: Network timeouts (if applicable)
- Rule #25: Security first
"""

import logging
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


class ApprovalRequiredMiddleware:
    """
    Intercept risky admin actions and require approval.
    
    Features:
    - Detects high-risk admin actions
    - Creates approval requests automatically
    - Allows bypass for users with permission
    - User-friendly error messages
    """
    
    RISKY_ACTIONS = {
        'delete_selected': 'Delete multiple items',
        'disable_cameras': 'Disable security cameras',
        'deactivate_ml_model': 'Turn off AI model',
        'bulk_delete_users': 'Delete user accounts',
        'change_retention_policy': 'Modify data retention',
        'disable_security_alerts': 'Disable security alerts',
        'bulk_archive': 'Archive multiple items',
        'reset_passwords': 'Reset user passwords',
        'disable_notifications': 'Disable system notifications',
        'purge_old_data': 'Permanently delete old data',
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only process admin POST requests with actions
        if (request.path.startswith('/admin/') and 
            request.method == 'POST' and 
            'action' in request.POST):
            
            action = request.POST.get('action')
            
            # Check if this is a risky action
            if action in self.RISKY_ACTIONS:
                # Check bypass permission
                if not request.user.has_perm('core.bypass_approval'):
                    # Store action data in session
                    request.session['pending_action'] = {
                        'action': action,
                        'action_name': self.RISKY_ACTIONS[action],
                        'path': request.path,
                        'post_data': dict(request.POST),
                    }
                    
                    # Redirect to approval request page
                    messages.warning(
                        request,
                        f"⏳ The action '{self.RISKY_ACTIONS[action]}' requires approval. "
                        "Please fill out an approval request."
                    )
                    return redirect('admin:create_approval_request')
        
        return self.get_response(request)


__all__ = ['ApprovalRequiredMiddleware']
