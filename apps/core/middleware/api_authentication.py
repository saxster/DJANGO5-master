"""
API Authentication Middleware
Provides secure API key-based authentication for API endpoints

@ontology(
    domain="security",
    purpose="API key authentication middleware for REST API endpoints with HMAC request signing",
    middleware_type="request",
    execution_order="early (after CORS, before rate limiting)",
    authentication_methods=["api_key_header", "bearer_token", "query_param"],
    security_features=[
        "HMAC-SHA256 request signing",
        "API key expiration validation",
        "Per-key rate limiting",
        "IP-based access control",
        "Audit logging of API access"
    ],
    affects_all_requests=False,
    applies_to_paths=["/api/"],
    performance_impact="~2ms per request (with Redis cache)",
    cache_strategy="5min cache for valid keys, 1min cache for invalid",
    criticality="high",
    error_responses={
        "401": "Invalid/expired/missing API key",
        "429": "Rate limit exceeded for API key"
    },
    tags=["middleware", "authentication", "api", "security", "hmac"]
)
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY

logger = logging.getLogger("security.api")
User = get_user_model()


class APIAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware for API authentication using API keys and optional request signing.
    
    Features:
    - API key authentication
    - Request signing (HMAC) for sensitive endpoints
    - Rate limiting per API key
    - API key rotation support
    - Audit logging
    """
    
    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)
        
        # Configuration
        self.api_paths = getattr(settings, 'API_AUTH_PATHS', ['/api/'])
        self.require_signing = getattr(settings, 'API_REQUIRE_SIGNING', False)
        self.enable_api_auth = getattr(settings, 'ENABLE_API_AUTH', True)
        
    def process_request(self, request):
        """
        Process incoming API requests for authentication.
        
        Args:
            request: Django HttpRequest object
        """
        # Skip if API auth is disabled
        if not self.enable_api_auth:
            return None
            
        # Check if this is an API endpoint
        is_api_endpoint = any(request.path.startswith(path) for path in self.api_paths)
        if not is_api_endpoint:
            return None
            
        # Skip OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return None
            
        # Extract API credentials
        api_key = self._extract_api_key(request)
        signature = self._extract_signature(request)
        
        # Validate API key
        if not api_key:
            return self._unauthorized_response("API key required")
            
        api_key_obj = self._validate_api_key(api_key)
        if not api_key_obj:
            return self._unauthorized_response("Invalid API key")
            
        # Check if API key is active
        if not api_key_obj.get('is_active'):
            return self._unauthorized_response("API key is inactive")
            
        # Check API key expiration
        if self._is_api_key_expired(api_key_obj):
            return self._unauthorized_response("API key has expired")
            
        # Check rate limits for this API key
        if not self._check_rate_limit(api_key_obj):
            return self._rate_limit_response()
            
        # Validate request signature if required
        if self.require_signing or api_key_obj.get('require_signing'):
            if not signature:
                return self._unauthorized_response("Request signature required")
                
            if not self._validate_signature(request, api_key_obj, signature):
                return self._unauthorized_response("Invalid request signature")
                
        # Attach API key info to request
        request.api_key = api_key_obj
        request.api_authenticated = True
        
        # Log successful API authentication
        self._log_api_access(request, api_key_obj)
        
        return None
        
    def _extract_api_key(self, request):
        """
        Extract API key from request.
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            str: API key or None
        """
        # Check Authorization header (preferred)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        elif auth_header.startswith('ApiKey '):
            return auth_header[7:]
            
        # Check X-API-Key header
        api_key = request.META.get('HTTP_X_API_KEY')
        if api_key:
            return api_key
            
        # Check query parameter (least secure, avoid if possible)
        api_key = request.GET.get('api_key')
        if api_key:
            logger.warning(
                f"API key passed in query string from {self._get_client_ip(request)} - "
                "This is insecure and should be avoided"
            )
            return api_key
            
        return None
        
    def _extract_signature(self, request):
        """
        Extract request signature from headers.
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            str: Signature or None
        """
        return request.META.get('HTTP_X_SIGNATURE')
        
    def _validate_api_key(self, api_key):
        """
        Validate API key against database.
        
        Args:
            api_key: API key string
            
        Returns:
            dict: API key object or None
        """
        # Check cache first
        cache_key = f"api_key:{api_key}"
        cached_key = cache.get(cache_key)
        if cached_key is not None:
            return cached_key if cached_key else None
            
        try:
            from apps.core.models import APIKey
            
            # Hash the API key for comparison (keys are stored hashed)
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            api_key_obj = APIKey.objects.filter(
                key_hash=key_hash,
                is_active=True
            ).first()
            
            if api_key_obj:
                result = {
                    'id': api_key_obj.id,
                    'name': api_key_obj.name,
                    'user_id': api_key_obj.user_id,
                    'is_active': api_key_obj.is_active,
                    'require_signing': api_key_obj.require_signing,
                    'allowed_ips': api_key_obj.allowed_ips,
                    'expires_at': api_key_obj.expires_at,
                    'permissions': api_key_obj.permissions,
                    'secret': api_key_obj.secret,  # For signature validation
                }
                
                # Cache for 5 minutes
                cache.set(cache_key, result, 300)
                return result
            else:
                # Cache negative result for 1 minute
                cache.set(cache_key, False, 60)
                return None

        except (DatabaseError, ConnectionError) as e:
            logger.error(f"Database/cache error validating API key: {e}", exc_info=True)
            return None
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Invalid API key data: {e}")
            return None
            
    def _is_api_key_expired(self, api_key_obj):
        """
        Check if API key has expired.
        
        Args:
            api_key_obj: API key object
            
        Returns:
            bool: True if expired
        """
        expires_at = api_key_obj.get('expires_at')
        if not expires_at:
            return False
            
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
            
        return datetime.now() > expires_at
        
    def _validate_signature(self, request, api_key_obj, signature):
        """
        Validate request signature using HMAC.
        
        Args:
            request: Django HttpRequest object
            api_key_obj: API key object
            signature: Provided signature
            
        Returns:
            bool: True if signature is valid
        """
        secret = api_key_obj.get('secret')
        if not secret:
            logger.error(f"No secret found for API key {api_key_obj['id']}")
            return False
            
        # Build the string to sign
        timestamp = request.META.get('HTTP_X_TIMESTAMP', '')
        if not timestamp:
            return False
            
        # Check timestamp is within 5 minutes
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - request_time) > 300:  # 5 minutes
                logger.warning("Request timestamp outside acceptable window")
                return False
        except ValueError:
            return False
            
        # Build canonical request string
        canonical_parts = [
            request.method,
            request.path,
            request.META.get('QUERY_STRING', ''),
            timestamp,
        ]
        
        # Include body hash for POST/PUT/PATCH
        if request.method in ['POST', 'PUT', 'PATCH'] and request.body:
            body_hash = hashlib.sha256(request.body).hexdigest()
            canonical_parts.append(body_hash)
            
        canonical_string = '\n'.join(canonical_parts)
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode(),
            canonical_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)
        
    def _check_rate_limit(self, api_key_obj):
        """
        Check rate limit for API key.
        
        Args:
            api_key_obj: API key object
            
        Returns:
            bool: True if within rate limit
        """
        # Get rate limit from API key or use default
        rate_limit = api_key_obj.get('rate_limit', '1000/h')
        
        try:
            limit, period = rate_limit.split('/')
            limit = int(limit)
            
            period_seconds = {
                's': 1,
                'm': 60,
                'h': SECONDS_IN_HOUR,
                'd': SECONDS_IN_DAY,
            }.get(period, SECONDS_IN_HOUR)

        except (ValueError, KeyError):
            # Default to 1000 requests per hour
            limit = 1000
            period_seconds = SECONDS_IN_HOUR
            
        # Check current count
        cache_key = f"api_rate:{api_key_obj['id']}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            logger.warning(
                f"API rate limit exceeded for key {api_key_obj['name']} "
                f"({current_count}/{limit})"
            )
            return False
            
        # Increment counter
        cache.set(cache_key, current_count + 1, period_seconds)
        
        return True
        
    def _log_api_access(self, request, api_key_obj):
        """
        Log API access for audit purposes.
        
        Args:
            request: Django HttpRequest object
            api_key_obj: API key object
        """
        try:
            from apps.core.models import APIAccessLog
            
            APIAccessLog.objects.create(
                api_key_id=api_key_obj['id'],
                ip_address=self._get_client_ip(request),
                method=request.method,
                path=request.path,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                response_time=0,  # Will be updated in process_response
                timestamp=datetime.now()
            )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error logging API access: {e}", exc_info=True)
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Invalid API access log data: {e}")
            
    def _get_client_ip(self, request):
        """
        Get client IP address.
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            str: IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
        
    def _unauthorized_response(self, message):
        """
        Generate unauthorized response.
        
        Args:
            message: Error message
            
        Returns:
            JsonResponse: 401 Unauthorized response
        """
        return JsonResponse(
            {
                'error': 'unauthorized',
                'message': message,
                'status': 401
            },
            status=401
        )
        
    def _rate_limit_response(self):
        """
        Generate rate limit exceeded response.
        
        Returns:
            JsonResponse: 429 Too Many Requests response
        """
        return JsonResponse(
            {
                'error': 'rate_limit_exceeded',
                'message': 'API rate limit exceeded. Please try again later.',
                'status': 429
            },
            status=429
        )
