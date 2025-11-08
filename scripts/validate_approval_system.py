#!/usr/bin/env python
"""
Approval System Validation Script
==================================
Validates that the approval system is correctly configured.

Usage:
    python scripts/validate_approval_system.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETDEFAULTENCODING', 'utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

django.setup()

from django.conf import settings
from django.contrib.auth.models import Group
from apps.core.models.admin_approval import ApprovalRequest, ApprovalAction


def validate_models():
    """Validate models exist and have correct fields."""
    print("✅ Validating models...")
    
    # Check ApprovalRequest
    assert hasattr(ApprovalRequest, 'requester'), "Missing requester field"
    assert hasattr(ApprovalRequest, 'status'), "Missing status field"
    assert hasattr(ApprovalRequest, 'approver_group'), "Missing approver_group field"
    assert hasattr(ApprovalRequest, 'callback_task_name'), "Missing callback_task_name field"
    
    # Check ApprovalAction
    assert hasattr(ApprovalAction, 'request'), "Missing request field"
    assert hasattr(ApprovalAction, 'approver'), "Missing approver field"
    assert hasattr(ApprovalAction, 'decision'), "Missing decision field"
    
    print("   ✓ Models are correctly configured")


def validate_service():
    """Validate service exists."""
    print("✅ Validating service...")
    
    try:
        from apps.core.services.approval_service import ApprovalService
        
        assert hasattr(ApprovalService, 'create_approval_request'), "Missing create_approval_request method"
        assert hasattr(ApprovalService, 'approve_request'), "Missing approve_request method"
        assert hasattr(ApprovalService, 'deny_request'), "Missing deny_request method"
        
        print("   ✓ Service is correctly configured")
    except ImportError as e:
        print(f"   ✗ Service import failed: {e}")
        sys.exit(1)


def validate_decorator():
    """Validate decorator exists."""
    print("✅ Validating decorator...")
    
    try:
        from apps.core.decorators.approval_required import requires_approval
        
        print("   ✓ Decorator is correctly configured")
    except ImportError as e:
        print(f"   ✗ Decorator import failed: {e}")
        sys.exit(1)


def validate_middleware():
    """Validate middleware exists."""
    print("✅ Validating middleware...")
    
    try:
        from apps.core.middleware.approval_middleware import ApprovalRequiredMiddleware
        
        # Check if enabled in settings
        middleware = getattr(settings, 'MIDDLEWARE', [])
        if 'apps.core.middleware.approval_middleware.ApprovalRequiredMiddleware' in middleware:
            print("   ✓ Middleware is enabled in settings")
        else:
            print("   ⚠ Middleware exists but not enabled in settings")
            print("     Add to MIDDLEWARE: 'apps.core.middleware.approval_middleware.ApprovalRequiredMiddleware'")
        
    except ImportError as e:
        print(f"   ✗ Middleware import failed: {e}")
        sys.exit(1)


def validate_tasks():
    """Validate Celery tasks exist."""
    print("✅ Validating Celery tasks...")
    
    try:
        from apps.core.tasks.approval_tasks import (
            execute_approved_action_task,
            expire_old_approval_requests_task
        )
        
        print("   ✓ Celery tasks are correctly configured")
    except ImportError as e:
        print(f"   ✗ Task import failed: {e}")
        sys.exit(1)


def validate_admin():
    """Validate admin is registered."""
    print("✅ Validating admin interface...")
    
    try:
        from django.contrib import admin
        from apps.core.admin.approval_admin import ApprovalRequestAdmin
        
        # Check if registered
        if ApprovalRequest in admin.site._registry:
            print("   ✓ Admin interface is registered")
        else:
            print("   ✗ Admin interface not registered")
            print("     Make sure apps.core.admin.approval_admin is imported")
            sys.exit(1)
        
    except ImportError as e:
        print(f"   ✗ Admin import failed: {e}")
        sys.exit(1)


def validate_templates():
    """Validate templates exist."""
    print("✅ Validating templates...")
    
    import os
    from pathlib import Path
    
    base_dir = Path(__file__).resolve().parent.parent
    templates_dir = base_dir / 'templates' / 'admin'
    
    required_templates = [
        'approval_request_form.html',
        'includes/pending_approvals.html',
    ]
    
    missing = []
    for template in required_templates:
        template_path = templates_dir / template
        if not template_path.exists():
            missing.append(str(template_path))
    
    if missing:
        print(f"   ✗ Missing templates: {', '.join(missing)}")
        sys.exit(1)
    else:
        print("   ✓ All templates exist")


def validate_email_config():
    """Validate email configuration."""
    print("✅ Validating email configuration...")
    
    if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
        print(f"   ✓ EMAIL_HOST configured: {settings.EMAIL_HOST}")
    else:
        print("   ⚠ EMAIL_HOST not configured - emails will fail")
        print("     Set EMAIL_HOST in settings")
    
    if hasattr(settings, 'DEFAULT_FROM_EMAIL'):
        print(f"   ✓ DEFAULT_FROM_EMAIL configured: {settings.DEFAULT_FROM_EMAIL}")
    else:
        print("   ⚠ DEFAULT_FROM_EMAIL not configured")


def check_sample_group():
    """Check if sample approver group exists."""
    print("✅ Checking for sample approver groups...")
    
    groups = Group.objects.filter(
        name__in=['SecurityLeads', 'DataAdmins', 'ITManagers']
    ).values_list('name', flat=True)
    
    if groups:
        print(f"   ✓ Found groups: {', '.join(groups)}")
    else:
        print("   ⚠ No sample approver groups found")
        print("     Create groups: SecurityLeads, DataAdmins, ITManagers")


def validate_database():
    """Validate database tables exist."""
    print("✅ Validating database tables...")
    
    try:
        # Try to query models
        ApprovalRequest.objects.count()
        ApprovalAction.objects.count()
        
        print("   ✓ Database tables exist")
    except Exception as e:
        print(f"   ✗ Database error: {e}")
        print("     Run: python manage.py migrate")
        sys.exit(1)


def main():
    """Run all validations."""
    print("\n" + "="*60)
    print("APPROVAL SYSTEM VALIDATION")
    print("="*60 + "\n")
    
    validate_models()
    validate_service()
    validate_decorator()
    validate_middleware()
    validate_tasks()
    validate_admin()
    validate_templates()
    validate_email_config()
    validate_database()
    check_sample_group()
    
    print("\n" + "="*60)
    print("✅ VALIDATION COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Enable middleware in settings (if not already)")
    print("2. Create approver groups (SecurityLeads, etc.)")
    print("3. Configure EMAIL_HOST for notifications")
    print("4. Add @requires_approval decorator to admin actions")
    print("5. Test with sample action")
    print("\nSee: docs/workflows/APPROVAL_SYSTEM_GUIDE.md")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
