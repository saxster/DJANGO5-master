#!/usr/bin/env python
"""
Activity Timeline Implementation Validator

Validates that all Activity Timeline components are properly implemented
and follow security/architecture best practices.
"""

import os
import sys
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"{GREEN}✓{RESET} {description}: {filepath}")
        return True
    else:
        print(f"{RED}✗{RESET} {description}: {filepath} - NOT FOUND")
        return False


def check_import_in_file(filepath: str, import_statement: str, description: str) -> bool:
    """Check if an import statement exists in a file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if import_statement in content:
                print(f"{GREEN}✓{RESET} {description}")
                return True
            else:
                print(f"{RED}✗{RESET} {description} - NOT FOUND")
                return False
    except FileNotFoundError:
        print(f"{RED}✗{RESET} {description} - FILE NOT FOUND")
        return False


def check_class_in_file(filepath: str, class_name: str, description: str) -> bool:
    """Check if a class definition exists in a file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if f"class {class_name}" in content:
                print(f"{GREEN}✓{RESET} {description}: {class_name}")
                return True
            else:
                print(f"{RED}✗{RESET} {description}: {class_name} - NOT FOUND")
                return False
    except FileNotFoundError:
        print(f"{RED}✗{RESET} {description} - FILE NOT FOUND")
        return False


def check_url_pattern(filepath: str, pattern: str, description: str) -> bool:
    """Check if a URL pattern exists"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if pattern in content:
                print(f"{GREEN}✓{RESET} {description}")
                return True
            else:
                print(f"{RED}✗{RESET} {description} - NOT FOUND")
                return False
    except FileNotFoundError:
        print(f"{RED}✗{RESET} {description} - FILE NOT FOUND")
        return False


def main():
    """Main validation function"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Activity Timeline Implementation Validator{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    results = []
    
    # Check service file
    print(f"\n{YELLOW}[1] Service Layer{RESET}")
    service_path = "apps/core/services/activity_timeline_service.py"
    results.append(check_file_exists(service_path, "Service file exists"))
    results.append(check_class_in_file(service_path, "ActivityTimelineService", "Service class defined"))
    results.append(check_import_in_file(service_path, "def get_person_timeline", "get_person_timeline method"))
    results.append(check_import_in_file(service_path, "def get_asset_timeline", "get_asset_timeline method"))
    results.append(check_import_in_file(service_path, "def calculate_kpis", "calculate_kpis method"))
    
    # Check views file
    print(f"\n{YELLOW}[2] View Layer{RESET}")
    views_path = "apps/core/views/timeline_views.py"
    results.append(check_file_exists(views_path, "Views file exists"))
    results.append(check_class_in_file(views_path, "PersonTimelineView", "PersonTimelineView class"))
    results.append(check_class_in_file(views_path, "AssetTimelineView", "AssetTimelineView class"))
    results.append(check_class_in_file(views_path, "LocationTimelineView", "LocationTimelineView class"))
    results.append(check_import_in_file(views_path, "LoginRequiredMixin", "Login required mixin"))
    
    # Check templates
    print(f"\n{YELLOW}[3] Templates{RESET}")
    results.append(check_file_exists(
        "templates/admin/core/person_timeline.html",
        "Person timeline template"
    ))
    results.append(check_file_exists(
        "templates/admin/core/asset_timeline.html",
        "Asset timeline template"
    ))
    results.append(check_file_exists(
        "templates/admin/core/location_timeline.html",
        "Location timeline template"
    ))
    results.append(check_file_exists(
        "templates/admin/peoples/change_form.html",
        "People admin template override"
    ))
    
    # Check URL configuration
    print(f"\n{YELLOW}[4] URL Configuration{RESET}")
    urls_path = "apps/core/urls_admin.py"
    results.append(check_file_exists(urls_path, "Admin URLs file exists"))
    results.append(check_url_pattern(
        urls_path,
        'path("timeline/person/<int:person_id>/"',
        "Person timeline URL pattern"
    ))
    results.append(check_url_pattern(
        urls_path,
        'path("timeline/asset/<int:asset_id>/"',
        "Asset timeline URL pattern"
    ))
    results.append(check_import_in_file(
        urls_path,
        "from apps.core.views.timeline_views import",
        "Timeline views imported"
    ))
    
    # Check admin integration
    print(f"\n{YELLOW}[5] Admin Integration{RESET}")
    admin_path = "apps/peoples/admin/people_admin.py"
    results.append(check_file_exists(admin_path, "People admin file exists"))
    results.append(check_import_in_file(admin_path, "from django.urls import reverse", "URL reverse imported"))
    results.append(check_import_in_file(admin_path, "def change_view", "change_view method override"))
    results.append(check_import_in_file(admin_path, "timeline_url", "Timeline URL in context"))
    
    # Check documentation
    print(f"\n{YELLOW}[6] Documentation{RESET}")
    results.append(check_file_exists(
        "ACTIVITY_TIMELINE_IMPLEMENTATION.md",
        "Implementation documentation"
    ))
    results.append(check_file_exists(
        "ACTIVITY_TIMELINE_QUICK_START.md",
        "Quick start guide"
    ))
    
    # Security checks
    print(f"\n{YELLOW}[7] Security & Best Practices{RESET}")
    results.append(check_import_in_file(
        views_path,
        "LoginRequiredMixin",
        "Login required on views"
    ))
    results.append(check_import_in_file(
        service_path,
        "select_related",
        "Query optimization (select_related)"
    ))
    results.append(check_import_in_file(
        service_path,
        "MAX_EVENTS_PER_SOURCE",
        "Event limiting (prevents DoS)"
    ))
    
    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"\n{BLUE}Summary:{RESET}")
    print(f"  Total checks: {total}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    print(f"  {RED}Failed: {failed}{RESET}")
    
    if failed == 0:
        print(f"\n{GREEN}✓ All validation checks passed!{RESET}")
        print(f"\n{BLUE}Next Steps:{RESET}")
        print("  1. Activate virtual environment")
        print("  2. Run: python manage.py check")
        print("  3. Start server: python manage.py runserver")
        print("  4. Navigate to Admin → People → Select person")
        print("  5. Click 'View Activity Timeline' button")
        return 0
    else:
        print(f"\n{RED}✗ Some validation checks failed. Please review above.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
