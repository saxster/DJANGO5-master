"""
Smart caching decorators with tenant awareness and intelligent invalidation
"""

import functools
import json
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.cache import never_cache
from datetime import date

from .utils import (
    get_tenant_cache_key,
    get_user_cache_key,
    cache_key_generator,
    CACHE_PATTERNS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


def smart_cache_view(
    timeout: Optional[int] = None,
    key_prefix: str = '',
    per_user: bool = False,
    per_tenant: bool = True,
    cache_anonymous: bool = True,
    vary_headers: Optional[List[str]] = None,
    invalidate_on: Optional[List[str]] = None
):
    """
    Advanced view caching decorator with intelligent key generation

    Args:
        timeout: Cache timeout in seconds (defaults based on key_prefix)
        key_prefix: Cache key prefix for categorization
        per_user: Create user-specific cache keys
        per_tenant: Create tenant-specific cache keys
        cache_anonymous: Whether to cache for anonymous users
        vary_headers: HTTP headers to vary cache on
        invalidate_on: Model names that should invalidate this cache

    Usage:
        @smart_cache_view(timeout=900, key_prefix='dashboard:metrics', per_user=True)
        def dashboard_view(request):
            return render(request, 'dashboard.html', context)
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Skip caching for authenticated users if cache_anonymous is False
            if not cache_anonymous and request.user.is_authenticated:
                logger.debug(f"Skipping cache for authenticated user: {request.user.id}")
                return view_func(request, *args, **kwargs)

            # Skip caching for POST, PUT, DELETE methods
            if request.method not in ('GET', 'HEAD'):
                logger.debug(f"Skipping cache for {request.method} request")
                return view_func(request, *args, **kwargs)

            # Generate cache key
            cache_key_parts = [key_prefix or view_func.__name__]

            # Add URL arguments to cache key
            if args:
                cache_key_parts.extend(str(arg) for arg in args)
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    cache_key_parts.append(f"{k}:{v}")

            # Add query parameters (excluding cache busters)
            query_params = dict(request.GET.items())
            cache_busters = ['_', 'nocache', 'timestamp']
            filtered_params = {k: v for k, v in query_params.items() if k not in cache_busters}

            if filtered_params:
                param_string = "&".join(f"{k}={v}" for k, v in sorted(filtered_params.items()))
                cache_key_parts.append(f"params:{param_string}")

            base_key = ":".join(cache_key_parts)

            # Apply user-specific caching if requested
            if per_user and request.user.is_authenticated:
                cache_key = get_user_cache_key(
                    base_key,
                    request.user.id,
                    request if per_tenant else None
                )
            elif per_tenant:
                cache_key = get_tenant_cache_key(base_key, request)
            else:
                cache_key = base_key

            # Try to get from cache
            try:
                cached_response = cache.get(cache_key)
                if cached_response is not None:
                    logger.debug(f"Cache HIT for key: {cache_key}")

                    # Restore HttpResponse if it was cached
                    if isinstance(cached_response, dict) and 'content' in cached_response:
                        response = HttpResponse(
                            cached_response['content'],
                            content_type=cached_response.get('content_type', 'text/html'),
                            status=cached_response.get('status', 200)
                        )
                        # Restore headers
                        for header, value in cached_response.get('headers', {}).items():
                            response[header] = value
                        response['X-Cache-Status'] = 'HIT'
                        return response
                    else:
                        # Direct return for simple cached data
                        if isinstance(cached_response, HttpResponse):
                            cached_response['X-Cache-Status'] = 'HIT'
                        return cached_response

            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Cache get error for key {cache_key}: {e}")

            # Cache miss - execute view
            logger.debug(f"Cache MISS for key: {cache_key}")
            response = view_func(request, *args, **kwargs)

            # Determine cache timeout
            cache_timeout = timeout
            if cache_timeout is None:
                # Use pattern-based timeout
                pattern_key = key_prefix.upper().replace(':', '_') if key_prefix else 'DEFAULT'
                cache_timeout = CACHE_TIMEOUTS.get(pattern_key, CACHE_TIMEOUTS['DEFAULT'])

            # Cache the response
            try:
                if isinstance(response, HttpResponse):
                    # Cache HttpResponse metadata
                    cached_data = {
                        'content': response.content.decode('utf-8') if response.content else '',
                        'content_type': response.get('Content-Type', 'text/html'),
                        'status': response.status_code,
                        'headers': dict(response.items())
                    }
                    cache.set(cache_key, cached_data, cache_timeout)
                else:
                    # Cache direct data (for JsonResponse, etc.)
                    cache.set(cache_key, response, cache_timeout)

                logger.debug(f"Cached response for key: {cache_key} (timeout: {cache_timeout}s)")

                # Add cache status header
                if hasattr(response, '__setitem__'):
                    response['X-Cache-Status'] = 'MISS'

            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Cache set error for key {cache_key}: {e}")

            return response

        # Store metadata for cache invalidation
        wrapper._cache_config = {
            'key_prefix': key_prefix,
            'per_user': per_user,
            'per_tenant': per_tenant,
            'invalidate_on': invalidate_on or []
        }

        # Apply vary headers if specified
        if vary_headers:
            wrapper = vary_on_headers(*vary_headers)(wrapper)

        return wrapper

    return decorator


def cache_dropdown_data(
    timeout: int = CACHE_TIMEOUTS['DROPDOWN_DATA'],
    model_name: Optional[str] = None
):
    """
    Specialized decorator for caching dropdown/select2 data

    Args:
        timeout: Cache timeout in seconds
        model_name: Model name for cache invalidation mapping

    Usage:
        @cache_dropdown_data(model_name='People')
        def get_people_dropdown(request):
            return JsonResponse({'results': people_data})
    """

    def decorator(view_func):
        @smart_cache_view(
            timeout=timeout,
            key_prefix=CACHE_PATTERNS['DROPDOWN_DATA'],
            per_tenant=True,
            invalidate_on=[model_name] if model_name else None
        )
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def cache_dashboard_metrics(
    timeout: int = CACHE_TIMEOUTS['DASHBOARD_METRICS'],
    per_user: bool = False
):
    """
    Specialized decorator for caching dashboard metrics

    Args:
        timeout: Cache timeout in seconds
        per_user: Whether to cache per user

    Usage:
        @cache_dashboard_metrics(per_user=True)
        def get_dashboard_data(request):
            return JsonResponse(dashboard_data)
    """

    def decorator(view_func):
        @smart_cache_view(
            timeout=timeout,
            key_prefix=CACHE_PATTERNS['DASHBOARD_METRICS'],
            per_user=per_user,
            per_tenant=True,
            invalidate_on=['People', 'Asset', 'PeopleEventlog']
        )
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def cache_with_invalidation(
    timeout: Optional[int] = None,
    cache_key: Optional[str] = None,
    invalidate_on: Optional[List[str]] = None,
    per_tenant: bool = True
):
    """
    Generic caching decorator with explicit invalidation mapping

    Args:
        timeout: Cache timeout in seconds
        cache_key: Explicit cache key (otherwise uses function name)
        invalidate_on: List of model names that should invalidate this cache
        per_tenant: Whether to use tenant-aware caching

    Usage:
        @cache_with_invalidation(
            cache_key='asset:status:summary',
            invalidate_on=['Asset'],
            timeout=300
        )
        def get_asset_status_summary(request):
            return asset_summary_data
    """

    def decorator(view_func):
        @smart_cache_view(
            timeout=timeout,
            key_prefix=cache_key or view_func.__name__,
            per_tenant=per_tenant,
            invalidate_on=invalidate_on
        )
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def method_cache(
    timeout: int = CACHE_TIMEOUTS['DEFAULT'],
    key_prefix: Optional[str] = None,
    per_instance: bool = True
):
    """
    Decorator for caching method results on model instances

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Cache key prefix
        per_instance: Include instance ID in cache key

    Usage:
        class MyModel(models.Model):
            @method_cache(timeout=3600, key_prefix='expensive_calculation')
            def expensive_calculation(self):
                return complex_calculation_result
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            key_parts = [
                key_prefix or f"{self.__class__.__name__}.{method.__name__}"
            ]

            if per_instance:
                key_parts.append(f"id:{self.pk}")

            if args:
                key_parts.extend(str(arg) for arg in args)

            if kwargs:
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}:{v}")

            cache_key = ":".join(key_parts)

            # Try cache first
            try:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Method cache HIT for {cache_key}")
                    return cached_result
            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Method cache get error for {cache_key}: {e}")

            # Cache miss - execute method
            logger.debug(f"Method cache MISS for {cache_key}")
            result = method(self, *args, **kwargs)

            # Cache the result
            try:
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cached method result for {cache_key}")
            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Method cache set error for {cache_key}: {e}")

            return result

        return wrapper

    return decorator


# Commonly used cache decorators with preset configurations
cache_short = functools.partial(smart_cache_view, timeout=5 * 60)  # 5 minutes
cache_medium = functools.partial(smart_cache_view, timeout=30 * 60)  # 30 minutes
cache_long = functools.partial(smart_cache_view, timeout=2 * 60 * 60)  # 2 hours

# Method decorators for class-based views
cache_view_short = method_decorator(cache_short)
cache_view_medium = method_decorator(cache_medium)
cache_view_long = method_decorator(cache_long)