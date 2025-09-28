"""
API Deprecation Headers Middleware
Implements RFC 9745 (Deprecation) and RFC 8594 (Sunset) standards.

Compliance with .claude/rules.md:
- Rule #6: Module < 200 lines
- Rule #11: Specific exception handling
- Rule #15: No sensitive data logging
"""

import re
import logging
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
from django.db import DatabaseError

logger = logging.getLogger('api.deprecation')


class APIDeprecationMiddleware(MiddlewareMixin):
    """
    Adds deprecation headers to API responses per RFC 9745 and RFC 8594.

    Headers added:
    - Deprecation: Unix timestamp when endpoint was deprecated (RFC 9745)
    - Sunset: HTTP date when endpoint will be removed (RFC 8594)
    - Warning: 299 code with deprecation message (RFC 7234)
    - Link: URL to migration documentation (RFC 8288)
    - X-API-Version: Current API version
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.cache_timeout = 3600
        self.api_paths = ['/api/', '/graphql/']

    def process_response(self, request, response):
        """Add deprecation headers if endpoint is deprecated."""
        if not self._is_api_request(request):
            return response

        try:
            deprecation = self._get_deprecation_info(request)
            if deprecation:
                self._add_deprecation_headers(response, deprecation)
                self._log_usage(request, deprecation)

        except ObjectDoesNotExist:
            pass
        except DatabaseError as e:
            logger.error(
                "Database error checking deprecation status",
                extra={'path': request.path, 'error': str(e)}
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                "Invalid deprecation data",
                extra={'path': request.path, 'error': str(e)}
            )

        return response

    def _is_api_request(self, request):
        """Check if request is to an API endpoint."""
        return any(request.path.startswith(path) for path in self.api_paths)

    def _get_deprecation_info(self, request):
        """Get deprecation info from cache or database."""
        cache_key = f"api_deprecation:{self._normalize_path(request.path)}"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached if cached != 'NOT_DEPRECATED' else None

        try:
            from apps.core.models.api_deprecation import APIDeprecation

            deprecation = APIDeprecation.objects.filter(
                endpoint_pattern=self._normalize_path(request.path),
                status__in=['deprecated', 'sunset_warning']
            ).first()

            if deprecation:
                deprecation.update_status()
                cache.set(cache_key, deprecation, self.cache_timeout)
            else:
                cache.set(cache_key, 'NOT_DEPRECATED', self.cache_timeout)

            return deprecation

        except DatabaseError:
            raise
        except (ValueError, ImportError) as e:
            logger.warning(f"Failed to load deprecation info: {e}")
            return None

    def _normalize_path(self, path):
        """
        Normalize API path to match deprecation registry patterns.
        /api/v1/people/123/ -> /api/v1/people/
        """
        path = re.sub(r'/\d+/', '/{id}/', path)
        path = re.sub(r'/[0-9a-f-]{36}/', '/{uuid}/', path)

        if not path.endswith('/'):
            path += '/'

        return path

    def _add_deprecation_headers(self, response, deprecation):
        """Add RFC-compliant deprecation headers."""
        if deprecation.deprecated_date:
            response['Deprecation'] = deprecation.get_deprecation_header()

        if deprecation.sunset_date:
            response['Sunset'] = deprecation.get_sunset_header()

        warning = deprecation.get_warning_header()
        if warning:
            response['Warning'] = warning

        link = deprecation.get_link_header()
        if link:
            response['Link'] = link

        response['X-Deprecated-Replacement'] = deprecation.replacement_endpoint or ''
        response['X-Deprecated-Version'] = deprecation.version_deprecated

    def _log_usage(self, request, deprecation):
        """Log deprecated endpoint usage for analytics."""
        if not deprecation.notify_on_usage:
            return

        try:
            from apps.core.models.api_deprecation import APIDeprecationUsage

            client_version = self._extract_client_version(request)
            user_id = request.user.id if request.user.is_authenticated else None

            APIDeprecationUsage.objects.create(
                deprecation=deprecation,
                user_id=user_id,
                client_version=client_version,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )

            logger.warning(
                f"Deprecated API usage detected",
                extra={
                    'endpoint': deprecation.endpoint_pattern,
                    'user_id': user_id,
                    'client_version': client_version,
                    'days_until_sunset': (deprecation.sunset_date - timezone.now()).days if deprecation.sunset_date else None,
                }
            )

        except DatabaseError as e:
            logger.error(f"Failed to log deprecation usage: {e}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid usage data: {e}")

    def _extract_client_version(self, request):
        """Extract client version from headers or user agent."""
        version_header = request.META.get('HTTP_X_CLIENT_VERSION')
        if version_header:
            return version_header

        user_agent = request.META.get('HTTP_USER_AGENT', '')

        match = re.search(r'IntelliWiz/(\d+\.\d+\.\d+)', user_agent)
        if match:
            return match.group(1)

        match = re.search(r'Version/(\d+\.\d+)', user_agent)
        if match:
            return match.group(1)

        return 'unknown'

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


from django.utils import timezone

__all__ = ['APIDeprecationMiddleware']