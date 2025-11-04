"""
Unified Tenant Middleware - Single Source of Truth

This middleware consolidates the functionality of:
1. TenantMiddleware (apps/tenants/middlewares.py)
2. MultiTenantURLMiddleware (apps/core/middleware/multi_tenant_url.py)

Into a single, comprehensive tenant context management middleware.

Features:
    - Multiple tenant identification strategies (hostname, path, header, JWT)
    - Sets BOTH THREAD_LOCAL.DB and request.tenant
    - Automatic cleanup in finally block
    - Tenant-aware caching
    - Inactive/deleted tenant handling
    - Comprehensive audit logging

Migration:
    Replace both old middlewares with this one in settings.py:

    OLD:
        'apps.tenants.middlewares.TenantMiddleware',
        'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware',

    NEW:
        'apps.tenants.middleware_unified.UnifiedTenantMiddleware',

Author: Multi-Tenancy Hardening - Comprehensive Resolution
Date: 2025-11-03
"""

import logging
import re
from typing import Optional
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseGone
from django.apps import apps as django_apps

from apps.tenants.models import Tenant
from apps.tenants.utils import get_tenant_by_slug, cleanup_tenant_context
from apps.tenants.constants import (
    DEFAULT_DB_ALIAS,
    SECURITY_EVENT_UNKNOWN_TENANT,
    SECURITY_EVENT_DELETED_TENANT_ACCESS,
)
from apps.core.utils_new.db_utils import THREAD_LOCAL, set_db_for_router
from apps.core.cache.tenant_aware import tenant_cache

logger = logging.getLogger('tenants.middleware')
security_logger = logging.getLogger('security.tenant_operations')


class TenantContext:
    """
    Stores tenant information for the current request.

    Attributes:
        tenant_pk: Tenant primary key (integer)
        tenant_slug: Tenant subdomain prefix (hyphenated)
        tenant_name: Human-readable tenant name
        db_alias: Database alias for routing (underscored)
    """

    def __init__(
        self,
        tenant_pk: int,
        tenant_slug: str,
        tenant_name: str,
        db_alias: str
    ):
        self.tenant_pk = tenant_pk
        self.tenant_slug = tenant_slug
        self.tenant_name = tenant_name
        self.db_alias = db_alias

    def __str__(self):
        return f"Tenant({self.tenant_slug})"

    def __repr__(self):
        return f"TenantContext(pk={self.tenant_pk}, slug={self.tenant_slug}, db={self.db_alias})"


class UnifiedTenantMiddleware:
    """
    Unified tenant middleware providing complete multi-tenant isolation.

    This middleware:
    1. Extracts tenant from request (hostname, path, header, or JWT)
    2. Sets THREAD_LOCAL.DB for database routing
    3. Sets request.tenant for view/template access
    4. Validates tenant is active
    5. Cleans up context in finally block
    6. Handles suspended/deleted tenants gracefully

    Configuration (settings.py):
        TENANT_STRICT_MODE = True  # Reject unknown hostnames (default in production)
        MULTI_TENANT_MODE = 'hostname'  # or 'path', 'header', 'auto'
        MULTI_TENANT_REQUIRE = False  # If True, all requests must have tenant
    """

    # URL path pattern for tenant extraction: /t/{tenant_slug}/
    TENANT_PATH_PATTERN = re.compile(r'^/t/(?P<tenant_slug>[\w-]+)/')

    # URLs to exclude from tenant extraction
    EXCLUDE_PATHS = {
        '/static/', '/media/', '/admin/django/', '/api/health/',
        '/health/', '/ready/', '/alive/', '/__debug__/', '/favicon.ico',
    }

    # Cache configuration
    CACHE_PREFIX = 'unified_tenant_lookup'
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, get_response):
        self.get_response = get_response

        # Load configuration
        self.strict_mode = getattr(settings, 'TENANT_STRICT_MODE', not settings.DEBUG)
        self.mode = getattr(settings, 'MULTI_TENANT_MODE', 'hostname')
        self.require_tenant = getattr(settings, 'MULTI_TENANT_REQUIRE', False)

        # Get tenant mappings
        from intelliwiz_config.settings.tenants import TENANT_MAPPINGS
        self.tenant_mappings = TENANT_MAPPINGS

        logger.info(
            f"UnifiedTenantMiddleware initialized: "
            f"mode={self.mode}, strict={self.strict_mode}, require={self.require_tenant}"
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and set tenant context.

        Args:
            request: HTTP request

        Returns:
            HTTP response (or 403/410 if tenant invalid)

        Security:
            - Thread-local context ALWAYS cleaned up in finally block
            - Inactive tenants rejected with 410 Gone
            - Unknown tenants rejected with 403 Forbidden (strict mode)
        """
        # Skip tenant extraction for excluded paths
        if self._should_skip(request.path):
            return self.get_response(request)

        tenant_context = None

        try:
            # Extract tenant using configured strategy
            tenant_context = self._extract_tenant(request)

            if tenant_context:
                # Set database routing context
                set_db_for_router(tenant_context.db_alias)

                # Set request context
                request.tenant = tenant_context

                # Log successful routing
                logger.debug(
                    "Request routed to tenant",
                    extra={
                        'hostname': request.get_host(),
                        'tenant_slug': tenant_context.tenant_slug,
                        'db_alias': tenant_context.db_alias,
                        'path': request.path
                    }
                )

            elif self.require_tenant:
                # Tenant required but not found
                logger.warning(
                    "Tenant required but not found",
                    extra={
                        'hostname': request.get_host(),
                        'path': request.path,
                        'security_event': SECURITY_EVENT_UNKNOWN_TENANT
                    }
                )
                return HttpResponseForbidden("Tenant context required")

            else:
                # No tenant context (acceptable for some views)
                request.tenant = None

            # Process request
            try:
                response = self.get_response(request)

                # Add tenant info to response headers (for debugging)
                if tenant_context:
                    response['X-Tenant-Slug'] = tenant_context.tenant_slug
                    response['X-Tenant-ID'] = str(tenant_context.tenant_pk)
                    response['X-DB-Alias'] = tenant_context.db_alias

                return response

            finally:
                # CRITICAL: Always cleanup thread-local
                cleanup_tenant_context()

        except HttpResponseGone as e:
            # Tenant deleted/suspended - return immediately
            return e

        except HttpResponseForbidden as e:
            # Unknown tenant in strict mode - return immediately
            return e

    def _should_skip(self, path: str) -> bool:
        """Check if path should be excluded from tenant extraction."""
        return any(path.startswith(exclude) for exclude in self.EXCLUDE_PATHS)

    def _extract_tenant(self, request: HttpRequest) -> Optional[TenantContext]:
        """
        Extract tenant from request using configured strategy.

        Strategies (in priority order if mode='auto'):
        1. Hostname mapping
        2. URL path (/t/{tenant_slug}/)
        3. HTTP header (X-Tenant-ID, X-Tenant-Slug)
        4. JWT claim (tenant_id, tenant_slug)

        Args:
            request: HTTP request

        Returns:
            TenantContext if tenant found and active, None otherwise

        Raises:
            HttpResponseForbidden: If strict mode rejects unknown hostname
            HttpResponseGone: If tenant is inactive/deleted
        """
        tenant_slug = None

        # Strategy 1: Hostname mapping (default)
        if self.mode in ('hostname', 'auto'):
            tenant_slug = self._extract_from_hostname(request)

        # Strategy 2: URL path
        if not tenant_slug and self.mode in ('path', 'auto'):
            tenant_slug = self._extract_from_path(request)

        # Strategy 3: HTTP headers
        if not tenant_slug and self.mode in ('header', 'auto'):
            tenant_slug = self._extract_from_header(request)

        # Strategy 4: JWT claim
        if not tenant_slug and self.mode in ('jwt', 'auto'):
            tenant_slug = self._extract_from_jwt(request)

        if not tenant_slug:
            return None

        # Look up tenant (with caching)
        return self._get_tenant_context(tenant_slug, request)

    def _extract_from_hostname(self, request: HttpRequest) -> Optional[str]:
        """Extract tenant slug from hostname mapping."""
        hostname = request.get_host().lower()
        db_alias = self.tenant_mappings.get(hostname)

        if db_alias:
            # Convert database alias to tenant slug
            from apps.tenants.utils import db_alias_to_slug
            return db_alias_to_slug(db_alias)

        # Unknown hostname
        if self.strict_mode:
            security_logger.warning(
                "Unknown hostname in strict mode",
                extra={
                    'hostname': hostname,
                    'path': request.path,
                    'security_event': SECURITY_EVENT_UNKNOWN_TENANT
                }
            )
            raise HttpResponseForbidden(
                "Access denied: Unknown tenant hostname. "
                "Please contact your administrator."
            )

        return None

    def _extract_from_path(self, request: HttpRequest) -> Optional[str]:
        """Extract tenant slug from URL path (/t/{tenant_slug}/)."""
        match = self.TENANT_PATH_PATTERN.match(request.path)
        if match:
            tenant_slug = match.group('tenant_slug')

            # Strip tenant prefix from path for URL resolution
            request.path_info = self.TENANT_PATH_PATTERN.sub('/', request.path)
            request.path = request.path_info

            logger.debug(f"Tenant extracted from path: {tenant_slug}")
            return tenant_slug

        return None

    def _extract_from_header(self, request: HttpRequest) -> Optional[str]:
        """Extract tenant slug from HTTP headers."""
        # Try X-Tenant-Slug first
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if tenant_slug:
            return tenant_slug.lower()

        # Try X-Tenant-ID (could be PK or slug)
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            # If numeric, assume it's a PK
            if tenant_id.isdigit():
                tenant = get_tenant_by_pk(int(tenant_id))
                return tenant.subdomain_prefix if tenant else None
            else:
                return tenant_id.lower()

        return None

    def _extract_from_jwt(self, request: HttpRequest) -> Optional[str]:
        """Extract tenant slug from JWT claims."""
        # This requires JWT to be already validated by authentication middleware
        if hasattr(request, 'auth') and hasattr(request.auth, 'payload'):
            payload = request.auth.payload

            # Try tenant_slug claim first
            if 'tenant_slug' in payload:
                return payload['tenant_slug'].lower()

            # Try tenant_id (could be PK or slug)
            if 'tenant_id' in payload:
                tenant_id = payload['tenant_id']
                if isinstance(tenant_id, int):
                    tenant = get_tenant_by_pk(tenant_id)
                    return tenant.subdomain_prefix if tenant else None
                else:
                    return str(tenant_id).lower()

        return None

    def _get_tenant_context(
        self,
        tenant_slug: str,
        request: HttpRequest
    ) -> Optional[TenantContext]:
        """
        Get tenant context with caching and validation.

        Args:
            tenant_slug: Tenant slug to look up
            request: HTTP request (for cache key uniqueness)

        Returns:
            TenantContext if tenant found and active

        Raises:
            HttpResponseGone: If tenant exists but is inactive

        Security:
            - Checks tenant is_active flag
            - Caches lookups for performance
            - Logs deleted tenant access attempts
        """
        # Build cache key (include hostname for uniqueness)
        cache_key = f"{self.CACHE_PREFIX}:{request.get_host()}:{tenant_slug}"

        # Try cache first
        cached_context = tenant_cache.get(cache_key)
        if cached_context:
            logger.debug(f"Tenant context from cache: {tenant_slug}")
            return cached_context

        # Look up tenant in database
        if not django_apps.ready:
            return None

        tenant = get_tenant_by_slug(tenant_slug, include_inactive=False)

        if not tenant:
            # Tenant not found or inactive
            # Check if it exists but is inactive
            tenant_inactive = get_tenant_by_slug(tenant_slug, include_inactive=True)

            if tenant_inactive and not tenant_inactive.is_active:
                # Tenant exists but is suspended
                security_logger.error(
                    f"Access attempt to suspended tenant: {tenant_slug}",
                    extra={
                        'tenant_slug': tenant_slug,
                        'suspended_at': tenant_inactive.suspended_at,
                        'reason': tenant_inactive.suspension_reason,
                        'security_event': SECURITY_EVENT_DELETED_TENANT_ACCESS
                    }
                )
                raise HttpResponseGone(
                    f"Tenant '{tenant_inactive.tenantname}' is currently suspended. "
                    f"Please contact support."
                )

            # Tenant truly doesn't exist
            logger.warning(f"Tenant not found: {tenant_slug}")
            return None

        # Create context
        from apps.tenants.utils import slug_to_db_alias

        context = TenantContext(
            tenant_pk=tenant.pk,
            tenant_slug=tenant.subdomain_prefix,
            tenant_name=tenant.tenantname,
            db_alias=slug_to_db_alias(tenant.subdomain_prefix)
        )

        # Cache for future requests
        tenant_cache.set(cache_key, context, timeout=self.CACHE_TTL)

        return context
