#!/usr/bin/env python3
"""
Quick Actions Implementation Validation

Validates that all Quick Actions files are properly created and structured.

Author: Claude Code
Date: 2025-11-07
"""

import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_file_exists(filepath, description):
    """Check if a file exists and print status."""
    if os.path.exists(filepath):
        print(f"{GREEN}✓{RESET} {description}")
        return True
    else:
        print(f"{RED}✗{RESET} {description} - MISSING: {filepath}")
        return False


def check_file_size(filepath, min_lines=50):
    """Check if file has minimum number of lines."""
    try:
        with open(filepath, 'r') as f:
            lines = len(f.readlines())
        if lines >= min_lines:
            print(f"  {BLUE}→{RESET} {lines} lines")
            return True
        else:
            print(f"  {YELLOW}!{RESET} Only {lines} lines (expected >= {min_lines})")
            return False
    except Exception as e:
        print(f"  {RED}!{RESET} Error reading file: {e}")
        return False


def validate_implementation():
    """Validate the Quick Actions implementation."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Quick Actions Implementation Validation{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    base_path = Path(__file__).parent.parent
    all_checks_passed = True
    
    # Files to check
    files_to_check = [
        (
            base_path / 'apps/core/models/quick_action.py',
            'Models: QuickAction, QuickActionExecution, QuickActionChecklist',
            200
        ),
        (
            base_path / 'apps/core/admin/quick_action_admin.py',
            'Admin: QuickActionAdmin, QuickActionExecutionAdmin',
            200
        ),
        (
            base_path / 'apps/core/services/quick_action_service.py',
            'Service: QuickActionService',
            400
        ),
        (
            base_path / 'apps/core/api/quick_action_views.py',
            'API Views: execute_quick_action, update_checklist_step',
            250
        ),
        (
            base_path / 'apps/core/management/commands/create_default_quick_actions.py',
            'Management Command: create_default_quick_actions',
            400
        ),
        (
            base_path / 'templates/admin/quick_actions/action_dialog.html',
            'Template: Action confirmation dialog',
            50
        ),
        (
            base_path / 'templates/admin/quick_actions/checklist.html',
            'Template: Interactive checklist',
            100
        ),
        (
            base_path / 'apps/core/urls/quick_actions.py',
            'URL Configuration: Quick Actions API endpoints',
            20
        ),
    ]
    
    print(f"{BLUE}Checking files:{RESET}\n")
    
    for filepath, description, min_lines in files_to_check:
        if check_file_exists(filepath, description):
            if not check_file_size(filepath, min_lines):
                all_checks_passed = False
        else:
            all_checks_passed = False
        print()
    
    # Check imports in models/__init__.py
    print(f"{BLUE}Checking model exports:{RESET}\n")
    models_init = base_path / 'apps/core/models/__init__.py'
    if os.path.exists(models_init):
        with open(models_init, 'r') as f:
            content = f.read()
            
        checks = [
            ('QuickAction' in content, 'QuickAction exported'),
            ('QuickActionExecution' in content, 'QuickActionExecution exported'),
            ('QuickActionChecklist' in content, 'QuickActionChecklist exported'),
            ('from .quick_action import' in content, 'quick_action module imported'),
        ]
        
        for check, description in checks:
            if check:
                print(f"{GREEN}✓{RESET} {description}")
            else:
                print(f"{RED}✗{RESET} {description}")
                all_checks_passed = False
        print()
    
    # Summary
    print(f"{BLUE}{'='*60}{RESET}")
    if all_checks_passed:
        print(f"{GREEN}✓ All validation checks passed!{RESET}")
        print(f"\n{BLUE}Next steps:{RESET}")
        print(f"  1. Run migrations:")
        print(f"     python manage.py makemigrations core")
        print(f"     python manage.py migrate core")
        print(f"  2. Seed default actions:")
        print(f"     python manage.py create_default_quick_actions")
        print(f"  3. Add URL config to main urls.py:")
        print(f"     path('api/quick-actions/', include('apps.core.urls.quick_actions')),")
        print(f"  4. Access admin at: /admin/core/quickaction/")
        return 0
    else:
        print(f"{RED}✗ Some validation checks failed{RESET}")
        print(f"\n{YELLOW}Please review the errors above{RESET}")
        return 1


def main():
    """Main entry point."""
    exit_code = validate_implementation()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
