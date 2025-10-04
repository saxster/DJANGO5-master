"""
Test Sentry Integration Command

Smoke test for Sentry connectivity and error capture.

Usage:
    python manage.py test_sentry_integration
    python manage.py test_sentry_integration --capture-test-error
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Sentry integration and connectivity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--capture-test-error',
            action='store_true',
            help='Capture a test error in Sentry',
        )

    def handle(self, *args, **options):
        """Execute Sentry integration tests."""
        from apps.core.observability.sentry_integration import SentryIntegration

        self.stdout.write(self.style.NOTICE('Testing Sentry integration...'))

        # Check if Sentry is initialized
        if not SentryIntegration._initialized:
            success = SentryIntegration.initialize()
            if not success:
                self.stdout.write(self.style.ERROR('✗ Sentry initialization failed'))
                return

        self.stdout.write(self.style.SUCCESS('✓ Sentry initialized'))

        # Test error capture if requested
        if options['capture_test_error']:
            self._test_error_capture()

        self.stdout.write(self.style.SUCCESS('\nSentry integration test complete!'))

    def _test_error_capture(self):
        """Capture a test error in Sentry."""
        try:
            import sentry_sdk

            self.stdout.write(self.style.NOTICE('\nCapturing test error...'))

            # Capture test exception
            try:
                raise ValueError("Test error from test_sentry_integration command")
            except ValueError as e:
                event_id = sentry_sdk.capture_exception(e)
                self.stdout.write(self.style.SUCCESS(f'✓ Error captured: {event_id}'))

        except ImportError:
            self.stdout.write(self.style.ERROR('✗ Sentry SDK not available'))
