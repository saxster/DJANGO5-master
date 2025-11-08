# Approval System Guide

## Overview

The Approval System provides a secure workflow for high-risk admin actions that require authorization before execution.

**User-Friendly Name:** "Approval Requests" (NOT "Approval Workflows")

## Features

- ✅ **Automatic Interception** - Middleware catches risky actions
- 📧 **Email Notifications** - Auto-notify approvers and requesters
- ⏰ **Auto-Expiration** - Requests expire after 24 hours (configurable)
- 📊 **Audit Trail** - Complete history of all approvals/denials
- 🔒 **Permission-Based** - Bypass for users with `core.bypass_approval`
- 🎯 **Async Execution** - Actions execute via Celery after approval

## Quick Start

### 1. Add Decorator to Admin Action

```python
from django.contrib import admin
from apps.core.decorators.approval_required import requires_approval

@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    actions = ['disable_selected_cameras']
    
    @requires_approval(
        approval_group_name='SecurityLeads',
        callback_task_name='apps.monitoring.tasks.disable_cameras_task',
        approvers_count=1,
        expires_hours=24
    )
    @admin.action(description='Disable selected cameras')
    def disable_selected_cameras(self, request, queryset):
        """This will be executed AFTER approval."""
        queryset.update(is_active=False)
```

### 2. Create Celery Callback Task

```python
# apps/monitoring/tasks.py
from celery import shared_task
from apps.monitoring.models import Camera

@shared_task(name='apps.monitoring.tasks.disable_cameras_task')
def disable_cameras_task(camera_ids):
    """Execute after approval."""
    Camera.objects.filter(id__in=camera_ids).update(is_active=False)
```

### 3. Create Approver Group

```python
from django.contrib.auth.models import Group

# In Django shell or migration
security_leads = Group.objects.create(name='SecurityLeads')
security_leads.people.add(admin_user1, admin_user2)
```

## User Workflow

### Requesting Approval

1. User selects items in admin
2. User clicks risky action (e.g., "Disable selected cameras")
3. System shows approval request form
4. User enters business justification
5. System creates approval request
6. Approvers receive email notification

### Approving/Denying

**Option 1: Quick Actions**
1. Approver receives email
2. Clicks link to admin
3. Clicks "✅ Approve" or "❌ Deny" button
4. Action executes immediately (if approved)

**Option 2: Admin Interface**
1. Go to Admin → Core → Approval Requests
2. Filter by "Status: Waiting"
3. Click request to review
4. Click "✅ Approve" or "❌ Deny"

### Dashboard Widget

Add to admin dashboard:

```python
# apps/core/context_processors.py
def pending_approvals(request):
    if request.user.is_staff:
        pending = ApprovalRequest.objects.filter(
            status='WAITING',
            approver_group__people=request.user
        ).select_related('requester')[:5]
        
        return {'pending_approvals': pending}
    return {}

# templates/admin/index.html
{% include "admin/includes/pending_approvals.html" %}
```

## Configuration

### Enable Middleware

```python
# intelliwiz_config/settings/base.py
MIDDLEWARE = [
    # ... other middleware ...
    'apps.core.middleware.approval_middleware.ApprovalRequiredMiddleware',
]
```

### Configure Risky Actions

Edit `RISKY_ACTIONS` in `approval_middleware.py`:

```python
RISKY_ACTIONS = {
    'delete_selected': 'Delete multiple items',
    'disable_cameras': 'Disable security cameras',
    'your_action': 'Your description',
}
```

### Add Celery Beat Schedule

For auto-expiration:

```python
# intelliwiz_config/settings/celery.py
CELERY_BEAT_SCHEDULE = {
    'expire-old-approvals': {
        'task': 'apps.core.tasks.expire_old_approval_requests',
        'schedule': crontab(minute='0'),  # Every hour
    },
}
```

## Permissions

### Bypass Approval

```python
# Give permission to skip approval (careful!)
from django.contrib.auth.models import Permission

bypass_perm = Permission.objects.get(
    codename='bypass_approval',
    content_type__app_label='core'
)
user.user_permissions.add(bypass_perm)
```

### Approver Groups

Create groups for different approval types:

```python
# SecurityLeads - approve security-related actions
# DataAdmins - approve data retention changes
# ITManagers - approve system configuration changes
```

## Email Notifications

### Approval Needed (to approvers)

```
Subject: ⏳ Approval Needed: Disable selected cameras

Hi John,

Jane Smith is requesting approval to:
Disable selected cameras

Reason: Cameras are being relocated for building renovation

Please review at: https://yoursite.com/admin/core/approvalrequest/123/

Expires in 24 hours.
```

### Approved (to requester)

```
Subject: ✅ Your request was approved

Hi Jane,

Good news! Your request to 'Disable selected cameras' has been approved.

Approved by: John Doe
```

### Denied (to requester)

```
Subject: ❌ Your request was denied

Hi Jane,

Your request to 'Disable selected cameras' was not approved.

Reason: Need more details on which cameras and why
Denied by: John Doe
```

## API Reference

### ApprovalService

```python
from apps.core.services.approval_service import ApprovalService

# Create approval request
approval = ApprovalService.create_approval_request(
    user=request.user,
    action_type='Delete old tickets',
    reason='Cleanup as per retention policy',
    target_model='tickets.Ticket',
    target_ids=[1, 2, 3],
    callback_task='apps.tickets.tasks.delete_tickets_task',
    approver_group=security_group,
    expires_hours=48
)

# Approve
ApprovalService.approve_request(
    approval_request=approval,
    approver=admin_user,
    comment='Approved - policy compliant'
)

# Deny
ApprovalService.deny_request(
    approval_request=approval,
    denier=admin_user,
    reason='Need legal review first'
)
```

### Decorator

```python
@requires_approval(
    approval_group_name='GroupName',
    callback_task_name='app.tasks.task_name',
    approvers_count=1,  # Number of approvals needed
    expires_hours=24    # Hours until expiration
)
def your_admin_action(modeladmin, request, queryset):
    # Your action code
    pass
```

## Troubleshooting

### Request not created

**Check:**
- User has permission to create requests
- Approver group exists
- Middleware is enabled

### Action not executing after approval

**Check:**
- Celery worker is running
- Callback task name is correct
- Task is registered in Celery

### Emails not sending

**Check:**
- `EMAIL_HOST` configured in settings
- `DEFAULT_FROM_EMAIL` set
- Approver has valid email address

### Request expired before approval

**Solution:**
- Increase `expires_hours` for complex approvals
- Set up email alerts for expiring requests

## Security Best Practices

1. ✅ **Always validate permissions** - Don't bypass security checks
2. ✅ **Audit all approvals** - Review logs regularly
3. ✅ **Use specific approver groups** - Not all admins
4. ✅ **Set reasonable expiration** - Not too long
5. ✅ **Require business justification** - Enforce reason field
6. ❌ **Never bypass for destructive actions** - Even for superusers

## Example: Complete Implementation

```python
# apps/monitoring/admin.py
from django.contrib import admin
from apps.core.decorators.approval_required import requires_approval
from apps.monitoring.models import Camera

@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active']
    actions = ['disable_selected_cameras', 'enable_selected_cameras']
    
    @requires_approval(
        approval_group_name='SecurityLeads',
        callback_task_name='apps.monitoring.tasks.disable_cameras_task',
        approvers_count=1,
        expires_hours=24
    )
    @admin.action(description='🔴 Disable selected cameras')
    def disable_selected_cameras(self, request, queryset):
        pass  # Will execute after approval
    
    @admin.action(description='🟢 Enable selected cameras')
    def enable_selected_cameras(self, request, queryset):
        # No approval needed - just enable
        queryset.update(is_active=True)
        self.message_user(request, f"Enabled {queryset.count()} cameras")

# apps/monitoring/tasks.py
from celery import shared_task
from apps.monitoring.models import Camera

@shared_task(name='apps.monitoring.tasks.disable_cameras_task')
def disable_cameras_task(camera_ids):
    """Disable cameras after approval."""
    Camera.objects.filter(id__in=camera_ids).update(is_active=False)
    return len(camera_ids)

# Create approver group (in shell or migration)
from django.contrib.auth.models import Group
from apps.peoples.models import People

security_leads = Group.objects.create(name='SecurityLeads')
lead1 = People.objects.get(username='security_lead1')
security_leads.people.add(lead1)
```

## Testing

```python
# Test approval workflow
from apps.core.services.approval_service import ApprovalService
from apps.core.models.admin_approval import ApprovalRequest

# 1. Create approval request
approval = ApprovalService.create_approval_request(
    user=user,
    action_type='Test action',
    reason='Testing approval system',
    target_model='monitoring.Camera',
    target_ids=[1, 2, 3],
    callback_task='apps.monitoring.tasks.disable_cameras_task',
    approver_group=group
)

# 2. Verify status
assert approval.status == 'WAITING'

# 3. Approve
ApprovalService.approve_request(approval, approver, 'Test approval')

# 4. Verify execution
assert approval.status == 'APPROVED'
```

## Related Documentation

- [CELERY_CONFIGURATION_GUIDE.md](CELERY_CONFIGURATION_GUIDE.md)
- [COMMON_COMMANDS.md](COMMON_COMMANDS.md)
- [Security Best Practices](../architecture/SYSTEM_ARCHITECTURE.md#security)
