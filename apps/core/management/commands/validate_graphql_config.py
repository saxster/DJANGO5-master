"""
Management command to validate GraphQL configuration.

Usage:
    python manage.py validate_graphql_config
    python manage.py validate_graphql_config --environment production
    python manage.py validate_graphql_config --report
    python manage.py validate_graphql_config --check-duplicates

This command helps maintain GraphQL settings centralization by:
1. Validating all settings are loaded correctly
2. Checking for duplicate definitions
3. Verifying environment-specific settings
4. Generating configuration reports
"""

import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from pathlib import Path


class Command(BaseCommand):
    help = 'Validate GraphQL configuration and check for settings duplication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            choices=['development', 'production', 'test'],
            help='Validate settings for specific environment'
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate detailed configuration report'
        )
        parser.add_argument(
            '--check-duplicates',
            action='store_true',
            help='Check for duplicate GraphQL settings in base.py'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix detected issues (use with caution)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  GraphQL Configuration Validation'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        errors = []
        warnings = []
        passed_checks = []

        # Run validation checks
        errors, warnings, passed = self.validate_settings_loaded()
        errors.extend(errors)
        warnings.extend(warnings)
        passed_checks.extend(passed)

        if options['check_duplicates']:
            dup_errors, dup_warnings = self.check_for_duplicates()
            errors.extend(dup_errors)
            warnings.extend(dup_warnings)

        if options['environment']:
            env_errors, env_warnings, env_passed = self.validate_environment(
                options['environment']
            )
            errors.extend(env_errors)
            warnings.extend(env_warnings)
            passed_checks.extend(env_passed)

        # Display results
        self.display_results(passed_checks, warnings, errors)

        if options['report']:
            self.generate_report()

        # Exit with appropriate status
        if errors:
            raise CommandError(f'GraphQL configuration validation failed with {len(errors)} error(s)')

        self.stdout.write(self.style.SUCCESS('\n✅ GraphQL configuration validation passed!\n'))

    def validate_settings_loaded(self):
        """Validate that all required GraphQL settings are loaded."""
        errors = []
        warnings = []
        passed = []

        required_settings = [
            'GRAPHQL_PATHS',
            'ENABLE_GRAPHQL_RATE_LIMITING',
            'GRAPHQL_RATE_LIMIT_MAX',
            'GRAPHQL_RATE_LIMIT_WINDOW',
            'GRAPHQL_MAX_QUERY_DEPTH',
            'GRAPHQL_MAX_QUERY_COMPLEXITY',
            'GRAPHQL_MAX_MUTATIONS_PER_REQUEST',
            'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION',
            'GRAPHQL_ENABLE_VALIDATION_CACHE',
            'GRAPHQL_VALIDATION_CACHE_TTL',
            'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
            'GRAPHQL_CSRF_HEADER_NAMES',
            'GRAPHQL_ALLOWED_ORIGINS',
            'GRAPHQL_STRICT_ORIGIN_VALIDATION',
            'GRAPHQL_SECURITY_LOGGING',
            'GRAPHQL_JWT',
        ]

        for setting in required_settings:
            if not hasattr(settings, setting):
                errors.append(f'Missing required setting: {setting}')
            else:
                passed.append(f'Setting loaded: {setting}')

        # Validate setting values
        if hasattr(settings, 'GRAPHQL_RATE_LIMIT_MAX'):
            if settings.GRAPHQL_RATE_LIMIT_MAX <= 0:
                errors.append('GRAPHQL_RATE_LIMIT_MAX must be positive')
            elif settings.GRAPHQL_RATE_LIMIT_MAX > 10000:
                warnings.append('GRAPHQL_RATE_LIMIT_MAX is very high (>10000) - possible DoS risk')
            else:
                passed.append(f'Rate limit: {settings.GRAPHQL_RATE_LIMIT_MAX} (reasonable)')

        if hasattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH'):
            if settings.GRAPHQL_MAX_QUERY_DEPTH <= 0 or settings.GRAPHQL_MAX_QUERY_DEPTH > 50:
                errors.append('GRAPHQL_MAX_QUERY_DEPTH must be between 1 and 50')
            else:
                passed.append(f'Query depth: {settings.GRAPHQL_MAX_QUERY_DEPTH} (safe)')

        if hasattr(settings, 'GRAPHQL_PATHS'):
            if not settings.GRAPHQL_PATHS:
                errors.append('GRAPHQL_PATHS cannot be empty')
            else:
                passed.append(f'GraphQL paths: {len(settings.GRAPHQL_PATHS)} endpoint(s)')

        return errors, warnings, passed

    def check_for_duplicates(self):
        """Check for duplicate GraphQL settings definitions in base.py."""
        errors = []
        warnings = []

        base_settings_path = Path(settings.BASE_DIR) / 'intelliwiz_config' / 'settings' / 'base.py'

        if not base_settings_path.exists():
            warnings.append(f'Could not find base settings file: {base_settings_path}')
            return errors, warnings

        with open(base_settings_path, 'r') as f:
            base_content = f.read()

        # Patterns that should NOT appear as direct assignments
        forbidden_patterns = [
            (r'^GRAPHQL_PATHS\s*=\s*\[', 'GRAPHQL_PATHS direct assignment'),
            (r'^ENABLE_GRAPHQL_RATE_LIMITING\s*=\s*True', 'ENABLE_GRAPHQL_RATE_LIMITING direct assignment'),
            (r'^GRAPHQL_RATE_LIMIT_MAX\s*=\s*\d+', 'GRAPHQL_RATE_LIMIT_MAX direct assignment'),
            (r'^GRAPHQL_MAX_QUERY_DEPTH\s*=\s*\d+', 'GRAPHQL_MAX_QUERY_DEPTH direct assignment'),
            (r'^GRAPHQL_SECURITY_LOGGING\s*=\s*\{', 'GRAPHQL_SECURITY_LOGGING direct assignment'),
        ]

        for pattern, description in forbidden_patterns:
            matches = re.findall(pattern, base_content, re.MULTILINE)
            if matches:
                errors.append(f'Found duplicate GraphQL setting in base.py: {description}')
                self.stdout.write(self.style.ERROR(f'  ❌ {description}'))

        # Check that import statement exists
        if 'from .security.graphql import' not in base_content:
            errors.append('base.py does not import from security.graphql module')
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ base.py imports from security module'))

        return errors, warnings

    def validate_environment(self, environment):
        """Validate settings for specific environment."""
        errors = []
        warnings = []
        passed = []

        if environment == 'production':
            # Production must have strict security settings
            if not settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION:
                errors.append('Production MUST disable GraphQL introspection')
            else:
                passed.append('Introspection disabled in production ✓')

            if not settings.GRAPHQL_STRICT_ORIGIN_VALIDATION:
                errors.append('Production MUST enable strict origin validation')
            else:
                passed.append('Strict origin validation enabled ✓')

            if settings.GRAPHQL_RATE_LIMIT_MAX > 200:
                warnings.append(f'Production rate limit ({settings.GRAPHQL_RATE_LIMIT_MAX}) seems high')
            else:
                passed.append(f'Production rate limit: {settings.GRAPHQL_RATE_LIMIT_MAX} ✓')

        elif environment == 'development':
            # Development should have relaxed settings
            if settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION:
                warnings.append('Development has introspection disabled (may hinder debugging)')

            if settings.GRAPHQL_RATE_LIMIT_MAX < 100:
                warnings.append('Development rate limit seems too restrictive for testing')
            else:
                passed.append(f'Development rate limit: {settings.GRAPHQL_RATE_LIMIT_MAX} ✓')

        return errors, warnings, passed

    def generate_report(self):
        """Generate detailed configuration report."""
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  GraphQL Configuration Report'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        report_sections = [
            ('Endpoint Configuration', [
                ('GRAPHQL_PATHS', settings.GRAPHQL_PATHS),
            ]),
            ('Rate Limiting', [
                ('ENABLE_GRAPHQL_RATE_LIMITING', settings.ENABLE_GRAPHQL_RATE_LIMITING),
                ('GRAPHQL_RATE_LIMIT_MAX', settings.GRAPHQL_RATE_LIMIT_MAX),
                ('GRAPHQL_RATE_LIMIT_WINDOW', f'{settings.GRAPHQL_RATE_LIMIT_WINDOW}s'),
            ]),
            ('Query Complexity Limits', [
                ('GRAPHQL_MAX_QUERY_DEPTH', settings.GRAPHQL_MAX_QUERY_DEPTH),
                ('GRAPHQL_MAX_QUERY_COMPLEXITY', settings.GRAPHQL_MAX_QUERY_COMPLEXITY),
                ('GRAPHQL_MAX_MUTATIONS_PER_REQUEST', settings.GRAPHQL_MAX_MUTATIONS_PER_REQUEST),
                ('GRAPHQL_ENABLE_COMPLEXITY_VALIDATION', settings.GRAPHQL_ENABLE_COMPLEXITY_VALIDATION),
            ]),
            ('Security Settings', [
                ('GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION', settings.GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION),
                ('GRAPHQL_STRICT_ORIGIN_VALIDATION', settings.GRAPHQL_STRICT_ORIGIN_VALIDATION),
                ('GRAPHQL_CSRF_HEADER_NAMES', settings.GRAPHQL_CSRF_HEADER_NAMES),
            ]),
            ('Performance', [
                ('GRAPHQL_ENABLE_VALIDATION_CACHE', settings.GRAPHQL_ENABLE_VALIDATION_CACHE),
                ('GRAPHQL_VALIDATION_CACHE_TTL', f'{settings.GRAPHQL_VALIDATION_CACHE_TTL}s'),
            ]),
        ]

        for section_title, section_settings in report_sections:
            self.stdout.write(self.style.SUCCESS(f'\n{section_title}:'))
            for setting_name, setting_value in section_settings:
                self.stdout.write(f'  {setting_name}: {setting_value}')

        # Metadata
        from intelliwiz_config.settings.security import graphql
        if hasattr(graphql, '__GRAPHQL_SETTINGS_VERSION__'):
            self.stdout.write(self.style.SUCCESS(f'\nSettings Version: {graphql.__GRAPHQL_SETTINGS_VERSION__}'))
        if hasattr(graphql, '__GRAPHQL_SETTINGS_LAST_UPDATED__'):
            self.stdout.write(self.style.SUCCESS(f'Last Updated: {graphql.__GRAPHQL_SETTINGS_LAST_UPDATED__}'))
        if hasattr(graphql, '__GRAPHQL_SETTINGS_SOURCE__'):
            self.stdout.write(self.style.SUCCESS(f'Source: {graphql.__GRAPHQL_SETTINGS_SOURCE__}'))

    def display_results(self, passed, warnings, errors):
        """Display validation results."""
        if passed:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Passed Checks ({len(passed)}):'))
            for check in passed:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {check}'))

        if warnings:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Warnings ({len(warnings)}):'))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f'  ⚠ {warning}'))

        if errors:
            self.stdout.write(self.style.ERROR(f'\n❌ Errors ({len(errors)}):'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  ✗ {error}'))
