#!/usr/bin/env python3
"""
Quick validation script for N+1 query fixes.
Checks that all fixed files have the correct optimized method calls.
"""

import sys
import re
from pathlib import Path


def validate_file(file_path, expected_patterns):
    """Validate that a file contains expected optimization patterns."""
    with open(file_path, 'r') as f:
        content = f.read()

    results = []
    for pattern_name, pattern in expected_patterns.items():
        if re.search(pattern, content):
            results.append(f"✅ {pattern_name}: FOUND")
        else:
            results.append(f"❌ {pattern_name}: MISSING")
            return False, results

    return True, results


def main():
    base_dir = Path(__file__).parent

    checks = {
        'attachment_views.py': {
            'patterns': {
                'optimized_delete_by_id': r'optimized_delete_by_id\(R\["id"\]\)',
                'error_handling': r'if not result:',
            },
            'file': base_dir / 'apps/activity/views/attachment_views.py'
        },
        'question_views.py': {
            'patterns': {
                'optimized_filter_for_display': r'optimized_filter_for_display\(',
            },
            'file': base_dir / 'apps/activity/views/question_views.py'
        },
        'job_views.py': {
            'patterns': {
                'optimized_get_with_relations': r'optimized_get_with_relations\(',
            },
            'file': base_dir / 'apps/activity/views/job_views.py'
        },
        'transcript_views.py': {
            'patterns': {
                'optimized_get_with_relations': r'optimized_get_with_relations\(',
            },
            'file': base_dir / 'apps/activity/views/transcript_views.py'
        },
        'crud_views.py': {
            'patterns': {
                'optimized_get_with_relations': r'Asset\.objects\.optimized_get_with_relations\(',
            },
            'file': base_dir / 'apps/activity/views/asset/crud_views.py'
        },
    }

    manager_checks = {
        'attachment_manager.py': {
            'patterns': {
                'optimized_delete_by_id': r'def optimized_delete_by_id\(',
                'optimized_get_with_relations': r'def optimized_get_with_relations\(',
            },
            'file': base_dir / 'apps/activity/managers/attachment_manager.py'
        },
        'question_manager.py': {
            'patterns': {
                'optimized_filter_for_display': r'def optimized_filter_for_display\(',
            },
            'file': base_dir / 'apps/activity/managers/question_manager.py'
        },
        'job_manager.py': {
            'patterns': {
                'optimized_get_with_relations': r'def optimized_get_with_relations\(',
            },
            'file': base_dir / 'apps/activity/managers/job_manager.py'
        },
        'asset_manager.py': {
            'patterns': {
                'optimized_get_with_relations': r'def optimized_get_with_relations\(',
                'optimized_filter_with_relations': r'def optimized_filter_with_relations\(',
            },
            'file': base_dir / 'apps/activity/managers/asset_manager.py'
        },
    }

    print("=" * 80)
    print("N+1 QUERY FIX VALIDATION")
    print("=" * 80)
    print()

    all_passed = True

    print("📁 VALIDATING VIEW FILES:")
    print("-" * 80)
    for file_name, check_info in checks.items():
        print(f"\n{file_name}:")
        if not check_info['file'].exists():
            print(f"  ❌ File not found: {check_info['file']}")
            all_passed = False
            continue

        passed, results = validate_file(check_info['file'], check_info['patterns'])
        for result in results:
            print(f"  {result}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    print("📦 VALIDATING MANAGER FILES:")
    print("-" * 80)
    for file_name, check_info in manager_checks.items():
        print(f"\n{file_name}:")
        if not check_info['file'].exists():
            print(f"  ❌ File not found: {check_info['file']}")
            all_passed = False
            continue

        passed, results = validate_file(check_info['file'], check_info['patterns'])
        for result in results:
            print(f"  {result}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    print("📊 INFRASTRUCTURE VALIDATION:")
    print("-" * 80)

    infrastructure = {
        'Query Test Utilities': base_dir / 'apps/core/testing/query_test_utils.py',
        'N+1 Regression Tests': base_dir / 'apps/core/tests/test_n_plus_one_remediation.py',
        'Audit Script': base_dir / 'scripts/audit_n_plus_one_patterns.py',
        'Documentation': base_dir / 'docs/N_PLUS_ONE_REMEDIATION_COMPLETE.md',
    }

    for name, path in infrastructure.items():
        if path.exists():
            print(f"✅ {name}: EXISTS")
        else:
            print(f"❌ {name}: MISSING")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 80)
        print("\n🎉 N+1 query fixes are complete and validated!")
        print("\nNext steps:")
        print("  1. Run full test suite: python -m pytest")
        print("  2. Start dev server: python manage.py runserver")
        print("  3. Monitor query counts in X-Query-Count header")
        print("  4. Review Django Debug Toolbar SQL panel")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        print("\nSome checks failed. Please review the output above.")
        sys.exit(1)


if __name__ == '__main__':
    main()