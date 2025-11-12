#!/usr/bin/env python
"""
Validate Saved Views + Exports Implementation
==============================================
Checks that all components are properly configured.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.conf import settings
from django.urls import reverse, NoReverseMatch


def validate_files():
    """Validate all required files exist"""
    print("🔍 Validating files...")
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    required_files = [
        'apps/core/views/saved_view_manager.py',
        'apps/core/services/view_export_service.py',
        'apps/core/tasks/export_tasks.py',
        'apps/core/urls/saved_views.py',
        'templates/admin/includes/save_view_button.html',
        'templates/admin/core/my_saved_views.html',
    ]
    
    all_exist = True
    for filepath in required_files:
        full_path = os.path.join(base_path, filepath)
        if os.path.exists(full_path):
            print(f"  ✅ {filepath}")
        else:
            print(f"  ❌ {filepath} - NOT FOUND")
            all_exist = False
    
    return all_exist


def validate_urls():
    """Validate URL patterns are registered"""
    print("\n🔍 Validating URLs...")
    
    url_names = [
        'saved_views:my_saved_views',
        'saved_views:api_save_view',
        'saved_views:api_load_view',
        'saved_views:api_export_view',
        'saved_views:api_delete_view',
    ]
    
    all_valid = True
    for url_name in url_names:
        try:
            url = reverse(url_name, kwargs={'view_id': 1} if 'view_id' in url_name else {})
            print(f"  ✅ {url_name} → {url}")
        except NoReverseMatch:
            print(f"  ❌ {url_name} - NOT REGISTERED")
            all_valid = False
    
    return all_valid


def validate_model():
    """Validate DashboardSavedView model"""
    print("\n🔍 Validating model...")
    
    try:
        from apps.core.models.dashboard_saved_view import DashboardSavedView
        
        # Check model fields
        required_fields = [
            'name', 'description', 'view_type', 'scope_config',
            'filters', 'visible_panels', 'sort_order', 'sharing_level',
            'is_default', 'view_count', 'last_accessed_at', 'page_url',
            'email_frequency', 'export_format', 'export_schedule'
        ]
        
        model_fields = [f.name for f in DashboardSavedView._meta.get_fields()]
        
        all_fields_exist = True
        for field in required_fields:
            if field in model_fields:
                print(f"  ✅ Field: {field}")
            else:
                print(f"  ❌ Field: {field} - MISSING")
                all_fields_exist = False
        
        # Check methods
        if hasattr(DashboardSavedView, 'can_user_access'):
            print(f"  ✅ Method: can_user_access")
        else:
            print(f"  ❌ Method: can_user_access - MISSING")
            all_fields_exist = False
        
        return all_fields_exist
        
    except ImportError as e:
        print(f"  ❌ Failed to import DashboardSavedView: {e}")
        return False


def validate_services():
    """Validate service classes"""
    print("\n🔍 Validating services...")
    
    try:
        from apps.core.services.view_export_service import ViewExportService
        
        # Check methods
        required_methods = [
            'get_view_data',
            'export_to_csv',
            'export_to_excel',
            'export_to_pdf',
            'schedule_export'
        ]
        
        all_methods_exist = True
        for method in required_methods:
            if hasattr(ViewExportService, method):
                print(f"  ✅ Method: ViewExportService.{method}")
            else:
                print(f"  ❌ Method: ViewExportService.{method} - MISSING")
                all_methods_exist = False
        
        return all_methods_exist
        
    except ImportError as e:
        print(f"  ❌ Failed to import ViewExportService: {e}")
        return False


def validate_tasks():
    """Validate Celery tasks"""
    print("\n🔍 Validating Celery tasks...")
    
    try:
        from apps.core.tasks.export_tasks import export_saved_view, cleanup_old_export_schedules
        
        print(f"  ✅ Task: export_saved_view")
        print(f"  ✅ Task: cleanup_old_export_schedules")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Failed to import export tasks: {e}")
        return False


def validate_dependencies():
    """Validate required Python packages"""
    print("\n🔍 Validating dependencies...")
    
    packages = {
        'openpyxl': 'Excel export',
        'reportlab': 'PDF export',
        'django_celery_beat': 'Scheduled exports'
    }
    
    all_installed = True
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"  ✅ {package} ({description})")
        except ImportError:
            print(f"  ⚠️  {package} ({description}) - NOT INSTALLED")
            print(f"      Install with: pip install {package}")
            all_installed = False
    
    return all_installed


def validate_settings():
    """Validate required settings"""
    print("\n🔍 Validating settings...")
    
    required_settings = [
        'DEFAULT_FROM_EMAIL',
        'CELERY_BROKER_URL',
    ]
    
    all_configured = True
    for setting in required_settings:
        if hasattr(settings, setting):
            value = getattr(settings, setting)
            if value:
                print(f"  ✅ {setting}: {value}")
            else:
                print(f"  ⚠️  {setting}: Not configured")
                all_configured = False
        else:
            print(f"  ❌ {setting}: Missing")
            all_configured = False
    
    return all_configured


def main():
    """Run all validations"""
    print("=" * 60)
    print("Saved Views + Exports - Validation")
    print("=" * 60)
    
    results = {
        'Files': validate_files(),
        'URLs': validate_urls(),
        'Model': validate_model(),
        'Services': validate_services(),
        'Tasks': validate_tasks(),
        'Dependencies': validate_dependencies(),
        'Settings': validate_settings(),
    }
    
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check:.<30} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All validations passed! Ready to use.")
    else:
        print("⚠️  Some validations failed. Review errors above.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
