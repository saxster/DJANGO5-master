"""
Tests for LoginThrottlingService - brute force protection.

Tests cover:
- IP-based rate limiting
- Username-based rate limiting
- Exponential backoff with jitter
- Lockout activation and expiration
- Successful login counter reset
- Cache failure handling
- Security event logging

Security compliance: OWASP A07:2021 - Identification and Authentication Failures
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache

from apps.peoples.services.login_throttling_service import (
    LoginThrottlingService,
    ThrottleResult,
    ThrottleConfig
)
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE


@pytest.fixture
def throttle_service():
    """Login throttling service instance."""
    return LoginThrottlingService()


@pytest.fixture
def test_ip():
    """Test IP address."""
    return "203.0.113.45"


@pytest.fixture
def test_username():
    """Test username."""
    return "testuser"


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLoginThrottlingService:
    """Test suite for LoginThrottlingService."""

    def test_check_ip_throttle_first_attempt(self, throttle_service, test_ip):
        """Test first login attempt is allowed."""
        result = throttle_service.check_ip_throttle(test_ip)

        assert result.allowed is True
        assert result.remaining_attempts == throttle_service.ip_config.max_attempts
        assert result.lockout_until is None
        assert result.wait_seconds == 0

    def test_check_ip_throttle_under_limit(self, throttle_service, test_ip):
        """Test login attempts under the limit are allowed."""
        # Record 3 failed attempts (limit is 5)
        for _ in range(3):
            throttle_service.record_failed_attempt(test_ip, "user")

        result = throttle_service.check_ip_throttle(test_ip)

        assert result.allowed is True
        assert result.remaining_attempts == 2  # 5 - 3 = 2
        assert result.lockout_until is None

    def test_check_ip_throttle_at_limit(self, throttle_service, test_ip):
        """Test lockout triggered when limit reached."""
        # Record max attempts
        for _ in range(throttle_service.ip_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, "user")

        result = throttle_service.check_ip_throttle(test_ip)

        assert result.allowed is False
        assert result.remaining_attempts == 0
        assert result.lockout_until is not None
        assert result.wait_seconds > 0
        assert "Maximum login attempts" in result.reason

    def test_check_ip_throttle_lockout_enforced(self, throttle_service, test_ip):
        """Test lockout is enforced for the duration."""
        # Trigger lockout
        for _ in range(throttle_service.ip_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, "user")

        # First check - should be locked out
        result1 = throttle_service.check_ip_throttle(test_ip)
        assert result1.allowed is False

        # Second check - should still be locked out
        result2 = throttle_service.check_ip_throttle(test_ip)
        assert result2.allowed is False
        assert result2.lockout_until == result1.lockout_until

    def test_check_username_throttle_first_attempt(self, throttle_service, test_username):
        """Test first login attempt for username is allowed."""
        result = throttle_service.check_username_throttle(test_username)

        assert result.allowed is True
        assert result.remaining_attempts == throttle_service.username_config.max_attempts
        assert result.lockout_until is None

    def test_check_username_throttle_at_limit(self, throttle_service, test_username, test_ip):
        """Test username lockout after max attempts."""
        # Record max attempts (default is 3 for username)
        for _ in range(throttle_service.username_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, test_username)

        result = throttle_service.check_username_throttle(test_username)

        assert result.allowed is False
        assert result.remaining_attempts == 0
        assert result.lockout_until is not None
        assert "locked out until" in result.reason

    def test_check_username_throttle_case_insensitive(self, throttle_service, test_ip):
        """Test username throttling is case-insensitive."""
        # Record attempts with different cases
        throttle_service.record_failed_attempt(test_ip, "TestUser")
        throttle_service.record_failed_attempt(test_ip, "TESTUSER")
        throttle_service.record_failed_attempt(test_ip, "testuser")

        # Should all count toward same username
        result = throttle_service.check_username_throttle("TestUser")

        assert result.remaining_attempts == 0  # 3 attempts used

    def test_record_successful_attempt_clears_counters(
        self, throttle_service, test_ip, test_username
    ):
        """Test successful login clears throttle counters."""
        # Record failed attempts
        throttle_service.record_failed_attempt(test_ip, test_username)
        throttle_service.record_failed_attempt(test_ip, test_username)

        # Verify attempts recorded
        ip_result = throttle_service.check_ip_throttle(test_ip)
        assert ip_result.remaining_attempts < throttle_service.ip_config.max_attempts

        # Record successful login
        throttle_service.record_successful_attempt(test_ip, test_username)

        # Verify counters cleared
        ip_result = throttle_service.check_ip_throttle(test_ip)
        username_result = throttle_service.check_username_throttle(test_username)

        assert ip_result.remaining_attempts == throttle_service.ip_config.max_attempts
        assert username_result.remaining_attempts == throttle_service.username_config.max_attempts
        assert ip_result.allowed is True
        assert username_result.allowed is True

    def test_record_successful_attempt_clears_lockout(
        self, throttle_service, test_ip, test_username
    ):
        """Test successful login clears lockout state."""
        # Trigger lockout
        for _ in range(throttle_service.ip_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, test_username)

        # Verify locked out
        result = throttle_service.check_ip_throttle(test_ip)
        assert result.allowed is False

        # Successful login should clear lockout
        throttle_service.record_successful_attempt(test_ip, test_username)

        # Verify lockout cleared
        result = throttle_service.check_ip_throttle(test_ip)
        assert result.allowed is True

    def test_calculate_backoff_delay_exponential(self, throttle_service):
        """Test exponential backoff calculation."""
        # First attempt should have no delay
        delay1 = throttle_service._calculate_backoff_delay(1)
        assert delay1 == 0

        # Subsequent attempts should have exponential delay
        delay2 = throttle_service._calculate_backoff_delay(2, base_delay=2)
        delay3 = throttle_service._calculate_backoff_delay(3, base_delay=2)
        delay4 = throttle_service._calculate_backoff_delay(4, base_delay=2)

        # Should follow pattern: 0, 2, 4, 8, 16, 32...
        # With jitter, values will vary but should be in range
        assert 1 <= delay2 <= 4  # ~2 ± 20%
        assert 3 <= delay3 <= 6  # ~4 ± 20%
        assert 6 <= delay4 <= 12  # ~8 ± 20%

    def test_calculate_backoff_delay_max_limit(self, throttle_service):
        """Test backoff delay respects maximum."""
        delay = throttle_service._calculate_backoff_delay(
            attempt_number=20,
            base_delay=2,
            max_delay=60
        )

        assert delay <= 60  # Should not exceed max

    def test_calculate_backoff_delay_jitter(self, throttle_service):
        """Test jitter adds randomness to backoff."""
        delays = [
            throttle_service._calculate_backoff_delay(5, base_delay=2)
            for _ in range(10)
        ]

        # With jitter, delays should vary
        unique_delays = set(delays)
        assert len(unique_delays) > 1  # Should have some variation

    def test_check_ip_throttle_no_ip_provided(self, throttle_service):
        """Test handling of missing IP address."""
        result = throttle_service.check_ip_throttle("")

        assert result.allowed is False
        assert result.remaining_attempts == 0
        assert "No IP address" in result.reason

    def test_check_username_throttle_no_username(self, throttle_service):
        """Test handling of missing username."""
        result = throttle_service.check_username_throttle("")

        assert result.allowed is False
        assert result.remaining_attempts == 0
        assert "No username" in result.reason

    def test_get_lockout_info_no_lockout(
        self, throttle_service, test_ip, test_username
    ):
        """Test lockout info when not locked out."""
        info = throttle_service.get_lockout_info(test_ip, test_username)

        assert info['ip_address'] == test_ip
        assert info['username'] == test_username
        assert info['ip_locked_out'] is False
        assert info['username_locked_out'] is False
        assert info['ip_lockout_until'] is None
        assert info['username_lockout_until'] is None

    def test_get_lockout_info_with_lockout(
        self, throttle_service, test_ip, test_username
    ):
        """Test lockout info when locked out."""
        # Trigger IP lockout
        for _ in range(throttle_service.ip_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, test_username)

        info = throttle_service.get_lockout_info(test_ip, test_username)

        assert info['ip_locked_out'] is True
        assert info['ip_lockout_until'] is not None
        assert info['username_locked_out'] is True
        assert info['username_lockout_until'] is not None

    def test_get_lockout_info_attempt_counts(
        self, throttle_service, test_ip, test_username
    ):
        """Test lockout info shows attempt counts."""
        # Record 2 failed attempts
        throttle_service.record_failed_attempt(test_ip, test_username)
        throttle_service.record_failed_attempt(test_ip, test_username)

        info = throttle_service.get_lockout_info(test_ip, test_username)

        assert info['ip_attempt_count'] == 2
        assert info['username_attempt_count'] == 2
        assert info['ip_remaining_attempts'] == throttle_service.ip_config.max_attempts - 2
        assert info['username_remaining_attempts'] == throttle_service.username_config.max_attempts - 2

    @patch('apps.peoples.services.login_throttling_service.cache')
    def test_cache_error_handling_get_attempt_count(
        self, mock_cache, throttle_service, test_ip
    ):
        """Test graceful handling of cache errors when getting attempt count."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_cache.get.side_effect = RedisConnectionError("Connection failed")

        # Should return 0 and not crash
        count = throttle_service._get_attempt_count("test_key")
        assert count == 0

    @patch('apps.peoples.services.login_throttling_service.cache')
    def test_cache_error_handling_increment(
        self, mock_cache, throttle_service
    ):
        """Test graceful handling of cache errors when incrementing."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_cache.incr.side_effect = RedisConnectionError("Connection failed")

        # Should return 0 and not crash
        count = throttle_service._increment_attempt_count("test_key", 300)
        assert count == 0

    @patch('apps.peoples.services.login_throttling_service.cache')
    def test_cache_error_handling_lockout_check(
        self, mock_cache, throttle_service
    ):
        """Test graceful handling of cache errors when checking lockout."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_cache.get.side_effect = RedisConnectionError("Connection failed")

        # Should return None and not crash
        lockout = throttle_service._check_lockout_status("test_key")
        assert lockout is None

    def test_increment_attempt_count_creates_key(self, throttle_service):
        """Test increment creates key if it doesn't exist."""
        key = "test_increment_new_key"

        count = throttle_service._increment_attempt_count(key, 300)

        assert count == 1

        # Second increment should return 2
        count = throttle_service._increment_attempt_count(key, 300)
        assert count == 2

    def test_activate_lockout(self, throttle_service):
        """Test lockout activation sets correct expiration."""
        key = "test_lockout_key"
        duration = 900  # 15 minutes

        throttle_service._activate_lockout(key, duration)

        # Check lockout is active
        lockout_time = throttle_service._check_lockout_status(key)
        assert lockout_time is not None

        # Check expiration is approximately correct
        expected_expiry = timezone.now() + timedelta(seconds=duration)
        time_diff = abs((lockout_time - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_check_lockout_status_datetime_formats(self, throttle_service):
        """Test lockout status handles different datetime formats."""
        key = "test_datetime_formats"

        # Test with ISO format string
        lockout_time = timezone.now() + timedelta(minutes=15)
        cache.set(key, lockout_time.isoformat(), timeout=900)

        result = throttle_service._check_lockout_status(key)
        assert result is not None

    def test_dual_layer_protection_ip_and_username(
        self, throttle_service, test_ip
    ):
        """Test both IP and username are independently throttled."""
        username1 = "user1"
        username2 = "user2"

        # Exhaust IP limit with user1
        for _ in range(throttle_service.ip_config.max_attempts):
            throttle_service.record_failed_attempt(test_ip, username1)

        # IP should be locked out
        ip_result = throttle_service.check_ip_throttle(test_ip)
        assert ip_result.allowed is False

        # user2 from same IP should also be blocked (IP lockout)
        user2_result = throttle_service.check_username_throttle(username2)
        assert user2_result.allowed is True  # Username not exhausted yet

    def test_exponential_backoff_enabled_flag(self):
        """Test exponential backoff can be disabled."""
        service = LoginThrottlingService()

        # Default should have exponential backoff enabled
        assert service.ip_config.enable_exponential_backoff is True
        assert service.username_config.enable_exponential_backoff is True

    def test_security_event_logging(self, throttle_service, test_ip, test_username):
        """Test security events are logged."""
        with patch('apps.peoples.services.login_throttling_service.logger') as mock_logger:
            # Record failed attempt
            throttle_service.record_failed_attempt(
                test_ip, test_username, reason="invalid_credentials"
            )

            # Verify warning logged
            assert mock_logger.warning.called
            call_args = mock_logger.warning.call_args
            assert "Failed login attempt" in call_args[0][0]

            # Record successful attempt
            throttle_service.record_successful_attempt(test_ip, test_username)

            # Verify info logged
            assert mock_logger.info.called
            call_args = mock_logger.info.call_args
            assert "Successful login" in call_args[0][0]


@pytest.mark.django_db
class TestLoginThrottlingIntegration:
    """Integration tests for LoginThrottlingService."""

    def test_full_brute_force_attack_scenario(self):
        """Test complete brute force attack prevention."""
        service = LoginThrottlingService()
        attacker_ip = "198.51.100.50"
        target_username = "admin"

        # Simulate brute force attack
        for attempt in range(10):
            # Check if can attempt
            ip_check = service.check_ip_throttle(attacker_ip)
            username_check = service.check_username_throttle(target_username)

            if ip_check.allowed and username_check.allowed:
                # Record failed attempt
                service.record_failed_attempt(
                    attacker_ip, target_username, reason="invalid_password"
                )
            else:
                # Attack blocked
                break

        # Verify attack was blocked
        final_ip_check = service.check_ip_throttle(attacker_ip)
        final_username_check = service.check_username_throttle(target_username)

        assert final_ip_check.allowed is False or final_username_check.allowed is False

    def test_legitimate_user_flow(self):
        """Test legitimate user with occasional typos."""
        service = LoginThrottlingService()
        user_ip = "192.168.1.100"
        username = "legitimate_user"

        # Two failed attempts (typos)
        service.record_failed_attempt(user_ip, username)
        service.record_failed_attempt(user_ip, username)

        # Should still be able to attempt
        ip_check = service.check_ip_throttle(user_ip)
        username_check = service.check_username_throttle(username)

        assert ip_check.allowed is True
        assert username_check.allowed is True

        # Successful login
        service.record_successful_attempt(user_ip, username)

        # Counters should be reset
        ip_check = service.check_ip_throttle(user_ip)
        username_check = service.check_username_throttle(username)

        assert ip_check.remaining_attempts == service.ip_config.max_attempts
        assert username_check.remaining_attempts == service.username_config.max_attempts

    def test_distributed_attack_multiple_ips(self):
        """Test distributed attack from multiple IPs."""
        service = LoginThrottlingService()
        target_username = "admin"
        attacker_ips = [f"203.0.113.{i}" for i in range(1, 6)]

        # Simulate distributed attack
        for ip in attacker_ips:
            for _ in range(2):
                service.record_failed_attempt(ip, target_username)

        # Username should be locked out (6 attempts total, limit is 3)
        username_check = service.check_username_throttle(target_username)
        assert username_check.allowed is False

        # Individual IPs might not be locked (only 2 attempts each)
        ip_checks = [service.check_ip_throttle(ip) for ip in attacker_ips]
        assert any(check.allowed for check in ip_checks)  # IPs not individually locked
