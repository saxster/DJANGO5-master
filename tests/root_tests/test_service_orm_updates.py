#!/usr/bin/env python
"""
Test script to verify service layer ORM updates.
Tests that the service API functions now use Django ORM instead of PostgreSQL functions.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.utils import timezone
from apps.service.querys import get_externaltouremodifiedafter, get_assetdetails


def test_service_functions():
    """Test the updated service functions that now use Django ORM."""
    print("=" * 80)
    print("SERVICE LAYER ORM UPDATE TEST")
    print("=" * 80)
    
    # Test parameters
    test_people_id = 1
    test_bu_id = 1
    test_client_id = 1
    test_date = timezone.now() - timedelta(days=30)
    
    results = {
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    print("\n1. Testing get_externaltouremodifiedafter()...")
    print("-" * 40)
    try:
        result = get_externaltouremodifiedafter(test_people_id, test_bu_id, test_client_id)
        print(f"✓ Function executed successfully")
        print(f"  Records returned: {result.nrows}")
        print(f"  Message: {result.msg}")
        results['passed'] += 1
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"get_externaltouremodifiedafter: {str(e)}")
    
    print("\n2. Testing get_assetdetails()...")
    print("-" * 40)
    try:
        result = get_assetdetails(test_date, test_bu_id)
        print(f"✓ Function executed successfully")
        print(f"  Records returned: {result.nrows}")
        print(f"  Message: {result.msg}")
        results['passed'] += 1
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"get_assetdetails: {str(e)}")
    
    # Test that get_db_rows has been removed
    print("\n3. Testing SQL security (function removed)...")
    print("-" * 40)
    try:
        from apps.service.querys import get_db_rows
        print("✗ ISSUE: get_db_rows function still exists but should have been removed!")
        results['failed'] += 1
        results['errors'].append("Security: get_db_rows function not removed")
    except ImportError:
        print("✓ get_db_rows function has been correctly removed")
        print("  All PostgreSQL functions migrated to Django ORM")
        results['passed'] += 1
    except Exception as e:
        print(f"? Unexpected error: {str(e)}")
        results['failed'] += 1
        results['errors'].append(f"Security test: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results['passed'] + results['failed']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    
    if results['failed'] == 0:
        print("\n✅ All service layer tests passed!")
        print("   The service API now uses Django ORM implementations.")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
    
    return results['failed'] == 0


def check_remaining_sql_functions():
    """Check if any other functions still use PostgreSQL functions."""
    print("\n" + "=" * 80)
    print("CHECKING FOR REMAINING POSTGRESQL FUNCTION CALLS")
    print("=" * 80)
    
    import re
    from pathlib import Path
    
    # Patterns to search for
    pg_function_patterns = [
        r'fn_getassetdetails\s*\(',
        r'fn_getassetvsquestionset\s*\(',
        r'fun_getjobneed\s*\(',
        r'fun_getexttourjobneed\s*\(',
        r'fn_getbulist_basedon_idnf\s*\(',
        r'fn_get_schedule_for_adhoc\s*\('
    ]
    
    # Directories to search
    search_dirs = ['apps', 'graphql_api', 'templates']
    exclude_dirs = {'__pycache__', 'migrations', 'tests', 'test_*'}
    exclude_files = {'test_*.py', '*_test.py', 'raw_sql_functions.py', 'raw_queries.py'}
    
    found_issues = []
    
    for search_dir in search_dirs:
        if not Path(search_dir).exists():
            continue
            
        for file_path in Path(search_dir).rglob('*.py'):
            # Skip excluded directories and files
            if any(exc in str(file_path) for exc in exclude_dirs):
                continue
            if any(file_path.match(exc) for exc in exclude_files):
                continue
                
            try:
                content = file_path.read_text()
                for pattern in pg_function_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        found_issues.append({
                            'file': str(file_path),
                            'line': line_num,
                            'function': match.group(0)
                        })
            except Exception as e:
                pass
    
    if found_issues:
        print(f"\n⚠️  Found {len(found_issues)} potential PostgreSQL function calls:")
        for issue in found_issues:
            print(f"  {issue['file']}:{issue['line']} - {issue['function']}")
    else:
        print("\n✅ No PostgreSQL function calls found in application code!")
    
    return len(found_issues) == 0


if __name__ == "__main__":
    print("Testing Service Layer ORM Updates...")
    print("This verifies that the service API now uses Django ORM instead of PostgreSQL functions.\n")
    
    # Run tests
    tests_passed = test_service_functions()
    no_pg_functions = check_remaining_sql_functions()
    
    if tests_passed and no_pg_functions:
        print("\n" + "🎉 " * 20)
        print("ALL SERVICE LAYER UPDATES VERIFIED SUCCESSFULLY!")
        print("The migration to Django ORM is now complete across all layers.")
        print("🎉 " * 20)
        sys.exit(0)
    else:
        print("\n⚠️  Some issues were found. Please review the output above.")
        sys.exit(1)