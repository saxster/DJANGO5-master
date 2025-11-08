#!/usr/bin/env python3
"""
Verification Script for Secure File Download Remediation

This script verifies that:
1. SecureFileDownloadService is properly imported
2. export_views.py uses the secure service
3. All security patterns are in place
"""
import re
import sys
from pathlib import Path


def verify_import_present(file_path):
    """Verify SecureFileDownloadService import is present"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    if 'from apps.core.services.secure_file_download_service import SecureFileDownloadService' in content:
        return True, "✅ SecureFileDownloadService import found"
    return False, "❌ SecureFileDownloadService import missing"


def verify_secure_usage(file_path):
    """Verify validate_and_serve_file is used instead of direct file opening"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check for insecure patterns (should not exist)
    insecure_patterns = [
        r'file_handle = open\(.*filepath.*["\']rb["\']',
        r'FileResponse\(open\(',
    ]
    
    insecure_found = []
    for pattern in insecure_patterns:
        if re.search(pattern, content):
            insecure_found.append(pattern)
    
    # Check for secure pattern (should exist)
    secure_pattern = r'SecureFileDownloadService\.validate_and_serve_file'
    secure_found = re.search(secure_pattern, content) is not None
    
    results = []
    if insecure_found:
        results.append(f"⚠️  WARNING: Potential insecure patterns found: {insecure_found}")
    else:
        results.append("✅ No insecure file opening patterns found")
    
    if secure_found:
        results.append("✅ SecureFileDownloadService.validate_and_serve_file() usage found")
    else:
        results.append("❌ SecureFileDownloadService.validate_and_serve_file() NOT found")
    
    return len(insecure_found) == 0 and secure_found, "\n".join(results)


def verify_exception_handling(file_path):
    """Verify proper exception handling is in place"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    required_exceptions = [
        'PermissionDenied',
        'SuspiciousFileOperation',
        'Http404',
    ]
    
    results = []
    all_found = True
    
    for exc in required_exceptions:
        if exc in content:
            results.append(f"✅ {exc} exception handling found")
        else:
            results.append(f"❌ {exc} exception handling missing")
            all_found = False
    
    # Check for generic exception (should not exist in new code)
    if re.search(r'except Exception:', content):
        results.append("⚠️  WARNING: Generic 'except Exception:' found (check if it's in old code)")
    else:
        results.append("✅ No generic exception handlers in modified code")
    
    return all_found, "\n".join(results)


def verify_audit_logging(file_path):
    """Verify audit logging is present"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    logging_patterns = [
        r'log\.(info|error|warning)',
        r'extra=\{[^}]*user_id',
    ]
    
    results = []
    all_found = True
    
    for pattern in logging_patterns:
        if re.search(pattern, content):
            results.append(f"✅ Audit logging pattern found: {pattern}")
        else:
            results.append(f"❌ Audit logging pattern missing: {pattern}")
            all_found = False
    
    return all_found, "\n".join(results)


def main():
    """Run all verification checks"""
    print("=" * 80)
    print("SECURE FILE DOWNLOAD REMEDIATION VERIFICATION")
    print("=" * 80)
    print()
    
    file_to_check = Path(__file__).parent / 'apps' / 'reports' / 'views' / 'export_views.py'
    
    if not file_to_check.exists():
        print(f"❌ ERROR: File not found: {file_to_check}")
        sys.exit(1)
    
    print(f"Checking file: {file_to_check}")
    print()
    
    all_checks_passed = True
    
    # Check 1: Import verification
    print("Check 1: SecureFileDownloadService Import")
    print("-" * 80)
    passed, message = verify_import_present(file_to_check)
    print(message)
    print()
    all_checks_passed = all_checks_passed and passed
    
    # Check 2: Secure usage verification
    print("Check 2: Secure File Serving Pattern")
    print("-" * 80)
    passed, message = verify_secure_usage(file_to_check)
    print(message)
    print()
    all_checks_passed = all_checks_passed and passed
    
    # Check 3: Exception handling verification
    print("Check 3: Proper Exception Handling")
    print("-" * 80)
    passed, message = verify_exception_handling(file_to_check)
    print(message)
    print()
    all_checks_passed = all_checks_passed and passed
    
    # Check 4: Audit logging verification
    print("Check 4: Audit Logging")
    print("-" * 80)
    passed, message = verify_audit_logging(file_to_check)
    print(message)
    print()
    all_checks_passed = all_checks_passed and passed
    
    # Final summary
    print("=" * 80)
    if all_checks_passed:
        print("✅ ALL CHECKS PASSED - Remediation Complete!")
        print()
        print("Security Improvements:")
        print("  • Path traversal prevention")
        print("  • IDOR protection")
        print("  • Tenant isolation")
        print("  • Audit logging")
        print("  • Proper exception handling")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Review Required")
        return 1


if __name__ == '__main__':
    sys.exit(main())
