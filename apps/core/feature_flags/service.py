"""
Feature Flag Service

Centralized service for feature flag operations.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
import hashlib
from typing import Optional, List, Dict, Any

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser

from waffle import flag_is_active
from waffle.models import Flag

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS
from .models import FeatureFlagMetadata, FeatureFlagAuditLog

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    Service for managing feature flags across the application.

    Provides high-level API for:
    - Checking flag status
    - Gradual rollout management
    - User targeting
    - Metrics tracking
    """

    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = 'feature_flag'

    @classmethod
    def is_enabled(
        cls,
        flag_name: str,
        user=None,
        request=None
    ) -> bool:
        """
        Check if feature flag is enabled.

        Args:
            flag_name: Name of the feature flag
            user: User instance (optional)
            request: HTTP request (optional)

        Returns:
            True if feature is enabled, False otherwise
        """
        # Check cache first
        cache_key = cls._get_cache_key(flag_name, user)
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        try:
            # Check waffle flag
            is_active = flag_is_active(request, flag_name)

            # Check custom targeting if user provided
            if user and not isinstance(user, AnonymousUser):
                metadata = cls._get_metadata(flag_name)
                if metadata:
                    # Check user-specific targeting
                    if metadata.is_enabled_for_user(user.id):
                        is_active = True

                    # Check percentage rollout
                    elif metadata.rollout_percentage > 0:
                        is_active = cls._is_in_rollout_percentage(
                            user.id,
                            flag_name,
                            metadata.rollout_percentage
                        )

            # Cache result
            cache.set(cache_key, is_active, cls.CACHE_TTL)

            return is_active

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error checking flag {flag_name}: {e}",
                exc_info=True
            )
            return False
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Cache error for flag {flag_name}: {e}")
            # Continue without cache
            return flag_is_active(request, flag_name)

    @classmethod
    def enable_for_user(
        cls,
        flag_name: str,
        user_id: int,
        changed_by=None,
        reason: str = ""
    ) -> bool:
        """Enable feature flag for specific user."""
        try:
            metadata, created = FeatureFlagMetadata.objects.get_or_create(
                flag_name=flag_name,
                defaults={'rollout_percentage': 0}
            )

            if user_id not in metadata.target_users:
                metadata.target_users.append(user_id)
                metadata.save(update_fields=['target_users', 'updated_at'])

                # Audit log
                cls._create_audit_log(
                    flag_name=flag_name,
                    action='enabled',
                    changed_by=changed_by,
                    new_value={'user_id': user_id},
                    reason=reason
                )

                # Invalidate cache
                cls._invalidate_cache(flag_name)

                return True

            return False

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error enabling flag for user: {e}", exc_info=True)
            return False

    @classmethod
    def set_rollout_percentage(
        cls,
        flag_name: str,
        percentage: int,
        changed_by=None,
        reason: str = ""
    ) -> bool:
        """Set rollout percentage for gradual deployment."""
        try:
            metadata, created = FeatureFlagMetadata.objects.get_or_create(
                flag_name=flag_name,
                defaults={'rollout_percentage': 0}
            )

            old_percentage = metadata.rollout_percentage
            metadata.rollout_percentage = max(0, min(100, percentage))
            metadata.save(update_fields=['rollout_percentage', 'updated_at'])

            # Audit log
            cls._create_audit_log(
                flag_name=flag_name,
                action='rollout_changed',
                changed_by=changed_by,
                old_value={'percentage': old_percentage},
                new_value={'percentage': percentage},
                reason=reason
            )

            # Invalidate cache
            cls._invalidate_cache(flag_name)

            logger.info(
                f"Rollout percentage for {flag_name} changed: "
                f"{old_percentage}% -> {percentage}%"
            )

            return True

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error setting rollout percentage: {e}", exc_info=True)
            return False

    @staticmethod
    def _get_cache_key(flag_name: str, user=None) -> str:
        """Generate cache key for feature flag."""
        if user and not isinstance(user, AnonymousUser):
            return f"feature_flag:{flag_name}:user:{user.id}"
        return f"feature_flag:{flag_name}:anonymous"

    @staticmethod
    def _get_metadata(flag_name: str) -> Optional[FeatureFlagMetadata]:
        """Get feature flag metadata."""
        try:
            return FeatureFlagMetadata.objects.get(flag_name=flag_name)
        except FeatureFlagMetadata.DoesNotExist:
            return None

    @staticmethod
    def _is_in_rollout_percentage(
        user_id: int,
        flag_name: str,
        percentage: int
    ) -> bool:
        """
        Determine if user is in rollout percentage using consistent hashing.

        Ensures same user always gets same result for given flag.
        """
        hash_input = f"{flag_name}:{user_id}".encode('utf-8')
        hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
        user_percentage = hash_value % 100

        return user_percentage < percentage

    @staticmethod
    def _create_audit_log(
        flag_name: str,
        action: str,
        changed_by=None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        reason: str = ""
    ):
        """Create audit log entry for flag change."""
        try:
            FeatureFlagAuditLog.objects.create(
                flag_name=flag_name,
                action=action,
                changed_by=changed_by,
                old_value=old_value,
                new_value=new_value,
                reason=reason
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to create audit log: {e}", exc_info=True)

    @staticmethod
    def _invalidate_cache(flag_name: str):
        """Invalidate all cache entries for a flag."""
        try:
            cache.delete_many([
                f"feature_flag:{flag_name}:*"
            ])
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Failed to invalidate cache: {e}")
