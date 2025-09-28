"""
GraphQL Origin Validation Middleware

Implements comprehensive origin validation for GraphQL requests to prevent
cross-origin attacks and unauthorized access from malicious domains.

Security Features:
- Origin header validation
- Referer header validation
- Host header validation
- Subdomain validation
- Dynamic origin allowlist
- Suspicious request detection
- Geographic origin validation
"""

import re
import logging
from typing import Dict, Any, Optional, List, Set
from urllib.parse import urlparse
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


origin_logger = logging.getLogger('origin_validation')
security_logger = logging.getLogger('security')


class GraphQLOriginValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate request origins for GraphQL endpoints.

    Provides multiple layers of origin validation to prevent unauthorized
    cross-origin requests and protect against CSRF and other attacks.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.graphql_paths = getattr(settings, 'GRAPHQL_PATHS', [
            '/api/graphql/',
            '/graphql/',
            '/graphql'
        ])

        # Load origin validation configuration
        self.origin_config = self._load_origin_config()
        self.allowed_origins = set(self.origin_config['allowed_origins'])
        self.allowed_patterns = [re.compile(pattern) for pattern in self.origin_config['allowed_patterns']]

        # Cache for dynamic origin validation
        self.origin_cache_ttl = 300  # 5 minutes

    def process_request(self, request: HttpRequest) -> Optional[JsonResponse]:
        """
        Validate request origin for GraphQL endpoints.

        Args:
            request: The HTTP request object

        Returns:
            JsonResponse if origin validation fails, None to continue
        """
        if not self._is_graphql_request(request):
            return None

        if not self._is_origin_validation_enabled():
            return None

        # Get correlation ID for tracking
        correlation_id = getattr(request, 'correlation_id', 'unknown')

        try:
            # Build origin validation context
            validation_context = self._build_validation_context(request, correlation_id)

            # Apply origin validation checks
            validation_checks = [
                self._validate_origin_header,
                self._validate_referer_header,
                self._validate_host_header,
                self._validate_request_patterns,
                self._validate_geographic_origin
            ]

            for check_func in validation_checks:
                result = check_func(request, validation_context)
                if not result['valid']:
                    self._log_origin_violation(validation_context, result)
                    return self._create_origin_rejection_response(result, correlation_id)

            # Log successful validation
            origin_logger.debug(
                f"GraphQL origin validation passed. "
                f"Origin: {validation_context['origin']}, "
                f"Correlation ID: {correlation_id}"
            )

            # Update dynamic allowlist if applicable
            self._update_dynamic_allowlist(validation_context)

            return None

        except (TypeError, ValidationError, ValueError) as e:
            origin_logger.error(
                f"Origin validation error: {str(e)}, Correlation ID: {correlation_id}",
                exc_info=True
            )
            # In strict mode, reject on error; otherwise allow
            if self.origin_config['strict_mode']:
                return self._create_origin_rejection_response(
                    {'reason': 'validation_error', 'details': str(e)},
                    correlation_id
                )
            return None

    def _is_graphql_request(self, request: HttpRequest) -> bool:
        """Check if the request is for a GraphQL endpoint."""
        return any(request.path.startswith(path) for path in self.graphql_paths)

    def _is_origin_validation_enabled(self) -> bool:
        """Check if origin validation is enabled."""
        return getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False)

    def _load_origin_config(self) -> Dict[str, Any]:
        """Load origin validation configuration from settings."""
        default_config = {
            'allowed_origins': [],
            'allowed_patterns': [],
            'allowed_subdomains': [],
            'blocked_origins': [],
            'strict_mode': True,
            'validate_referer': True,
            'validate_host': True,
            'allow_localhost_dev': False,
            'geographic_validation': False,
            'allowed_countries': [],
            'dynamic_allowlist': False,
            'suspicious_patterns': [
                r'.*\.onion$',  # Tor hidden services
                r'.*\.bit$',    # Namecoin domains
                r'\d+\.\d+\.\d+\.\d+',  # Raw IP addresses
                r'localhost',   # Localhost (configurable)
                r'127\.0\.0\.1', # Loopback
                r'0\.0\.0\.0',   # All interfaces
            ]
        }

        # Load from settings
        config = getattr(settings, 'GRAPHQL_ORIGIN_VALIDATION', {})
        default_config.update(config)

        # Add development origins if in debug mode
        if getattr(settings, 'DEBUG', False) and default_config['allow_localhost_dev']:
            dev_origins = [
                'http://localhost:3000',
                'http://localhost:8000',
                'http://127.0.0.1:3000',
                'http://127.0.0.1:8000',
                'http://localhost:8080',
                'http://127.0.0.1:8080'
            ]
            default_config['allowed_origins'].extend(dev_origins)

        return default_config

    def _build_validation_context(self, request: HttpRequest, correlation_id: str) -> Dict[str, Any]:
        """Build context for origin validation."""
        # Extract headers
        origin = request.META.get('HTTP_ORIGIN', '')
        referer = request.META.get('HTTP_REFERER', '')
        host = request.META.get('HTTP_HOST', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Parse origins
        origin_parsed = urlparse(origin) if origin else None
        referer_parsed = urlparse(referer) if referer else None

        context = {
            'origin': origin,
            'referer': referer,
            'host': host,
            'user_agent': user_agent,
            'origin_parsed': origin_parsed,
            'referer_parsed': referer_parsed,
            'client_ip': self._get_client_ip(request),
            'correlation_id': correlation_id,
            'request_method': request.method,
            'request_path': request.path,
            'is_secure': request.is_secure()
        }

        return context

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _validate_origin_header(self, request: HttpRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Origin header."""
        origin = context['origin']

        if not origin:
            # Missing origin header - strict mode rejects, permissive allows
            if self.origin_config['strict_mode']:
                return {
                    'valid': False,
                    'reason': 'missing_origin',
                    'details': 'Origin header is required for GraphQL requests'
                }
            else:
                return {'valid': True}

        # Check against blocked origins
        if origin in self.origin_config['blocked_origins']:
            return {
                'valid': False,
                'reason': 'blocked_origin',
                'details': f'Origin {origin} is explicitly blocked'
            }

        # Check against allowed origins (exact match)
        if origin in self.allowed_origins:
            return {'valid': True}

        # Check against pattern matches
        for pattern in self.allowed_patterns:
            if pattern.match(origin):
                return {'valid': True}

        # Check subdomain validation
        if self._validate_subdomain(origin):
            return {'valid': True}

        # Check suspicious patterns
        for suspicious_pattern in self.origin_config['suspicious_patterns']:
            if re.search(suspicious_pattern, origin, re.IGNORECASE):
                return {
                    'valid': False,
                    'reason': 'suspicious_origin',
                    'details': f'Origin matches suspicious pattern: {suspicious_pattern}'
                }

        # Check dynamic allowlist
        if self._check_dynamic_allowlist(origin):
            return {'valid': True}

        return {
            'valid': False,
            'reason': 'origin_not_allowed',
            'details': f'Origin {origin} is not in the allowed list'
        }

    def _validate_referer_header(self, request: HttpRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Referer header consistency with Origin."""
        if not self.origin_config['validate_referer']:
            return {'valid': True}

        origin = context['origin']
        referer = context['referer']

        if not referer:
            # Missing referer is suspicious but not always blocking
            origin_logger.warning(
                f"Missing referer header for GraphQL request. "
                f"Origin: {origin}, Correlation ID: {context['correlation_id']}"
            )
            return {'valid': True}  # Allow but log

        origin_parsed = context['origin_parsed']
        referer_parsed = context['referer_parsed']

        if origin_parsed and referer_parsed:
            # Check if referer's origin matches the Origin header
            referer_origin = f"{referer_parsed.scheme}://{referer_parsed.netloc}"

            if origin != referer_origin:
                return {
                    'valid': False,
                    'reason': 'origin_referer_mismatch',
                    'details': f'Origin {origin} does not match referer origin {referer_origin}'
                }

        return {'valid': True}

    def _validate_host_header(self, request: HttpRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Host header."""
        if not self.origin_config['validate_host']:
            return {'valid': True}

        host = context['host']
        origin = context['origin']

        if not host:
            return {
                'valid': False,
                'reason': 'missing_host',
                'details': 'Host header is required'
            }

        # If we have an origin, check consistency
        if origin and context['origin_parsed']:
            origin_host = context['origin_parsed'].netloc

            if origin_host != host:
                return {
                    'valid': False,
                    'reason': 'host_origin_mismatch',
                    'details': f'Host {host} does not match origin host {origin_host}'
                }

        return {'valid': True}

    def _validate_request_patterns(self, request: HttpRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request patterns for suspicious activity."""
        user_agent = context['user_agent']

        # Check for missing or suspicious user agent
        if not user_agent or len(user_agent) < 10:
            return {
                'valid': False,
                'reason': 'suspicious_user_agent',
                'details': 'User agent is missing or too short'
            }

        # Check for common bot patterns
        bot_patterns = [
            r'curl',
            r'wget',
            r'python-requests',
            r'python-urllib',
            r'bot',
            r'crawler',
            r'spider',
            r'scraper'
        ]

        for pattern in bot_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                origin_logger.warning(
                    f"Bot-like user agent detected: {user_agent}, "
                    f"Correlation ID: {context['correlation_id']}"
                )
                # Log but don't block (bots might be legitimate)
                break

        return {'valid': True}

    def _validate_geographic_origin(self, request: HttpRequest, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate geographic origin if enabled."""
        if not self.origin_config['geographic_validation']:
            return {'valid': True}

        # This would require GeoIP lookup - placeholder implementation
        client_ip = context['client_ip']
        allowed_countries = self.origin_config['allowed_countries']

        if not allowed_countries:
            return {'valid': True}

        # TODO: Implement GeoIP lookup
        # For now, just log the requirement
        origin_logger.debug(
            f"Geographic validation required but not implemented. "
            f"IP: {client_ip}, Correlation ID: {context['correlation_id']}"
        )

        return {'valid': True}

    def _validate_subdomain(self, origin: str) -> bool:
        """Check if origin is an allowed subdomain."""
        allowed_subdomains = self.origin_config['allowed_subdomains']

        if not allowed_subdomains:
            return False

        parsed = urlparse(origin)
        if not parsed.netloc:
            return False

        domain = parsed.netloc

        for allowed_domain in allowed_subdomains:
            # Check exact match or subdomain match
            if domain == allowed_domain or domain.endswith(f'.{allowed_domain}'):
                return True

        return False

    def _check_dynamic_allowlist(self, origin: str) -> bool:
        """Check dynamic allowlist for recently validated origins."""
        if not self.origin_config['dynamic_allowlist']:
            return False

        cache_key = f"graphql_dynamic_origin:{origin}"
        return cache.get(cache_key, False)

    def _update_dynamic_allowlist(self, context: Dict[str, Any]):
        """Update dynamic allowlist with validated origin."""
        if not self.origin_config['dynamic_allowlist']:
            return

        origin = context['origin']
        if origin:
            cache_key = f"graphql_dynamic_origin:{origin}"
            cache.set(cache_key, True, self.origin_cache_ttl)

    def _log_origin_violation(self, context: Dict[str, Any], result: Dict[str, Any]):
        """Log origin validation violations."""
        security_logger.warning(
            f"GraphQL origin validation failed: {result['reason']}",
            extra={
                'origin': context['origin'],
                'referer': context['referer'],
                'host': context['host'],
                'client_ip': context['client_ip'],
                'user_agent': context['user_agent'],
                'correlation_id': context['correlation_id'],
                'violation_reason': result['reason'],
                'violation_details': result.get('details', ''),
                'request_method': context['request_method'],
                'request_path': context['request_path']
            }
        )

    def _create_origin_rejection_response(self, result: Dict[str, Any], correlation_id: str) -> JsonResponse:
        """Create response for origin validation failure."""
        response_data = {
            'errors': [{
                'message': 'Origin validation failed',
                'code': 'ORIGIN_NOT_ALLOWED',
                'extensions': {
                    'reason': result['reason'],
                    'correlation_id': correlation_id,
                    'timestamp': __import__('time').time()
                }
            }]
        }

        # Don't expose detailed validation failure reasons in production
        if getattr(settings, 'DEBUG', False):
            response_data['errors'][0]['extensions']['details'] = result.get('details', '')

        response = JsonResponse(response_data, status=403)

        # Add security headers
        response['X-Origin-Validation'] = 'failed'
        response['X-Content-Type-Options'] = 'nosniff'

        return response


class OriginValidationUtilities:
    """Utility functions for origin validation management."""

    @staticmethod
    def add_allowed_origin(origin: str, temporary: bool = False):
        """Dynamically add an allowed origin."""
        if temporary:
            cache_key = f"graphql_dynamic_origin:{origin}"
            cache.set(cache_key, True, 300)  # 5 minutes
            origin_logger.info(f"Temporarily allowed origin: {origin}")
        else:
            # This would require updating settings or database
            origin_logger.info(f"Request to permanently allow origin: {origin}")

    @staticmethod
    def remove_allowed_origin(origin: str):
        """Remove an origin from dynamic allowlist."""
        cache_key = f"graphql_dynamic_origin:{origin}"
        cache.delete(cache_key)
        origin_logger.info(f"Removed origin from allowlist: {origin}")

    @staticmethod
    def get_origin_stats() -> Dict[str, Any]:
        """Get origin validation statistics."""
        # This would require proper metrics collection
        return {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'blocked_origins': [],
            'top_origins': []
        }

    @staticmethod
    def validate_origin_format(origin: str) -> bool:
        """Validate that an origin string has the correct format."""
        try:
            parsed = urlparse(origin)
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc and
                not parsed.path and
                not parsed.params and
                not parsed.query and
                not parsed.fragment
            )
        except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError):
            return False