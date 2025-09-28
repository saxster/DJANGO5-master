#!/usr/bin/env python3
"""
Pre-commit Hook: Validate Transaction Usage

Ensures all handle_valid_form methods use transaction.atomic.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

import re
import sys
from pathlib import Path


def find_handle_valid_form_methods(file_path):
    """
    Find all handle_valid_form methods in a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of tuples: (line_number, method_name, has_transaction)
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  Could not read {file_path}: {e}")
        return []

    methods = []
    handle_valid_form_pattern = re.compile(r'def (handle_valid_form)\(')

    for match in handle_valid_form_pattern.finditer(content):
        method_name = match.group(1)
        line_num = content[:match.start()].count('\n') + 1

        next_match = handle_valid_form_pattern.search(content, match.end())
        method_end = next_match.start() if next_match else len(content)
        method_content = content[match.start():method_end]

        next_class = re.search(r'^class ', method_content, re.MULTILINE)
        if next_class:
            method_content = method_content[:next_class.start()]

        has_transaction = bool(re.search(
            r'with transaction\.atomic|@transaction\.atomic|@atomic_view_operation',
            method_content
        ))

        methods.append((line_num, method_name, has_transaction, file_path))

    return methods


def check_transaction_usage(changed_files):
    """
    Check that all handle_valid_form methods use transactions.

    Args:
        changed_files: List of modified file paths

    Returns:
        Tuple: (success: bool, violations: list)
    """
    violations = []

    for file_path in changed_files:
        if not file_path.endswith('.py'):
            continue

        if 'views' not in str(file_path):
            continue

        methods = find_handle_valid_form_methods(file_path)

        for line_num, method_name, has_transaction, filepath in methods:
            if not has_transaction:
                violations.append({
                    'file': filepath,
                    'line': line_num,
                    'method': method_name,
                    'message': 'handle_valid_form must use transaction.atomic'
                })

    return len(violations) == 0, violations


def main():
    """Main validation function"""
    import subprocess

    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("⚠️  Could not get staged files")
        return 0

    staged_files = result.stdout.strip().split('\n')
    staged_files = [f for f in staged_files if f]

    if not staged_files:
        return 0

    success, violations = check_transaction_usage(staged_files)

    if not success:
        print("\n❌ TRANSACTION VALIDATION FAILED")
        print("=" * 70)
        print("\nThe following handle_valid_form methods are missing transaction.atomic:\n")

        for violation in violations:
            print(f"  📄 {violation['file']}:{violation['line']}")
            print(f"     Method: {violation['method']}")
            print(f"     Issue: {violation['message']}")
            print()

        print("=" * 70)
        print("\n📖 Fix Required:")
        print("   Wrap the method body with transaction.atomic:")
        print()
        print("   def handle_valid_form(self, form, request, create):")
        print("       try:")
        print("           with transaction.atomic(using=get_current_db_name()):")
        print("               obj = form.save()")
        print("               putils.save_userinfo(obj, request.user, request.session)")
        print("               return JsonResponse({'pk': obj.id})")
        print("       except IntegrityError:")
        print("           return handle_intergrity_error('ModelName')")
        print()
        print("=" * 70)
        print()
        print("Commit blocked. Fix violations and try again.")
        print()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())