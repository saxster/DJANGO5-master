#!/usr/bin/env python3
"""Validation script for admin test files."""

import os
import ast
from pathlib import Path

def count_test_methods(filepath):
    """Count test methods in a Python file."""
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read(), filename=filepath)
    
    test_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith('test_'):
                test_count += 1
    
    return test_count

def validate_test_file(filepath):
    """Validate a test file structure."""
    filename = os.path.basename(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    checks = {
        'has_docstring': '"""' in content[:500],
        'has_pytest_import': 'import pytest' in content,
        'has_django_db_marker': '@pytest.mark.django_db' in content,
        'has_test_class': 'class Test' in content,
        'test_count': count_test_methods(filepath)
    }
    
    return checks

def main():
    """Validate all admin test files."""
    test_files = [
        'tests/test_quick_actions.py',
        'tests/test_priority_alerts.py',
        'tests/test_approvals.py',
        'tests/test_team_dashboard.py',
        'tests/test_smart_assignment.py',
        'tests/test_timeline.py',
        'tests/test_saved_views.py',
        'tests/test_integration.py',
        'tests/test_performance.py'
    ]
    
    print("=" * 80)
    print("ADMIN TEST SUITE VALIDATION")
    print("=" * 80)
    print()
    
    total_tests = 0
    
    for test_file in test_files:
        if os.path.exists(test_file):
            results = validate_test_file(test_file)
            filename = os.path.basename(test_file)
            
            print(f"📄 {filename}")
            print(f"   ✓ Docstring: {'Yes' if results['has_docstring'] else 'No'}")
            print(f"   ✓ Pytest import: {'Yes' if results['has_pytest_import'] else 'No'}")
            print(f"   ✓ Django DB marker: {'Yes' if results['has_django_db_marker'] else 'No'}")
            print(f"   ✓ Test class: {'Yes' if results['has_test_class'] else 'No'}")
            print(f"   ✓ Test methods: {results['test_count']}")
            print()
            
            total_tests += results['test_count']
        else:
            print(f"❌ {test_file} - NOT FOUND")
            print()
    
    print("=" * 80)
    print(f"SUMMARY: {len(test_files)} test files, {total_tests} total tests")
    print("=" * 80)
    print()
    
    print("✅ Next Steps:")
    print("   1. Activate virtual environment: source venv/bin/activate")
    print("   2. Run tests: pytest tests/test_*.py -v")
    print("   3. Check coverage: pytest tests/ --cov=apps.core --cov=apps.y_helpdesk")
    print()

if __name__ == '__main__':
    main()
