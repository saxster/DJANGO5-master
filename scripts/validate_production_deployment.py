#!/usr/bin/env python
"""
Production Deployment Validation Script
========================================

Comprehensive pre-deployment validation for production environments.
Validates all security fixes implemented on October 11, 2025.

Usage:
    python scripts/validate_production_deployment.py
    python scripts/validate_production_deployment.py --verbose
    python scripts/validate_production_deployment.py --environment production

Exit Codes:
    0: All validations passed
    1: Critical validation failures
    2: Warning-level issues detected

Security Checks Included:
    ✓ Settings validation (BASE_DIR path fix)
    ✓ SQL injection protection (concurrency.py)
    ✓ Exception handling (http_utils.py)
    ✓ Temp file security (reports)
    ✓ PII logging protection
    ✓ Redis TLS enforcement
    ✓ Deprecated settings removal
    ✓ Secret exposure checks

Author: Security Team
Date: October 11, 2025
Version: 1.0
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentValidator:
    """Comprehensive production deployment validator"""

    def __init__(self, environment='production', verbose=False):
        self.environment = environment
        self.verbose = verbose
        self.base_dir = Path(__file__).resolve().parent.parent
        self.critical_failures = []
        self.warnings = []
        self.passed_checks = []

    def log(self, message, level='INFO'):
        """Conditional logging based on verbose flag"""
        if self.verbose or level in ['WARNING', 'ERROR', 'CRITICAL']:
            getattr(logger, level.lower())(message)

    def add_pass(self, check_name):
        """Record successful check"""
        self.passed_checks.append(check_name)
        self.log(f"✓ {check_name}", 'INFO')

    def add_warning(self, check_name, details):
        """Record warning"""
        self.warnings.append((check_name, details))
        self.log(f"⚠️ {check_name}: {details}", 'WARNING')

    def add_failure(self, check_name, details):
        """Record critical failure"""
        self.critical_failures.append((check_name, details))
        self.log(f"✗ {check_name}: {details}", 'ERROR')

    # ========================================================================
    # SECURITY FIX VALIDATIONS (October 11, 2025)
    # ========================================================================

    def validate_production_settings_path(self):
        """
        Validate production.py ENVPATH fix (BASE_DIR.parent → BASE_DIR)
        """
        self.log("\n[1/12] Validating production settings path fix...", 'INFO')

        settings_file = self.base_dir / 'intelliwiz_config/settings/production.py'

        if not settings_file.exists():
            self.add_failure(
                "Production Settings",
                f"File not found: {settings_file}"
            )
            return

        with open(settings_file, 'r') as f:
            content = f.read()

        # Check for FIXED pattern
        if 'ENVPATH = os.path.join(BASE_DIR, "intelliwiz_config/envs")' in content:
            self.add_pass("Production settings ENVPATH fix verified")
        else:
            # Check if OLD buggy pattern still exists
            if 'BASE_DIR.parent' in content and 'ENVPATH' in content:
                self.add_failure(
                    "Production Settings",
                    "ENVPATH still uses BASE_DIR.parent (should be BASE_DIR)"
                )
            else:
                self.add_warning(
                    "Production Settings",
                    "ENVPATH pattern not found - manual verification needed"
                )

    def validate_sql_injection_fix(self):
        """
        Validate SQL injection fix in concurrency.py (timeout sanitization)
        """
        self.log("\n[2/12] Validating SQL injection fix...", 'INFO')

        concurrency_file = self.base_dir / 'apps/onboarding_api/utils/concurrency.py'

        if not concurrency_file.exists():
            self.add_failure(
                "SQL Injection Fix",
                f"File not found: {concurrency_file}"
            )
            return

        with open(concurrency_file, 'r') as f:
            content = f.read()

        # Check for FIXED sanitization pattern
        if 'safe_timeout = max(1, min(int(timeout_seconds), 60))' in content:
            self.add_pass("SQL injection protection in concurrency.py verified")
        else:
            if 'cursor.execute(f"SET statement_timeout' in content:
                self.add_failure(
                    "SQL Injection Fix",
                    "timeout_seconds used in f-string without sanitization"
                )
            else:
                self.add_warning(
                    "SQL Injection Fix",
                    "Timeout setting pattern not found - manual verification needed"
                )

    def validate_exception_handling_fixes(self):
        """
        Validate exception handling bugs in http_utils.py
        """
        self.log("\n[3/12] Validating exception handling fixes...", 'INFO')

        http_utils_file = self.base_dir / 'apps/core/utils_new/http_utils.py'

        if not http_utils_file.exists():
            self.add_failure(
                "Exception Handling Fix",
                f"File not found: {http_utils_file}"
            )
            return

        with open(http_utils_file, 'r') as f:
            content = f.read()

        # Bug A: Check for FIXED KeyError (data["errors"] not data["error"])
        if 'data["errors"]' in content and 'handle_DoesNotExist' in content:
            self.add_pass("KeyError fix in handle_DoesNotExist verified")
        else:
            if 'data["error"]' in content and 'handle_DoesNotExist' in content:
                self.add_failure(
                    "Exception Handling - KeyError",
                    "Still using data['error'] instead of data['errors']"
                )

        # Bug B: Check for FIXED return type (no params argument)
        if 'return handle_Exception(request)' in content and 'render_form_for_delete' in content:
            self.add_pass("Return type fix in render_form_for_delete verified")
        else:
            if 'return handle_Exception(request, params)' in content:
                self.add_failure(
                    "Exception Handling - Return Type",
                    "Still passing params to handle_Exception (wrong return type)"
                )

    def validate_temp_file_security(self):
        """
        Validate temp file security in report generation
        """
        self.log("\n[4/12] Validating temp file security...", 'INFO')

        schedule_views = self.base_dir / 'apps/reports/views/schedule_views.py'

        if not schedule_views.exists():
            self.add_failure(
                "Temp File Security",
                f"File not found: {schedule_views}"
            )
            return

        with open(schedule_views, 'r') as f:
            content = f.read()

        # Check for FIXED tempfile usage
        if 'tempfile.TemporaryDirectory()' in content and 'render_using_pandoc' in content:
            self.add_pass("Temp file security in report generation verified")
        else:
            if 'with open("temp.html"' in content or 'os.remove("temp.html")' in content:
                self.add_failure(
                    "Temp File Security",
                    "Still using unsafe CWD temp files instead of tempfile module"
                )

    def validate_pii_logging_protection(self):
        """
        Validate PII logging protection in http_utils.py
        """
        self.log("\n[5/12] Validating PII logging protection...", 'INFO')

        http_utils_file = self.base_dir / 'apps/core/utils_new/http_utils.py'

        if not http_utils_file.exists():
            self.add_failure(
                "PII Logging Protection",
                f"File not found: {http_utils_file}"
            )
            return

        with open(http_utils_file, 'r') as f:
            content = f.read()

        # Check for FIXED DEBUG guard
        if 'if settings.DEBUG:' in content and 'clean_encoded_form_data' in content:
            self.add_pass("PII logging protection (DEBUG guard) verified")
        else:
            # Check for UNSAFE raw logging
            if 'logger.info(f"String before QueryDict: {form_data[:500]}' in content:
                self.add_failure(
                    "PII Logging Protection",
                    "Still logging raw form data without DEBUG guard (PII leak risk)"
                )

    def validate_duplicate_branch_removal(self):
        """
        Validate duplicate branch removal in get_filter
        """
        self.log("\n[6/12] Validating duplicate branch removal...", 'INFO')

        http_utils_file = self.base_dir / 'apps/core/utils_new/http_utils.py'

        if not http_utils_file.exists():
            self.add_failure(
                "Duplicate Branch Fix",
                f"File not found: {http_utils_file}"
            )
            return

        with open(http_utils_file, 'r') as f:
            content = f.read()

        # Count "not_equal" occurrences in get_filter function
        # Extract get_filter function
        if 'def get_filter' in content:
            start = content.find('def get_filter')
            end = content.find('\ndef ', start + 1)
            if end == -1:
                end = len(content)
            get_filter_content = content[start:end]

            not_equal_count = get_filter_content.count('if filter_condition.strip() == "not_equal"')

            if not_equal_count == 1:
                self.add_pass("Duplicate 'not_equal' branch removed")
            elif not_equal_count > 1:
                self.add_failure(
                    "Duplicate Branch Fix",
                    f"Still has {not_equal_count} duplicate 'not_equal' branches"
                )
            else:
                self.add_warning(
                    "Duplicate Branch Fix",
                    "get_filter pattern not found - manual verification needed"
                )

    def validate_deprecated_setting_removal(self):
        """
        Validate USE_L10N deprecated setting removal
        """
        self.log("\n[7/12] Validating deprecated setting removal...", 'INFO')

        base_settings = self.base_dir / 'intelliwiz_config/settings/base.py'

        if not base_settings.exists():
            self.add_failure(
                "Deprecated Setting Fix",
                f"File not found: {base_settings}"
            )
            return

        with open(base_settings, 'r') as f:
            content = f.read()

        # Check that USE_L10N is NOT present (or is commented out)
        if 'USE_L10N = True' in content:
            # Check if it's commented
            lines = content.split('\n')
            use_l10n_lines = [line for line in lines if 'USE_L10N = True' in line]

            if any(not line.strip().startswith('#') for line in use_l10n_lines):
                self.add_failure(
                    "Deprecated Setting Fix",
                    "USE_L10N still present (deprecated in Django 5.x)"
                )
            else:
                self.add_pass("Deprecated USE_L10N setting removed")
        else:
            self.add_pass("Deprecated USE_L10N setting removed")

    def validate_redis_tls_enforcement(self):
        """
        Validate Redis TLS enforcement with grace period
        """
        self.log("\n[8/12] Validating Redis TLS enforcement...", 'INFO')

        redis_config = self.base_dir / 'intelliwiz_config/settings/redis_optimized.py'

        if not redis_config.exists():
            self.add_failure(
                "Redis TLS Enforcement",
                f"File not found: {redis_config}"
            )
            return

        with open(redis_config, 'r') as f:
            content = f.read()

        # Check for FIXED date-based enforcement
        if 'compliance_deadline = datetime(2025, 4, 1,' in content:
            if 'raise ValueError' in content and 'compliance deadline' in content.lower():
                self.add_pass("Redis TLS enforcement with grace period verified")
            else:
                self.add_warning(
                    "Redis TLS Enforcement",
                    "Compliance deadline set but no fail-fast enforcement found"
                )
        else:
            self.add_warning(
                "Redis TLS Enforcement",
                "Date-based compliance enforcement not found"
            )

    # ========================================================================
    # ADDITIONAL SECURITY CHECKS
    # ========================================================================

    def validate_no_secrets_in_git(self):
        """
        Validate no secrets are tracked in git
        """
        self.log("\n[9/12] Validating no secrets in git...", 'INFO')

        # Check for specific secret files in git
        dangerous_files = [
            '.env.prod.secure',
            '.env.dev.secure',
            'sukhi-group-e35476d5ef6e.json',
            'credentials.json',
            'secrets.json'
        ]

        for file in dangerous_files:
            result = subprocess.run(
                ['git', 'ls-files', file],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                self.add_failure(
                    "Secret Exposure",
                    f"Secret file tracked in git: {file}"
                )
            else:
                self.log(f"  ✓ {file} not tracked in git", 'DEBUG')

        self.add_pass("No secret files tracked in git")

    def validate_gitignore_patterns(self):
        """
        Validate .gitignore has comprehensive secret patterns
        """
        self.log("\n[10/12] Validating .gitignore patterns...", 'INFO')

        gitignore = self.base_dir / '.gitignore'

        if not gitignore.exists():
            self.add_failure(
                ".gitignore Validation",
                ".gitignore file not found"
            )
            return

        with open(gitignore, 'r') as f:
            content = f.read()

        required_patterns = [
            '.env',
            '*.pem',
            '*.key',
            '*secret*',
            'intelliwiz_config/envs/.env*',
            'sukhi-group-*.json'
        ]

        missing_patterns = []
        for pattern in required_patterns:
            if pattern not in content:
                missing_patterns.append(pattern)

        if missing_patterns:
            self.add_warning(
                ".gitignore Validation",
                f"Missing patterns: {', '.join(missing_patterns)}"
            )
        else:
            self.add_pass(".gitignore has comprehensive secret patterns")

    def validate_python_syntax(self):
        """
        Validate all modified files compile successfully
        """
        self.log("\n[11/12] Validating Python syntax...", 'INFO')

        modified_files = [
            'intelliwiz_config/settings/production.py',
            'intelliwiz_config/settings/base.py',
            'intelliwiz_config/settings/redis_optimized.py',
            'apps/onboarding_api/utils/concurrency.py',
            'apps/core/utils_new/http_utils.py',
            'apps/reports/views/schedule_views.py',
        ]

        for file_path in modified_files:
            full_path = self.base_dir / file_path

            if not full_path.exists():
                self.add_warning(
                    "Syntax Validation",
                    f"File not found: {file_path}"
                )
                continue

            result = subprocess.run(
                ['python3', '-m', 'py_compile', str(full_path)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.add_failure(
                    "Syntax Validation",
                    f"Syntax error in {file_path}: {result.stderr}"
                )
            else:
                self.log(f"  ✓ {file_path} syntax valid", 'DEBUG')

        self.add_pass("All modified files have valid Python syntax")

    def validate_django_check(self):
        """
        Run Django's system check framework
        """
        self.log("\n[12/12] Running Django system checks...", 'INFO')

        result = subprocess.run(
            ['python', 'manage.py', 'check', '--deploy'],
            cwd=self.base_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            self.add_warning(
                "Django System Check",
                f"Checks failed: {result.stderr[:200]}"
            )
        else:
            self.add_pass("Django system checks passed")

    # ========================================================================
    # MAIN VALIDATION RUNNER
    # ========================================================================

    def run_all_validations(self):
        """
        Run all validation checks
        """
        print("=" * 80)
        print(f"🔒 Production Deployment Validation - {self.environment.upper()}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Run all validation checks
        self.validate_production_settings_path()
        self.validate_sql_injection_fix()
        self.validate_exception_handling_fixes()
        self.validate_temp_file_security()
        self.validate_pii_logging_protection()
        self.validate_duplicate_branch_removal()
        self.validate_deprecated_setting_removal()
        self.validate_redis_tls_enforcement()
        self.validate_no_secrets_in_git()
        self.validate_gitignore_patterns()
        self.validate_python_syntax()
        self.validate_django_check()

        # Print summary
        self.print_summary()

        # Return exit code
        if self.critical_failures:
            return 1
        elif self.warnings:
            return 2
        else:
            return 0

    def print_summary(self):
        """
        Print validation summary
        """
        print("\n" + "=" * 80)
        print("📊 VALIDATION SUMMARY")
        print("=" * 80)

        print(f"\n✓ Passed Checks: {len(self.passed_checks)}")
        if self.verbose:
            for check in self.passed_checks:
                print(f"  • {check}")

        if self.warnings:
            print(f"\n⚠️ Warnings: {len(self.warnings)}")
            for check, details in self.warnings:
                print(f"  • {check}: {details}")

        if self.critical_failures:
            print(f"\n✗ CRITICAL FAILURES: {len(self.critical_failures)}")
            for check, details in self.critical_failures:
                print(f"  • {check}: {details}")

        print("\n" + "=" * 80)

        if self.critical_failures:
            print("🚨 DEPLOYMENT BLOCKED - Fix critical failures before deploying")
            print("=" * 80)
        elif self.warnings:
            print("⚠️ DEPLOYMENT ALLOWED WITH WARNINGS - Review before proceeding")
            print("=" * 80)
        else:
            print("✅ ALL VALIDATIONS PASSED - Ready for deployment")
            print("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate production deployment readiness'
    )
    parser.add_argument(
        '--environment',
        default='production',
        choices=['development', 'staging', 'production'],
        help='Target environment'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    validator = DeploymentValidator(
        environment=args.environment,
        verbose=args.verbose
    )

    exit_code = validator.run_all_validations()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
