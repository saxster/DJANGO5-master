#!/usr/bin/env python3
"""
Validation Script for Logging Security Implementation.

Tests critical logging security components without requiring Django/pytest:
- LogSanitizationMiddleware enabled
- SanitizingFilter properly configured
- Critical fixes applied
- Services created and importable
- Migration guide exists

Run: python3 validate_logging_security_implementation.py
"""

import os
import sys
import re
from pathlib import Path


class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_test(name, passed, details=""):
    """Print test result."""
    status = f"{Colors.GREEN}✅ PASS{Colors.NC}" if passed else f"{Colors.RED}❌ FAIL{Colors.NC}"
    print(f"{status} - {name}")
    if details and not passed:
        print(f"     {Colors.YELLOW}{details}{Colors.NC}")


def test_middleware_enabled():
    """Test LogSanitizationMiddleware is in MIDDLEWARE list."""
    settings_path = "intelliwiz_config/settings/base.py"

    with open(settings_path, 'r') as f:
        content = f.read()

    enabled = 'apps.core.middleware.logging_sanitization.LogSanitizationMiddleware' in content

    print_test(
        "LogSanitizationMiddleware enabled in settings",
        enabled,
        f"Middleware not found in {settings_path}"
    )
    return enabled


def test_sanitizing_filter_exists():
    """Test SanitizingFilter class exists."""
    middleware_path = "apps/core/middleware/logging_sanitization.py"

    with open(middleware_path, 'r') as f:
        content = f.read()

    exists = 'class SanitizingFilter(logging.Filter):' in content

    print_test(
        "SanitizingFilter class created",
        exists,
        f"SanitizingFilter not found in {middleware_path}"
    )
    return exists


def test_logging_config_has_filter():
    """Test logging configuration includes sanitization filter."""
    logging_path = "intelliwiz_config/settings/logging.py"

    with open(logging_path, 'r') as f:
        content = f.read()

    has_filters = '"sanitize"' in content or "'sanitize'" in content
    has_filter_function = '_get_filters()' in content

    passed = has_filters and has_filter_function

    print_test(
        "Logging configuration includes sanitization filter",
        passed,
        f"Filter configuration not found in {logging_path}"
    )
    return passed


def test_password_logging_fixed():
    """Test authentication service password logging is fixed."""
    auth_service_path = "apps/peoples/services/authentication_service.py"

    with open(auth_service_path, 'r') as f:
        content = f.read()

    password_in_error = '"Authentication failed for user %s with password %s"' in content

    fixed = not password_in_error

    print_test(
        "Password logging removed from authentication service",
        fixed,
        f"Password still in error message template at line 90"
    )
    return fixed


def test_email_logging_fixed():
    """Test background tasks email logging is fixed."""
    tasks_path = "background_tasks/tasks.py"

    with open(tasks_path, 'r') as f:
        content = f.read()

    email_logging = bool(re.search(r'logger\.info\(f".*\{p\[.email.\].*=', content))

    fixed = not email_logging

    print_test(
        "Email address logging removed from background tasks",
        fixed,
        "Email logging patterns still found in background_tasks/tasks.py"
    )
    return fixed


def test_services_created():
    """Test all required services exist."""
    services = [
        "apps/core/services/log_rotation_monitoring_service.py",
        "apps/core/services/log_access_auditing_service.py",
        "apps/core/services/realtime_log_scanner_service.py",
        "apps/core/services/pii_detection_service.py",
        "apps/core/services/logging_compliance_service.py",
    ]

    all_exist = all(os.path.exists(service) for service in services)

    print_test(
        "All logging security services created",
        all_exist,
        "Some services missing: " + ", ".join([s for s in services if not os.path.exists(s)])
    )
    return all_exist


def test_security_settings_module():
    """Test logging security settings module exists."""
    settings_path = "intelliwiz_config/settings/security/logging.py"

    exists = os.path.exists(settings_path)

    if exists:
        with open(settings_path, 'r') as f:
            content = f.read()

        has_config = 'LOG_RETENTION_DAYS' in content and 'COMPLIANCE_SETTINGS' in content
    else:
        has_config = False

    print_test(
        "Logging security settings module created",
        exists and has_config,
        f"Module missing or incomplete at {settings_path}"
    )
    return exists and has_config


def test_migration_guide_exists():
    """Test migration guide documentation exists."""
    guide_path = "docs/security/LOGGING_SECURITY_MIGRATION_GUIDE.md"

    exists = os.path.exists(guide_path)

    if exists:
        with open(guide_path, 'r') as f:
            content = f.read()

        comprehensive = (
            'get_sanitized_logger' in content and
            'BEFORE' in content and
            'AFTER' in content and
            'Prohibited Patterns' in content
        )
    else:
        comprehensive = False

    print_test(
        "Migration guide documentation created",
        exists and comprehensive,
        f"Migration guide missing or incomplete"
    )
    return exists and comprehensive


def test_error_handling_sanitizes_tracebacks():
    """Test error handling sanitizes tracebacks."""
    error_handling_path = "apps/core/error_handling.py"

    with open(error_handling_path, 'r') as f:
        content = f.read()

    imports_sanitization = 'from apps.core.middleware.logging_sanitization import LogSanitizationService' in content
    sanitizes_traceback = 'LogSanitizationService.sanitize_message' in content and 'traceback' in content

    passed = imports_sanitization and sanitizes_traceback

    print_test(
        "Error handling sanitizes tracebacks",
        passed,
        "LogSanitizationService not used in error_handling.py"
    )
    return passed


def test_comprehensive_tests_exist():
    """Test comprehensive test suite exists."""
    test_path = "apps/core/tests/test_logging_security_comprehensive.py"

    exists = os.path.exists(test_path)

    if exists:
        with open(test_path, 'r') as f:
            content = f.read()

        has_tests = (
            'LogRotationMonitoringServiceTest' in content and
            'LogAccessAuditingServiceTest' in content and
            'PIIDetectionServiceTest' in content
        )
    else:
        has_tests = False

    print_test(
        "Comprehensive test suite created",
        exists and has_tests,
        f"Test suite missing or incomplete"
    )
    return exists and has_tests


def test_audit_script_exists():
    """Test standalone audit script exists."""
    script_path = "scripts/audit_logging_security_standalone.py"

    exists = os.path.exists(script_path)

    if exists:
        with open(script_path, 'r') as f:
            content = f.read()

        is_executable = 'if __name__' in content
    else:
        is_executable = False

    print_test(
        "Standalone audit script created",
        exists and is_executable,
        f"Audit script missing or incomplete"
    )
    return exists and is_executable


def main():
    """Run all validation tests."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}🔒 LOGGING SECURITY IMPLEMENTATION VALIDATION{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}\n")

    tests = [
        ("Middleware Configuration", test_middleware_enabled),
        ("Sanitization Filter", test_sanitizing_filter_exists),
        ("Logging Config Integration", test_logging_config_has_filter),
        ("Security Settings Module", test_security_settings_module),
        ("Password Logging Fix", test_password_logging_fixed),
        ("Email Logging Fix", test_email_logging_fixed),
        ("Services Creation", test_services_created),
        ("Error Handling Enhancement", test_error_handling_sanitizes_tracebacks),
        ("Migration Guide", test_migration_guide_exists),
        ("Comprehensive Tests", test_comprehensive_tests_exist),
        ("Audit Script", test_audit_script_exists),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print_test(test_name, False, f"Test error: {e}")
            results.append(False)

    passed = sum(results)
    total = len(results)

    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}📊 VALIDATION SUMMARY{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}\n")
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {(passed/total*100):.1f}%\n")

    if passed == total:
        print(f"{Colors.GREEN}✅ ALL VALIDATIONS PASSED{Colors.NC}")
        print(f"\n{Colors.GREEN}Logging security implementation is complete and compliant with Rule #15{Colors.NC}\n")
        return 0
    else:
        print(f"{Colors.RED}❌ {total - passed} VALIDATION(S) FAILED{Colors.NC}")
        print(f"\n{Colors.YELLOW}Please fix the failing validations before proceeding.{Colors.NC}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())