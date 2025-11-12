"""
Multi-Tenant URL Middleware

Provides tenant awareness in URLs for proper isolation and deep linking.

Supports three tenant identification strategies:
1. URL path: /t/{tenant_slug}/operations/tasks/
2. Subdomain: tenant1.example.com
3. Header/JWT: X-Tenant-ID or JWT claim

Usage:
    Add to MIDDLEWARE in settings.py:
    'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware'

Configuration:
    # settings.py
    MULTI_TENANT_ENABLED = True
    MULTI_TENANT_MODE = 'path'  # or 'subdomain' or 'header'
    MULTI_TENANT_DOMAIN = 'example.com'  # For subdomain mode

Features:
    - Automatic tenant extraction from URLs
    - Tenant context in request object
    - Tenant-aware URL generation
    - Deep linking support with tenant context
    - Fallback strategies
"""

import logging
import re
from typing import Optional
from django.conf import settings
from django.http import HttpRequest, Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from apps.core.cache.tenant_aware import tenant_cache as cache
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.tenants.utils import get_tenant_by_slug as resolve_tenant_by_slug, get_tenant_by_pk

logger = logging.getLogger(__name__)


class TenantContext:
    """
    Stores tenant information for the current request.
    """
    def __init__(self, tenant_id: str, tenant_slug: str, tenant_name: str = None):
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.tenant_name = tenant_name or tenant_slug

    def __str__(self):
        return f"Tenant({self.tenant_slug})"

    def __repr__(self):
        return f"TenantContext(id={self.tenant_id}, slug={self.tenant_slug})"


class MultiTenantURLMiddleware:
    """
    Middleware to handle multi-tenant URL routing and context.

    Extracts tenant information from:
    - URL path: /t/{tenant_slug}/...
    - Subdomain: {tenant}.example.com
    - Header: X-Tenant-ID
    - JWT claim: tenant_id

    Sets request.tenant for use throughout the application.
    """

    # URL path pattern for tenant extraction: /t/{tenant_slug}/
    TENANT_PATH_PATTERN = re.compile(r'^/t/(?P<tenant_slug>[\w-]+)/')

    # Cache key prefix for tenant lookups
    # NOTE: Uses tenant-aware cache to prevent cross-tenant collisions
    CACHE_PREFIX = 'tenant_lookup'
    CACHE_TTL = 3600  # 1 hour

    # URLs to exclude from tenant extraction
    EXCLUDE_PATHS = {
        '/static/',
        '/media/',
        '/admin/django/',  # Django admin uses superuser, not tenant
        '/api/health/',
        '/health/',
        '/ready/',
        '/alive/',
        '/__debug__/',
        '/favicon.ico',
    }

    def __init__(self, get_response):
        self.get_response = get_response

        # Load configuration
        self.enabled = getattr(settings, 'MULTI_TENANT_ENABLED', True)
        self.mode = getattr(settings, 'MULTI_TENANT_MODE', 'path')  # path|subdomain|header
        self.domain = getattr(settings, 'MULTI_TENANT_DOMAIN', 'example.com')
        self.require_tenant = getattr(settings, 'MULTI_TENANT_REQUIRE', False)
        self.default_tenant = getattr(settings, 'MULTI_TENANT_DEFAULT', None)

        logger.info(
            f"MultiTenantURLMiddleware initialized: "
            f"mode={self.mode}, enabled={self.enabled}, require={self.require_tenant}"
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and extract tenant information.
        """
        if not self.enabled:
            return self.get_response(request)

        # Skip tenant extraction for excluded paths
        if self._should_skip(request.path):
            return self.get_response(request)

        # Extract tenant using configured strategy
        tenant = self._extract_tenant(request)

        if tenant:
            # Set tenant context on request
            request.tenant = tenant

            # If using path mode, strip tenant prefix from path for URL resolution
            if self.mode == 'path' and self.TENANT_PATH_PATTERN.match(request.path):
                # Remove /t/{tenant_slug}/ prefix
                original_path = request.path
                request.path_info = self.TENANT_PATH_PATTERN.sub('/', request.path)
                request.path = request.path_info

                logger.debug(f"Tenant path transformed: {original_path} → {request.path}")

        elif self.require_tenant and not self._is_anonymous_allowed(request.path):
            # Tenant required but not found
            logger.warning(f"Tenant required but not found for path: {request.path}")
            return self._handle_missing_tenant(request)

        elif self.default_tenant:
            # Use default tenant as fallback
            request.tenant = self._get_default_tenant()

        else:
            # No tenant context (acceptable for some views)
            request.tenant = None

        # Process request
        try:
            response = self.get_response(request)

            # Add tenant info to response headers (for debugging)
            if hasattr(request, 'tenant') and request.tenant:
                response['X-Tenant-ID'] = request.tenant.tenant_id
                response['X-Tenant-Slug'] = request.tenant.tenant_slug

            return response
        finally:
            # CRITICAL: Cleanup thread-local context
            from apps.tenants.utils import cleanup_tenant_context
            cleanup_tenant_context()

    def _should_skip(self, path: str) -> bool:
        """
        Check if path should be excluded from tenant extraction.
        """
        return any(path.startswith(excluded) for excluded in self.EXCLUDE_PATHS)

    def _extract_tenant(self, request: HttpRequest) -> Optional[TenantContext]:
        """
        Extract tenant using configured strategy.
        """
        if self.mode == 'path':
            return self._extract_from_path(request)
        elif self.mode == 'subdomain':
            return self._extract_from_subdomain(request)
        elif self.mode == 'header':
            return self._extract_from_header(request)
        else:
            logger.error(f"Invalid MULTI_TENANT_MODE: {self.mode}")
            return None

    def _extract_from_path(self, request: HttpRequest) -> Optional[TenantContext]:
        """
        Extract tenant from URL path: /t/{tenant_slug}/
        """
        match = self.TENANT_PATH_PATTERN.match(request.path)
        if match:
            tenant_slug = match.group('tenant_slug')
            return self._get_tenant_by_slug(tenant_slug)
        return None

    def _extract_from_subdomain(self, request: HttpRequest) -> Optional[TenantContext]:
        """
        Extract tenant from subdomain: {tenant}.example.com
        """
        from django.core.exceptions import DisallowedHost

        try:
            host = request.get_host().split(':')[0]  # Remove port
        except DisallowedHost:
            # Cannot extract tenant from subdomain if host validation fails
            return None

        # Check if subdomain present
        if host.endswith(f".{self.domain}"):
            tenant_slug = host.replace(f".{self.domain}", '')
            return self._get_tenant_by_slug(tenant_slug)

        return None

    def _extract_from_header(self, request: HttpRequest) -> Optional[TenantContext]:
        """
        Extract tenant from HTTP header or JWT.
        """
        # Try X-Tenant-ID header
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            return self._get_tenant_by_id(tenant_id)

        # Try X-Tenant-Slug header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if tenant_slug:
            return self._get_tenant_by_slug(tenant_slug)

        # Try JWT claim (if user authenticated with JWT)
        if hasattr(request, 'user') and hasattr(request.user, 'jwt_payload'):
            tenant_id = request.user.jwt_payload.get('tenant_id')
            if tenant_id:
                return self._get_tenant_by_id(tenant_id)

        return None

    def _get_tenant_by_slug(self, slug: str) -> Optional[TenantContext]:
        """
        Get tenant information by slug with caching.
        """
        # Check cache first
        cache_key = f"{self.CACHE_PREFIX}:slug:{slug}"
        cached = cache.get(cache_key)
        if cached:
            return TenantContext(**cached)

        # Query database via centralized utilities
        try:
            tenant = resolve_tenant_by_slug(slug.lower(), include_inactive=False)
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error fetching tenant by slug '{slug}': {e}",
                exc_info=True,
                extra={'slug': slug, 'cache_key': cache_key}
            )
            return None

        if not tenant:
            return None

        context_data = {
            'tenant_id': str(tenant.pk),
            'tenant_slug': tenant.subdomain_prefix,
            'tenant_name': tenant.tenantname
        }

        cache.set(cache_key, context_data, self.CACHE_TTL)

        return TenantContext(**context_data)

    def _get_tenant_by_id(self, tenant_id: str) -> Optional[TenantContext]:
        """
        Get tenant information by ID with caching.
        """
        # Check cache first
        cache_key = f"{self.CACHE_PREFIX}:id:{tenant_id}"
        cached = cache.get(cache_key)
        if cached:
            return TenantContext(**cached)

        try:
            numeric_id = int(tenant_id)
        except (TypeError, ValueError):
            numeric_id = None

        tenant = None
        if numeric_id is not None:
            try:
                tenant = get_tenant_by_pk(numeric_id, include_inactive=False)
            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    f"Database error fetching tenant by ID '{tenant_id}': {e}",
                    exc_info=True,
                    extra={'tenant_id': tenant_id, 'cache_key': cache_key}
                )
                return None

        if not tenant and isinstance(tenant_id, str):
            tenant = resolve_tenant_by_slug(tenant_id.lower(), include_inactive=False)

        if not tenant:
            return None

        context_data = {
            'tenant_id': str(tenant.pk),
            'tenant_slug': tenant.subdomain_prefix,
            'tenant_name': tenant.tenantname
        }

        cache.set(cache_key, context_data, self.CACHE_TTL)

        return TenantContext(**context_data)

    def _get_default_tenant(self) -> Optional[TenantContext]:
        """
        Get default tenant as fallback.
        """
        if not self.default_tenant:
            return None

        return self._get_tenant_by_slug(self.default_tenant)

    def _is_anonymous_allowed(self, path: str) -> bool:
        """
        Check if path allows anonymous access (no tenant required).
        """
        anonymous_paths = {
            '/auth/login/',
            '/auth/logout/',
            '/api/v1/public/',
            '/api/health/',
        }
        return any(path.startswith(anon) for anon in anonymous_paths)

    def _handle_missing_tenant(self, request: HttpRequest) -> HttpResponse:
        """
        Handle requests that require tenant but don't have one.
        """
        # If user is authenticated, redirect to tenant selection
        if request.user.is_authenticated:
            return redirect('tenant_selection')

        # Otherwise, redirect to login
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")


def get_tenant_url(view_name: str, tenant: TenantContext, **kwargs) -> str:
    """
    Generate tenant-aware URL.

    Usage:
        url = get_tenant_url('operations:task-list', request.tenant)
        # Returns: /t/acme-corp/operations/tasks/

    Args:
        view_name: Django URL name (namespace:name)
        tenant: TenantContext object
        **kwargs: URL parameters

    Returns:
        Complete URL with tenant prefix
    """
    mode = getattr(settings, 'MULTI_TENANT_MODE', 'path')

    if mode == 'path':
        # Generate standard URL then prepend tenant path
        base_url = reverse(view_name, kwargs=kwargs)
        return f"/t/{tenant.tenant_slug}{base_url}"

    elif mode == 'subdomain':
        # Generate standard URL (tenant is in subdomain)
        return reverse(view_name, kwargs=kwargs)

    elif mode == 'header':
        # Generate standard URL (tenant is in header)
        return reverse(view_name, kwargs=kwargs)

    else:
        # Fallback to standard URL
        return reverse(view_name, kwargs=kwargs)


def get_current_tenant(request: HttpRequest) -> Optional[TenantContext]:
    """
    Get tenant context from current request.

    Usage:
        tenant = get_current_tenant(request)
        if tenant:
            logger.debug(f"Current tenant: {tenant.tenant_name}")

    Args:
        request: HttpRequest object

    Returns:
        TenantContext if available, None otherwise
    """
    return getattr(request, 'tenant', None)


# Template context processor
def tenant_context_processor(request):
    """
    Add tenant context to all templates.

    Add to TEMPLATES['OPTIONS']['context_processors']:
        'apps.core.middleware.multi_tenant_url.tenant_context_processor'

    Usage in templates:
        {% if tenant %}
            <p>Current tenant: {{ tenant.tenant_name }}</p>
            <a href="{% tenant_url 'operations:task-list' %}">Tasks</a>
        {% endif %}
    """
    return {
        'tenant': get_current_tenant(request),
        'tenant_url': lambda view_name, **kwargs: get_tenant_url(
            view_name,
            get_current_tenant(request),
            **kwargs
        ) if get_current_tenant(request) else reverse(view_name, kwargs=kwargs)
    }


# Template tag for tenant-aware URLs
"""
Add to your template tags (apps/core/templatetags/tenant_tags.py):

from django import template
from apps.core.middleware.multi_tenant_url import get_tenant_url, get_current_tenant

register = template.Library()

@register.simple_tag(takes_context=True)
def tenant_url(context, view_name, *args, **kwargs):
    '''
    Generate tenant-aware URL in templates.

    Usage:
        {% load tenant_tags %}
        <a href="{% tenant_url 'operations:task-list' %}">Tasks</a>
    '''
    request = context['request']
    tenant = get_current_tenant(request)
    if tenant:
        return get_tenant_url(view_name, tenant, **kwargs)
    return reverse(view_name, kwargs=kwargs)
"""
