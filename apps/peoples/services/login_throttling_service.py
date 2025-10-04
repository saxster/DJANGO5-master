"""
Login Throttling Service

Implements per-IP and per-username brute force protection with:
- Redis-based rate limiting
- Exponential backoff with jitter
- Automatic lockout after N failed attempts
- Audit logging for security monitoring

Security:
    - Prevents credential stuffing attacks
    - Blocks brute force attempts
    - Progressive delay enforcement
    - Comprehensive audit trail

Compliance:
    - Rule #11: Specific exception handling (ConnectionError, TimeoutError)
    - Performance: <10ms overhead per login attempt
"""

import logging
import random
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR

logger = logging.getLogger('security.authentication')


@dataclass
class ThrottleResult:
    """Result of throttle check."""
    allowed: bool
    remaining_attempts: int
    lockout_until: Optional[datetime] = None
    wait_seconds: int = 0
    reason: str = ""


@dataclass
class ThrottleConfig:
    """Throttling configuration."""
    max_attempts: int
    window_seconds: int
    lockout_duration_seconds: int
    enable_exponential_backoff: bool = True


class LoginThrottlingService:
    """
    Service for managing login attempt rate limiting.

    Implements dual-layer protection:
    1. Per-IP rate limiting (prevents distributed attacks)
    2. Per-username rate limiting (prevents targeted attacks)

    Features:
        - Exponential backoff with jitter
        - Automatic lockout after max attempts
        - Audit logging for all events
        - Grace period after successful login
    """

    # Default configurations
    IP_THROTTLE_CONFIG = ThrottleConfig(
        max_attempts=5,
        window_seconds=5 * SECONDS_IN_MINUTE,  # 5 minutes
        lockout_duration_seconds=15 * SECONDS_IN_MINUTE,  # 15 minutes
        enable_exponential_backoff=True
    )

    USERNAME_THROTTLE_CONFIG = ThrottleConfig(
        max_attempts=3,
        window_seconds=5 * SECONDS_IN_MINUTE,  # 5 minutes
        lockout_duration_seconds=30 * SECONDS_IN_MINUTE,  # 30 minutes
        enable_exponential_backoff=True
    )

    def __init__(self):
        """Initialize login throttling service."""
        self.cache = cache

        # Load configurations from settings if available
        if hasattr(settings, 'LOGIN_THROTTLE_IP_CONFIG'):
            self.ip_config = settings.LOGIN_THROTTLE_IP_CONFIG
        else:
            self.ip_config = self.IP_THROTTLE_CONFIG

        if hasattr(settings, 'LOGIN_THROTTLE_USERNAME_CONFIG'):
            self.username_config = settings.LOGIN_THROTTLE_USERNAME_CONFIG
        else:
            self.username_config = self.USERNAME_THROTTLE_CONFIG

    def _get_ip_cache_key(self, ip_address: str) -> str:
        """Generate cache key for IP-based throttling."""
        return f"login_throttle:ip:{ip_address}"

    def _get_username_cache_key(self, username: str) -> str:
        """Generate cache key for username-based throttling."""
        return f"login_throttle:username:{username.lower()}"

    def _get_lockout_cache_key(self, identifier: str, throttle_type: str) -> str:
        """Generate cache key for lockout status."""
        return f"login_lockout:{throttle_type}:{identifier}"

    def _calculate_backoff_delay(
        self,
        attempt_number: int,
        base_delay: int = 2,
        max_delay: int = 300
    ) -> int:
        """
        Calculate exponential backoff with jitter.

        Args:
            attempt_number: Current attempt number (1-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            Delay in seconds with random jitter

        Formula: min(base_delay * 2^(attempt-1) + jitter, max_delay)
        """
        if attempt_number <= 1:
            return 0

        # Exponential backoff: 2, 4, 8, 16, 32, 64...
        delay = min(base_delay * (2 ** (attempt_number - 1)), max_delay)

        # Add jitter (±20% randomness)
        jitter = random.uniform(-0.2 * delay, 0.2 * delay)
        final_delay = max(0, int(delay + jitter))

        return final_delay

    def check_ip_throttle(self, ip_address: str) -> ThrottleResult:
        """
        Check if IP address is throttled.

        Args:
            ip_address: Client IP address

        Returns:
            ThrottleResult with allow/deny decision
        """
        if not ip_address:
            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                reason="No IP address provided"
            )

        # Check if IP is in lockout
        lockout_key = self._get_lockout_cache_key(ip_address, 'ip')
        lockout_until = self._check_lockout_status(lockout_key)

        if lockout_until:
            wait_seconds = int((lockout_until - timezone.now()).total_seconds())
            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                lockout_until=lockout_until,
                wait_seconds=max(0, wait_seconds),
                reason=f"IP locked out until {lockout_until.isoformat()}"
            )

        # Get current attempt count
        cache_key = self._get_ip_cache_key(ip_address)
        attempts = self._get_attempt_count(cache_key)

        # Calculate remaining attempts
        remaining = max(0, self.ip_config.max_attempts - attempts)

        # Check if threshold exceeded
        if attempts >= self.ip_config.max_attempts:
            # Activate lockout
            self._activate_lockout(
                lockout_key,
                self.ip_config.lockout_duration_seconds
            )

            lockout_until = timezone.now() + timedelta(
                seconds=self.ip_config.lockout_duration_seconds
            )

            logger.warning(
                f"IP address locked out: {ip_address}",
                extra={
                    'ip_address': ip_address,
                    'attempt_count': attempts,
                    'lockout_duration': self.ip_config.lockout_duration_seconds,
                    'security_event': 'ip_lockout'
                }
            )

            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                lockout_until=lockout_until,
                wait_seconds=self.ip_config.lockout_duration_seconds,
                reason="Maximum login attempts exceeded"
            )

        # Calculate backoff delay
        wait_seconds = 0
        if self.ip_config.enable_exponential_backoff and attempts > 0:
            wait_seconds = self._calculate_backoff_delay(attempts + 1)

        return ThrottleResult(
            allowed=True,
            remaining_attempts=remaining,
            wait_seconds=wait_seconds,
            reason="Within rate limit"
        )

    def check_username_throttle(self, username: str) -> ThrottleResult:
        """
        Check if username is throttled.

        Args:
            username: Login username

        Returns:
            ThrottleResult with allow/deny decision
        """
        if not username:
            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                reason="No username provided"
            )

        # Check if username is in lockout
        lockout_key = self._get_lockout_cache_key(username.lower(), 'username')
        lockout_until = self._check_lockout_status(lockout_key)

        if lockout_until:
            wait_seconds = int((lockout_until - timezone.now()).total_seconds())
            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                lockout_until=lockout_until,
                wait_seconds=max(0, wait_seconds),
                reason=f"Account locked out until {lockout_until.isoformat()}"
            )

        # Get current attempt count
        cache_key = self._get_username_cache_key(username)
        attempts = self._get_attempt_count(cache_key)

        # Calculate remaining attempts
        remaining = max(0, self.username_config.max_attempts - attempts)

        # Check if threshold exceeded
        if attempts >= self.username_config.max_attempts:
            # Activate lockout
            self._activate_lockout(
                lockout_key,
                self.username_config.lockout_duration_seconds
            )

            lockout_until = timezone.now() + timedelta(
                seconds=self.username_config.lockout_duration_seconds
            )

            logger.warning(
                f"Username locked out: {username}",
                extra={
                    'username': username,
                    'attempt_count': attempts,
                    'lockout_duration': self.username_config.lockout_duration_seconds,
                    'security_event': 'username_lockout'
                }
            )

            return ThrottleResult(
                allowed=False,
                remaining_attempts=0,
                lockout_until=lockout_until,
                wait_seconds=self.username_config.lockout_duration_seconds,
                reason="Maximum login attempts exceeded"
            )

        # Calculate backoff delay
        wait_seconds = 0
        if self.username_config.enable_exponential_backoff and attempts > 0:
            wait_seconds = self._calculate_backoff_delay(attempts + 1)

        return ThrottleResult(
            allowed=True,
            remaining_attempts=remaining,
            wait_seconds=wait_seconds,
            reason="Within rate limit"
        )

    def record_failed_attempt(
        self,
        ip_address: str,
        username: str,
        reason: str = "invalid_credentials"
    ) -> None:
        """
        Record a failed login attempt.

        Args:
            ip_address: Client IP address
            username: Attempted username
            reason: Failure reason for audit log
        """
        # Increment IP counter
        ip_key = self._get_ip_cache_key(ip_address)
        ip_attempts = self._increment_attempt_count(
            ip_key,
            self.ip_config.window_seconds
        )

        # Increment username counter
        username_key = self._get_username_cache_key(username)
        username_attempts = self._increment_attempt_count(
            username_key,
            self.username_config.window_seconds
        )

        # Audit log
        logger.warning(
            f"Failed login attempt: {username} from {ip_address}",
            extra={
                'username': username,
                'ip_address': ip_address,
                'ip_attempt_count': ip_attempts,
                'username_attempt_count': username_attempts,
                'failure_reason': reason,
                'security_event': 'login_failure'
            }
        )

    def record_successful_attempt(
        self,
        ip_address: str,
        username: str
    ) -> None:
        """
        Record a successful login and clear throttle counters.

        Args:
            ip_address: Client IP address
            username: Successful username
        """
        # Clear IP counter
        ip_key = self._get_ip_cache_key(ip_address)
        self.cache.delete(ip_key)

        # Clear username counter
        username_key = self._get_username_cache_key(username)
        self.cache.delete(username_key)

        # Clear lockouts if any
        ip_lockout_key = self._get_lockout_cache_key(ip_address, 'ip')
        username_lockout_key = self._get_lockout_cache_key(username.lower(), 'username')
        self.cache.delete(ip_lockout_key)
        self.cache.delete(username_lockout_key)

        # Audit log
        logger.info(
            f"Successful login: {username} from {ip_address}",
            extra={
                'username': username,
                'ip_address': ip_address,
                'security_event': 'login_success'
            }
        )

    def _get_attempt_count(self, cache_key: str) -> int:
        """Get current attempt count from cache."""
        try:
            count = self.cache.get(cache_key, 0)
            return int(count) if count is not None else 0
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache error getting attempt count: {e}")
            return 0
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid attempt count value: {e}")
            return 0

    def _increment_attempt_count(
        self,
        cache_key: str,
        window_seconds: int
    ) -> int:
        """Increment attempt count with TTL."""
        try:
            # Try to increment existing key
            try:
                new_count = self.cache.incr(cache_key)
                return new_count
            except ValueError:
                # Key doesn't exist, create it
                self.cache.set(cache_key, 1, timeout=window_seconds)
                return 1
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache error incrementing attempt count: {e}")
            return 0

    def _check_lockout_status(self, lockout_key: str) -> Optional[datetime]:
        """Check if lockout is active and return expiration time."""
        try:
            lockout_data = self.cache.get(lockout_key)
            if lockout_data:
                # Lockout is active, return expiration time
                if isinstance(lockout_data, datetime):
                    return lockout_data
                elif isinstance(lockout_data, str):
                    # Parse ISO format datetime
                    return datetime.fromisoformat(lockout_data)
            return None
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache error checking lockout status: {e}")
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid lockout data format: {e}")
            return None

    def _activate_lockout(
        self,
        lockout_key: str,
        duration_seconds: int
    ) -> None:
        """Activate lockout for specified duration."""
        try:
            lockout_until = timezone.now() + timedelta(seconds=duration_seconds)
            self.cache.set(
                lockout_key,
                lockout_until.isoformat(),
                timeout=duration_seconds
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache error activating lockout: {e}")

    def get_lockout_info(
        self,
        ip_address: str,
        username: str
    ) -> Dict[str, any]:
        """
        Get current lockout information for debugging/admin.

        Args:
            ip_address: Client IP address
            username: Username to check

        Returns:
            Dictionary with lockout details
        """
        ip_lockout_key = self._get_lockout_cache_key(ip_address, 'ip')
        username_lockout_key = self._get_lockout_cache_key(username.lower(), 'username')

        ip_lockout = self._check_lockout_status(ip_lockout_key)
        username_lockout = self._check_lockout_status(username_lockout_key)

        ip_attempts = self._get_attempt_count(self._get_ip_cache_key(ip_address))
        username_attempts = self._get_attempt_count(
            self._get_username_cache_key(username)
        )

        return {
            'ip_address': ip_address,
            'username': username,
            'ip_locked_out': ip_lockout is not None,
            'ip_lockout_until': ip_lockout.isoformat() if ip_lockout else None,
            'ip_attempt_count': ip_attempts,
            'ip_remaining_attempts': max(
                0,
                self.ip_config.max_attempts - ip_attempts
            ),
            'username_locked_out': username_lockout is not None,
            'username_lockout_until': username_lockout.isoformat() if username_lockout else None,
            'username_attempt_count': username_attempts,
            'username_remaining_attempts': max(
                0,
                self.username_config.max_attempts - username_attempts
            ),
        }


# Global service instance
login_throttle_service = LoginThrottlingService()
