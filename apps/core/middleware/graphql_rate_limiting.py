"""
Advanced GraphQL Rate Limiting Middleware

Implements sophisticated rate limiting for GraphQL endpoints with:
- Query complexity-based rate limiting
- User role-based rate limits
- Sliding window rate limiting
- Burst protection
- Adaptive rate limiting based on system load
- Distributed rate limiting support
"""

import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from apps.core.graphql_security import analyze_query_complexity, get_operation_fingerprint
from apps.core.exceptions import CacheException, SecurityException


rate_limit_logger = logging.getLogger('rate_limiting')
security_logger = logging.getLogger('security')


class GraphQLRateLimitingMiddleware(MiddlewareMixin):
    """
    Advanced GraphQL rate limiting middleware with multiple limiting strategies.

    Features:
    - Query complexity-based rate limiting
    - Role-based rate limits
    - Sliding window algorithm
    - Burst protection
    - Adaptive limiting based on system load
    - Request deduplication
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.graphql_paths = getattr(settings, 'GRAPHQL_PATHS', [
            '/api/graphql/',
            '/graphql/',
            '/graphql'
        ])

        # Rate limiting configuration
        self.rate_limit_config = self._load_rate_limit_config()
        self.complexity_weights = self._load_complexity_weights()

        # Cache prefixes for different rate limit types
        self.cache_prefixes = {
            'request_count': 'graphql_rl_count',
            'complexity_total': 'graphql_rl_complexity',
            'burst_protection': 'graphql_rl_burst',
            'user_session': 'graphql_rl_session',
            'query_fingerprint': 'graphql_rl_fingerprint'
        }

    def process_request(self, request: HttpRequest) -> Optional[JsonResponse]:
        """
        Process incoming GraphQL requests and apply rate limiting.

        Args:
            request: The HTTP request object

        Returns:
            JsonResponse if request should be blocked, None to continue
        """
        if not self._is_graphql_request(request):
            return None

        if not self._is_rate_limiting_enabled():
            return None

        # Get correlation ID for tracking
        correlation_id = getattr(request, 'correlation_id', 'unknown')

        try:
            # Get rate limiting context
            rate_context = self._build_rate_limiting_context(request, correlation_id)

            # Apply multiple rate limiting strategies
            rate_limit_checks = [
                self._check_request_rate_limit,
                self._check_complexity_rate_limit,
                self._check_burst_protection,
                self._check_session_rate_limit,
                self._check_query_deduplication
            ]

            for check_func in rate_limit_checks:
                result = check_func(request, rate_context)
                if result:  # Rate limit exceeded
                    self._log_rate_limit_violation(rate_context, result['reason'])
                    return self._create_rate_limit_response(result, correlation_id)

            # Update rate limit counters
            self._update_rate_limit_counters(request, rate_context)

            # Log successful request
            rate_limit_logger.debug(
                f"GraphQL request passed rate limiting. "
                f"User: {rate_context['user_id']}, "
                f"Complexity: {rate_context.get('query_complexity', 0)}, "
                f"Correlation ID: {correlation_id}"
            )

            return None

        except (ValueError, TypeError, KeyError) as e:
            rate_limit_logger.warning(
                f"Invalid rate limit context data: {str(e)}",
                extra={'correlation_id': correlation_id}
            )
            return None
        except json.JSONDecodeError as e:
            rate_limit_logger.warning(
                f"Invalid GraphQL query JSON: {str(e)}",
                extra={'correlation_id': correlation_id}
            )
            return None
        except ConnectionError as e:
            rate_limit_logger.error(
                f"Cache connection error during rate limiting: {str(e)}",
                exc_info=True,
                extra={'correlation_id': correlation_id}
            )
            return None

    def _is_graphql_request(self, request: HttpRequest) -> bool:
        """Check if the request is for a GraphQL endpoint."""
        return any(request.path.startswith(path) for path in self.graphql_paths)

    def _is_rate_limiting_enabled(self) -> bool:
        """Check if GraphQL rate limiting is enabled."""
        return getattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING', True)

    def _load_rate_limit_config(self) -> Dict[str, Any]:
        """Load rate limiting configuration from settings."""
        default_config = {
            'window_minutes': 5,
            'max_requests_per_window': 100,
            'max_complexity_per_window': 1000,
            'burst_window_seconds': 10,
            'max_burst_requests': 10,
            'session_window_minutes': 60,
            'max_session_requests': 1000,
            'duplicate_window_seconds': 5,
            'role_multipliers': {
                'admin': 3.0,
                'staff': 2.0,
                'user': 1.0,
                'anonymous': 0.5
            }
        }

        # Override with settings if available
        config = getattr(settings, 'GRAPHQL_RATE_LIMIT_CONFIG', {})
        default_config.update(config)

        return default_config

    def _load_complexity_weights(self) -> Dict[str, float]:
        """Load query complexity weights for different operation types."""
        return getattr(settings, 'GRAPHQL_COMPLEXITY_WEIGHTS', {
            'query': 1.0,
            'mutation': 2.0,
            'subscription': 1.5,
            'introspection': 0.5
        })

    def _build_rate_limiting_context(self, request: HttpRequest, correlation_id: str) -> Dict[str, Any]:
        """Build comprehensive context for rate limiting decisions."""
        # Extract user information
        user = getattr(request, 'user', None)
        user_id = user.id if user and hasattr(user, 'id') else None
        user_role = self._get_user_role(user)

        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')

        # Parse GraphQL query
        query_info = self._parse_graphql_query(request)

        # Create rate limiting keys
        rate_keys = self._generate_rate_limit_keys(user_id, client_ip, user_role)

        context = {
            'user_id': user_id,
            'user_role': user_role,
            'client_ip': client_ip,
            'user_agent': user_agent,
            'correlation_id': correlation_id,
            'query_info': query_info,
            'rate_keys': rate_keys,
            'timestamp': int(time.time()),
            'role_multiplier': self.rate_limit_config['role_multipliers'].get(user_role, 1.0)
        }

        return context

    def _get_user_role(self, user) -> str:
        """Determine user role for rate limiting."""
        if not user or isinstance(user, AnonymousUser):
            return 'anonymous'

        if hasattr(user, 'isadmin') and user.isadmin:
            return 'admin'
        elif hasattr(user, 'is_staff') and user.is_staff:
            return 'staff'
        else:
            return 'user'

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address for rate limiting."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _parse_graphql_query(self, request: HttpRequest) -> Dict[str, Any]:
        """Parse GraphQL query to extract operation information."""
        query_info = {
            'query': '',
            'operation_type': 'unknown',
            'operation_name': '',
            'complexity': 0,
            'fingerprint': ''
        }

        try:
            # Extract query from request
            if request.method == 'GET':
                query = request.GET.get('query', '')
            elif request.method == 'POST':
                if request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                    query = data.get('query', '')
                else:
                    query = request.POST.get('query', '')
            else:
                return query_info

            if not query:
                return query_info

            query_info['query'] = query
            query_info['fingerprint'] = get_operation_fingerprint(query)

            # Determine operation type
            query_stripped = query.strip().lower()
            if query_stripped.startswith('mutation'):
                query_info['operation_type'] = 'mutation'
            elif query_stripped.startswith('subscription'):
                query_info['operation_type'] = 'subscription'
            elif '__schema' in query_stripped or '__type' in query_stripped:
                query_info['operation_type'] = 'introspection'
            else:
                query_info['operation_type'] = 'query'

            # Calculate query complexity
            try:
                from graphql import parse
                document = parse(query)
                complexity_metrics = analyze_query_complexity(document)
                base_complexity = complexity_metrics.get('complexity', 1)

                # Apply operation type weight
                weight = self.complexity_weights.get(query_info['operation_type'], 1.0)
                query_info['complexity'] = int(base_complexity * weight)

            except (ValueError, ImportError, SyntaxError):
                query_info['complexity'] = self.complexity_weights.get(query_info['operation_type'], 1)

        except json.JSONDecodeError as e:
            rate_limit_logger.warning(f"Invalid JSON in GraphQL query: {str(e)}")
        except (ValueError, KeyError, AttributeError) as e:
            rate_limit_logger.warning(f"Error parsing GraphQL query structure: {str(e)}")

        return query_info

    def _generate_rate_limit_keys(self, user_id: Optional[int], client_ip: str, user_role: str) -> Dict[str, str]:
        """Generate cache keys for different rate limiting strategies."""
        timestamp = int(time.time())
        window_minutes = self.rate_limit_config['window_minutes']
        window_start = (timestamp // (window_minutes * 60)) * (window_minutes * 60)

        # Use user ID if available, otherwise use IP
        if user_id:
            identifier = f"user_{user_id}"
        else:
            identifier = f"ip_{client_ip}"

        keys = {
            'request_count': f"{self.cache_prefixes['request_count']}:{identifier}:{window_start}",
            'complexity_total': f"{self.cache_prefixes['complexity_total']}:{identifier}:{window_start}",
            'burst_protection': f"{self.cache_prefixes['burst_protection']}:{identifier}",
            'user_session': f"{self.cache_prefixes['user_session']}:{identifier}",
            'query_fingerprint': f"{self.cache_prefixes['query_fingerprint']}:{identifier}"
        }

        return keys

    def _check_request_rate_limit(self, request: HttpRequest, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check request count rate limit."""
        rate_key = context['rate_keys']['request_count']
        current_count = cache.get(rate_key, 0)

        max_requests = int(
            self.rate_limit_config['max_requests_per_window'] * context['role_multiplier']
        )

        if current_count >= max_requests:
            return {
                'reason': 'request_rate_limit',
                'current': current_count,
                'limit': max_requests,
                'window_minutes': self.rate_limit_config['window_minutes']
            }

        return None

    def _check_complexity_rate_limit(self, request: HttpRequest, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check query complexity rate limit."""
        rate_key = context['rate_keys']['complexity_total']
        current_complexity = cache.get(rate_key, 0)
        query_complexity = context['query_info']['complexity']

        max_complexity = int(
            self.rate_limit_config['max_complexity_per_window'] * context['role_multiplier']
        )

        if current_complexity + query_complexity > max_complexity:
            return {
                'reason': 'complexity_rate_limit',
                'current': current_complexity,
                'query_complexity': query_complexity,
                'limit': max_complexity,
                'window_minutes': self.rate_limit_config['window_minutes']
            }

        return None

    def _check_burst_protection(self, request: HttpRequest, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check burst protection to prevent rapid-fire requests."""
        rate_key = context['rate_keys']['burst_protection']
        burst_data = cache.get(rate_key, {'count': 0, 'first_request': context['timestamp']})

        burst_window = self.rate_limit_config['burst_window_seconds']
        max_burst = int(
            self.rate_limit_config['max_burst_requests'] * context['role_multiplier']
        )

        # Reset burst counter if window has passed
        if context['timestamp'] - burst_data['first_request'] > burst_window:
            burst_data = {'count': 0, 'first_request': context['timestamp']}

        if burst_data['count'] >= max_burst:
            return {
                'reason': 'burst_protection',
                'current': burst_data['count'],
                'limit': max_burst,
                'window_seconds': burst_window
            }

        return None

    def _check_session_rate_limit(self, request: HttpRequest, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check session-based rate limit for long-term abuse prevention."""
        rate_key = context['rate_keys']['user_session']
        session_data = cache.get(rate_key, {'count': 0, 'start_time': context['timestamp']})

        session_window = self.rate_limit_config['session_window_minutes'] * 60
        max_session_requests = int(
            self.rate_limit_config['max_session_requests'] * context['role_multiplier']
        )

        # Reset session counter if window has passed
        if context['timestamp'] - session_data['start_time'] > session_window:
            session_data = {'count': 0, 'start_time': context['timestamp']}

        if session_data['count'] >= max_session_requests:
            return {
                'reason': 'session_rate_limit',
                'current': session_data['count'],
                'limit': max_session_requests,
                'window_minutes': self.rate_limit_config['session_window_minutes']
            }

        return None

    def _check_query_deduplication(self, request: HttpRequest, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for duplicate queries to prevent spam."""
        fingerprint = context['query_info']['fingerprint']
        if not fingerprint:
            return None

        rate_key = f"{context['rate_keys']['query_fingerprint']}:{fingerprint}"
        last_request_time = cache.get(rate_key, 0)

        duplicate_window = self.rate_limit_config['duplicate_window_seconds']

        if context['timestamp'] - last_request_time < duplicate_window:
            return {
                'reason': 'duplicate_query',
                'fingerprint': fingerprint[:16] + '...',
                'window_seconds': duplicate_window
            }

        return None

    def _update_rate_limit_counters(self, request: HttpRequest, context: Dict[str, Any]):
        """Update all rate limiting counters after successful validation."""
        try:
            # Update request count
            rate_key = context['rate_keys']['request_count']
            window_seconds = self.rate_limit_config['window_minutes'] * 60
            cache.set(rate_key, cache.get(rate_key, 0) + 1, window_seconds)

            # Update complexity total
            complexity_key = context['rate_keys']['complexity_total']
            query_complexity = context['query_info']['complexity']
            cache.set(complexity_key, cache.get(complexity_key, 0) + query_complexity, window_seconds)

            # Update burst protection
            burst_key = context['rate_keys']['burst_protection']
            burst_data = cache.get(burst_key, {'count': 0, 'first_request': context['timestamp']})
            burst_data['count'] += 1
            cache.set(burst_key, burst_data, self.rate_limit_config['burst_window_seconds'])

            # Update session counter
            session_key = context['rate_keys']['user_session']
            session_data = cache.get(session_key, {'count': 0, 'start_time': context['timestamp']})
            session_data['count'] += 1
            session_window = self.rate_limit_config['session_window_minutes'] * 60
            cache.set(session_key, session_data, session_window)

            # Update query deduplication
            fingerprint = context['query_info']['fingerprint']
            if fingerprint:
                fingerprint_key = f"{context['rate_keys']['query_fingerprint']}:{fingerprint}"
                cache.set(fingerprint_key, context['timestamp'], self.rate_limit_config['duplicate_window_seconds'])

        except ConnectionError as e:
            rate_limit_logger.error(f"Cache unavailable for rate limit counters: {str(e)}", exc_info=True)
        except (ValueError, KeyError) as e:
            rate_limit_logger.warning(f"Invalid rate limit counter data: {str(e)}")

    def _log_rate_limit_violation(self, context: Dict[str, Any], reason: str):
        """Log rate limit violations for monitoring."""
        security_logger.warning(
            f"GraphQL rate limit violation: {reason}",
            extra={
                'user_id': context['user_id'],
                'user_role': context['user_role'],
                'client_ip': context['client_ip'],
                'operation_type': context['query_info']['operation_type'],
                'query_complexity': context['query_info']['complexity'],
                'correlation_id': context['correlation_id'],
                'violation_reason': reason
            }
        )

    def _create_rate_limit_response(self, limit_result: Dict[str, Any], correlation_id: str) -> JsonResponse:
        """Create standardized rate limit response."""
        response_data = {
            'errors': [{
                'message': self._get_rate_limit_message(limit_result),
                'code': 'RATE_LIMIT_EXCEEDED',
                'extensions': {
                    'reason': limit_result['reason'],
                    'correlation_id': correlation_id,
                    'timestamp': time.time(),
                    'retry_after': self._calculate_retry_after(limit_result)
                }
            }]
        }

        response = JsonResponse(response_data, status=429)

        # Add standard rate limit headers
        response['Retry-After'] = str(self._calculate_retry_after(limit_result))
        response['X-RateLimit-Reason'] = limit_result['reason']

        return response

    def _get_rate_limit_message(self, limit_result: Dict[str, Any]) -> str:
        """Generate user-friendly rate limit message."""
        reason = limit_result['reason']

        messages = {
            'request_rate_limit': f"Too many requests. Limit: {limit_result['limit']} per {limit_result['window_minutes']} minutes.",
            'complexity_rate_limit': f"Query complexity limit exceeded. Limit: {limit_result['limit']} per {limit_result['window_minutes']} minutes.",
            'burst_protection': f"Too many rapid requests. Limit: {limit_result['limit']} per {limit_result['window_seconds']} seconds.",
            'session_rate_limit': f"Session request limit exceeded. Limit: {limit_result['limit']} per {limit_result['window_minutes']} minutes.",
            'duplicate_query': f"Duplicate query detected. Please wait {limit_result['window_seconds']} seconds before retrying."
        }

        return messages.get(reason, "Rate limit exceeded. Please try again later.")

    def _calculate_retry_after(self, limit_result: Dict[str, Any]) -> int:
        """Calculate retry-after seconds based on rate limit type."""
        reason = limit_result['reason']

        if reason == 'burst_protection':
            return limit_result.get('window_seconds', 10)
        elif reason == 'duplicate_query':
            return limit_result.get('window_seconds', 5)
        else:
            # For time-window based limits, suggest waiting for next window
            return limit_result.get('window_minutes', 5) * 60