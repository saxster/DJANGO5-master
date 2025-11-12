"""
Test exception handling in V2 API views per Rule #11.

Ensures all views use specific exceptions from apps.core.exceptions.patterns
instead of generic "except Exception:".

Tests for:
- calendar_views.py:222 - Calendar attachment endpoint
- reports_views.py:139 - Report generation endpoint
- reports_views.py:399 - Report scheduling endpoint
- telemetry_views.py:57 - Telemetry batch ingestion (SECURITY)

These tests verify that generic "except Exception:" handlers have been replaced
with specific exception types from patterns.py, and that error messages don't
expose internal implementation details to clients.
"""

import uuid
import ast
import re
from pathlib import Path

from django.test import TestCase

from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    VALIDATION_EXCEPTIONS,
    CACHE_EXCEPTIONS,
    SERIALIZATION_EXCEPTIONS,
)


class ExceptionHandlingPatternTests(TestCase):
    """Test that views use correct exception patterns from patterns.py."""

    def test_database_exceptions_imported(self):
        """Test that DATABASE_EXCEPTIONS is correctly imported."""
        from apps.api.v2.views.calendar_views import DATABASE_EXCEPTIONS
        from django.db import IntegrityError, OperationalError

        # Verify it's a tuple of database exception types
        self.assertIsInstance(DATABASE_EXCEPTIONS, tuple)
        self.assertIn(IntegrityError, DATABASE_EXCEPTIONS)
        self.assertIn(OperationalError, DATABASE_EXCEPTIONS)

    def test_cache_exceptions_imported(self):
        """Test that CACHE_EXCEPTIONS is correctly imported."""
        from apps.api.v2.views.reports_views import CACHE_EXCEPTIONS

        # Verify it's a tuple
        self.assertIsInstance(CACHE_EXCEPTIONS, tuple)
        # Should have at least one exception type
        self.assertGreater(len(CACHE_EXCEPTIONS), 0)

    def test_validation_exceptions_available(self):
        """Test that VALIDATION_EXCEPTIONS is available from patterns."""
        from apps.core.exceptions.patterns import VALIDATION_EXCEPTIONS
        from django.core.exceptions import ValidationError

        # Verify it's a tuple with validation-related exceptions
        self.assertIsInstance(VALIDATION_EXCEPTIONS, tuple)
        self.assertIn(ValidationError, VALIDATION_EXCEPTIONS)
        self.assertIn(ValueError, VALIDATION_EXCEPTIONS)

    def test_serialization_exceptions_available(self):
        """Test that SERIALIZATION_EXCEPTIONS is available from patterns."""
        from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS

        # Verify it's a tuple
        self.assertIsInstance(SERIALIZATION_EXCEPTIONS, tuple)
        # Should include common serialization exceptions
        self.assertIn(ValueError, SERIALIZATION_EXCEPTIONS)
        self.assertIn(TypeError, SERIALIZATION_EXCEPTIONS)
        self.assertIn(KeyError, SERIALIZATION_EXCEPTIONS)


class CodeAnalysisTests(TestCase):
    """Verify that generic 'except Exception:' handlers have been replaced."""

    def _read_source_file(self, file_path):
        """Helper to read source file content."""
        full_path = Path(__file__).parent.parent / file_path
        with open(full_path, 'r') as f:
            return f.read()

    def test_calendar_views_no_generic_exception(self):
        """Verify calendar_views.py doesn't use generic 'except Exception:'."""
        source = self._read_source_file('views/calendar_views.py')

        # Look for 'except Exception:' patterns (basic check)
        # This is a simple regex check - not foolproof but catches the obvious cases
        generic_exception_pattern = r'except\s+Exception\s*:'
        matches = re.findall(generic_exception_pattern, source)

        # Should have NO generic exception handlers
        self.assertEqual(len(matches), 0,
            f"Found {len(matches)} generic 'except Exception:' handler(s) in calendar_views.py")

        # Verify it uses SERIALIZATION_EXCEPTIONS
        self.assertIn('SERIALIZATION_EXCEPTIONS', source,
            "calendar_views.py should import and use SERIALIZATION_EXCEPTIONS")

    def test_reports_views_no_generic_exception(self):
        """Verify reports_views.py doesn't use generic 'except Exception:'."""
        source = self._read_source_file('views/reports_views.py')

        # Look for 'except Exception:' patterns
        generic_exception_pattern = r'except\s+Exception\s*:'
        matches = re.findall(generic_exception_pattern, source)

        # Should have NO generic exception handlers
        self.assertEqual(len(matches), 0,
            f"Found {len(matches)} generic 'except Exception:' handler(s) in reports_views.py")

        # Verify it uses VALIDATION_EXCEPTIONS and SERIALIZATION_EXCEPTIONS
        self.assertIn('VALIDATION_EXCEPTIONS', source,
            "reports_views.py should import and use VALIDATION_EXCEPTIONS")
        self.assertIn('SERIALIZATION_EXCEPTIONS', source,
            "reports_views.py should import and use SERIALIZATION_EXCEPTIONS")

    def test_telemetry_views_no_generic_exception(self):
        """Verify telemetry_views.py doesn't use generic 'except Exception:'."""
        source = self._read_source_file('views/telemetry_views.py')

        # Look for 'except Exception:' patterns
        generic_exception_pattern = r'except\s+Exception\s*:'
        matches = re.findall(generic_exception_pattern, source)

        # Should have NO generic exception handlers
        self.assertEqual(len(matches), 0,
            f"Found {len(matches)} generic 'except Exception:' handler(s) in telemetry_views.py")

        # Verify it uses VALIDATION_EXCEPTIONS and SERIALIZATION_EXCEPTIONS
        self.assertIn('VALIDATION_EXCEPTIONS', source,
            "telemetry_views.py should import and use VALIDATION_EXCEPTIONS")
        self.assertIn('SERIALIZATION_EXCEPTIONS', source,
            "telemetry_views.py should import and use SERIALIZATION_EXCEPTIONS")

    def test_telemetry_views_no_str_e_exposure(self):
        """
        SECURITY TEST: Verify telemetry_views.py doesn't expose exception details.

        This is the critical security fix - line 64 previously had:
            'message': str(e)
        which exposed internal error details to clients.
        """
        source = self._read_source_file('views/telemetry_views.py')

        # Check that error messages are generic, not str(e)
        # Should NOT find patterns like: 'message': str(e)
        str_e_pattern = r"['\"]message['\"]\s*:\s*str\(e\)"
        matches = re.findall(str_e_pattern, source)

        self.assertEqual(len(matches), 0,
            "telemetry_views.py should NOT expose exception details via str(e)")

        # Verify it uses generic error messages
        self.assertIn('An error occurred', source,
            "telemetry_views.py should use generic error messages")
        self.assertIn('Invalid telemetry data', source,
            "telemetry_views.py should have specific validation error message")

    def test_all_views_use_exc_info_true(self):
        """Verify all exception handlers log with exc_info=True for stack traces."""
        files_to_check = [
            'views/calendar_views.py',
            'views/reports_views.py',
            'views/telemetry_views.py'
        ]

        for file_path in files_to_check:
            source = self._read_source_file(file_path)

            # Check that exception logging includes exc_info=True
            # Look for logger.error/exception calls with exc_info
            has_exc_info = (
                'exc_info=True' in source or
                'logger.exception(' in source  # exception() automatically includes exc_info
            )

            self.assertTrue(has_exc_info,
                f"{file_path} should log exceptions with exc_info=True or use logger.exception()")


class ExceptionMessageSecurityTests(TestCase):
    """Test that error messages don't expose internal details."""

    def test_error_messages_are_generic(self):
        """Verify error messages exposed to clients are generic."""
        from apps.api.v2.views import telemetry_views, reports_views, calendar_views

        # Get source code
        import inspect

        # Check telemetry_views
        source = inspect.getsource(telemetry_views)

        # Should have generic messages, not internal details
        self.assertIn('Invalid telemetry data', source)
        self.assertIn('An error occurred', source)

        # Should NOT have messages that expose internals like:
        # - "Database connection failed"
        # - "Redis timeout"
        # - "NoneType object"
        # etc.

        # Verify reports_views has generic messages
        reports_source = inspect.getsource(reports_views)
        self.assertIn('An error occurred', reports_source)
        self.assertIn('Invalid', reports_source)  # For validation errors

    def test_exception_types_not_exposed_in_messages(self):
        """Verify exception type names aren't exposed in client-facing messages."""
        from apps.api.v2.views import telemetry_views
        import inspect

        source = inspect.getsource(telemetry_views)

        # Check that we log type(e).__name__ but don't return it to client
        # Logs should have type(e).__name__ for debugging
        self.assertIn('type(e).__name__', source,
            "Should log exception type for debugging")

        # But client-facing messages should be generic
        # Parse the Response objects to check their error messages
        # This is a basic check - actual runtime tests would be more thorough

        # Find all Response( calls with error messages
        response_pattern = r'Response\(\{[^}]*["\']message["\']\s*:\s*["\']([^"\']+)["\']'
        matches = re.findall(response_pattern, source)

        # Verify messages are generic
        for message in matches:
            # Should not contain exception type names
            self.assertNotIn('Error', message,
                f"Message should not end with 'Error': {message}")
            self.assertNotIn('Exception', message,
                f"Message should not contain 'Exception': {message}")


class ImportComplianceTests(TestCase):
    """Verify files import correct exception patterns."""

    def test_calendar_views_imports_serialization_exceptions(self):
        """Verify calendar_views imports SERIALIZATION_EXCEPTIONS."""
        from apps.api.v2.views import calendar_views

        # Check that module has the import
        self.assertTrue(hasattr(calendar_views, 'SERIALIZATION_EXCEPTIONS'),
            "calendar_views should import SERIALIZATION_EXCEPTIONS")

    def test_reports_views_imports_all_needed_exceptions(self):
        """Verify reports_views imports all needed exception types."""
        from apps.api.v2.views import reports_views

        # Check that module has all imports
        self.assertTrue(hasattr(reports_views, 'CACHE_EXCEPTIONS'),
            "reports_views should import CACHE_EXCEPTIONS")
        self.assertTrue(hasattr(reports_views, 'VALIDATION_EXCEPTIONS'),
            "reports_views should import VALIDATION_EXCEPTIONS")
        self.assertTrue(hasattr(reports_views, 'SERIALIZATION_EXCEPTIONS'),
            "reports_views should import SERIALIZATION_EXCEPTIONS")
        self.assertTrue(hasattr(reports_views, 'CELERY_EXCEPTIONS'),
            "reports_views should import CELERY_EXCEPTIONS")

    def test_telemetry_views_imports_all_needed_exceptions(self):
        """Verify telemetry_views imports all needed exception types."""
        from apps.api.v2.views import telemetry_views

        # Check that module has all imports
        self.assertTrue(hasattr(telemetry_views, 'VALIDATION_EXCEPTIONS'),
            "telemetry_views should import VALIDATION_EXCEPTIONS")
        self.assertTrue(hasattr(telemetry_views, 'SERIALIZATION_EXCEPTIONS'),
            "telemetry_views should import SERIALIZATION_EXCEPTIONS")
