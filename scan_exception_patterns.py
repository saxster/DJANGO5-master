#!/usr/bin/env python3
"""
Simple Exception Pattern Scanner

Scans for remaining forbidden exception patterns in the codebase.
Does not require Django environment setup.
"""

import os
import re
from pathlib import Path


def scan_for_forbidden_patterns():
    """Scan codebase for remaining forbidden exception patterns."""
    print("🔍 Scanning for Forbidden Exception Patterns...")

    forbidden_patterns = [
        (r'except\s+Exception\s*:', 'Generic Exception catching'),
        (r'except\s*:', 'Bare except clause'),
    ]

    critical_files = [
        'apps/peoples/views.py',
        'apps/api/middleware.py',
        'apps/core/services/security_monitoring_service.py',
        'apps/schedhuler/views.py',
        'apps/activity/views/',
        'apps/core/error_handling.py'
    ]

    violations = []
    files_scanned = 0

    for file_pattern in critical_files:
        if file_pattern.endswith('/'):
            # Directory pattern
            dir_path = Path(file_pattern)
            if dir_path.exists():
                for py_file in dir_path.rglob('*.py'):
                    violations.extend(scan_file(py_file, forbidden_patterns))
                    files_scanned += 1
        else:
            # Single file
            file_path = Path(file_pattern)
            if file_path.exists():
                violations.extend(scan_file(file_path, forbidden_patterns))
                files_scanned += 1

    print(f"📊 Scanned {files_scanned} files")

    if violations:
        print(f"❌ Found {len(violations)} forbidden exception patterns:")
        for i, violation in enumerate(violations[:20]):  # Show first 20
            print(f"  {i+1}. 📁 {violation['file']}:{violation['line']}")
            print(f"     🔍 {violation['pattern']}")
            print(f"     💻 {violation['code']}")
            print()

        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more violations")
        return False
    else:
        print("✅ No forbidden exception patterns found in scanned files")
        return True


def scan_file(file_path, forbidden_patterns):
    """Scan a single file for forbidden patterns."""
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        for pattern, description in forbidden_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                violations.append({
                    'file': str(file_path),
                    'line': line_num,
                    'pattern': description,
                    'code': lines[line_num - 1].strip() if line_num <= len(lines) else ''
                })
    except Exception as e:
        print(f"⚠️  Could not scan {file_path}: {e}")

    return violations


def main():
    """Main function."""
    print("🚨 EXCEPTION PATTERN SCANNER")
    print("=" * 40)

    success = scan_for_forbidden_patterns()

    if success:
        print("\n🎉 SCAN COMPLETED SUCCESSFULLY!")
        print("✅ No forbidden patterns found in critical files")
    else:
        print("\n❌ FORBIDDEN PATTERNS DETECTED")
        print("⚠️  These patterns violate Rule 11 from .claude/rules.md")
        print("⚠️  They must be replaced with specific exception handling")

    return success


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)