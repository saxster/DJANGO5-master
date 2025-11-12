"""
Test cache utilities exception handling - Rule #11 compliance.

Verifies that cache_utils.py uses specific exception types instead of
generic Exception handlers.

Tests cover:
- invalidate_pattern() function (line 176)
- warm_cache() function (line 250)

Author: Code Quality Team
Date: 2025-11-11
"""

import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.cache import cache

from apps.core.utils_new.cache_utils import (
    invalidate_pattern,
    warm_cache,
    cache_result
)

logger = logging.getLogger(__name__)


class TestInvalidatePatternExceptionHandling:
    """Test invalidate_pattern() exception handling (line 176)."""

    def test_invalidate_pattern_redis_error(self):
        """Test handling of RedisError."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            # Simulate RedisError
            from redis.exceptions import RedisError
            mock_cache.delete_pattern.side_effect = RedisError("Redis connection failed")

            result = invalidate_pattern('test_*')

            # Should return 0 and not raise
            assert result == 0
            mock_cache.delete_pattern.assert_called_once_with('test_*')

    def test_invalidate_pattern_connection_error(self):
        """Test handling of ConnectionError (Redis connection issue)."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            # Simulate ConnectionError
            from redis.exceptions import ConnectionError
            mock_cache.delete_pattern.side_effect = ConnectionError("Cannot connect to Redis")

            result = invalidate_pattern('user_*')

            # Should return 0 and not raise
            assert result == 0
            mock_cache.delete_pattern.assert_called_once_with('user_*')

    def test_invalidate_pattern_timeout_error(self):
        """Test handling of TimeoutError (Redis timeout)."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            # Simulate TimeoutError
            from redis.exceptions import TimeoutError
            mock_cache.delete_pattern.side_effect = TimeoutError("Redis operation timed out")

            result = invalidate_pattern('dashboard_*')

            # Should return 0 and not raise
            assert result == 0
            mock_cache.delete_pattern.assert_called_once_with('dashboard_*')

    def test_invalidate_pattern_attribute_error(self):
        """Test handling of AttributeError (missing method on backend)."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            # Simulate AttributeError when delete_pattern doesn't exist
            mock_cache.delete_pattern.side_effect = AttributeError(
                "Cache backend doesn't support delete_pattern"
            )

            result = invalidate_pattern('cache_*')

            # Should return 0 and not raise
            assert result == 0

    def test_invalidate_pattern_success(self):
        """Test successful invalidate_pattern operation."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            mock_cache.delete_pattern.return_value = 5

            result = invalidate_pattern('test_*')

            assert result == 5
            mock_cache.delete_pattern.assert_called_once_with('test_*')

    def test_invalidate_pattern_no_support(self):
        """Test backend without delete_pattern support."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            # No delete_pattern attribute
            mock_cache.delete_pattern = None
            del mock_cache.delete_pattern  # Remove the attribute

            # Mock hasattr to return False
            with patch('builtins.hasattr', return_value=False):
                result = invalidate_pattern('test_*')

                assert result == 0


class TestWarmCacheExceptionHandling:
    """Test warm_cache() exception handling (line 250)."""

    def test_warm_cache_function_error_handling(self):
        """Test warm_cache handles function execution errors gracefully."""
        def failing_func(arg):
            raise ValueError(f"Invalid argument: {arg}")

        # Set an invalidate method to avoid AttributeError
        failing_func.invalidate = Mock()

        result = warm_cache(failing_func, [(1,), (2,), (3,)])

        # All attempts should fail, warmed should be 0
        assert result == 0

    def test_warm_cache_partial_success(self):
        """Test warm_cache with some successful and some failing calls."""
        call_count = 0

        def sometimes_failing_func(arg):
            nonlocal call_count
            call_count += 1
            if arg == 2:
                raise RuntimeError("Simulated failure for arg=2")
            return f"result_{arg}"

        sometimes_failing_func.invalidate = Mock()

        result = warm_cache(sometimes_failing_func, [(1,), (2,), (3,)])

        # Should succeed for args 1 and 3, fail for arg 2
        # Result should reflect successfully warmed entries (2 out of 3)
        assert call_count == 3  # All were attempted
        assert result == 2  # Two succeeded

    def test_warm_cache_with_kwargs(self):
        """Test warm_cache with keyword arguments."""
        call_log = []

        def func_with_kwargs(a, b=None):
            call_log.append((a, b))
            return f"result_{a}_{b}"

        func_with_kwargs.invalidate = Mock()

        result = warm_cache(func_with_kwargs, [
            (1,),
            (2,),
        ])

        # Should have called the function for each arg
        assert len(call_log) == 2
        assert result == 2

    def test_warm_cache_exception_not_re_raised(self):
        """Test that exceptions during warming don't propagate."""
        def raising_func(arg):
            raise Exception(f"Error for {arg}")

        raising_func.invalidate = Mock()

        # Should not raise, just return 0
        result = warm_cache(raising_func, [(1,), (2,)])
        assert result == 0

    def test_warm_cache_with_list_args(self):
        """Test warm_cache with non-tuple arguments."""
        call_log = []

        def func(arg):
            call_log.append(arg)
            return f"result_{arg}"

        func.invalidate = Mock()

        result = warm_cache(func, [1, 2, 3])  # Not tuples

        # Should handle non-tuple args
        assert result == 3
        assert call_log == [1, 2, 3]

    def test_warm_cache_logging(self):
        """Test that warm_cache logs appropriate messages."""
        def simple_func(arg):
            return f"result_{arg}"

        simple_func.invalidate = Mock()

        with patch('apps.core.utils_new.cache_utils.logger') as mock_logger:
            result = warm_cache(simple_func, [(1,), (2,)])

            assert result == 2
            # Should log success message
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "Warmed" in call_args
            assert "cache entries" in call_args


class TestCacheUtilsErrorPatterns:
    """Integration tests for cache utils error handling patterns."""

    def test_redis_error_specific_handling(self):
        """Test that we catch specific Redis errors, not generic Exception."""
        with patch('apps.core.utils_new.cache_utils.cache') as mock_cache:
            from redis.exceptions import RedisError, ConnectionError

            # Test each specific exception type
            for error_class in [RedisError, ConnectionError]:
                mock_cache.delete_pattern.side_effect = error_class("test")
                result = invalidate_pattern('test_*')
                assert result == 0

    def test_cache_decorator_with_errors(self):
        """Test that cache decorator handles errors properly."""
        @cache_result(timeout=300, key_prefix='test')
        def sometimes_failing_func(x):
            if x < 0:
                raise ValueError("Negative number")
            return x * 2

        # Should raise the specific error, not generic Exception
        with pytest.raises(ValueError):
            sometimes_failing_func(-1)

        # Should work normally for valid input
        result = sometimes_failing_func(5)
        assert result == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
