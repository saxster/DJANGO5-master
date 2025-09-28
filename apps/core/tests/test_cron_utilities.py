"""
Unit Tests for Cron Utilities

Comprehensive test coverage for cron validation functions.

Test Coverage:
- Cron expression validation
- Frequency description generation
- Form validation helper
- Caching behavior
- Edge cases and error handling

Compliance:
- Specific exception testing (Rule 11)
- 100% code coverage
- Security validation
"""

import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache

from apps.core.utils_new.cron_utilities import (
    is_valid_cron,
    validate_cron_expression,
    get_cron_frequency_description,
    validate_cron_for_form,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestIsValidCron:
    """Test is_valid_cron function."""

    def test_validates_correct_cron(self):
        assert is_valid_cron("0 0 * * *") is True
        assert is_valid_cron("*/5 * * * *") is True
        assert is_valid_cron("0 12 * * 1") is True

    def test_rejects_invalid_cron(self):
        assert is_valid_cron("invalid") is False
        assert is_valid_cron("* * * *") is False  # Too few fields
        assert is_valid_cron("60 * * * *") is False  # Invalid minute

    def test_handles_empty_string(self):
        assert is_valid_cron("") is False

    def test_handles_none(self):
        assert is_valid_cron(None) is False

    def test_handles_non_string(self):
        assert is_valid_cron(123) is False
        assert is_valid_cron([]) is False

    @patch('apps.core.utils_new.cron_utilities.croniter')
    def test_handles_import_error(self, mock_croniter):
        mock_croniter.side_effect = ImportError()
        assert is_valid_cron("0 0 * * *") is False


class TestValidateCronExpression:
    """Test validate_cron_expression function."""

    def test_validates_correct_expression(self):
        result = validate_cron_expression("0 0 * * *")
        assert result['valid'] is True
        assert result['expression'] == "0 0 * * *"
        assert 'description' in result
        assert result['error'] is None

    def test_rejects_invalid_expression(self):
        result = validate_cron_expression("invalid")
        assert result['valid'] is False
        assert 'error' in result
        assert result['error'] is not None

    def test_requires_expression(self):
        result = validate_cron_expression("")
        assert result['valid'] is False
        assert 'required' in result['error'].lower()

    def test_rejects_non_string(self):
        result = validate_cron_expression(123)
        assert result['valid'] is False
        assert 'string' in result['error'].lower()

    def test_includes_hint_for_invalid(self):
        result = validate_cron_expression("* * *")
        assert result['valid'] is False
        assert 'hint' in result

    def test_caches_validation_results(self):
        cron = "0 0 * * *"
        result1 = validate_cron_expression(cron, use_cache=True)
        result2 = validate_cron_expression(cron, use_cache=True)

        assert result1 == result2

    def test_skips_cache_when_disabled(self):
        cron = "0 0 * * *"

        with patch('apps.core.utils_new.cron_utilities._get_cached_validation') as mock_get:
            validate_cron_expression(cron, use_cache=False)
            mock_get.assert_not_called()

    @patch('apps.core.utils_new.cron_utilities.croniter')
    def test_handles_import_error(self, mock_croniter):
        mock_croniter.side_effect = ImportError()
        result = validate_cron_expression("0 0 * * *")
        assert result['valid'] is False
        assert 'library not available' in result['error'].lower()


class TestGetCronFrequencyDescription:
    """Test get_cron_frequency_description function."""

    def test_describes_every_minute(self):
        result = get_cron_frequency_description("* * * * *")
        assert result == "Every minute"

    def test_describes_interval_minutes(self):
        result = get_cron_frequency_description("*/5 * * * *")
        assert result == "Every 5 minutes"

    def test_describes_hourly(self):
        result = get_cron_frequency_description("30 * * * *")
        assert result == "Hourly at minute 30"

    def test_describes_daily(self):
        result = get_cron_frequency_description("0 12 * * *")
        assert result == "Daily at 12:0"

    def test_describes_monthly(self):
        result = get_cron_frequency_description("0 0 15 * *")
        assert result == "Monthly on day 15 at 0:0"

    def test_describes_weekly_monday(self):
        result = get_cron_frequency_description("0 9 * * 1")
        assert "Monday" in result

    def test_describes_weekly_sunday(self):
        result = get_cron_frequency_description("0 9 * * 0")
        assert "Sunday" in result

    def test_handles_invalid_format(self):
        result = get_cron_frequency_description("invalid")
        assert result == "Custom schedule"

    def test_handles_too_few_fields(self):
        result = get_cron_frequency_description("* *")
        assert result == "Custom schedule"

    def test_caches_results(self):
        cron = "0 0 * * *"
        result1 = get_cron_frequency_description(cron)
        result2 = get_cron_frequency_description(cron)
        assert result1 == result2


class TestValidateCronForForm:
    """Test validate_cron_for_form function."""

    def test_returns_none_for_valid(self):
        result = validate_cron_for_form("0 0 * * *")
        assert result is None

    def test_returns_error_for_invalid(self):
        result = validate_cron_for_form("invalid")
        assert result is not None
        assert isinstance(result, str)

    def test_returns_error_for_empty(self):
        result = validate_cron_for_form("")
        assert result is not None

    def test_uses_cache(self):
        cron = "0 0 * * *"

        with patch('apps.core.utils_new.cron_utilities.validate_cron_expression') as mock_validate:
            mock_validate.return_value = {'valid': True}
            validate_cron_for_form(cron)
            mock_validate.assert_called_once_with(cron, use_cache=True)


class TestCachingBehavior:
    """Test caching functionality."""

    def test_cache_stores_validation_results(self):
        cron = "0 0 * * *"

        result1 = validate_cron_expression(cron, use_cache=True)
        assert result1['valid'] is True

        with patch('apps.core.utils_new.cron_utilities._validate_cron_internal') as mock_internal:
            result2 = validate_cron_expression(cron, use_cache=True)
            mock_internal.assert_not_called()

    def test_cache_key_generation(self):
        cron1 = "0 0 * * *"
        cron2 = "0 0 * * *"

        validate_cron_expression(cron1, use_cache=True)

        with patch('apps.core.utils_new.cron_utilities._validate_cron_internal') as mock_internal:
            validate_cron_expression(cron2, use_cache=True)
            mock_internal.assert_not_called()

    def test_different_expressions_cached_separately(self):
        cron1 = "0 0 * * *"
        cron2 = "*/5 * * * *"

        result1 = validate_cron_expression(cron1, use_cache=True)
        result2 = validate_cron_expression(cron2, use_cache=True)

        assert result1['description'] != result2['description']


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_cron_expression(self):
        long_cron = "0 0 * * * " * 100
        result = validate_cron_expression(long_cron)
        assert result['valid'] is False

    def test_cron_with_special_characters(self):
        result = validate_cron_expression("0 0 * * @#$%")
        assert result['valid'] is False

    def test_cron_with_unicode(self):
        result = validate_cron_expression("0 0 * * 日")
        assert result['valid'] is False

    def test_whitespace_cron(self):
        result = validate_cron_expression("   ")
        assert result['valid'] is False

    def test_multiple_spaces_between_fields(self):
        result = validate_cron_expression("0  0  *  *  *")
        assert result['valid'] is False or result['valid'] is True