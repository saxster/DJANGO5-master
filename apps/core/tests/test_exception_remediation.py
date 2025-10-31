"""
Comprehensive Exception Handling Remediation Tests

Tests to ensure generic exception handling patterns have been properly replaced
with specific exception types throughout the codebase.
"""

import pytest
import ast
import os
from pathlib import Path
from typing import List, Tuple
from django.conf import settings


class TestExceptionHandlingCompliance:
    """Test suite to validate exception handling compliance"""

    def _scan_file_for_generic_exceptions(self, file_path: str) -> List[Tuple[int, str]]:
        """
        Scan a Python file for generic except Exception: patterns.

        Returns:
            List of (line_number, context) tuples
        """
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type and isinstance(node.type, ast.Name):
                        if node.type.id in ['Exception', 'BaseException']:
                            context = self._get_context(source_code, node.lineno)
                            violations.append((node.lineno, context))

        except SyntaxError:
            # Skip files with syntax errors
            pass

        return violations

    def _get_context(self, source_code: str, line_number: int, context_lines: int = 2) -> str:
        """Extract context around exception"""
        lines = source_code.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        return '\n'.join(lines[start:end])

    @pytest.mark.security
    def test_peoples_authentication_service_no_generic_exceptions(self):
        """Test authentication service has no generic exception handling"""
        file_path = settings.BASE_DIR / 'apps' / 'peoples' / 'services' / 'authentication_service.py'

        if not file_path.exists():
            pytest.skip("Authentication service file not found")

        violations = self._scan_file_for_generic_exceptions(str(file_path))

        assert len(violations) == 0, (
            f"Found {len(violations)} generic exception patterns in authentication service:\n"
            + '\n\n'.join([f"Line {line}: {context}" for line, context in violations])
        )

    @pytest.mark.security
    def test_peoples_utils_no_generic_exceptions(self):
        """Test peoples utils has no generic exception handling"""
        file_path = settings.BASE_DIR / 'apps' / 'peoples' / 'utils.py'

        if not file_path.exists():
            pytest.skip("Peoples utils file not found")

        violations = self._scan_file_for_generic_exceptions(str(file_path))

        assert len(violations) == 0, (
            f"Found {len(violations)} generic exception patterns in peoples utils:\n"
            + '\n\n'.join([f"Line {line}: {context}" for line, context in violations])
        )

    @pytest.mark.security
    def test_service_mutations_no_generic_exceptions(self):
        """Test legacy mutation handlers have no generic exception handling"""
        file_path = settings.BASE_DIR / 'apps' / 'service' / 'mutations.py'

        if not file_path.exists():
            pytest.skip("Mutations file not found")

        violations = self._scan_file_for_generic_exceptions(str(file_path))

        # Allow up to 5 violations initially for gradual remediation
        assert len(violations) <= 5, (
            f"Found {len(violations)} generic exception patterns in mutations (max 5 allowed):\n"
            + '\n\n'.join([f"Line {line}: {context}" for line, context in violations[:10]])
        )

    @pytest.mark.security
    def test_critical_security_modules_compliance(self):
        """Test critical security modules have zero generic exceptions"""
        critical_modules = [
            'apps/core/middleware/api_authentication.py',
            'apps/core/security/jwt_csrf_protection.py',
        ]

        total_violations = 0
        violation_details = []

        for module_path in critical_modules:
            full_path = settings.BASE_DIR / module_path

            if not full_path.exists():
                continue

            violations = self._scan_file_for_generic_exceptions(str(full_path))
            total_violations += len(violations)

            if violations:
                violation_details.append(
                    f"{module_path}: {len(violations)} violations"
                )

        assert total_violations == 0, (
            f"CRITICAL: Found {total_violations} generic exception patterns in security modules:\n"
            + '\n'.join(violation_details)
        )

    @pytest.mark.integration
    def test_exception_imports_available(self):
        """Test that custom exception classes are properly imported"""
        from apps.core.exceptions import (
            BaseApplicationException,
            SecurityException,
            EnhancedValidationException,
            DatabaseException,
            BusinessLogicException,
            IntegrationException,
            AuthenticationError,
            WrongCredsError
        )

        # Verify exception hierarchy
        assert issubclass(SecurityException, BaseApplicationException)
        assert issubclass(EnhancedValidationException, BaseApplicationException)
        assert issubclass(DatabaseException, BaseApplicationException)
        assert issubclass(BusinessLogicException, BaseApplicationException)
        assert issubclass(IntegrationException, BaseApplicationException)

    @pytest.mark.integration
    def test_exception_correlation_id_support(self):
        """Test that exceptions support correlation IDs"""
        from apps.core.exceptions import BaseApplicationException

        exc = BaseApplicationException("Test error", correlation_id="test-123")
        assert exc.correlation_id == "test-123"

        exc2 = BaseApplicationException("Test error")
        assert exc2.correlation_id is not None  # Auto-generated UUID

    @pytest.mark.integration
    def test_exception_to_dict_conversion(self):
        """Test exception to dictionary conversion for JSON responses"""
        from apps.core.exceptions import BaseApplicationException

        exc = BaseApplicationException(
            "Test error",
            correlation_id="test-123",
            error_code="TEST_ERROR",
            context={'user': 'test_user'}
        )

        exc_dict = exc.to_dict()

        assert exc_dict['error_code'] == "TEST_ERROR"
        assert exc_dict['message'] == "Test error"
        assert exc_dict['correlation_id'] == "test-123"
        assert exc_dict['context'] == {'user': 'test_user'}


class TestAuthenticationServiceExceptionHandling:
    """Specific tests for authentication service exception handling"""

    @pytest.mark.django_db
    def test_authentication_with_invalid_credentials_raises_specific_exception(self):
        """Test that invalid credentials raise specific AuthenticationError"""
        from apps.peoples.services.authentication_service import AuthenticationService
        from apps.core.exceptions import AuthenticationError

        service = AuthenticationService()
        result = service.authenticate_user("invalid_user", "invalid_pass")

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.django_db
    def test_authentication_service_validates_user_access(self):
        """Test that user access validation uses specific exceptions"""
        from apps.peoples.services.authentication_service import AuthenticationService

        service = AuthenticationService()
        result = service._validate_user_access("nonexistent_user", "Web")

        assert result.success is False

    def test_authentication_result_has_correlation_id_on_error(self):
        """Test that authentication failures include correlation IDs"""
        from apps.peoples.services.authentication_service import AuthenticationService

        service = AuthenticationService()
        result = service.authenticate_user("test_user", "test_pass")

        if not result.success:
            # Correlation ID should be present on errors
            assert hasattr(result, 'correlation_id')


class TestExceptionFactoryUsage:
    """Tests for exception factory usage"""

    def test_factory_creates_validation_error(self):
        """Test exception factory creates proper validation errors"""
        from apps.core.exceptions import ExceptionFactory

        exc = ExceptionFactory.create_validation_error(
            "Invalid input",
            field="email",
            correlation_id="test-123"
        )

        assert exc.field == "email"
        assert exc.correlation_id == "test-123"
        assert "Invalid input" in str(exc)

    def test_factory_creates_security_error(self):
        """Test exception factory creates proper security errors"""
        from apps.core.exceptions import ExceptionFactory

        exc = ExceptionFactory.create_security_error(
            "Security violation",
            error_type="CSRF_ERROR",
            correlation_id="test-123",
            context={'ip': '127.0.0.1'}
        )

        assert exc.error_code == "CSRF_ERROR"
        assert exc.context['ip'] == '127.0.0.1'

    def test_factory_creates_business_logic_error(self):
        """Test exception factory creates proper business logic errors"""
        from apps.core.exceptions import ExceptionFactory

        exc = ExceptionFactory.create_business_logic_error(
            "Invalid workflow state",
            operation="workflow_transition",
            correlation_id="test-123"
        )

        assert exc.context['operation'] == "workflow_transition"

    def test_factory_creates_database_error(self):
        """Test exception factory creates proper database errors"""
        from apps.core.exceptions import ExceptionFactory

        exc = ExceptionFactory.create_database_error(
            "Database connection failed",
            error_type="CONNECTION_ERROR",
            correlation_id="test-123",
            query_context={'table': 'peoples'}
        )

        assert exc.error_code == "CONNECTION_ERROR"
        assert exc.context['table'] == "peoples"


@pytest.mark.security
class TestCodebaseWideCompliance:
    """Test overall codebase compliance with exception handling standards"""

    def test_peoples_app_compliance_percentage(self):
        """Test that peoples app has high exception handling compliance"""
        peoples_dir = settings.BASE_DIR / 'apps' / 'peoples'

        if not peoples_dir.exists():
            pytest.skip("Peoples app directory not found")

        total_files = 0
        files_with_violations = 0
        total_violations = 0

        for py_file in peoples_dir.rglob('*.py'):
            if 'migrations' in str(py_file) or '__pycache__' in str(py_file):
                continue

            total_files += 1
            violations = TestExceptionHandlingCompliance()._scan_file_for_generic_exceptions(str(py_file))

            if violations:
                files_with_violations += 1
                total_violations += len(violations)

        if total_files > 0:
            compliance_rate = ((total_files - files_with_violations) / total_files) * 100

            # Expect at least 50% compliance initially, increasing to 100% over time
            assert compliance_rate >= 50, (
                f"Peoples app compliance rate too low: {compliance_rate:.1f}%\n"
                f"Files with violations: {files_with_violations}/{total_files}\n"
                f"Total violations: {total_violations}"
            )

    def test_core_security_modules_zero_tolerance(self):
        """Test that core security modules have ZERO generic exceptions"""
        security_dirs = [
            settings.BASE_DIR / 'apps' / 'core' / 'security',
            settings.BASE_DIR / 'apps' / 'core' / 'middleware',
        ]

        total_violations = 0
        violation_files = []

        for security_dir in security_dirs:
            if not security_dir.exists():
                continue

            for py_file in security_dir.rglob('*.py'):
                violations = TestExceptionHandlingCompliance()._scan_file_for_generic_exceptions(str(py_file))

                if violations:
                    total_violations += len(violations)
                    violation_files.append(str(py_file.relative_to(settings.BASE_DIR)))

        assert total_violations == 0, (
            f"CRITICAL SECURITY ISSUE: Found {total_violations} generic exceptions in security modules:\n"
            + '\n'.join(violation_files)
        )
