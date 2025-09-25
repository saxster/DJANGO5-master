#!/usr/bin/env python
"""
Test script to validate URL configuration
"""
import os
import sys
import django

# Add project root to Python path
sys.path.insert(0, '/home/jarvis/DJANGO5/YOUTILITY5')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

try:
    django.setup()
    print("✅ Django setup successful")
    
    # Test URL imports
    from intelliwiz_config.urls_optimized import urlpatterns
    print(f"✅ Optimized URLs loaded: {len(urlpatterns)} patterns")
    
    # Test individual URL modules
    from apps.core import urls_operations
    print(f"✅ Operations URLs: {len(urls_operations.urlpatterns)} patterns")
    
    from apps.core import urls_assets  
    print(f"✅ Assets URLs: {len(urls_assets.urlpatterns)} patterns")
    
    from apps.core import urls_people
    print(f"✅ People URLs: {len(urls_people.urlpatterns)} patterns")
    
    from apps.core import urls_helpdesk
    print(f"✅ Helpdesk URLs: {len(urls_helpdesk.urlpatterns)} patterns")
    
    from apps.core import urls_admin
    print(f"✅ Admin URLs: {len(urls_admin.urlpatterns)} patterns")
    
    print("\n🎉 All URL modules loaded successfully!")
    print("\nYou can now run: python manage.py check")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Check that all view classes exist and are correctly named")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Check Django settings and app configuration")