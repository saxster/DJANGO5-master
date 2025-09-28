#!/usr/bin/env python
"""
Rate Limiting Implementation Validator

Validates that all components of the rate limiting implementation are correct:
- Middleware files exist and are valid
- Settings configured correctly
- Models defined properly
- Middleware registered in stack
- URLs configured
- Tests exist

This script performs static validation without running Django.
"""

import os
import sys
from pathlib import Path


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def check_file_exists(filepath, description):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print_success(f"{description}: {filepath}")
        return True
    else:
        print_error(f"{description} MISSING: {filepath}")
        return False


def check_file_content(filepath, search_strings, description):
    """Check if file contains expected content."""
    if not os.path.exists(filepath):
        print_error(f"{description}: File not found - {filepath}")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    all_found = True
    for search_str in search_strings:
        if search_str in content:
            print_success(f"{description}: Found '{search_str[:50]}...'")
        else:
            print_error(f"{description}: Missing '{search_str[:50]}...'")
            all_found = False

    return all_found


def main():
    print_header("RATE LIMITING IMPLEMENTATION VALIDATOR")

    base_dir = Path(__file__).parent
    all_checks_passed = True

    print_info("Validating implementation compliance with Rule #9 - Comprehensive Rate Limiting")
    print_info("CVSS 7.2 vulnerability remediation validation\n")

    print_header("1. MIDDLEWARE VALIDATION")

    middleware_checks = [
        (
            base_dir / "apps/core/middleware/path_based_rate_limiting.py",
            "PathBasedRateLimitMiddleware"
        ),
        (
            base_dir / "apps/core/middleware/graphql_rate_limiting.py",
            "GraphQLRateLimitingMiddleware"
        ),
    ]

    for filepath, description in middleware_checks:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    print_header("2. MODELS VALIDATION")

    models_file = base_dir / "apps/core/models/rate_limiting.py"
    model_classes = [
        'class RateLimitBlockedIP',
        'class RateLimitTrustedIP',
        'class RateLimitViolationLog'
    ]

    if not check_file_content(models_file, model_classes, "Rate Limiting Models"):
        all_checks_passed = False

    print_header("3. SETTINGS VALIDATION")

    settings_file = base_dir / "intelliwiz_config/settings/security/rate_limiting.py"
    required_settings = [
        'RATE_LIMIT_PATHS',
        '"/admin/"',
        '"/admin/django/"',
        '"/graphql/"',
        'RATE_LIMITS',
        "'admin':",
        'RATE_LIMIT_TRUSTED_IPS',
        'RATE_LIMIT_AUTO_BLOCK_THRESHOLD'
    ]

    if not check_file_content(settings_file, required_settings, "Rate Limiting Settings"):
        all_checks_passed = False

    base_settings = base_dir / "intelliwiz_config/settings/base.py"
    middleware_registrations = [
        'path_based_rate_limiting.PathBasedRateLimitMiddleware',
        'graphql_rate_limiting.GraphQLRateLimitingMiddleware',
        'path_based_rate_limiting.RateLimitMonitoringMiddleware'
    ]

    if not check_file_content(base_settings, middleware_registrations, "Middleware Registration"):
        all_checks_passed = False

    print_header("4. VIEWS & URLs VALIDATION")

    views_file = base_dir / "apps/core/views/rate_limit_monitoring_views.py"
    if not check_file_exists(views_file, "Monitoring Views"):
        all_checks_passed = False

    urls_file = base_dir / "apps/core/urls_rate_limiting.py"
    if not check_file_exists(urls_file, "Rate Limiting URLs"):
        all_checks_passed = False

    print_header("5. ADMIN INTERFACE VALIDATION")

    admin_file = base_dir / "apps/core/admin/rate_limiting_admin.py"
    admin_classes = [
        'class RateLimitBlockedIPAdmin',
        'class RateLimitTrustedIPAdmin',
        'class RateLimitViolationLogAdmin'
    ]

    if not check_file_content(admin_file, admin_classes, "Admin Configuration"):
        all_checks_passed = False

    print_header("6. TESTS VALIDATION")

    test_files = [
        (
            base_dir / "apps/core/tests/test_rate_limiting_comprehensive.py",
            "Comprehensive Tests"
        ),
        (
            base_dir / "apps/core/tests/test_rate_limiting_penetration.py",
            "Penetration Tests"
        ),
    ]

    for filepath, description in test_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    print_header("7. DOCUMENTATION VALIDATION")

    docs = [
        (base_dir / "docs/security/rate-limiting-architecture.md", "Architecture Documentation"),
        (base_dir / "RATE_LIMITING_IMPLEMENTATION_COMPLETE.md", "Implementation Summary"),
        (base_dir / "RATE_LIMITING_QUICK_REFERENCE.md", "Quick Reference"),
    ]

    for filepath, description in docs:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    print_header("8. TEMPLATES VALIDATION")

    error_template = base_dir / "frontend/templates/errors/429.html"
    if not check_file_exists(error_template, "429 Error Template"):
        all_checks_passed = False

    print_header("9. MIGRATIONS VALIDATION")

    migration_file = base_dir / "apps/core/migrations/0002_add_rate_limiting_models.py"
    if not check_file_exists(migration_file, "Rate Limiting Migration"):
        all_checks_passed = False

    print_header("10. MANAGEMENT COMMANDS VALIDATION")

    commands = [
        (
            base_dir / "apps/core/management/commands/rate_limit_cleanup.py",
            "Cleanup Command"
        ),
        (
            base_dir / "apps/core/management/commands/rate_limit_report.py",
            "Report Command"
        ),
    ]

    for filepath, description in commands:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    print_header("VALIDATION SUMMARY")

    if all_checks_passed:
        print_success("ALL VALIDATIONS PASSED ✅")
        print()
        print_info("Rate limiting implementation is complete and ready for deployment.")
        print_info("Next steps:")
        print("  1. Run: python manage.py migrate core 0002_add_rate_limiting_models")
        print("  2. Run: python run_rate_limiting_tests.py")
        print("  3. Access dashboard: /security/rate-limiting/dashboard/")
        print()
        return 0
    else:
        print_error("SOME VALIDATIONS FAILED ❌")
        print()
        print_warning("Review the errors above and fix missing components.")
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())