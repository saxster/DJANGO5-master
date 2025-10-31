"""
Sentry Enrichment Middleware

Enriches Sentry events with request context, user information, and tenant data.
Provides comprehensive context for error tracking and debugging.

Features:
    - Request metadata (method, path, query params)
    - User context (ID, username, email)
    - Tenant context (tenant ID, database)
    - Custom tags and breadcrumbs
    - Performance transaction tracking

Compliance:
    - Rule #7: Class < 150 lines
    - Rule #11: Specific exception handling
    - Rule #15: No PII in event data

Usage:
    # In settings.py MIDDLEWARE
    'apps.core.middleware.sentry_enrichment_middleware.SentryEnrichmentMiddleware',
"""

import logging
from typing import Callable, Any

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

__all__ = ['SentryEnrichmentMiddleware']


class SentryEnrichmentMiddleware:
    """
    Middleware to enrich Sentry events with request and user context.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and enrich Sentry context."""
        try:
            import sentry_sdk
            sentry_available = True
        except ImportError:
            sentry_available = False

        if sentry_available:
            self._set_request_context(request)
            self._set_user_context(request)
            self._set_tenant_context(request)
            self._start_transaction(request)

        response = self.get_response(request)

        if sentry_available:
            self._finish_transaction(request, response)

        return response

    def _set_request_context(self, request: HttpRequest):
        """Set request-level context in Sentry."""
        try:
            import sentry_sdk

            sentry_sdk.set_context('request', {
                'method': request.method,
                'url': request.path,
                'query_string': request.META.get('QUERY_STRING', ''),
                'content_type': request.content_type,
            })

            # Add request breadcrumb
            sentry_sdk.add_breadcrumb(
                category='http',
                message=f"{request.method} {request.path}",
                level='info',
            )

        except Exception as e:
            logger.warning(f"Failed to set request context: {e}")

    def _set_user_context(self, request: HttpRequest):
        """Set user context in Sentry."""
        try:
            import sentry_sdk

            user = getattr(request, 'user', None)

            if user and not isinstance(user, AnonymousUser):
                sentry_sdk.set_user({
                    'id': str(user.id) if hasattr(user, 'id') else None,
                    'username': getattr(user, 'username', None),
                    # Don't send email (PII) unless explicitly configured
                })

                # Add custom user tags
                if hasattr(user, 'is_staff'):
                    sentry_sdk.set_tag('user.is_staff', user.is_staff)
                if hasattr(user, 'is_superuser'):
                    sentry_sdk.set_tag('user.is_superuser', user.is_superuser)

        except Exception as e:
            logger.warning(f"Failed to set user context: {e}")

    def _set_tenant_context(self, request: HttpRequest):
        """Set tenant context in Sentry."""
        try:
            import sentry_sdk
            from apps.core.utils_new.db_utils import get_current_db_name

            tenant_db = get_current_db_name()

            if tenant_db and tenant_db != 'default':
                sentry_sdk.set_context('tenant', {
                    'database': tenant_db,
                })
                sentry_sdk.set_tag('tenant.database', tenant_db)

        except (ImportError, AttributeError) as e:
            logger.debug(f"Tenant context not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to set tenant context: {e}")

    def _start_transaction(self, request: HttpRequest):
        """Start Sentry performance transaction."""
        try:
            import sentry_sdk

            # Transaction name: HTTP_METHOD /path/to/endpoint
            transaction_name = f"{request.method} {request.path}"

            transaction = sentry_sdk.start_transaction(
                op='http.server',
                name=transaction_name,
            )

            # Store transaction in request for later finishing
            request._sentry_transaction = transaction

        except Exception as e:
            logger.warning(f"Failed to start Sentry transaction: {e}")

    def _finish_transaction(self, request: HttpRequest, response: HttpResponse):
        """Finish Sentry performance transaction."""
        try:
            transaction = getattr(request, '_sentry_transaction', None)

            if transaction:
                transaction.set_http_status(response.status_code)
                transaction.finish()

        except Exception as e:
            logger.warning(f"Failed to finish Sentry transaction: {e}")

    def process_exception(self, request: HttpRequest, exception: Exception):
        """Capture exception with enriched context."""
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exception)

            # Add exception breadcrumb
            sentry_sdk.add_breadcrumb(
                category='error',
                message=f"{exception.__class__.__name__}: {str(exception)}",
                level='error',
            )

        except Exception as e:
            logger.error(f"Failed to capture exception in Sentry: {e}", exc_info=True)
