"""
Database transaction decorators and security decorators for background tasks and views.

This module provides decorators for:
1. Ensuring consistent transaction handling across the application
2. CSRF protection for AJAX, HTMX, and standard form submissions
3. Rate limiting for abuse prevention
4. Staff access control

CRITICAL SECURITY NOTE:
The CSRF protection decorators implement Rule #3 from .claude/rules.md - Mandatory CSRF Protection.
ALL mutation endpoints MUST use csrf_protect_ajax or csrf_protect_htmx instead of @csrf_exempt.

Compliance: CVSS 8.1 vulnerability remediation
Rule Reference: .claude/rules.md - Rule #3 (Mandatory CSRF Protection)
"""

import functools
import logging
import json
from typing import Callable, Any
from django.db import transaction, DatabaseError, OperationalError
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.core.cache import cache
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import SecurityException
import uuid
import time

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


def atomic_task(using_db=None):
    """
    Decorator for background tasks to ensure atomic database operations.

    Args:
        using_db: Database alias to use. If None, uses get_current_db_name()

    Usage:
        @atomic_task()
        @shared_task
        def my_task():
            # All database operations will be wrapped in atomic transaction
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            db_name = using_db or get_current_db_name()
            correlation_id = str(uuid.uuid4())

            try:
                with transaction.atomic(using=db_name):
                    logger.info(
                        f"Starting atomic task: {func.__name__}",
                        extra={
                            "correlation_id": correlation_id,
                            "database": db_name,
                            "task_name": func.__name__
                        }
                    )

                    result = func(*args, **kwargs)

                    # Add database info to task result if it's a dict
                    if isinstance(result, dict):
                        result.setdefault("story", "")
                        result["story"] = f"using database: {db_name}\n" + result["story"]

                    logger.info(
                        f"Completed atomic task: {func.__name__}",
                        extra={
                            "correlation_id": correlation_id,
                            "database": db_name,
                            "task_name": func.__name__
                        }
                    )

                    return result

            except (DatabaseError, OperationalError) as e:
                logger.error(
                    f"Database error in atomic task: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "database": db_name,
                        "task_name": func.__name__,
                        "error_type": "database"
                    },
                    exc_info=True
                )
                error_response = ErrorHandler.handle_task_exception(
                    e,
                    task_name=func.__name__,
                    task_params={"error_type": "database"},
                    correlation_id=correlation_id
                )
                return error_response
            except (ValidationError, ValueError, TypeError) as e:
                logger.warning(
                    f"Validation error in atomic task: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "task_name": func.__name__,
                        "error_type": "validation"
                    }
                )
                error_response = ErrorHandler.handle_task_exception(
                    e,
                    task_name=func.__name__,
                    task_params={"error_type": "validation"},
                    correlation_id=correlation_id
                )
                return error_response
            except (PermissionDenied, SecurityException) as e:
                logger.error(
                    f"Security error in atomic task: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "task_name": func.__name__,
                        "error_type": "security"
                    },
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def atomic_view(using_db=None):
    """
    Decorator for views to ensure atomic database operations.

    Args:
        using_db: Database alias to use. If None, uses get_current_db_name()

    Usage:
        @atomic_view()
        def my_view(request):
            # All database operations will be wrapped in atomic transaction
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            db_name = using_db or get_current_db_name()
            correlation_id = str(uuid.uuid4())

            try:
                with transaction.atomic(using=db_name):
                    logger.debug(
                        f"Starting atomic view: {func.__name__}",
                        extra={
                            "correlation_id": correlation_id,
                            "database": db_name,
                            "view_name": func.__name__,
                            "user": getattr(request.user, 'id', None)
                        }
                    )

                    result = func(request, *args, **kwargs)

                    logger.debug(
                        f"Completed atomic view: {func.__name__}",
                        extra={
                            "correlation_id": correlation_id,
                            "database": db_name,
                            "view_name": func.__name__,
                            "user": getattr(request.user, 'id', None)
                        }
                    )

                    return result

            except (DatabaseError, OperationalError) as e:
                logger.error(
                    f"Database error in atomic view: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "database": db_name,
                        "view_name": func.__name__,
                        "user": getattr(request.user, 'id', None),
                        "error_type": "database"
                    },
                    exc_info=True
                )
                raise
            except (ValidationError, PermissionDenied) as e:
                logger.warning(
                    f"Validation/permission error in atomic view: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "view_name": func.__name__,
                        "user": getattr(request.user, 'id', None),
                        "error_type": "validation"
                    }
                )
                raise
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(
                    f"Data error in atomic view: {func.__name__}",
                    extra={
                        "correlation_id": correlation_id,
                        "view_name": func.__name__,
                        "error_type": "data_error"
                    },
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def retry_on_db_error(max_retries=3, delay=None):
    """
    Retry decorator for database errors in Celery tasks.

    ENHANCED: Now uses exponential backoff with jitter instead of fixed delay.
    The 'delay' parameter is deprecated - timing controlled by RetryPolicy.DATABASE_OPERATION.

    Automatically retries tasks that fail due to database integrity or
    operational errors (e.g., deadlocks, connection issues).

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        delay: DEPRECATED - ignored, uses exponential backoff instead

    Usage:
        @retry_on_db_error(max_retries=3)
        @atomic_task()
        @shared_task
        def my_task():
            # Task will be retried up to 3 times with exponential backoff
            pass

    Benefits over old implementation:
        - Exponential backoff (0.2s, 0.4s, 0.8s...) instead of fixed delay
        - Jitter to prevent thundering herd
        - Better transient error detection
        - Delegates to apps.core.utils_new.retry_mechanism
    """
    from django.db import IntegrityError, OperationalError
    from apps.core.utils_new.retry_mechanism import with_retry

    if delay is not None:
        logger.warning(
            "retry_on_db_error 'delay' parameter is deprecated. "
            "Using exponential backoff from RetryPolicy.DATABASE_OPERATION instead."
        )

    # Delegate to the enhanced retry mechanism with DATABASE_OPERATION policy
    return with_retry(
        exceptions=(IntegrityError, OperationalError),
        max_retries=max_retries,
        retry_policy='DATABASE_OPERATION',
        raise_on_exhausted=True
    )


# ============================================================================
# CSRF PROTECTION DECORATORS
# ============================================================================


def csrf_protect_ajax(view_func: Callable) -> Callable:
    """
    CSRF protection decorator that works with AJAX/JSON requests.

    This decorator validates CSRF tokens from:
    - X-CSRFToken header (standard AJAX)
    - X-CSRF-Token header (alternative)
    - csrfmiddlewaretoken in JSON body
    - csrfmiddlewaretoken in form data

    Usage:
        @csrf_protect_ajax
        def my_api_view(request):
            data = json.loads(request.body)
            return JsonResponse({'success': True})

    Security Features:
    - Validates CSRF tokens for all POST/PUT/PATCH/DELETE requests
    - Logs all CSRF validation failures
    - Supports both header and body token submission
    - Compatible with Django's standard CSRF middleware

    Args:
        view_func: The view function to protect

    Returns:
        Wrapped view function with CSRF protection
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        # Safe methods don't need CSRF protection
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return view_func(request, *args, **kwargs)

        # Extract CSRF token from request
        csrf_token = _get_csrf_token_from_request(request)

        if not csrf_token:
            security_logger.error(
                f"CSRF token missing for AJAX request to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous',
                    'ip': _get_client_ip(request),
                    'method': request.method,
                    'path': request.path
                }
            )
            return JsonResponse({
                'error': 'CSRF token missing',
                'code': 'CSRF_TOKEN_REQUIRED',
                'help': 'Include CSRF token in X-CSRFToken header or request body'
            }, status=403)

        # Validate CSRF token using Django's middleware
        csrf_middleware = CsrfViewMiddleware(lambda r: None)

        # Temporarily set the CSRF token in request.META for validation
        request.META['HTTP_X_CSRFTOKEN'] = csrf_token

        # Validate the token
        reason = csrf_middleware.process_view(request, view_func, args, kwargs)

        if reason:
            security_logger.error(
                f"CSRF token validation failed for AJAX request to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous',
                    'ip': _get_client_ip(request),
                    'method': request.method,
                    'path': request.path,
                    'reason': str(reason)
                }
            )
            return JsonResponse({
                'error': 'CSRF token validation failed',
                'code': 'CSRF_TOKEN_INVALID',
                'help': 'Refresh the page and try again'
            }, status=403)

        # CSRF validation passed
        return view_func(request, *args, **kwargs)

    return wrapper


def csrf_protect_htmx(view_func: Callable) -> Callable:
    """
    CSRF protection decorator optimized for HTMX requests.

    This decorator provides CSRF protection while being fully compatible with HTMX's
    request patterns, including:
    - hx-get, hx-post, hx-put, hx-delete, hx-patch
    - HTMX-specific headers (HX-Request, HX-Target, HX-Trigger)
    - CSRF tokens in headers or form data

    Usage:
        @csrf_protect_htmx
        @require_http_methods(["POST"])
        def htmx_action(request):
            return HttpResponse('<div>Updated content</div>')

    Security Features:
    - Validates CSRF tokens for all HTMX mutations
    - Detects HTMX requests via HX-Request header
    - Logs security events with correlation IDs
    - Returns HTMX-compatible error responses

    Args:
        view_func: The view function to protect

    Returns:
        Wrapped view function with HTMX-aware CSRF protection
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        # Safe methods don't need CSRF protection
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return view_func(request, *args, **kwargs)

        # Check if this is an HTMX request
        is_htmx = request.META.get('HTTP_HX_REQUEST') == 'true'

        # Extract CSRF token
        csrf_token = _get_csrf_token_from_request(request)

        if not csrf_token:
            security_logger.error(
                f"CSRF token missing for {'HTMX' if is_htmx else 'standard'} request to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous',
                    'ip': _get_client_ip(request),
                    'method': request.method,
                    'path': request.path,
                    'is_htmx': is_htmx,
                    'hx_target': request.META.get('HTTP_HX_TARGET'),
                    'hx_trigger': request.META.get('HTTP_HX_TRIGGER')
                }
            )

            if is_htmx:
                # Return HTMX-compatible error response
                return HttpResponse(
                    '<div class="alert alert-danger">CSRF token missing. Please refresh the page.</div>',
                    status=403
                )
            else:
                return JsonResponse({
                    'error': 'CSRF token missing',
                    'code': 'CSRF_TOKEN_REQUIRED'
                }, status=403)

        # Validate CSRF token using Django's middleware
        csrf_middleware = CsrfViewMiddleware(lambda r: None)
        request.META['HTTP_X_CSRFTOKEN'] = csrf_token

        reason = csrf_middleware.process_view(request, view_func, args, kwargs)

        if reason:
            security_logger.error(
                f"CSRF token validation failed for {'HTMX' if is_htmx else 'standard'} request",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous',
                    'ip': _get_client_ip(request),
                    'path': request.path,
                    'reason': str(reason)
                }
            )

            if is_htmx:
                return HttpResponse(
                    '<div class="alert alert-danger">CSRF validation failed. Please refresh the page.</div>',
                    status=403
                )
            else:
                return JsonResponse({
                    'error': 'CSRF token validation failed',
                    'code': 'CSRF_TOKEN_INVALID'
                }, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper


def rate_limit(max_requests: int = 50, window_seconds: int = 300):
    """
    Rate limiting decorator for view functions.

    This decorator implements per-user and per-IP rate limiting to prevent abuse
    and brute-force attacks.

    Usage:
        @rate_limit(max_requests=50, window_seconds=300)  # 50 requests per 5 minutes
        def expensive_operation(request):
            return JsonResponse({'result': 'success'})

    Args:
        max_requests: Maximum number of requests allowed in the time window
        window_seconds: Time window in seconds

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Create rate limit key
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
            client_ip = _get_client_ip(request)

            if user_id:
                rate_limit_key = f"rate_limit:user:{user_id}:{request.path}"
            else:
                rate_limit_key = f"rate_limit:ip:{client_ip}:{request.path}"

            # Check current request count
            current_requests = cache.get(rate_limit_key, 0)

            if current_requests >= max_requests:
                security_logger.warning(
                    f"Rate limit exceeded for {request.path}",
                    extra={
                        'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                        'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
                        'ip': client_ip,
                        'path': request.path,
                        'current_requests': current_requests,
                        'max_requests': max_requests
                    }
                )

                # Check if HTMX request
                is_htmx = request.META.get('HTTP_HX_REQUEST') == 'true'

                if is_htmx:
                    return HttpResponse(
                        '<div class="alert alert-warning">Too many requests. Please wait a moment and try again.</div>',
                        status=429
                    )
                else:
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'retry_after': window_seconds
                    }, status=429)

            # Increment request count
            cache.set(rate_limit_key, current_requests + 1, window_seconds)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_staff(view_func: Callable) -> Callable:
    """
    Decorator to require staff status for view access.

    Usage:
        @require_staff
        def admin_function(request):
            return JsonResponse({'admin': 'data'})

    Args:
        view_func: The view function to protect

    Returns:
        Wrapped view function with staff check
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            security_logger.warning(
                f"Unauthenticated access attempt to staff-only endpoint {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'ip': _get_client_ip(request),
                    'path': request.path
                }
            )
            raise PermissionDenied("Authentication required")

        if not request.user.is_staff:
            security_logger.warning(
                f"Non-staff access attempt to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'unknown'),
                    'ip': _get_client_ip(request),
                    'path': request.path
                }
            )
            raise PermissionDenied("Staff access required")

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _get_csrf_token_from_request(request: HttpRequest) -> str:
    """
    Extract CSRF token from various request sources.

    Checks in order:
    1. X-CSRFToken header (AJAX standard)
    2. X-CSRF-Token header (alternative)
    3. csrfmiddlewaretoken in POST data
    4. csrfmiddlewaretoken in JSON body

    Args:
        request: Django HttpRequest object

    Returns:
        CSRF token string or None if not found
    """
    # Check headers first (most common for AJAX/HTMX)
    csrf_token = request.META.get('HTTP_X_CSRFTOKEN')
    if csrf_token:
        return csrf_token

    csrf_token = request.META.get('HTTP_X_CSRF_TOKEN')
    if csrf_token:
        return csrf_token

    # Check POST data
    if hasattr(request, 'POST'):
        csrf_token = request.POST.get('csrfmiddlewaretoken')
        if csrf_token:
            return csrf_token

    # Check JSON body
    if request.content_type == 'application/json':
        try:
            if hasattr(request, 'body') and request.body:
                body_data = json.loads(request.body.decode('utf-8'))
                csrf_token = body_data.get('csrfmiddlewaretoken')
                if csrf_token:
                    return csrf_token
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            pass

    return None


def _get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address from request, handling proxies correctly.

    Args:
        request: Django HttpRequest object

    Returns:
        Client IP address as string
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


def require_monitoring_api_key(view_func: Callable) -> Callable:
    """
    Decorator to require valid monitoring API key for access.

    This decorator is specifically designed for monitoring endpoints that need
    to be accessed by external monitoring systems (Prometheus, Grafana, Datadog, etc.)
    without CSRF tokens.

    Security Features:
    - Validates API key from headers or query params
    - Rate limiting per API key (1000 requests/hour default)
    - IP whitelisting support (optional)
    - Audit logging for all accesses
    - Supports both APIKey model and dedicated MonitoringAPIKey

    Usage:
        @require_monitoring_api_key
        def monitoring_endpoint(request):
            return JsonResponse({'status': 'healthy'})

    API Key Formats:
    - Header: Authorization: Bearer <api_key>
    - Header: X-Monitoring-API-Key: <api_key>
    - Query: ?api_key=<api_key> (discouraged, logs warning)

    Args:
        view_func: The view function to protect

    Returns:
        Wrapped view function with API key authentication

    Rule Compliance:
    - Rule #3 Alternative Protection: API key authentication instead of CSRF
    - Used for read-only monitoring endpoints accessed by external systems
    - CSRF not applicable as endpoints are stateless and read-only
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        api_key = _extract_monitoring_api_key(request)

        if not api_key:
            security_logger.error(
                f"Monitoring API key missing for request to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'ip': _get_client_ip(request),
                    'path': request.path
                }
            )
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'API_KEY_REQUIRED',
                'help': 'Include monitoring API key in Authorization header or X-Monitoring-API-Key header'
            }, status=401)

        api_key_obj = _validate_monitoring_api_key(api_key, request)

        if not api_key_obj:
            security_logger.error(
                f"Invalid monitoring API key for request to {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'ip': _get_client_ip(request),
                    'path': request.path
                }
            )
            return JsonResponse({
                'error': 'Invalid API key',
                'code': 'API_KEY_INVALID'
            }, status=401)

        if not _check_monitoring_rate_limit(api_key_obj):
            security_logger.warning(
                f"Monitoring API rate limit exceeded for {request.path}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'api_key_name': api_key_obj.get('name', 'unknown'),
                    'ip': _get_client_ip(request),
                    'path': request.path
                }
            )
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'code': 'RATE_LIMIT_EXCEEDED',
                'retry_after': 3600
            }, status=429)

        request.monitoring_api_key = api_key_obj
        request.monitoring_authenticated = True

        return view_func(request, *args, **kwargs)

    return wrapper


def _extract_monitoring_api_key(request: HttpRequest) -> str:
    """
    Extract monitoring API key from request headers or query params.

    Checks in order:
    1. Authorization: Bearer <key>
    2. X-Monitoring-API-Key: <key>
    3. X-API-Key: <key>
    4. Query param: api_key (discouraged)

    Args:
        request: Django HttpRequest object

    Returns:
        API key string or None
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]

    api_key = request.META.get('HTTP_X_MONITORING_API_KEY')
    if api_key:
        return api_key

    api_key = request.META.get('HTTP_X_API_KEY')
    if api_key:
        return api_key

    api_key = request.GET.get('api_key')
    if api_key:
        logger.warning(
            f"Monitoring API key passed in query string from {_get_client_ip(request)} - "
            "This is insecure and should be avoided. Use headers instead."
        )
        return api_key

    return None


def _validate_monitoring_api_key(api_key: str, request: HttpRequest) -> dict:
    """
    Validate monitoring API key against database.

    Supports both general APIKey model and dedicated MonitoringAPIKey model.

    Args:
        api_key: API key string
        request: Django HttpRequest object (for IP validation)

    Returns:
        API key object dict or None if invalid
    """
    cache_key = f"monitoring_api_key:{api_key}"
    cached_key = cache.get(cache_key)

    if cached_key is not None:
        if not cached_key:
            return None
        if _validate_ip_whitelist(cached_key, request):
            return cached_key
        return None

    try:
        from apps.core.models import APIKey
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_obj = APIKey.objects.filter(
            key_hash=key_hash,
            is_active=True
        ).first()

        if api_key_obj:
            if api_key_obj.expires_at and timezone.now() > api_key_obj.expires_at:
                cache.set(cache_key, False, 300)
                return None

            result = {
                'id': api_key_obj.id,
                'name': api_key_obj.name,
                'user_id': api_key_obj.user_id if api_key_obj.user else None,
                'is_active': api_key_obj.is_active,
                'allowed_ips': api_key_obj.allowed_ips or [],
                'permissions': api_key_obj.permissions or {},
                'rate_limit': '1000/h',
            }

            if _validate_ip_whitelist(result, request):
                cache.set(cache_key, result, 300)
                return result

        cache.set(cache_key, False, 60)
        return None

    except (DatabaseError, ConnectionError) as e:
        logger.error(f"Database error validating monitoring API key: {e}", exc_info=True)
        return None
    except (ValueError, KeyError, AttributeError) as e:
        logger.warning(f"Invalid monitoring API key data: {e}")
        return None


def _validate_ip_whitelist(api_key_obj: dict, request: HttpRequest) -> bool:
    """
    Validate request IP against API key's IP whitelist.

    Args:
        api_key_obj: API key object dict
        request: Django HttpRequest object

    Returns:
        True if IP is allowed or no whitelist configured
    """
    allowed_ips = api_key_obj.get('allowed_ips', [])
    if not allowed_ips:
        return True

    client_ip = _get_client_ip(request)
    is_allowed = client_ip in allowed_ips

    if not is_allowed:
        security_logger.warning(
            f"IP {client_ip} not in whitelist for API key {api_key_obj.get('name', 'unknown')}",
            extra={
                'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                'api_key_name': api_key_obj.get('name', 'unknown'),
                'ip': client_ip,
                'allowed_ips': allowed_ips
            }
        )

    return is_allowed


def _check_monitoring_rate_limit(api_key_obj: dict) -> bool:
    """
    Check rate limit for monitoring API key.

    Default: 1000 requests per hour per API key

    Args:
        api_key_obj: API key object dict

    Returns:
        True if within rate limit
    """
    rate_limit = api_key_obj.get('rate_limit', '1000/h')

    try:
        limit, period = rate_limit.split('/')
        limit = int(limit)

        period_seconds = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
        }.get(period, 3600)

    except (ValueError, KeyError):
        limit = 1000
        period_seconds = 3600

    cache_key = f"monitoring_rate:{api_key_obj['id']}"
    current_count = cache.get(cache_key, 0)

    if current_count >= limit:
        logger.warning(
            f"Monitoring API rate limit exceeded for key {api_key_obj.get('name', 'unknown')} "
            f"({current_count}/{limit})"
        )
        return False

    cache.set(cache_key, current_count + 1, period_seconds)
    return True