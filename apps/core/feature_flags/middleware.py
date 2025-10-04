"""
Feature Flag Middleware

Adds feature flag context to requests.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS
from .service import FeatureFlagService

logger = logging.getLogger(__name__)


class FeatureFlagMiddleware(MiddlewareMixin):
    """
    Middleware to attach feature flag checking to requests.

    Adds `request.feature_flags` object with helper methods.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Attach feature flag helper to request."""
        request.feature_flags = FeatureFlagHelper(request)
        return None


class FeatureFlagHelper:
    """
    Helper class attached to request for easy feature flag checks.

    Usage in views:
        if request.feature_flags.is_enabled('new_dashboard'):
            return new_dashboard_view(request)
    """

    def __init__(self, request: HttpRequest):
        self.request = request
        self.user = getattr(request, 'user', None)
        self._cache = {}

    def is_enabled(self, flag_name: str) -> bool:
        """
        Check if feature flag is enabled for current request.

        Args:
            flag_name: Name of the feature flag

        Returns:
            True if feature is enabled
        """
        # Check local cache first
        if flag_name in self._cache:
            return self._cache[flag_name]

        try:
            result = FeatureFlagService.is_enabled(
                flag_name,
                user=self.user,
                request=self.request
            )

            self._cache[flag_name] = result
            return result

        except (DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS) as e:
            logger.error(
                f"Error checking feature flag '{flag_name}': {e}",
                exc_info=True
            )
            return False

    def get_enabled_flags(self) -> list:
        """
        Get list of all enabled flags for current request.

        Returns:
            List of enabled flag names
        """
        try:
            from waffle.models import Flag

            all_flags = Flag.objects.filter(everyone=True).values_list('name', flat=True)

            enabled = []
            for flag_name in all_flags:
                if self.is_enabled(flag_name):
                    enabled.append(flag_name)

            return enabled

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error getting enabled flags: {e}", exc_info=True)
            return []

    def __contains__(self, flag_name: str) -> bool:
        """Allow 'in' operator: if 'beta_feature' in request.feature_flags:"""
        return self.is_enabled(flag_name)

    def __getitem__(self, flag_name: str) -> bool:
        """Allow dict-like access: request.feature_flags['beta_feature']"""
        return self.is_enabled(flag_name)
