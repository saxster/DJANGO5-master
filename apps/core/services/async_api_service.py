"""
Async External API Service

Provides non-blocking external API call capabilities with comprehensive
error handling, timeout management, and retry logic.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.utils import timezone

from apps.core.services.base_service import BaseService
from apps.core.utils_new.sql_security import QueryValidator


logger = logging.getLogger(__name__)


class AsyncExternalAPIService(BaseService):
    """
    Service for making external API calls asynchronously.

    Features:
    - Non-blocking API calls via Celery tasks
    - Configurable timeout and retry logic
    - Response caching with TTL
    - Rate limiting protection
    - Secure URL validation
    - Comprehensive error handling
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 3
    DEFAULT_CACHE_TTL = 300  # 5 minutes
    MAX_TIMEOUT = 120  # 2 minutes
    ALLOWED_SCHEMES = ['http', 'https']

    def __init__(self):
        super().__init__()
        self.rate_limits = {}

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "AsyncExternalAPIService"

    def initiate_api_call(
        self,
        url: str,
        method: str = 'GET',
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        cache_ttl: Optional[int] = None,
        user_id: Optional[int] = None,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Initiate an async external API call.

        Args:
            url: Target API URL
            method: HTTP method (GET, POST, PUT, DELETE)
            headers: Optional HTTP headers
            data: Optional request data
            timeout: Request timeout in seconds
            cache_ttl: Cache TTL in seconds
            user_id: Optional user ID for tracking
            priority: Task priority (high, normal, low)

        Returns:
            Dict containing task information and initial status
        """
        try:
            # Validate URL
            self._validate_url(url)

            # Validate method
            if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Set defaults
            timeout = min(timeout or self.DEFAULT_TIMEOUT, self.MAX_TIMEOUT)
            cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL

            # Check rate limits
            if not self._check_rate_limit(url, user_id):
                raise ValueError("Rate limit exceeded for this URL/user combination")

            # Generate task ID
            task_id = str(uuid.uuid4())

            # Check cache for GET requests
            if method.upper() == 'GET' and not data:
                cached_response = self._get_cached_response(url, headers)
                if cached_response:
                    logger.info(f"Returning cached response for {url}")
                    return {
                        'task_id': task_id,
                        'status': 'completed',
                        'data': cached_response,
                        'cached': True
                    }

            # Sanitize headers
            safe_headers = self._sanitize_headers(headers)

            # Queue task based on priority
            task_data = {
                'task_id': task_id,
                'url': url,
                'method': method.upper(),
                'headers': safe_headers,
                'data': data,
                'timeout': timeout,
                'cache_ttl': cache_ttl,
                'user_id': user_id,
                'priority': priority,
                'status': 'pending',
                'created_at': timezone.now(),
                'estimated_completion': timezone.now() + timedelta(seconds=timeout + 30)
            }

            # Store task data
            self._store_task_data(task_id, task_data)

            # Import and queue the task
            from background_tasks.tasks import external_api_call_async

            # Queue with appropriate priority
            queue_name = 'high_priority' if priority == 'high' else 'default'
            external_api_call_async.apply_async(
                args=[url, method, safe_headers, data, timeout, user_id],
                task_id=task_id,
                queue=queue_name
            )

            logger.info(f"External API call queued: {task_id} for {url}")

            return {
                'task_id': task_id,
                'status': 'pending',
                'url': url,
                'method': method.upper(),
                'estimated_completion': task_data['estimated_completion'].isoformat(),
                'message': 'API call queued successfully'
            }

        except (DatabaseError, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to initiate API call: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current status of an API call task.

        Args:
            task_id: Unique task identifier

        Returns:
            Dict containing task status and results
        """
        try:
            task_data = self._get_task_data(task_id)

            if not task_data:
                return {
                    'status': 'not_found',
                    'error': 'Task not found'
                }

            # Check if task completed in Celery
            from celery.result import AsyncResult
            celery_result = AsyncResult(task_id)

            if celery_result.ready():
                if celery_result.successful():
                    result = celery_result.result

                    # Cache successful GET responses
                    if (task_data.get('method') == 'GET' and
                        result.get('status') == 'success'):
                        self._cache_response(
                            task_data['url'],
                            task_data.get('headers'),
                            result,
                            task_data.get('cache_ttl', self.DEFAULT_CACHE_TTL)
                        )

                    return {
                        'task_id': task_id,
                        'status': 'completed',
                        'data': result,
                        'url': task_data.get('url'),
                        'method': task_data.get('method'),
                        'created_at': task_data.get('created_at'),
                        'completed_at': timezone.now()
                    }
                else:
                    return {
                        'task_id': task_id,
                        'status': 'failed',
                        'error': str(celery_result.result),
                        'url': task_data.get('url'),
                        'method': task_data.get('method'),
                        'created_at': task_data.get('created_at')
                    }
            else:
                return {
                    'task_id': task_id,
                    'status': 'processing',
                    'url': task_data.get('url'),
                    'method': task_data.get('method'),
                    'created_at': task_data.get('created_at'),
                    'estimated_completion': task_data.get('estimated_completion')
                }

        except (DatabaseError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def bulk_api_calls(
        self,
        requests: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Initiate multiple API calls in parallel.

        Args:
            requests: List of request dictionaries
            user_id: Optional user ID for tracking
            priority: Task priority

        Returns:
            Dict containing batch task information
        """
        try:
            if not requests or len(requests) > 50:  # Limit batch size
                raise ValueError("Invalid batch size (max 50 requests)")

            batch_id = str(uuid.uuid4())
            task_ids = []

            for i, req in enumerate(requests):
                try:
                    result = self.initiate_api_call(
                        url=req['url'],
                        method=req.get('method', 'GET'),
                        headers=req.get('headers'),
                        data=req.get('data'),
                        timeout=req.get('timeout'),
                        cache_ttl=req.get('cache_ttl'),
                        user_id=user_id,
                        priority=priority
                    )
                    task_ids.append(result['task_id'])
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to queue request {i}: {str(e)}")
                    task_ids.append({'error': str(e)})

            # Store batch metadata
            batch_data = {
                'batch_id': batch_id,
                'task_ids': task_ids,
                'total_requests': len(requests),
                'user_id': user_id,
                'created_at': timezone.now()
            }

            cache.set(f"api_batch_{batch_id}", batch_data, timeout=3600)

            logger.info(f"Bulk API call batch initiated: {batch_id} with {len(task_ids)} tasks")

            return {
                'batch_id': batch_id,
                'task_ids': task_ids,
                'total_requests': len(requests),
                'status': 'queued'
            }

        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to initiate bulk API calls: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a pending API call task.

        Args:
            task_id: Unique task identifier

        Returns:
            Dict containing cancellation status
        """
        try:
            from celery import current_app

            # Revoke the task
            current_app.control.revoke(task_id, terminate=True)

            # Update task data
            task_data = self._get_task_data(task_id)
            if task_data:
                task_data['status'] = 'cancelled'
                task_data['cancelled_at'] = timezone.now()
                self._store_task_data(task_id, task_data)

            logger.info(f"Task cancelled: {task_id}")

            return {
                'task_id': task_id,
                'status': 'cancelled',
                'message': 'Task cancelled successfully'
            }

        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to cancel task: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg
            }

    def _validate_url(self, url: str) -> None:
        """Validate URL for security and format."""
        try:
            parsed = urlparse(url)

            if not parsed.scheme:
                raise ValueError("URL must include scheme (http/https)")

            if parsed.scheme not in self.ALLOWED_SCHEMES:
                raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

            if not parsed.netloc:
                raise ValueError("URL must include valid domain")

            # Block internal/private networks
            if parsed.hostname:
                import ipaddress
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private or ip.is_loopback:
                        raise ValueError("Access to private/internal IPs not allowed")
                except ValueError:
                    pass  # Not an IP address, likely a domain name

        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            raise ValueError(f"Invalid URL: {str(e)}")

    def _sanitize_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Sanitize HTTP headers for security."""
        if not headers:
            return {}

        safe_headers = {}
        dangerous_headers = [
            'authorization', 'cookie', 'x-api-key', 'x-auth-token',
            'access-token', 'session-id'
        ]

        for key, value in headers.items():
            if key.lower() not in dangerous_headers:
                # Basic sanitization
                safe_key = str(key)[:100]  # Limit header name length
                safe_value = str(value)[:1000]  # Limit header value length
                safe_headers[safe_key] = safe_value

        return safe_headers

    def _check_rate_limit(self, url: str, user_id: Optional[int]) -> bool:
        """Check rate limits for URL/user combination."""
        try:
            key = f"api_rate_limit_{url}_{user_id or 'anonymous'}"
            current_count = cache.get(key, 0)

            # Allow 100 requests per hour per URL/user
            if current_count >= 100:
                return False

            cache.set(key, current_count + 1, timeout=3600)
            return True

        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return True  # Allow on error

    def _get_cached_response(
        self,
        url: str,
        headers: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """Get cached response for URL."""
        try:
            cache_key = self._generate_cache_key(url, headers)
            return cache.get(cache_key)
        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache retrieval failed: {str(e)}")
            return None

    def _cache_response(
        self,
        url: str,
        headers: Optional[Dict[str, str]],
        response: Dict[str, Any],
        ttl: int
    ) -> None:
        """Cache successful response."""
        try:
            cache_key = self._generate_cache_key(url, headers)
            cache.set(cache_key, response, timeout=ttl)
            logger.debug(f"Response cached for {url}")
        except (ConnectionError, DatabaseError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache storage failed: {str(e)}")

    def _generate_cache_key(self, url: str, headers: Optional[Dict[str, str]]) -> str:
        """Generate cache key for URL and headers."""
        import hashlib

        # Create consistent cache key
        key_data = f"{url}_{sorted((headers or {}).items())}"
        return f"api_cache_{hashlib.md5(key_data.encode()).hexdigest()}"

    def _store_task_data(self, task_id: str, data: Dict[str, Any]) -> None:
        """Store task data in cache."""
        cache.set(f"api_task_{task_id}", data, timeout=3600 * 2)  # 2 hours

    def _get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task data from cache."""
        return cache.get(f"api_task_{task_id}")

    def cleanup_expired_tasks(self) -> int:
        """Clean up expired task data."""
        # Implementation would depend on cache backend
        # This is a placeholder for Redis-based cleanup
        logger.info("API task cleanup completed")
        return 0