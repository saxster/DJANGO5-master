#!/usr/bin/env python3
"""
Simple check script to verify Django ORM migration components exist
This can be run without Django fully initialized
"""
import os
import sys

print("Django ORM Migration Basic Check")
print("=" * 50)

# Check Python version
print(f"Python version: {sys.version}")

# Check if we're in the right directory
print(f"Current directory: {os.getcwd()}")

# Check if key files exist
files_to_check = [
    "apps/core/queries.py",
    "apps/core/cache_manager.py", 
    "scripts/database_optimizations.sql",
    "monitoring/django_monitoring.py",
    "monitoring/views.py",
    "monitoring/alerts.py"
]

print("\nChecking for migration files:")
for file in files_to_check:
    if os.path.exists(file):
        print(f"✅ {file} exists")
    else:
        print(f"❌ {file} NOT FOUND")

# Check if Django is installed
print("\nChecking Django installation:")
try:
    import django
    print(f"✅ Django {django.__version__} is installed")
except ImportError:
    print("❌ Django is not installed in current environment")
    print("   Run: pip install django")

# Check if we can find settings
print("\nChecking Django settings:")
settings_files = [
    "YOUTILITY3/settings.py",
    "YOUTILITY3/settings/__init__.py",
    "settings.py"
]

settings_found = False
for settings_file in settings_files:
    if os.path.exists(settings_file):
        print(f"✅ Found settings at: {settings_file}")
        settings_found = True
        break

if not settings_found:
    print("❌ Could not find Django settings file")

# Check documentation
print("\nChecking documentation:")
docs = [
    "docs/DJANGO_ORM_MIGRATION_GUIDE.md",
    "docs/DEVELOPER_TRAINING.md",
    "docs/PRODUCTION_RUNBOOKS.md",
    "docs/MIGRATION_VERIFICATION_GUIDE.md"
]

for doc in docs:
    if os.path.exists(doc):
        size = os.path.getsize(doc)
        print(f"✅ {doc} ({size:,} bytes)")
    else:
        print(f"❌ {doc} NOT FOUND")

print("\n" + "=" * 50)
print("Basic file check complete!")
print("\nTo run full verification:")
print("1. Activate your virtual environment")
print("2. Run: python manage.py shell")
print("3. Follow the verification guide in docs/MIGRATION_VERIFICATION_GUIDE.md")