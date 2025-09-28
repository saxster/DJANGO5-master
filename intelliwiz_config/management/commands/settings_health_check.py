"""
Django management command for settings health checks.
Validates configuration integrity, security compliance, and operational readiness.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from intelliwiz_config.settings.health_checks import run_health_check, validate_settings_compliance
import json


class Command(BaseCommand):
    help = 'Run comprehensive settings health check and compliance validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            choices=['development', 'production', 'test'],
            default='development',
            help='Environment to validate (default: development)'
        )
        parser.add_argument(
            '--compliance-only',
            action='store_true',
            help='Run only compliance validation'
        )
        parser.add_argument(
            '--json-output',
            action='store_true',
            help='Output results in JSON format'
        )
        parser.add_argument(
            '--fail-on-warnings',
            action='store_true',
            help='Exit with error code if warnings are found'
        )

    def handle(self, *args, **options):
        environment = options['environment']
        compliance_only = options['compliance_only']
        json_output = options['json_output']
        fail_on_warnings = options['fail_on_warnings']

        try:
            if compliance_only:
                results = validate_settings_compliance()
                self._output_compliance_results(results, json_output)

                if not results['line_count_compliance'] or not results['security_compliance']:
                    raise CommandError("Settings compliance validation failed")

            else:
                results = run_health_check(environment)
                self._output_health_results(results, json_output)

                if results['status'] == 'unhealthy':
                    raise CommandError(f"Settings health check failed: {len(results['errors'])} errors found")

                if fail_on_warnings and results['warnings']:
                    raise CommandError(f"Settings health check warnings: {len(results['warnings'])} warnings found")

        except Exception as e:
            if not json_output:
                self.stdout.write(
                    self.style.ERROR(f'Health check failed: {str(e)}')
                )
            raise CommandError(str(e))

    def _output_health_results(self, results, json_output):
        """Output health check results."""
        if json_output:
            self.stdout.write(json.dumps(results, indent=2))
            return

        # Console output
        self.stdout.write(
            self.style.SUCCESS('=' * 60)
        )
        self.stdout.write(
            self.style.SUCCESS(f'SETTINGS HEALTH CHECK - {results["environment"].upper()}')
        )
        self.stdout.write(
            self.style.SUCCESS('=' * 60)
        )

        # Summary
        if results['status'] == 'healthy':
            self.stdout.write(
                self.style.SUCCESS(f'✅ {results["summary"]}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ {results["summary"]}')
            )

        # Checks
        self.stdout.write('\nCHECKS PERFORMED:')
        for check in results['checks']:
            if '✓' in check:
                self.stdout.write(self.style.SUCCESS(f'  {check}'))
            elif '⚠' in check:
                self.stdout.write(self.style.WARNING(f'  {check}'))
            else:
                self.stdout.write(self.style.ERROR(f'  {check}'))

        # Errors
        if results['errors']:
            self.stdout.write('\nERRORS:')
            for error in results['errors']:
                self.stdout.write(self.style.ERROR(f'  ❌ {error}'))

        # Warnings
        if results['warnings']:
            self.stdout.write('\nWARNINGS:')
            for warning in results['warnings']:
                self.stdout.write(self.style.WARNING(f'  ⚠️  {warning}'))

        if not results['errors'] and not results['warnings']:
            self.stdout.write('\n🎉 All checks passed successfully!')

    def _output_compliance_results(self, results, json_output):
        """Output compliance validation results."""
        if json_output:
            self.stdout.write(json.dumps(results, indent=2))
            return

        # Console output
        self.stdout.write(
            self.style.SUCCESS('=' * 60)
        )
        self.stdout.write(
            self.style.SUCCESS('SETTINGS COMPLIANCE VALIDATION')
        )
        self.stdout.write(
            self.style.SUCCESS('=' * 60)
        )

        # Line count compliance
        if results['line_count_compliance']:
            self.stdout.write(
                self.style.SUCCESS('✅ Line count compliance: PASSED')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Line count compliance: FAILED')
            )

        # Security compliance
        if results['security_compliance']:
            self.stdout.write(
                self.style.SUCCESS('✅ Security compliance: PASSED')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Security compliance: FAILED')
            )

        # Violations
        if results['violations']:
            self.stdout.write('\nVIOLATIONS:')
            for violation in results['violations']:
                self.stdout.write(self.style.ERROR(f'  ❌ {violation}'))

        # Recommendations
        if results['recommendations']:
            self.stdout.write('\nRECOMMENDATIONS:')
            for recommendation in results['recommendations']:
                self.stdout.write(self.style.WARNING(f'  💡 {recommendation}'))

        if not results['violations']:
            self.stdout.write('\n🎉 All compliance checks passed!')