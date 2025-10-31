"""
Legacy URL Redirect Middleware

Automatically redirects old/legacy URLs to their new standardized equivalents.
Tracks redirect usage for monitoring and eventual deprecation.

Usage:
    Add to MIDDLEWARE in settings.py:
    'apps.core.middleware.legacy_url_redirect.LegacyURLRedirectMiddleware'

Features:
    - Automatic HTTP 301 redirects for permanent moves
    - HTTP 302 redirects for temporary/testing redirects
    - Usage tracking and logging
    - Configurable redirect mappings
    - Query string preservation
    - Support for regex patterns
"""

import logging
import re
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect, HttpRequest
from django.urls import reverse, NoReverseMatch
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LegacyURLRedirectMiddleware:
    """
    Middleware to handle legacy URL redirects after URL architecture refactoring.

    Redirects old URL patterns to new standardized patterns while:
    - Preserving query strings
    - Logging usage for monitoring
    - Supporting both exact and regex pattern matching
    - Providing deprecation warnings
    """

    # Redirect mapping: old_pattern → (new_pattern, status_code, deprecation_date)
    # status_code: 301 = permanent, 302 = temporary
    REDIRECT_MAP = {
        # Scheduler paths

        # Peoples → People (grammatical fix)
        r'^/peoples/': ('/people/', 301, '2026-06-01'),

        # Work order management (verbose → concise)
        r'^/work_order_management/': ('/operations/work-orders/', 301, '2026-06-01'),

        # Help desk variations
        r'^/y_helpdesk/': ('/help-desk/', 301, '2026-06-01'),

        # Old operations URLs
        r'^/activity/adhoctasks/': ('/operations/tasks/adhoc/', 301, '2026-03-01'),
        r'^/activity/adhoctours/': ('/operations/tours/adhoc/', 301, '2026-03-01'),

        # Old scheduler URLs with incorrect spelling
        r'^/scheduler/schedhule_tour/': ('/operations/tours/schedule/', 301, '2026-03-01'),
        r'^/scheduler/schedhule_task/': ('/operations/tasks/schedule/', 301, '2026-03-01'),
        r'^/scheduler/jobneedtours/': ('/operations/tours/', 301, '2026-03-01'),
        r'^/scheduler/jobneedtasks/': ('/operations/tasks/', 301, '2026-03-01'),

        # Old API endpoints that should be under /api/v1/
        r'^/activity/api/meter_readings/': ('/api/v1/meter-readings/', 301, '2026-06-01'),
        r'^/activity/api/vehicle_entries/': ('/api/v1/vehicle-entries/', 301, '2026-06-01'),

        # Onboarding variations
        r'^/onboarding/typeassist/': ('/admin/config/types/', 301, '2026-03-01'),
        r'^/onboarding/shift/': ('/admin/config/shifts/', 301, '2026-03-01'),
        r'^/onboarding/geofence/': ('/admin/config/geofences/', 301, '2026-03-01'),

        # Client billing
        r'^/clientbilling/': ('/admin/billing/', 301, '2026-06-01'),

        # Legacy authentication URLs
        r'^/peoples/verifyemail': ('/auth/verify-email/', 301, '2026-03-01'),

        # Old attendance URLs
        r'^/attendance/': ('/people/attendance/', 301, '2026-03-01'),
    }

    # Exact URL redirects (faster lookup, no regex)
    EXACT_REDIRECT_MAP = {
        '/peoples/': ('/people/', 301),
        '/y_helpdesk/': ('/help-desk/', 301),
    }

    # URLs to exclude from redirect logging (too noisy)
    EXCLUDE_FROM_LOGGING = {
        '/static/',
        '/media/',
        '/favicon.ico',
        '/__debug__/',
        '/api/health/',
    }

    # Cache key prefix for tracking redirect usage
    CACHE_PREFIX = 'legacy_url_redirect'
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, get_response):
        self.get_response = get_response

        # Compile regex patterns for performance
        self.compiled_patterns = [
            (re.compile(pattern), new_url, status, deprecation_date)
            for pattern, (new_url, status, deprecation_date) in self.REDIRECT_MAP.items()
        ]

        # Check if redirect tracking is enabled
        self.enable_tracking = getattr(
            settings, 'LEGACY_URL_REDIRECT_TRACKING', True
        )

        # Check if redirects are enabled (can be disabled in production initially)
        self.enable_redirects = getattr(
            settings, 'LEGACY_URL_REDIRECT_ENABLED', True
        )

        logger.info(
            f"LegacyURLRedirectMiddleware initialized: "
            f"redirects={'enabled' if self.enable_redirects else 'disabled'}, "
            f"tracking={'enabled' if self.enable_tracking else 'disabled'}"
        )

    def __call__(self, request: HttpRequest):
        """
        Process the request through the middleware.
        """
        # Skip redirect processing for excluded paths
        if self._should_skip(request.path):
            return self.get_response(request)

        # Try exact match first (faster)
        redirect_response = self._try_exact_redirect(request)
        if redirect_response:
            return redirect_response

        # Try regex pattern match
        redirect_response = self._try_pattern_redirect(request)
        if redirect_response:
            return redirect_response

        # No redirect needed, continue with normal request processing
        return self.get_response(request)

    def _should_skip(self, path: str) -> bool:
        """
        Check if the path should be excluded from redirect processing.
        """
        return any(path.startswith(excluded) for excluded in self.EXCLUDE_FROM_LOGGING)

    def _try_exact_redirect(self, request: HttpRequest) -> Optional[HttpResponsePermanentRedirect]:
        """
        Try exact URL match for faster redirect (no regex).
        """
        if not self.enable_redirects:
            return None

        path = request.path
        if path in self.EXACT_REDIRECT_MAP:
            new_url, status_code = self.EXACT_REDIRECT_MAP[path]
            return self._create_redirect_response(
                request, path, new_url, status_code, 'exact_match'
            )

        return None

    def _try_pattern_redirect(self, request: HttpRequest) -> Optional[HttpResponsePermanentRedirect]:
        """
        Try regex pattern match for redirect.
        """
        if not self.enable_redirects:
            return None

        path = request.path

        for pattern, new_url_template, status_code, deprecation_date in self.compiled_patterns:
            match = pattern.search(path)
            if match:
                # Replace matched pattern with new URL
                new_path = pattern.sub(new_url_template, path)

                # Check if deprecation warning needed
                if self._is_near_deprecation(deprecation_date):
                    logger.warning(
                        f"Legacy URL redirect near deprecation: {path} → {new_path} "
                        f"(deprecation date: {deprecation_date})"
                    )

                return self._create_redirect_response(
                    request, path, new_path, status_code, 'pattern_match'
                )

        return None

    def _create_redirect_response(
        self,
        request: HttpRequest,
        old_url: str,
        new_url: str,
        status_code: int,
        match_type: str
    ):
        """
        Create redirect response with query string preservation and tracking.
        """
        # Preserve query string
        query_string = request.META.get('QUERY_STRING', '')
        if query_string:
            new_url = f"{new_url}?{query_string}"

        # Track redirect usage
        if self.enable_tracking:
            self._track_redirect_usage(old_url, new_url, match_type, request)

        # Log redirect
        logger.info(
            f"Legacy URL redirect ({match_type}): {old_url} → {new_url} "
            f"[{status_code}] (user: {getattr(request.user, 'username', 'anonymous')})"
        )

        # Create appropriate redirect response
        if status_code == 301:
            response = HttpResponsePermanentRedirect(new_url)
        else:
            response = HttpResponseRedirect(new_url)

        # Add informative headers
        response['X-Redirect-Reason'] = 'legacy-url-migration'
        response['X-Redirect-Type'] = match_type
        response['X-Original-URL'] = old_url

        return response

    def _track_redirect_usage(
        self,
        old_url: str,
        new_url: str,
        match_type: str,
        request: HttpRequest
    ):
        """
        Track redirect usage in cache for monitoring.
        """
        try:
            cache_key = f"{self.CACHE_PREFIX}:{old_url}"
            usage_data = cache.get(cache_key, {})

            # Update usage statistics
            usage_data['count'] = usage_data.get('count', 0) + 1
            usage_data['new_url'] = new_url
            usage_data['match_type'] = match_type
            usage_data['last_used'] = datetime.now(dt_timezone.utc).isoformat()
            usage_data['users'] = usage_data.get('users', set())

            if request.user.is_authenticated:
                usage_data['users'].add(request.user.username)

            # Store back in cache
            cache.set(cache_key, usage_data, self.CACHE_TTL)

        except Exception as e:
            logger.error(f"Error tracking redirect usage: {e}")

    def _is_near_deprecation(self, deprecation_date_str: str) -> bool:
        """
        Check if we're within 30 days of deprecation date.
        """
        try:
            from datetime import datetime
            deprecation_date = datetime.strptime(deprecation_date_str, '%Y-%m-%d')
            days_until_deprecation = (deprecation_date - datetime.now()).days
            return 0 < days_until_deprecation <= 30
        except Exception:
            return False

    @classmethod
    def get_redirect_statistics(cls) -> Dict[str, dict]:
        """
        Get redirect usage statistics from cache.

        Returns:
            Dictionary of old_url → usage_data
        """
        stats = {}
        try:
            # Get all redirect cache keys
            cache_pattern = f"{cls.CACHE_PREFIX}:*"
            # Note: This is Redis-specific; adjust for other cache backends
            for key in cache.keys(cache_pattern):
                old_url = key.replace(f"{cls.CACHE_PREFIX}:", '')
                stats[old_url] = cache.get(key, {})
        except Exception as e:
            logger.error(f"Error fetching redirect statistics: {e}")

        return stats

    @classmethod
    def clear_redirect_statistics(cls):
        """
        Clear all redirect tracking statistics.
        """
        try:
            cache_pattern = f"{cls.CACHE_PREFIX}:*"
            for key in cache.keys(cache_pattern):
                cache.delete(key)
            logger.info("Cleared all legacy URL redirect statistics")
        except Exception as e:
            logger.error(f"Error clearing redirect statistics: {e}")


# Management command helpers
def get_redirect_report() -> str:
    """
    Generate a human-readable redirect usage report.

    Usage in Django shell:
        >>> from apps.core.middleware.legacy_url_redirect import get_redirect_report
        >>> print(get_redirect_report())
    """
    stats = LegacyURLRedirectMiddleware.get_redirect_statistics()

    if not stats:
        return "No legacy URL redirects recorded."

    lines = [
        "=" * 80,
        "LEGACY URL REDIRECT REPORT",
        "=" * 80,
        f"Total Unique Legacy URLs: {len(stats)}",
        f"Total Redirects: {sum(s.get('count', 0) for s in stats.values())}",
        "",
        "Top 10 Most Used Legacy URLs:",
        "-" * 80,
    ]

    # Sort by usage count
    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1].get('count', 0),
        reverse=True
    )[:10]

    for old_url, data in sorted_stats:
        lines.append(f"  {old_url}")
        lines.append(f"    → {data.get('new_url', 'N/A')}")
        lines.append(f"    Count: {data.get('count', 0)}")
        lines.append(f"    Last Used: {data.get('last_used', 'N/A')}")
        lines.append(f"    Match Type: {data.get('match_type', 'N/A')}")
        lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def export_redirect_statistics_json() -> dict:
    """
    Export redirect statistics as JSON for external analysis.

    Usage:
        >>> from apps.core.middleware.legacy_url_redirect import export_redirect_statistics_json
        >>> import json
        >>> stats = export_redirect_statistics_json()
        >>> with open('redirect_stats.json', 'w') as f:
        ...     json.dump(stats, f, indent=2)
    """
    stats = LegacyURLRedirectMiddleware.get_redirect_statistics()

    # Convert sets to lists for JSON serialization
    for data in stats.values():
        if 'users' in data and isinstance(data['users'], set):
            data['users'] = list(data['users'])

    return {
        'generated_at': datetime.now(dt_timezone.utc).isoformat(),
        'total_unique_urls': len(stats),
        'total_redirects': sum(s.get('count', 0) for s in stats.values()),
        'statistics': stats
    }
