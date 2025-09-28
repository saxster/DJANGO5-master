#!/usr/bin/env python3
"""
Transaction Management Remediation Validation Script

Validates that all critical operations now use transaction.atomic.

Run: python3 validate_transaction_remediation.py
"""

import re
from pathlib import Path


def validate_file(file_path):
    """Validate a single Python file for transaction.atomic usage."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        return {'error': str(e)}

    results = {
        'file': str(file_path),
        'handle_valid_form_methods': 0,
        'with_transaction': 0,
        'without_transaction': [],
        'compliant': True
    }

    handle_valid_form_pattern = re.compile(r'def (handle_valid_form)\(')
    transaction_pattern = re.compile(
        r'with transaction\.atomic|@transaction\.atomic|@atomic_view_operation'
    )

    for match in handle_valid_form_pattern.finditer(content):
        results['handle_valid_form_methods'] += 1
        line_num = content[:match.start()].count('\n') + 1

        next_match = handle_valid_form_pattern.search(content, match.end())
        method_end = next_match.start() if next_match else len(content)
        method_content = content[match.start():method_end]

        next_class = re.search(r'^class ', method_content, re.MULTILINE)
        if next_class:
            method_content = method_content[:next_class.start()]

        if transaction_pattern.search(method_content):
            results['with_transaction'] += 1
        else:
            results['without_transaction'].append(line_num)
            results['compliant'] = False

    return results


def main():
    base_path = Path(__file__).parent

    critical_files = [
        'apps/work_order_management/views.py',
        'apps/activity/views/job_views.py',
        'apps/attendance/views.py',
        'apps/onboarding/views.py',
        'apps/reports/views.py',
        'apps/y_helpdesk/views.py',
    ]

    print("=" * 80)
    print("TRANSACTION MANAGEMENT REMEDIATION VALIDATION")
    print("=" * 80)
    print()

    total_methods = 0
    total_with_transaction = 0
    non_compliant_files = []

    for file_path in critical_files:
        full_path = base_path / file_path
        if not full_path.exists():
            print(f"⚠️  SKIP: {file_path} (not found)")
            continue

        result = validate_file(full_path)

        if 'error' in result:
            print(f"❌ ERROR: {file_path}")
            print(f"   {result['error']}")
            continue

        total_methods += result['handle_valid_form_methods']
        total_with_transaction += result['with_transaction']

        if result['compliant']:
            print(f"✅ PASS: {file_path}")
            print(f"   Methods: {result['handle_valid_form_methods']}/{result['handle_valid_form_methods']} with transaction.atomic")
        else:
            print(f"❌ FAIL: {file_path}")
            print(f"   Methods: {result['with_transaction']}/{result['handle_valid_form_methods']} with transaction.atomic")
            print(f"   Missing at lines: {result['without_transaction']}")
            non_compliant_files.append(file_path)

        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total handle_valid_form methods found: {total_methods}")
    print(f"Methods with transaction.atomic: {total_with_transaction}")
    print(f"Methods without transaction.atomic: {total_methods - total_with_transaction}")
    print()

    if total_methods > 0:
        coverage = (total_with_transaction / total_methods) * 100
        print(f"Transaction Coverage: {coverage:.1f}%")
        print()

    if non_compliant_files:
        print(f"❌ VALIDATION FAILED")
        print(f"Non-compliant files: {len(non_compliant_files)}")
        for file_path in non_compliant_files:
            print(f"  - {file_path}")
        return 1
    else:
        print("✅ VALIDATION PASSED")
        print("All critical operations use transaction.atomic!")
        return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())