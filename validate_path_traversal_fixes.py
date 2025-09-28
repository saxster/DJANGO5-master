#!/usr/bin/env python3
"""
Path Traversal Vulnerability Validation Script

This script validates that all path traversal vulnerabilities have been fixed.
Run this script to verify the security remediation is effective.

Usage:
    python3 validate_path_traversal_fixes.py
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from apps.peoples.models import upload_peopleimg
from apps.service.utils import write_file_to_dir
from apps.core.services.secure_file_download_service import SecureFileDownloadService
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404

User = get_user_model()

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """Print section header."""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{text.center(80)}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_test(name, passed, details=""):
    """Print test result."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"      {YELLOW}{details}{RESET}")


def test_upload_peopleimg_security():
    """Test upload_peopleimg() path traversal prevention."""
    print_header("Testing upload_peopleimg() Security")

    from apps.onboarding.models import Bt

    # Create test data
    try:
        client = Bt.objects.create(
            bucode='VALTEST',
            buname='Validation Test',
            butype='CLIENT'
        )

        user = User.objects.create(
            loginid='val_user',
            peoplecode='VAL001',
            peoplename='Validation User',
            email='val@example.com',
            dateofbirth='1990-01-01',
            client=client
        )
    except Exception as e:
        # User might already exist
        user = User.objects.filter(loginid='val_user').first()
        if not user:
            print_test("User creation", False, str(e))
            return False

    # Test 1: Path traversal prevention
    malicious_filename = '../../../etc/passwd'
    result = upload_peopleimg(user, malicious_filename)
    test_1_passed = '..' not in result and '/etc/' not in result
    print_test(
        "Path traversal prevention (../../../etc/passwd)",
        test_1_passed,
        f"Result: {result}"
    )

    # Test 2: Null byte injection
    result = upload_peopleimg(user, 'image.jpg\x00.php')
    test_2_passed = '\x00' not in result and '.php' not in result
    print_test(
        "Null byte injection prevention",
        test_2_passed,
        f"Result: {result}"
    )

    # Test 3: Script extension rejection
    result = upload_peopleimg(user, 'malware.exe')
    test_3_passed = result == "master/people/blank.png"
    print_test(
        "Script extension rejection",
        test_3_passed,
        f"Result: {result}"
    )

    # Test 4: Valid extension acceptance
    result = upload_peopleimg(user, 'photo.jpg')
    test_4_passed = result != "master/people/blank.png" and '.jpg' in result
    print_test(
        "Valid extension acceptance",
        test_4_passed,
        f"Result: {result}"
    )

    return test_1_passed and test_2_passed and test_3_passed and test_4_passed


def test_write_file_to_dir_security():
    """Test write_file_to_dir() security."""
    print_header("Testing write_file_to_dir() Security")

    # Test 1: Path traversal rejection
    try:
        write_file_to_dir(b'malicious', '../../../etc/cron.d/evil')
        print_test("Path traversal rejection", False, "Expected exception not raised")
        test_1_passed = False
    except (ValueError, PermissionError):
        print_test("Path traversal rejection", True, "Exception raised as expected")
        test_1_passed = True

    # Test 2: Empty buffer rejection
    try:
        write_file_to_dir(b'', 'test.txt')
        print_test("Empty buffer rejection", False, "Expected exception not raised")
        test_2_passed = False
    except ValueError:
        print_test("Empty buffer rejection", True, "Exception raised as expected")
        test_2_passed = True

    # Test 3: Null byte handling
    try:
        result = write_file_to_dir(b'content', 'file\x00.php')
        # Should either reject or strip null bytes
        test_3_passed = '\x00' not in result
        print_test("Null byte handling", test_3_passed, f"Result: {result}")
    except (ValueError, PermissionError):
        print_test("Null byte handling", True, "Rejected as expected")
        test_3_passed = True

    return test_1_passed and test_2_passed and test_3_passed


def test_secure_download_service():
    """Test SecureFileDownloadService security."""
    print_header("Testing SecureFileDownloadService Security")

    # Get or create test user
    try:
        user = User.objects.filter(loginid='val_user').first()
        if not user:
            print_test("User retrieval", False, "Test user not found")
            return False
    except Exception as e:
        print_test("User retrieval", False, str(e))
        return False

    # Test 1: Path traversal prevention
    try:
        SecureFileDownloadService.validate_and_serve_file(
            filepath='../../../etc',
            filename='passwd',
            user=user
        )
        print_test("Path traversal prevention", False, "Expected exception not raised")
        test_1_passed = False
    except (Http404, SuspiciousFileOperation):
        print_test("Path traversal prevention", True, "Exception raised as expected")
        test_1_passed = True

    # Test 2: Unauthenticated access prevention
    try:
        SecureFileDownloadService.validate_and_serve_file(
            filepath='uploads',
            filename='test.txt',
            user=None
        )
        print_test("Unauthenticated access prevention", False, "Expected exception not raised")
        test_2_passed = False
    except PermissionDenied:
        print_test("Unauthenticated access prevention", True, "Exception raised as expected")
        test_2_passed = True

    # Test 3: Absolute path rejection
    try:
        SecureFileDownloadService.validate_and_serve_file(
            filepath='/etc',
            filename='passwd',
            user=user
        )
        print_test("Absolute path rejection", False, "Expected exception not raised")
        test_3_passed = False
    except (Http404, SuspiciousFileOperation):
        print_test("Absolute path rejection", True, "Exception raised as expected")
        test_3_passed = True

    return test_1_passed and test_2_passed and test_3_passed


def main():
    """Run all validation tests."""
    print_header("PATH TRAVERSAL VULNERABILITY VALIDATION")
    print(f"{YELLOW}Validating security fixes for CVSS 9.8 vulnerabilities{RESET}")

    results = []

    # Test 1: upload_peopleimg()
    results.append(("upload_peopleimg()", test_upload_peopleimg_security()))

    # Test 2: write_file_to_dir()
    results.append(("write_file_to_dir()", test_write_file_to_dir_security()))

    # Test 3: SecureFileDownloadService
    results.append(("SecureFileDownloadService", test_secure_download_service()))

    # Print summary
    print_header("VALIDATION SUMMARY")

    all_passed = all(result[1] for result in results)

    for name, passed in results:
        status = f"{GREEN}✓ SECURE{RESET}" if passed else f"{RED}✗ VULNERABLE{RESET}"
        print(f"{status} - {name}")

    print(f"\n{BLUE}{'=' * 80}{RESET}")

    if all_passed:
        print(f"\n{GREEN}✓✓✓ ALL SECURITY CHECKS PASSED ✓✓✓{RESET}")
        print(f"{GREEN}Path traversal vulnerabilities have been successfully remediated.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}✗✗✗ SOME SECURITY CHECKS FAILED ✗✗✗{RESET}")
        print(f"{RED}Path traversal vulnerabilities still present!{RESET}\n")
        return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n{RED}✗ VALIDATION SCRIPT ERROR: {str(e)}{RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)