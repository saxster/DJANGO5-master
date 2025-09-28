#!/usr/bin/env python3
"""
Security fixes test runner.

This script validates the critical fixes applied to the task and tour system
by performing code analysis and basic validation.
"""

import os
import re
import sys
from pathlib import Path


def check_expiry_datetime_fixes():
    """Check that expiry datetime bug is fixed in forms."""
    forms_file = Path("apps/schedhuler/forms.py")

    if not forms_file.exists():
        print("❌ Forms file not found")
        return False

    content = forms_file.read_text()

    # Check for the bug pattern (should NOT be present)
    bug_pattern = r'def clean_expirydatetime\(self\):\s*if val := self\.cleaned_data\.get\("plandatetime"\)'
    if re.search(bug_pattern, content, re.MULTILINE | re.DOTALL):
        print("❌ Expiry datetime bug still present")
        return False

    # Check for the fix pattern (should be present)
    fix_pattern = r'def clean_expirydatetime\(self\):\s*if val := self\.cleaned_data\.get\("expirydatetime"\)'
    fix_count = len(re.findall(fix_pattern, content, re.MULTILINE | re.DOTALL))

    if fix_count >= 3:  # Should be 3 instances fixed
        print("✅ Expiry datetime bug fixed in all forms")
        return True
    else:
        print(f"❌ Expiry datetime fix incomplete ({fix_count}/3 instances)")
        return False


def check_sentinel_resolver_utility():
    """Check that sentinel resolver utility exists and has required functions."""
    resolver_file = Path("apps/core/utils_new/sentinel_resolvers.py")

    if not resolver_file.exists():
        print("❌ Sentinel resolver utility not found")
        return False

    content = resolver_file.read_text()

    required_functions = [
        "get_none_job",
        "get_none_asset",
        "get_none_jobneed",
        "resolve_parent_job",
        "resolve_asset_reference"
    ]

    missing_functions = []
    for func in required_functions:
        if func not in content:
            missing_functions.append(func)

    if missing_functions:
        print(f"❌ Missing sentinel resolver functions: {missing_functions}")
        return False

    print("✅ Sentinel resolver utility complete")
    return True


def check_sentinel_id_replacements():
    """Check that sentinel IDs have been replaced with resolvers."""
    views_file = Path("apps/schedhuler/views.py")

    if not views_file.exists():
        print("❌ Views file not found")
        return False

    content = views_file.read_text()

    # Check that import is present
    if "from apps.core.utils_new.sentinel_resolvers import" not in content:
        print("❌ Sentinel resolver import missing from views")
        return False

    # Check that hardcoded -1 and 1 assignments are replaced
    bad_patterns = [
        r'\.parent_id\s*=\s*-1',
        r'\.parent_id\s*=\s*1',
        r'\.asset_id\s*=\s*-1',
        r'\.asset_id\s*=\s*1'
    ]

    for pattern in bad_patterns:
        if re.search(pattern, content):
            print(f"❌ Found unreplaced sentinel ID pattern: {pattern}")
            return False

    # Check that resolvers are being used
    if "get_none_job()" not in content or "get_none_asset()" not in content:
        print("❌ Sentinel resolvers not being used in views")
        return False

    print("✅ Sentinel IDs replaced with proper resolvers")
    return True


def check_database_indexes():
    """Check that database indexes have been added."""
    models_file = Path("apps/activity/models/job_model.py")
    migration_file = Path("apps/activity/migrations/0007_add_performance_indexes.py")

    if not models_file.exists():
        print("❌ Job models file not found")
        return False

    content = models_file.read_text()

    # Check for db_index=True on identifier fields
    identifier_indexes = len(re.findall(r'identifier.*?db_index=True', content, re.DOTALL))

    if identifier_indexes >= 2:  # Job and Jobneed identifier fields
        print("✅ Database indexes added to identifier fields")
        index_check = True
    else:
        print(f"❌ Database indexes missing ({identifier_indexes}/2 fields)")
        index_check = False

    # Check migration file exists
    if migration_file.exists():
        print("✅ Database migration created")
        migration_check = True
    else:
        print("❌ Database migration file missing")
        migration_check = False

    return index_check and migration_check


def check_post_security_fixes():
    """Check that unsafe GET mutations have been fixed."""
    views_file = Path("apps/schedhuler/views.py")
    template_files = [
        Path("frontend/templates/schedhuler/schd_i_tourform_job.html"),
        Path("frontend/templates/schedhuler/i_tourform_jobneed_temp.html")
    ]

    if not views_file.exists():
        print("❌ Views file not found for POST security check")
        return False

    views_content = views_file.read_text()

    # Check that deleteChekpointFromTour requires POST
    if 'if request.method != "POST"' not in views_content:
        print("❌ Delete endpoint still accepts GET requests")
        return False

    # Check templates use POST
    template_checks = []
    for template_file in template_files:
        if template_file.exists():
            template_content = template_file.read_text()
            # Check for fire_ajax_post usage
            if "fire_ajax_post" in template_content:
                template_checks.append(True)
            else:
                print(f"❌ Template {template_file.name} still uses GET")
                template_checks.append(False)
        else:
            print(f"⚠️  Template {template_file.name} not found")
            template_checks.append(False)

    if all(template_checks):
        print("✅ POST security fixes applied")
        return True
    else:
        print("❌ POST security fixes incomplete")
        return False


def check_constants_usage():
    """Check that string literals have been replaced with constants."""
    files_to_check = [
        Path("apps/schedhuler/views.py"),
        Path("apps/service/utils.py")
    ]

    all_good = True

    for file_path in files_to_check:
        if not file_path.exists():
            print(f"❌ File {file_path} not found for constants check")
            all_good = False
            continue

        content = file_path.read_text()

        # Check for imports
        if "from apps.core.constants import JobConstants" not in content:
            print(f"❌ JobConstants import missing from {file_path.name}")
            all_good = False
            continue

        # Check for usage of constants instead of literals
        if "JobConstants.Identifier.TASK" not in content:
            print(f"❌ Constants not being used in {file_path.name}")
            all_good = False
            continue

    if all_good:
        print("✅ Constants being used instead of string literals")

    return all_good


def check_test_files():
    """Check that comprehensive test suite has been created."""
    test_files = [
        Path("apps/schedhuler/tests/test_security_fixes.py"),
        Path("apps/core/tests/test_sentinel_resolvers.py"),
        Path("apps/schedhuler/tests/test_performance.py"),
        Path("apps/activity/tests/test_task_tour_integration.py")
    ]

    missing_tests = []
    for test_file in test_files:
        if not test_file.exists():
            missing_tests.append(test_file.name)

    if missing_tests:
        print(f"❌ Missing test files: {missing_tests}")
        return False

    print("✅ Comprehensive test suite created")
    return True


def main():
    """Run all security and fix validations."""
    print("🔍 Running security fixes validation...\n")

    checks = [
        ("Expiry DateTime Fixes", check_expiry_datetime_fixes),
        ("Sentinel Resolver Utility", check_sentinel_resolver_utility),
        ("Sentinel ID Replacements", check_sentinel_id_replacements),
        ("Database Indexes", check_database_indexes),
        ("POST Security Fixes", check_post_security_fixes),
        ("Constants Usage", check_constants_usage),
        ("Test Suite", check_test_files)
    ]

    results = []

    for check_name, check_func in checks:
        print(f"\n📋 Checking {check_name}...")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Error during {check_name}: {e}")
            results.append(False)

    print(f"\n{'='*50}")
    print("📊 VALIDATION SUMMARY")
    print(f"{'='*50}")

    passed = sum(results)
    total = len(results)

    for i, (check_name, _) in enumerate(checks):
        status = "✅ PASSED" if results[i] else "❌ FAILED"
        print(f"{check_name:.<30} {status}")

    print(f"\nOverall: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All security fixes validated successfully!")
        return 0
    else:
        print("⚠️  Some fixes need attention")
        return 1


if __name__ == "__main__":
    sys.exit(main())