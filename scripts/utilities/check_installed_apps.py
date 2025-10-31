#!/usr/bin/env python
"""
Check what apps are installed and test URL loading
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/jarvis/DJANGO5/YOUTILITY5')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

try:
    django.setup()
    
    from django.conf import settings
    
    print("📋 INSTALLED_APPS:")
    for app in settings.INSTALLED_APPS:
        if app.startswith('apps.'):
            print(f"  ✅ {app}")
    
    print("\n🔍 Checking problematic apps:")
    
    problem_apps = [
        'apps.employee_creation',
        'apps.activity',
        'apps.reminder'
    ]
    
    for app in problem_apps:
        if app in settings.INSTALLED_APPS:
            print(f"  ✅ {app} - INSTALLED")
        else:
            print(f"  ❌ {app} - NOT INSTALLED")
    
    print("\n🧪 Testing URL imports:")
    
    # Test URL imports one by one
    try:
        from apps.core import urls_operations
        print("  ✅ Operations URLs loaded")
    except Exception as e:
        print(f"  ❌ Operations URLs failed: {e}")
    
    try:
        from apps.core import urls_assets
        print("  ✅ Assets URLs loaded")
    except Exception as e:
        print(f"  ❌ Assets URLs failed: {e}")
    
    try:
        from apps.core import urls_people
        print("  ✅ People URLs loaded")
    except Exception as e:
        print(f"  ❌ People URLs failed: {e}")
    
    try:
        from apps.core import urls_helpdesk
        print("  ✅ Helpdesk URLs loaded")
    except Exception as e:
        print(f"  ❌ Helpdesk URLs failed: {e}")
    
    try:
        from apps.core import urls_admin
        print("  ✅ Admin URLs loaded")
    except Exception as e:
        print(f"  ❌ Admin URLs failed: {e}")
    
    try:
        from intelliwiz_config.urls_optimized import urlpatterns
        print(f"  ✅ Main optimized URLs loaded: {len(urlpatterns)} patterns")
    except Exception as e:
        print(f"  ❌ Main URLs failed: {e}")
    
    print("\n🎉 URL loading test complete!")
        
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    
print("\nRun this with: python check_installed_apps.py")
