#!/usr/bin/env python
"""
File Upload Security Validation Script

Quick validation that all file upload security fixes are in place.
Run this after remediation to verify compliance.

Usage:
    python validate_file_upload_security.py
"""

import os
import sys
import re
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} MISSING: {filepath}")
        return False


def check_file_contains(filepath, pattern, description):
    """Check if file contains pattern."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if re.search(pattern, content):
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description} - Pattern not found")
                return False
    except FileNotFoundError:
        print(f"❌ {description} - File not found: {filepath}")
        return False


def validate_fixes():
    """Validate all security fixes are in place."""
    print("=" * 80)
    print("FILE UPLOAD SECURITY VALIDATION")
    print("=" * 80)
    print()

    checks_passed = 0
    checks_failed = 0

    print("📋 Checking Critical Vulnerability Fixes...")
    print()

    if check_file_contains(
        'apps/journal/models.py',
        r'upload_to=upload_journal_media',
        "Journal model uses secure upload callable"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        'apps/journal/models.py',
        r'get_valid_filename',
        "Journal upload callable sanitizes filenames"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        'apps/service/utils.py',
        r'DEPRECATED.*Legacy upload',
        "perform_uploadattachment marked as deprecated"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        'apps/service/utils.py',
        r'SecureFileUploadService\.validate_and_process_upload',
        "perform_uploadattachment uses SecureFileUploadService"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        'apps/onboarding/utils.py',
        r'safe_filename = get_valid_filename',
        "Bulk upload sanitizes filenames"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("📋 Checking Security Infrastructure...")
    print()

    if check_file_exists(
        'scripts/scan_file_upload_vulnerabilities.py',
        "Automated vulnerability scanner"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_exists(
        'apps/core/services/file_upload_audit_service.py',
        "Audit service"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_exists(
        'apps/core/views/file_upload_security_dashboard.py',
        "Security dashboard views"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("📋 Checking Test Suite...")
    print()

    if check_file_exists(
        'apps/core/tests/test_file_upload_penetration.py',
        "Penetration test suite"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_exists(
        'apps/core/tests/test_file_upload_integration.py',
        "Integration test suite"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_exists(
        'apps/core/tests/test_file_upload_performance.py',
        "Performance test suite"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("📋 Checking Pre-commit Hook Enhancement...")
    print()

    if check_file_contains(
        '.githooks/pre-commit',
        r'upload_to=',
        "Pre-commit validates upload_to patterns"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        '.githooks/pre-commit',
        r'request\.FILES',
        "Pre-commit validates direct FILES access"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("📋 Checking Configuration...")
    print()

    if check_file_contains(
        'intelliwiz_config/settings/security/file_upload.py',
        r'CLAMAV_SETTINGS',
        "ClamAV settings configured"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_contains(
        'intelliwiz_config/settings/security/file_upload.py',
        r"'ENABLE_MALWARE_SCANNING'.*True",
        "Malware scanning enabled by default"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("📋 Checking Documentation...")
    print()

    if check_file_exists(
        'docs/security/clamav-setup-guide.md',
        "ClamAV setup guide"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    if check_file_exists(
        'FILE_UPLOAD_SECURITY_REMEDIATION_COMPLETE.md',
        "Remediation summary document"
    ):
        checks_passed += 1
    else:
        checks_failed += 1

    print()
    print("=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    print(f"✅ Checks Passed: {checks_passed}")
    print(f"❌ Checks Failed: {checks_failed}")
    print(f"Total Checks: {checks_passed + checks_failed}")
    print()

    if checks_failed == 0:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ File upload security remediation is COMPLETE")
        print()
        print("Next steps:")
        print("1. Run: python manage.py migrate")
        print("2. Run: python -m pytest apps/core/tests/test_file_upload*.py -m security -v")
        print("3. Run: python scripts/scan_file_upload_vulnerabilities.py")
        print("4. Access dashboard: /security/file-upload/dashboard/")
        print()
        return 0
    else:
        print(f"⚠️  {checks_failed} validations failed")
        print("Please review the failed checks above")
        print()
        return 1


if __name__ == '__main__':
    exit_code = validate_fixes()
    sys.exit(exit_code)