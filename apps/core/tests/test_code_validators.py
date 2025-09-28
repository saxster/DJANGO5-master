"""
Unit Tests for Code Validators

Comprehensive test coverage for code and field validation functions.

Test Coverage:
- Peoplecode validation
- Login ID validation
- Mobile number validation
- Name validation
- Code uniqueness validation
- Input sanitization
- RegexValidator instances

Compliance:
- Specific exception testing (Rule 11)
- 100% code coverage
- Security validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from django.core.exceptions import ValidationError

from apps.core.utils_new.code_validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    NAME_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
    EMAIL_VALIDATOR,
    validate_peoplecode,
    validate_loginid,
    validate_mobile_number,
    validate_name,
    validate_code_uniqueness,
    sanitize_code_input,
)


class TestPeoplecodeValidator:
    """Test validate_peoplecode function."""

    def test_validates_correct_code(self):
        assert validate_peoplecode("ABC123") is None
        assert validate_peoplecode("test-code_01") is None
        assert validate_peoplecode("CODE#123") is None

    def test_rejects_code_with_spaces(self):
        result = validate_peoplecode("ABC 123")
        assert result is not None
        assert "spaces" in result.lower()

    def test_rejects_code_ending_with_dot(self):
        result = validate_peoplecode("ABC123.")
        assert result is not None
        assert "'.'" in result

    def test_rejects_invalid_characters(self):
        result = validate_peoplecode("ABC@123")
        assert result is not None

    def test_rejects_empty_code(self):
        result = validate_peoplecode("")
        assert result is not None
        assert "required" in result.lower()

    def test_rejects_none(self):
        result = validate_peoplecode(None)
        assert result is not None

    def test_accepts_numbers_only(self):
        assert validate_peoplecode("12345") is None

    def test_accepts_letters_only(self):
        assert validate_peoplecode("ABCDEF") is None


class TestLoginidValidator:
    """Test validate_loginid function."""

    def test_validates_correct_loginid(self):
        assert validate_loginid("user123") is None
        assert validate_loginid("user_name") is None
        assert validate_loginid("user-name") is None
        assert validate_loginid("user@domain") is None
        assert validate_loginid("user.name") is None

    def test_rejects_loginid_with_spaces(self):
        result = validate_loginid("user name")
        assert result is not None
        assert "spaces" in result.lower()

    def test_rejects_short_loginid(self):
        result = validate_loginid("usr")
        assert result is not None
        assert "4 characters" in result

    def test_rejects_empty_loginid(self):
        result = validate_loginid("")
        assert result is not None
        assert "required" in result.lower()

    def test_rejects_invalid_characters(self):
        result = validate_loginid("user#name")
        assert result is not None

    def test_accepts_minimum_length(self):
        assert validate_loginid("usr1") is None


class TestMobileNumberValidator:
    """Test validate_mobile_number function."""

    def test_validates_correct_mobile(self):
        assert validate_mobile_number("+1234567890") is None
        assert validate_mobile_number("+919876543210") is None

    def test_rejects_without_country_code(self):
        result = validate_mobile_number("9876543210")
        assert result is not None
        assert "country code" in result.lower()

    def test_rejects_non_digits(self):
        result = validate_mobile_number("+91abcd1234")
        assert result is not None
        assert "digits" in result.lower()

    def test_rejects_too_short(self):
        result = validate_mobile_number("+123")
        assert result is not None
        assert "10-15 digits" in result

    def test_rejects_too_long(self):
        result = validate_mobile_number("+1234567890123456")
        assert result is not None
        assert "10-15 digits" in result

    def test_rejects_empty(self):
        result = validate_mobile_number("")
        assert result is not None
        assert "required" in result.lower()


class TestNameValidator:
    """Test validate_name function."""

    def test_validates_correct_name(self):
        assert validate_name("John Doe") is None
        assert validate_name("John-Doe") is None
        assert validate_name("John_Doe") is None
        assert validate_name("John@Doe") is None
        assert validate_name("John.Doe") is None

    def test_rejects_empty_name(self):
        result = validate_name("")
        assert result is not None
        assert "required" in result.lower()

    def test_rejects_whitespace_only(self):
        result = validate_name("   ")
        assert result is not None
        assert "required" in result.lower()

    def test_rejects_invalid_characters(self):
        result = validate_name("John$Doe")
        assert result is not None

    def test_accepts_numbers_in_name(self):
        assert validate_name("John Doe 2") is None


class TestCodeUniquenessValidator:
    """Test validate_code_uniqueness function."""

    def test_returns_none_for_unique_code(self):
        mock_model = Mock()
        mock_model.objects.filter.return_value.exclude.return_value.exists.return_value = False

        result = validate_code_uniqueness(
            mock_model,
            "UNIQUE123",
            exclude_id=1,
            client_id=10
        )
        assert result is None

    def test_returns_error_for_duplicate_code(self):
        mock_model = Mock()
        mock_model.objects.filter.return_value.exclude.return_value.exists.return_value = True

        result = validate_code_uniqueness(
            mock_model,
            "DUPLICATE",
            exclude_id=1,
            client_id=10
        )
        assert result is not None
        assert "already in use" in result.lower()

    def test_filters_by_client_id(self):
        mock_model = Mock()
        mock_queryset = Mock()
        mock_model.objects.filter.return_value = mock_queryset
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.exclude.return_value = mock_queryset
        mock_queryset.exists.return_value = False

        validate_code_uniqueness(mock_model, "CODE", client_id=10)

        mock_queryset.filter.assert_called_with(client_id=10)

    def test_excludes_current_id(self):
        mock_model = Mock()
        mock_queryset = Mock()
        mock_model.objects.filter.return_value = mock_queryset
        mock_queryset.exclude.return_value = mock_queryset
        mock_queryset.exists.return_value = False

        validate_code_uniqueness(mock_model, "CODE", exclude_id=5)

        mock_queryset.exclude.assert_called_with(id=5)

    def test_handles_attribute_error(self):
        mock_model = Mock()
        mock_model.objects.filter.side_effect = AttributeError("Test error")

        result = validate_code_uniqueness(mock_model, "CODE")
        assert result is not None
        assert "unable to validate" in result.lower()


class TestSanitizeCodeInput:
    """Test sanitize_code_input function."""

    def test_removes_whitespace(self):
        result = sanitize_code_input("  CODE123  ")
        assert result == "CODE123"

    def test_removes_null_bytes(self):
        result = sanitize_code_input("CODE\x00123")
        assert result == "CODE123"

    def test_limits_length(self):
        long_code = "A" * 100
        result = sanitize_code_input(long_code)
        assert len(result) == 50

    def test_handles_empty_string(self):
        result = sanitize_code_input("")
        assert result == ""

    def test_handles_none(self):
        result = sanitize_code_input(None)
        assert result == ""

    def test_handles_numbers(self):
        result = sanitize_code_input(12345)
        assert result == "12345"


class TestRegexValidators:
    """Test RegexValidator instances."""

    def test_peoplecode_validator_accepts_valid(self):
        try:
            PEOPLECODE_VALIDATOR("ABC123")
        except ValidationError:
            pytest.fail("Should not raise ValidationError")

    def test_peoplecode_validator_rejects_invalid(self):
        with pytest.raises(ValidationError):
            PEOPLECODE_VALIDATOR("ABC@123")

    def test_loginid_validator_accepts_valid(self):
        try:
            LOGINID_VALIDATOR("user@domain")
        except ValidationError:
            pytest.fail("Should not raise ValidationError")

    def test_loginid_validator_rejects_invalid(self):
        with pytest.raises(ValidationError):
            LOGINID_VALIDATOR("user#name")

    def test_name_validator_accepts_valid(self):
        try:
            NAME_VALIDATOR("John Doe")
        except ValidationError:
            pytest.fail("Should not raise ValidationError")

    def test_name_validator_rejects_invalid(self):
        with pytest.raises(ValidationError):
            NAME_VALIDATOR("John$Doe")

    def test_mobile_validator_accepts_valid(self):
        try:
            MOBILE_NUMBER_VALIDATOR("+1234567890")
        except ValidationError:
            pytest.fail("Should not raise ValidationError")

    def test_mobile_validator_rejects_invalid(self):
        with pytest.raises(ValidationError):
            MOBILE_NUMBER_VALIDATOR("1234567890")


class TestEdgeCases:
    """Test edge cases and security."""

    def test_sql_injection_attempt_in_code(self):
        result = validate_peoplecode("'; DROP TABLE users; --")
        assert result is not None

    def test_xss_attempt_in_code(self):
        result = validate_peoplecode("<script>alert('xss')</script>")
        assert result is not None

    def test_path_traversal_in_code(self):
        result = validate_peoplecode("../../../etc/passwd")
        assert result is not None

    def test_unicode_characters(self):
        result = validate_peoplecode("CODE日本")
        assert result is not None

    def test_emoji_in_code(self):
        result = validate_peoplecode("CODE😀123")
        assert result is not None

    def test_very_long_input_sanitization(self):
        long_input = "A" * 10000
        result = sanitize_code_input(long_input)
        assert len(result) <= 50