"""
Management command for settings health check.

Validates Django settings configuration and reports any issues.

Usage:
    python manage.py settings_health_check
    python manage.py settings_health_check --environment production
    python manage.py settings_health_check --verbose
    python manage.py settings_health_check --report settings_report.json

Features:
- Validates critical settings
- Environment-specific checks
- Human-readable output
- JSON report generation
- Exit codes for CI/CD integration

Author: Claude Code
Date: 2025-10-01
"""

import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from intelliwiz_config.settings.validation import SettingsValidator, SettingsValidationError


class Command(BaseCommand):
    help = 'Validate Django settings configuration and report any issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            default='development',
            choices=['development', 'production', 'test'],
            help='Environment to validate settings for (default: development)'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed validation output including warnings'
        )

        parser.add_argument(
            '--report',
            type=str,
            help='Generate JSON report and save to specified file'
        )

        parser.add_argument(
            '--fail-on-warnings',
            action='store_true',
            help='Exit with error code if warnings are found (for strict CI/CD)'
        )

    def handle(self, *args, **options):
        environment = options['environment']
        verbose = options['verbose']
        report_file = options.get('report')
        fail_on_warnings = options['fail_on_warnings']

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'=' * 70}\n"
            f"Django Settings Health Check\n"
            f"{'=' * 70}\n"
        ))

        self.stdout.write(f"Environment: {self.style.WARNING(environment)}")
        self.stdout.write(f"Verbose: {verbose}")
        self.stdout.write(f"Fail on warnings: {fail_on_warnings}\n")

        # Create validator
        validator = SettingsValidator(settings)

        # Run validation
        try:
            validator.validate_all(environment)

            # All checks passed
            self._display_success(validator, verbose)

            # Generate report if requested
            if report_file:
                self._generate_report(validator, report_file, environment, success=True)

            # Exit with warning code if warnings exist and fail_on_warnings is set
            if validator.warnings and fail_on_warnings:
                sys.exit(2)  # Exit code 2 for warnings

            return 0

        except SettingsValidationError as e:
            # Validation failed
            self._display_failure(validator, e, verbose)

            # Generate report if requested
            if report_file:
                self._generate_report(validator, report_file, environment, success=False, error=e)

            # Exit with error code
            sys.exit(1)

        except Exception as e:
            # Unexpected error
            self.stdout.write(self.style.ERROR(
                f"\n❌ Unexpected error during validation:\n{str(e)}\n"
            ))
            raise CommandError(f"Validation failed with unexpected error: {e}")

    def _display_success(self, validator: SettingsValidator, verbose: bool):
        """Display success message."""
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Settings validation PASSED\n"
        ))

        self.stdout.write(f"Correlation ID: {validator.correlation_id}")

        if validator.warnings:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  {len(validator.warnings)} warnings found:\n"
            ))
            for warning in validator.warnings:
                self.stdout.write(f"  • {warning}")

            if not verbose:
                self.stdout.write(self.style.NOTICE(
                    "\nRun with --verbose to see detailed information"
                ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "No warnings found - settings are fully compliant!"
            ))

        self.stdout.write("")

    def _display_failure(self, validator: SettingsValidator, error: SettingsValidationError, verbose: bool):
        """Display failure message."""
        self.stdout.write(self.style.ERROR(
            f"\n❌ Settings validation FAILED\n"
        ))

        self.stdout.write(f"Correlation ID: {error.correlation_id}")
        self.stdout.write(f"Critical issues: {len(error.failed_checks)}\n")

        self.stdout.write(self.style.ERROR("Critical Issues:"))
        for i, check in enumerate(error.failed_checks, 1):
            self.stdout.write(f"  {i}. {check}")

        if validator.warnings:
            self.stdout.write(self.style.WARNING(f"\n⚠️  {len(validator.warnings)} warnings:"))
            for warning in validator.warnings:
                self.stdout.write(f"  • {warning}")

        self.stdout.write(self.style.ERROR(
            f"\n🚨 Settings must be fixed before deployment!\n"
        ))

    def _generate_report(self, validator: SettingsValidator, report_file: str,
                        environment: str, success: bool, error: SettingsValidationError = None):
        """Generate JSON report."""
        report = {
            'environment': environment,
            'correlation_id': validator.correlation_id,
            'success': success,
            'summary': {
                'failed_checks': len(validator.failed_checks),
                'warnings': len(validator.warnings),
            },
            'failed_checks': validator.failed_checks,
            'warnings': validator.warnings,
        }

        if error:
            report['error_message'] = str(error)

        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)

            self.stdout.write(self.style.SUCCESS(
                f"\n📄 Report generated: {report_file}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\n❌ Failed to generate report: {e}"
            ))
