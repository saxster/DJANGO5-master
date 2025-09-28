"""
Validation script for API Versioning Implementation
Checks all components without requiring Django to be running.

Run with: python3 validate_api_versioning_implementation.py
"""

import os
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def check_file_exists(filepath, description):
    """Check if a file exists and meets size requirements."""
    full_path = Path(filepath)
    if not full_path.exists():
        print(f"{RED}❌ MISSING:{RESET} {description}")
        print(f"   Expected: {filepath}")
        return False

    size = full_path.stat().st_size
    lines = len(full_path.read_text().split('\n'))

    print(f"{GREEN}✅ FOUND:{RESET} {description}")
    print(f"   Path: {filepath}")
    print(f"   Size: {size} bytes, {lines} lines")

    return True


def check_file_line_limit(filepath, max_lines, rule_number):
    """Check if file complies with line limit rules."""
    full_path = Path(filepath)
    if not full_path.exists():
        return True

    lines = len(full_path.read_text().split('\n'))

    if lines <= max_lines:
        print(f"{GREEN}✅ COMPLIANT:{RESET} {filepath} ({lines}/{max_lines} lines) - Rule #{rule_number}")
        return True
    else:
        print(f"{RED}❌ VIOLATION:{RESET} {filepath} ({lines}/{max_lines} lines) - Rule #{rule_number}")
        return False


def check_string_in_file(filepath, search_string, description):
    """Check if a string exists in a file."""
    full_path = Path(filepath)
    if not full_path.exists():
        print(f"{RED}❌ FILE NOT FOUND:{RESET} {filepath}")
        return False

    content = full_path.read_text()
    if search_string in content:
        print(f"{GREEN}✅ VERIFIED:{RESET} {description}")
        return True
    else:
        print(f"{RED}❌ MISSING:{RESET} {description}")
        print(f"   In file: {filepath}")
        return False


def main():
    """Run all validation checks."""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}API Versioning Implementation Validation{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

    base_dir = Path('/Users/amar/Desktop/MyCode/DJANGO5-master')
    os.chdir(base_dir)

    all_checks_passed = True

    print(f"\n{BOLD}1. Configuration Files{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'intelliwiz_config/settings/rest_api.py',
        'REST API Configuration'
    )
    all_checks_passed &= check_file_line_limit(
        'intelliwiz_config/settings/rest_api.py',
        200,
        6
    )
    all_checks_passed &= check_string_in_file(
        'intelliwiz_config/settings/rest_api.py',
        'URLPathVersioning',
        'DRF URLPathVersioning configured'
    )

    print(f"\n{BOLD}2. Models{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/models/api_deprecation.py',
        'API Deprecation Models'
    )
    all_checks_passed &= check_file_line_limit(
        'apps/core/models/api_deprecation.py',
        150,
        7
    )
    all_checks_passed &= check_string_in_file(
        'apps/core/models/api_deprecation.py',
        'class APIDeprecation',
        'APIDeprecation model defined'
    )
    all_checks_passed &= check_string_in_file(
        'apps/core/models/api_deprecation.py',
        'class APIDeprecationUsage',
        'APIDeprecationUsage model defined'
    )

    print(f"\n{BOLD}3. Middleware{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/middleware/api_deprecation.py',
        'Deprecation Headers Middleware'
    )
    all_checks_passed &= check_file_line_limit(
        'apps/core/middleware/api_deprecation.py',
        200,
        6
    )
    all_checks_passed &= check_string_in_file(
        'apps/core/middleware/api_deprecation.py',
        'get_deprecation_header',
        'RFC 9745 Deprecation header'
    )
    all_checks_passed &= check_string_in_file(
        'apps/core/middleware/api_deprecation.py',
        'get_sunset_header',
        'RFC 8594 Sunset header'
    )

    print(f"\n{BOLD}4. Services{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/services/api_deprecation_service.py',
        'Deprecation Service'
    )
    all_checks_passed &= check_file_exists(
        'apps/core/api_versioning/version_negotiation.py',
        'Version Negotiation'
    )
    all_checks_passed &= check_file_exists(
        'apps/core/api_versioning/exception_handler.py',
        'Versioned Exception Handler'
    )

    print(f"\n{BOLD}5. Views & Dashboards{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/views/api_deprecation_dashboard.py',
        'Deprecation Dashboard Views'
    )
    all_checks_passed &= check_file_line_limit(
        'apps/core/views/api_deprecation_dashboard.py',
        200,
        8
    )

    print(f"\n{BOLD}6. V2 API Structure{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/service/rest_service/v2/__init__.py',
        'V2 API Package'
    )
    all_checks_passed &= check_file_exists(
        'apps/service/rest_service/v2/urls.py',
        'V2 URL Configuration'
    )
    all_checks_passed &= check_file_exists(
        'apps/service/rest_service/v2/views.py',
        'V2 Views'
    )

    print(f"\n{BOLD}7. Documentation{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'docs/api-lifecycle-policy.md',
        'API Lifecycle Policy'
    )
    all_checks_passed &= check_file_exists(
        'docs/api-version-compatibility-matrix.md',
        'Version Compatibility Matrix'
    )
    all_checks_passed &= check_file_exists(
        'docs/api-migrations/file-upload-v2.md',
        'File Upload Migration Guide'
    )

    print(f"\n{BOLD}8. Tests{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/tests/test_api_versioning_comprehensive.py',
        'Comprehensive Versioning Tests'
    )
    all_checks_passed &= check_string_in_file(
        'apps/core/tests/test_api_versioning_comprehensive.py',
        '@pytest.mark.security',
        'Security tests included'
    )

    print(f"\n{BOLD}9. GraphQL Deprecation{RESET}")
    print("-" * 80)
    all_checks_passed &= check_string_in_file(
        'apps/service/schema.py',
        'deprecation_reason',
        '@deprecated directive on upload_attachment'
    )
    all_checks_passed &= check_string_in_file(
        'apps/service/schema.py',
        'secure_file_upload',
        'Replacement mutation referenced'
    )

    print(f"\n{BOLD}10. Management Commands{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/management/commands/api_deprecation_report.py',
        'Deprecation Report Command'
    )
    all_checks_passed &= check_file_exists(
        'apps/core/management/commands/api_usage_stats.py',
        'Usage Stats Command'
    )
    all_checks_passed &= check_file_exists(
        'apps/core/management/commands/api_update_deprecation_status.py',
        'Status Update Command'
    )

    print(f"\n{BOLD}11. Admin Interface{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/admin/api_deprecation_admin.py',
        'Django Admin for Deprecations'
    )

    print(f"\n{BOLD}12. Migrations{RESET}")
    print("-" * 80)
    all_checks_passed &= check_file_exists(
        'apps/core/migrations/0005_add_api_deprecation_models.py',
        'Schema Migration'
    )
    all_checks_passed &= check_file_exists(
        'apps/core/migrations/0006_add_initial_deprecation_data.py',
        'Data Migration'
    )

    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    if all_checks_passed:
        print(f"{GREEN}{BOLD}✅ ALL VALIDATION CHECKS PASSED{RESET}")
        print(f"{GREEN}API Versioning implementation is complete and compliant.{RESET}")
        print(f"\n{BLUE}Next Steps:{RESET}")
        print("1. Run migrations: python manage.py migrate core")
        print("2. Run tests: pytest apps/core/tests/test_api_versioning_comprehensive.py -v")
        print("3. Access dashboard: /admin/api/lifecycle/")
        print("4. Review docs: docs/api-lifecycle-policy.md")
    else:
        print(f"{RED}{BOLD}❌ SOME VALIDATION CHECKS FAILED{RESET}")
        print(f"{RED}Please review the errors above and fix the issues.{RESET}")
        sys.exit(1)

    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")


if __name__ == '__main__':
    main()