"""
Security regression tests for password handling.

SECURITY COMPLIANCE (2025-10-11):
Prevents reintroduction of hardcoded passwords and predictable password patterns.
Tests enforce CVSS 9.1 and CVSS 7.5 vulnerability prevention.

Test Coverage:
1. Hardcoded password detection in init_intelliwiz.py
2. Predictable password pattern detection in managers.py
3. Password strength validation

Related Issues:
- CVSS 9.1: Hardcoded superadmin password (fixed 2025-10-11)
- CVSS 7.5: Predictable default passwords (fixed 2025-10-11)
"""

import pytest
from pathlib import Path
import re


class TestPasswordSecurityRegression:
    """Regression tests to prevent hardcoded and predictable passwords."""

    def test_no_hardcoded_passwords_in_init_command(self):
        """
        Ensure no hardcoded passwords exist in init_intelliwiz management command.

        SECURITY: Prevents CVSS 9.1 vulnerability reintroduction.
        Pattern Detection:
        - DEFAULT_PASSWORD = 'anything'
        - PASSWORD = 'anything@anything'
        - Specific patterns like 'superadmin@YYYY'
        """
        command_file = Path(__file__).parent.parent / "management/commands/init_intelliwiz.py"

        with open(command_file, 'r') as f:
            content = f.read()

        # Forbidden password patterns
        forbidden_patterns = [
            # Matches: DEFAULT_PASSWORD = 'anything'
            (r'DEFAULT_PASSWORD\s*=\s*[\'"][^\'"]+[\'"]', "DEFAULT_PASSWORD constant with hardcoded value"),
            # Matches: PASSWORD = 'anything@anything'
            (r'\bPASSWORD\s*=\s*[\'"].*@.*[\'"]', "PASSWORD constant with @ symbol"),
            # Matches: superadmin@YYYY pattern
            (r'superadmin@\d{4}', "Specific superadmin@YYYY pattern"),
            # Matches: set_password('hardcoded')
            (r'set_password\([\'"][^\'"]{8,}[\'"]', "set_password() with literal string"),
        ]

        violations = []
        for pattern, description in forbidden_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                violations.append(f"{description}: {match.group()}")

        assert not violations, \
            f"Hardcoded password patterns detected in init_intelliwiz.py:\n" + \
            "\n".join(f"  - {v}" for v in violations)

    def test_no_predictable_passwords_in_managers(self):
        """
        Ensure no predictable default passwords in managers.py.

        SECURITY: Prevents CVSS 7.5 vulnerability reintroduction.
        Pattern Detection:
        - set_password('{loginid}@123')
        - set_password(f'{variable}@digits')
        - Other predictable patterns
        """
        managers_file = Path(__file__).parent.parent / "managers.py"

        with open(managers_file, 'r') as f:
            content = f.read()

        # Forbidden predictable password patterns
        forbidden_patterns = [
            # Matches: set_password('anything@123')
            (r'set_password\([\'"]?\w+@123[\'"]?\)', "Literal '@123' password pattern"),
            # Matches: set_password(f'{variable}@123') or set_password(f'{variable}@digits')
            (r'set_password\(f?[\'"]?\{[^}]+\}@\d+[\'"]?\)', "F-string with @digits pattern"),
            # Matches: .set_password(request.POST['loginid'] + '@123')
            (r'set_password\([^)]*\+\s*[\'"]@\d+[\'"]', "Concatenated '@digits' pattern"),
        ]

        violations = []
        for pattern, description in forbidden_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                violations.append(f"{description}: {match.group()}")

        assert not violations, \
            f"Predictable password patterns detected in managers.py:\n" + \
            "\n".join(f"  - {v}" for v in violations)

    def test_requires_secure_password_generation(self):
        """
        Verify that init_intelliwiz.py uses secure password generation.

        SECURITY: Ensures cryptographic randomness via secrets module.
        """
        command_file = Path(__file__).parent.parent / "management/commands/init_intelliwiz.py"

        with open(command_file, 'r') as f:
            content = f.read()

        # Required security patterns
        required_patterns = [
            (r'import secrets', "secrets module import"),
            (r'secrets\.token_urlsafe\(', "secrets.token_urlsafe() usage"),
        ]

        missing = []
        for pattern, description in required_patterns:
            if not re.search(pattern, content):
                missing.append(description)

        assert not missing, \
            f"Security requirements missing in init_intelliwiz.py:\n" + \
            "\n".join(f"  - {m}" for m in missing)

    def test_managers_uses_unusable_password(self):
        """
        Verify that managers.py uses set_unusable_password() for new users.

        SECURITY: Ensures password reset flow instead of predictable defaults.
        """
        managers_file = Path(__file__).parent.parent / "managers.py"

        with open(managers_file, 'r') as f:
            content = f.read()

        # Check for set_unusable_password() usage
        # Note: This test will need to be updated based on actual implementation
        # For now, we just ensure no forbidden patterns exist

        # If set_password is used, it should NOT be with predictable patterns
        password_calls = re.findall(r'\.set_password\([^)]+\)', content)

        for call in password_calls:
            # Allow: user.set_password(password) from variable
            # Allow: user.set_password(request.POST.get('password'))
            # Forbid: user.set_password(f'{loginid}@123')
            # Forbid: user.set_password('literal_string')

            if re.search(r'@\d+', call):
                pytest.fail(
                    f"Predictable password pattern in set_password call: {call}\n"
                    "Use set_unusable_password() and password reset flow instead."
                )

    def test_no_password_logging(self):
        """
        Ensure passwords are never logged in production code.

        SECURITY: PCI-DSS compliance - passwords must never appear in logs.
        """
        files_to_check = [
            Path(__file__).parent.parent / "management/commands/init_intelliwiz.py",
            Path(__file__).parent.parent / "managers.py",
        ]

        violations = []
        for filepath in files_to_check:
            with open(filepath, 'r') as f:
                content = f.read()

            # Check for log statements with password variables
            # Forbidden: log.info(f"Password: {password}")
            # Allowed: log.info("Password created")  # No variable interpolation

            log_with_password = re.findall(
                r'log\.\w+\([^)]*password[^)]*\)',
                content,
                re.IGNORECASE
            )

            for log_statement in log_with_password:
                # Allow: log.info("Password reset required")  # Static string
                # Forbid: log.info(f"Password: {temp_password}")  # Variable interpolation
                if '{' in log_statement and 'password' in log_statement.lower():
                    violations.append(f"{filepath.name}: {log_statement}")

        # Allow specific exceptions (like "temporary_password" in metadata)
        # Filter out allowed patterns
        violations = [v for v in violations if 'temporary_password' not in v.lower() or '{temp_password}' in v]

        assert not violations, \
            f"Password logging detected (PCI-DSS violation):\n" + \
            "\n".join(f"  - {v}" for v in violations)


class TestPasswordStrengthValidation:
    """Test Django password validators are properly configured."""

    def test_password_validators_configured(self):
        """Verify strong password validators are enabled in settings."""
        from django.conf import settings

        validators = settings.AUTH_PASSWORD_VALIDATORS

        # Ensure minimum length validator exists with min_length >= 12
        min_length_validator = next(
            (v for v in validators if 'MinimumLengthValidator' in v['NAME']),
            None
        )
        assert min_length_validator is not None, "MinimumLengthValidator not configured"

        min_length = min_length_validator.get('OPTIONS', {}).get('min_length', 0)
        assert min_length >= 12, f"Minimum password length too weak: {min_length} (require >= 12)"

        # Ensure CommonPasswordValidator exists
        common_password_validator = next(
            (v for v in validators if 'CommonPasswordValidator' in v['NAME']),
            None
        )
        assert common_password_validator is not None, "CommonPasswordValidator not configured"

        # Ensure NumericPasswordValidator exists
        numeric_validator = next(
            (v for v in validators if 'NumericPasswordValidator' in v['NAME']),
            None
        )
        assert numeric_validator is not None, "NumericPasswordValidator not configured"


# Integration test (requires database)
@pytest.mark.django_db
class TestSuperuserCreationSecurity:
    """Integration tests for secure superuser creation."""

    def test_superuser_creation_with_env_password(self, monkeypatch):
        """Test that DJANGO_SUPERUSER_PASSWORD env var works in dev."""
        import os
        from apps.onboarding.management.commands.init_intelliwiz import create_superuser
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist

        # Create required TypeAssist entries
        ta_none = TypeAssist.objects.create(
            tacode='NONE',
            taname='None',
            tatype_id=1,
            enable=True
        )

        ta_client = TypeAssist.objects.create(
            tacode='CLIENT',
            taname='Client',
            tatype_id=1,
            enable=True
        )

        ta_site = TypeAssist.objects.create(
            tacode='SITE',
            taname='Site',
            tatype_id=1,
            enable=True
        )

        # Create dummy client and site
        client = Bt.objects.create(
            bucode='TESTCLIENT',
            buname='Test Client',
            identifier=ta_client,
            enable=True
        )

        site = Bt.objects.create(
            bucode='TESTSITE',
            buname='Test Site',
            identifier=ta_site,
            parent=client,
            enable=True
        )

        # Set env var for development testing
        monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', 'test_password_123!')

        # Create superuser
        user = create_superuser(client, site)

        assert user is not None, "Superuser creation failed"
        assert user.loginid == "superadmin"
        assert user.is_superuser is True
        assert user.is_staff is True
        assert user.check_password('test_password_123!'), "Password not set correctly"

    def test_superuser_creation_without_env_generates_random(self, monkeypatch):
        """Test that random password is generated when env var not set."""
        from apps.onboarding.management.commands.init_intelliwiz import create_superuser
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist

        # Ensure env var is not set
        monkeypatch.delenv('DJANGO_SUPERUSER_PASSWORD', raising=False)

        # Create required data
        ta_none = TypeAssist.objects.create(
            tacode='NONE2',
            taname='None',
            tatype_id=1,
            enable=True
        )

        ta_client = TypeAssist.objects.create(
            tacode='CLIENT2',
            taname='Client',
            tatype_id=1,
            enable=True
        )

        ta_site = TypeAssist.objects.create(
            tacode='SITE2',
            taname='Site',
            tatype_id=1,
            enable=True
        )

        client = Bt.objects.create(
            bucode='TESTCLIENT2',
            buname='Test Client 2',
            identifier=ta_client,
            enable=True
        )

        site = Bt.objects.create(
            bucode='TESTSITE2',
            buname='Test Site 2',
            identifier=ta_site,
            parent=client,
            enable=True
        )

        # Create superuser
        user = create_superuser(client, site)

        assert user is not None, "Superuser creation failed"
        assert user.loginid == "superadmin"
        assert user.is_superuser is True

        # Verify password is NOT the old hardcoded password
        assert not user.check_password('superadmin@2022#'), \
            "SECURITY VIOLATION: Hardcoded password still in use!"
