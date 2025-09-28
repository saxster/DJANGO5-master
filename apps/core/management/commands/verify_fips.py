"""
FIPS Compliance Verification Command

Validates FIPS 140-2 compliance for encryption implementation.

Usage:
    python manage.py verify_fips
    python manage.py verify_fips --verbose
    python manage.py verify_fips --quiet
"""

import ssl
from django.core.management.base import BaseCommand
from apps.core.services.fips_validator import FIPSValidator


class Command(BaseCommand):
    help = "Verify FIPS 140-2 compliance for encryption implementation"

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed test results'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output (exit code only)'
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        quiet = options.get('quiet', False)

        if not quiet:
            self.stdout.write("Running FIPS 140-2 compliance validation...")
            self.stdout.write(f"OpenSSL Version: {ssl.OPENSSL_VERSION}")
            self.stdout.write("")

        validation_passed = FIPSValidator.validate_fips_mode()

        if not quiet:
            if validation_passed:
                self.stdout.write(self.style.SUCCESS("✅ FIPS validation PASSED"))
            else:
                self.stdout.write(self.style.ERROR("❌ FIPS validation FAILED"))

            if verbose:
                report = FIPSValidator.generate_compliance_report(verbose=True)
                self.stdout.write("\n" + report)

        exit(0 if validation_passed else 1)