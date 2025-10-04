"""
Security and PII redaction services for Conversational Onboarding (Phase 2)
"""
import re
import hashlib
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    PII (Personally Identifiable Information) redaction service
    Sanitizes prompts and logs before LLM processing
    """

    def __init__(self):
        self.redaction_patterns = self._load_redaction_patterns()
        self.allowlisted_fields = self._load_allowlisted_fields()

    def redact_text(self, text: str, context: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Redact PII from text and return sanitized version with metadata

        Args:
            text: Text to redact
            context: Context for redaction (e.g., 'prompt', 'log', 'response')

        Returns:
            Tuple of (redacted_text, redaction_metadata)
        """
        if not text:
            return text, {}

        redacted_text = text
        redactions = []

        # Apply redaction patterns
        for pattern_name, pattern_config in self.redaction_patterns.items():
            regex = pattern_config['regex']
            replacement = pattern_config['replacement']
            sensitivity = pattern_config.get('sensitivity', 'high')

            matches = re.finditer(regex, redacted_text, re.IGNORECASE)
            for match in matches:
                original_value = match.group()

                # Create redaction record
                redaction_record = {
                    'type': pattern_name,
                    'original_length': len(original_value),
                    'position': match.start(),
                    'sensitivity': sensitivity,
                    'redacted_at': datetime.now().isoformat()
                }

                # Generate replacement based on type
                if pattern_name == 'email':
                    redacted_value = self._redact_email(original_value)
                elif pattern_name == 'phone':
                    redacted_value = self._redact_phone(original_value)
                elif pattern_name == 'ssn':
                    redacted_value = '[REDACTED_SSN]'
                elif pattern_name == 'credit_card':
                    redacted_value = '[REDACTED_CC]'
                else:
                    redacted_value = replacement

                redacted_text = redacted_text.replace(original_value, redacted_value)
                redactions.append(redaction_record)

        # Additional context-specific redaction
        if context in ['prompt', 'log']:
            redacted_text, additional_redactions = self._redact_context_specific(
                redacted_text, context
            )
            redactions.extend(additional_redactions)

        redaction_metadata = {
            'redactions_count': len(redactions),
            'redactions': redactions,
            'context': context,
            'redacted_at': datetime.now().isoformat()
        }

        return redacted_text, redaction_metadata

    def redact_dict(self, data: Dict[str, Any], context: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Redact PII from dictionary recursively
        """
        if not isinstance(data, dict):
            return data, {}

        redacted_data = {}
        all_redactions = []

        for key, value in data.items():
            # Check if field is allowlisted
            if self._is_field_allowlisted(key, context):
                redacted_data[key] = value
                continue

            if isinstance(value, str):
                redacted_value, redaction_meta = self.redact_text(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(value, dict):
                redacted_value, redaction_meta = self.redact_dict(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(value, list):
                redacted_value, redaction_meta = self._redact_list(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            else:
                redacted_data[key] = value

        return redacted_data, {'redactions': all_redactions}

    def _load_redaction_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load PII redaction patterns"""
        patterns = {
            'email': {
                'regex': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'replacement': '[REDACTED_EMAIL]',
                'sensitivity': 'medium'
            },
            'phone': {
                'regex': r'(\+?1[-.\s]?)?(\(?[0-9]{3}\)?[-.\s]?)[0-9]{3}[-.\s]?[0-9]{4}',
                'replacement': '[REDACTED_PHONE]',
                'sensitivity': 'medium'
            },
            'ssn': {
                'regex': r'\b\d{3}-?\d{2}-?\d{4}\b',
                'replacement': '[REDACTED_SSN]',
                'sensitivity': 'high'
            },
            'credit_card': {
                'regex': r'\b(?:\d{4}[-.\s]?){3}\d{4}\b',
                'replacement': '[REDACTED_CC]',
                'sensitivity': 'high'
            },
            'ip_address': {
                'regex': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
                'replacement': '[REDACTED_IP]',
                'sensitivity': 'low'
            },
            'name_patterns': {
                'regex': r'\b(Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b',
                'replacement': '[REDACTED_NAME]',
                'sensitivity': 'medium'
            }
        }

        # Load custom patterns from settings if available
        custom_patterns = getattr(settings, 'PII_REDACTION_PATTERNS', {})
        patterns.update(custom_patterns)

        return patterns

    def _load_allowlisted_fields(self) -> Dict[str, List[str]]:
        """Load fields that are allowed to pass through without redaction"""
        default_allowlist = {
            'general': ['id', 'uuid', 'created_at', 'updated_at', 'status'],
            'business': ['business_unit_type', 'security_level', 'max_users', 'operating_hours'],
            'system': ['trace_id', 'session_id', 'confidence_score', 'processing_time']
        }

        custom_allowlist = getattr(settings, 'PII_ALLOWLISTED_FIELDS', {})

        # Merge allowlists
        for context, fields in custom_allowlist.items():
            if context in default_allowlist:
                default_allowlist[context].extend(fields)
            else:
                default_allowlist[context] = fields

        return default_allowlist

    def _is_field_allowlisted(self, field_name: str, context: Optional[str] = None) -> bool:
        """Check if a field is allowlisted for the given context"""
        # Check general allowlist
        if field_name in self.allowlisted_fields.get('general', []):
            return True

        # Check context-specific allowlist
        if context and field_name in self.allowlisted_fields.get(context, []):
            return True

        return False

    def _redact_email(self, email: str) -> str:
        """Redact email while preserving domain for business context"""
        try:
            local, domain = email.split('@')
            if len(local) > 2:
                redacted_local = local[0] + '*' * (len(local) - 2) + local[-1]
            else:
                redacted_local = '*' * len(local)
            return f"{redacted_local}@{domain}"
        except ValueError:
            return '[REDACTED_EMAIL]'

    def _redact_phone(self, phone: str) -> str:
        """Redact phone while preserving area code"""
        # Extract digits
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 10:
            # Keep area code, redact rest
            return f"({digits[:3]}) ***-****"
        else:
            return '[REDACTED_PHONE]'

    def _redact_context_specific(self, text: str, context: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply context-specific redaction rules"""
        redactions = []
        redacted_text = text

        if context == 'log':
            # Redact potential API keys and tokens
            api_key_pattern = r'\b[A-Za-z0-9]{20,}\b'
            matches = re.finditer(api_key_pattern, redacted_text)
            for match in matches:
                if len(match.group()) > 16:  # Likely an API key
                    redacted_text = redacted_text.replace(match.group(), '[REDACTED_TOKEN]')
                    redactions.append({
                        'type': 'api_token',
                        'position': match.start(),
                        'sensitivity': 'high'
                    })

        return redacted_text, redactions

    def _redact_list(self, data_list: List[Any], context: Optional[str] = None) -> Tuple[List[Any], Dict[str, Any]]:
        """Redact PII from list items"""
        redacted_list = []
        all_redactions = []

        for item in data_list:
            if isinstance(item, str):
                redacted_item, redaction_meta = self.redact_text(item, context)
                redacted_list.append(redacted_item)
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(item, dict):
                redacted_item, redaction_meta = self.redact_dict(item, context)
                redacted_list.append(redacted_item)
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            else:
                redacted_list.append(item)

        return redacted_list, {'redactions': all_redactions}


class RateLimiter:
    """
    Rate limiting service with budget controls and graceful degradation

    Enhanced with:
    - Circuit breaker pattern for cache failures
    - In-memory fallback cache
    - Fail-closed for critical resources
    - Retry-After headers for rate limit responses
    """

    def __init__(self):
        self.cache = cache
        self.fallback_cache = {}  # In-memory fallback for resilience
        self.cache_failure_count = 0
        self.circuit_breaker_threshold = getattr(settings, 'RATE_LIMITER_CIRCUIT_BREAKER_THRESHOLD', 5)
        self.circuit_breaker_reset_time = None

        # Critical resources that should fail-closed on cache failure
        self.critical_resources = getattr(
            settings,
            'RATE_LIMITER_CRITICAL_RESOURCES',
            ['llm_calls', 'translations', 'knowledge_ingestion']
        )

    def check_rate_limit(
        self,
        user_identifier: str,
        resource_type: str,
        limit_type: str = 'requests'
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if user is within rate limits with graceful degradation

        Args:
            user_identifier: User or tenant identifier
            resource_type: Type of resource (llm_calls, translations, etc.)
            limit_type: Type of limit (requests, tokens, cost)

        Returns:
            Tuple of (is_allowed, limit_info)
        """
        # Check circuit breaker state
        if self._is_circuit_breaker_open():
            return self._handle_circuit_breaker_open(resource_type)

        # Get limits from settings
        limits = self._get_limits(resource_type, limit_type)

        limit_info = {
            'allowed': True,
            'current_usage': 0,
            'limit': limits.get('daily', 1000),
            'window': 'daily',
            'reset_time': None,
            'retry_after': None
        }

        try:
            # Check daily limit
            daily_key = f"rate_limit:{resource_type}:{limit_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d')}"
            current_daily = self.cache.get(daily_key, 0)
            daily_limit = limits.get('daily', 1000)

            if current_daily >= daily_limit:
                reset_time = self._get_next_reset_time('daily')
                retry_after = self._calculate_retry_after(reset_time)

                limit_info.update({
                    'allowed': False,
                    'current_usage': current_daily,
                    'limit': daily_limit,
                    'window': 'daily',
                    'reset_time': reset_time,
                    'retry_after': retry_after
                })

                logger.warning(
                    f"Rate limit exceeded for user {user_identifier}",
                    extra={
                        'user_identifier': user_identifier,
                        'resource_type': resource_type,
                        'current_usage': current_daily,
                        'limit': daily_limit,
                        'retry_after': retry_after
                    }
                )
                return False, limit_info

            # Check hourly limit if configured
            if 'hourly' in limits:
                hourly_key = f"rate_limit:{resource_type}:{limit_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
                current_hourly = self.cache.get(hourly_key, 0)
                hourly_limit = limits['hourly']

                if current_hourly >= hourly_limit:
                    reset_time = self._get_next_reset_time('hourly')
                    retry_after = self._calculate_retry_after(reset_time)

                    limit_info.update({
                        'allowed': False,
                        'current_usage': current_hourly,
                        'limit': hourly_limit,
                        'window': 'hourly',
                        'reset_time': reset_time,
                        'retry_after': retry_after
                    })

                    logger.warning(
                        f"Hourly rate limit exceeded for user {user_identifier}",
                        extra={
                            'user_identifier': user_identifier,
                            'resource_type': resource_type,
                            'window': 'hourly',
                            'retry_after': retry_after
                        }
                    )
                    return False, limit_info

            # Reset failure count on successful cache access
            if self.cache_failure_count > 0:
                logger.info(f"Cache recovered, resetting failure count from {self.cache_failure_count}")
                self.cache_failure_count = 0

            limit_info['current_usage'] = current_daily
            return True, limit_info

        except (ConnectionError, DatabaseError, IntegrityError, TimeoutError) as e:
            # Increment failure count
            self.cache_failure_count += 1

            # Generate correlation ID for tracking
            correlation_id = str(uuid.uuid4())

            logger.error(
                f"Cache failure in rate limiter (failure #{self.cache_failure_count})",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'correlation_id': correlation_id,
                    'failure_count': self.cache_failure_count
                },
                exc_info=True
            )

            # Check if circuit breaker should open
            if self.cache_failure_count >= self.circuit_breaker_threshold:
                self.circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
                logger.critical(
                    f"Circuit breaker OPENED after {self.cache_failure_count} failures",
                    extra={'correlation_id': correlation_id, 'reset_time': self.circuit_breaker_reset_time.isoformat()}
                )

            # Use fallback strategy
            return self._check_fallback_limit(user_identifier, resource_type, limit_type, correlation_id)

    def increment_usage(
        self,
        user_identifier: str,
        resource_type: str,
        amount: int = 1,
        limit_type: str = 'requests'
    ) -> bool:
        """
        Increment usage counters with fallback on cache failure

        Args:
            user_identifier: User identifier
            resource_type: Resource type
            amount: Amount to increment by
            limit_type: Type of limit

        Returns:
            True if increment was successful (including fallback)
        """
        try:
            # Increment daily counter
            daily_key = f"rate_limit:{resource_type}:{limit_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d')}"
            self.cache.set(daily_key, self.cache.get(daily_key, 0) + amount, 86400)

            # Increment hourly counter if needed
            limits = self._get_limits(resource_type, limit_type)
            if 'hourly' in limits:
                hourly_key = f"rate_limit:{resource_type}:{limit_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
                self.cache.set(hourly_key, self.cache.get(hourly_key, 0) + amount, 3600)

            return True

        except (ConnectionError, DatabaseError, IntegrityError, TimeoutError) as e:
            # Log failure but continue (usage tracking is best-effort)
            correlation_id = str(uuid.uuid4())

            logger.warning(
                f"Failed to increment usage counter - using fallback",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'amount': amount,
                    'error': str(e),
                    'correlation_id': correlation_id
                }
            )

            # Increment fallback counter
            fallback_key = f"{resource_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
            self.fallback_cache[fallback_key] = self.fallback_cache.get(fallback_key, 0) + amount

            return True  # Return True even with fallback (best-effort)

    def get_usage_stats(self, user_identifier: str, resource_type: str) -> Dict[str, Any]:
        """
        Get current usage statistics for a user with fallback support

        Args:
            user_identifier: User identifier
            resource_type: Resource type

        Returns:
            Dict with usage statistics (empty dict on failure)
        """
        try:
            daily_key = f"rate_limit:{resource_type}:requests:{user_identifier}:{datetime.now().strftime('%Y-%m-%d')}"
            hourly_key = f"rate_limit:{resource_type}:requests:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"

            return {
                'daily_usage': self.cache.get(daily_key, 0),
                'hourly_usage': self.cache.get(hourly_key, 0),
                'resource_type': resource_type,
                'user_identifier': user_identifier,
                'timestamp': datetime.now().isoformat(),
                'source': 'primary_cache'
            }

        except (ConnectionError, DatabaseError, IntegrityError, TimeoutError) as e:
            logger.warning(
                f"Failed to get usage stats from cache - using fallback",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'error': str(e)
                }
            )

            # Try fallback cache
            fallback_key = f"{resource_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
            fallback_usage = self.fallback_cache.get(fallback_key, 0)

            return {
                'hourly_usage': fallback_usage,
                'resource_type': resource_type,
                'user_identifier': user_identifier,
                'timestamp': datetime.now().isoformat(),
                'source': 'fallback_cache',
                'warning': 'Primary cache unavailable'
            }

    def _get_limits(self, resource_type: str, limit_type: str) -> Dict[str, int]:
        """Get rate limits for resource type"""
        default_limits = {
            'llm_calls': {
                'requests': {'daily': 100, 'hourly': 20},
                'tokens': {'daily': 50000, 'hourly': 10000},
                'cost': {'daily': 1000}  # cents
            },
            'translations': {
                'requests': {'daily': 500, 'hourly': 100},
                'characters': {'daily': 100000, 'hourly': 20000}
            },
            'knowledge_queries': {
                'requests': {'daily': 200, 'hourly': 50}
            }
        }

        # Get custom limits from settings
        custom_limits = getattr(settings, 'ONBOARDING_RATE_LIMITS', {})

        limits = default_limits.get(resource_type, {}).get(limit_type, {'daily': 100})
        custom_resource_limits = custom_limits.get(resource_type, {}).get(limit_type, {})

        # Merge with custom limits
        limits.update(custom_resource_limits)

        return limits

    def _get_next_reset_time(self, window: str) -> str:
        """Get next reset time for the given window"""
        now = datetime.now()

        if window == 'hourly':
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_hour.isoformat()
        else:  # daily
            next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return next_day.isoformat()

    def _calculate_retry_after(self, reset_time: str) -> int:
        """
        Calculate Retry-After value in seconds

        Args:
            reset_time: ISO format reset time string

        Returns:
            Seconds until reset time
        """
        try:
            reset_dt = datetime.fromisoformat(reset_time)
            now = datetime.now()
            delta = (reset_dt - now).total_seconds()
            return max(int(delta), 60)  # Minimum 60 seconds
        except (ValueError, TypeError):
            return 3600  # Default to 1 hour

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open"""
        if self.circuit_breaker_reset_time is None:
            return False

        # Check if reset time has passed
        if datetime.now() >= self.circuit_breaker_reset_time:
            logger.info("Circuit breaker CLOSED - reset time reached")
            self.circuit_breaker_reset_time = None
            self.cache_failure_count = 0
            return False

        return True

    def _handle_circuit_breaker_open(self, resource_type: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle request when circuit breaker is open

        Args:
            resource_type: Type of resource being rate limited

        Returns:
            Tuple of (is_allowed, limit_info)
        """
        is_critical = resource_type in self.critical_resources

        if is_critical:
            # Fail-closed for critical resources
            retry_after = int((self.circuit_breaker_reset_time - datetime.now()).total_seconds())

            logger.warning(
                f"Circuit breaker OPEN - blocking critical resource: {resource_type}",
                extra={
                    'resource_type': resource_type,
                    'retry_after': retry_after,
                    'strategy': 'fail_closed'
                }
            )

            return False, {
                'allowed': False,
                'reason': 'circuit_breaker_open',
                'critical_resource': True,
                'retry_after': retry_after,
                'reset_time': self.circuit_breaker_reset_time.isoformat()
            }
        else:
            # Fail-open for non-critical resources with logging
            logger.warning(
                f"Circuit breaker OPEN - allowing non-critical resource: {resource_type}",
                extra={
                    'resource_type': resource_type,
                    'strategy': 'fail_open_with_logging'
                }
            )

            return True, {
                'allowed': True,
                'reason': 'circuit_breaker_open_fail_open',
                'critical_resource': False,
                'warning': 'Rate limiting unavailable - degraded mode'
            }

    def _check_fallback_limit(
        self,
        user_identifier: str,
        resource_type: str,
        limit_type: str,
        correlation_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using in-memory fallback cache

        Args:
            user_identifier: User identifier
            resource_type: Resource type
            limit_type: Limit type
            correlation_id: Correlation ID for tracking

        Returns:
            Tuple of (is_allowed, limit_info)
        """
        is_critical = resource_type in self.critical_resources

        # For critical resources, fail-closed
        if is_critical:
            logger.warning(
                f"Fallback check for critical resource - BLOCKING: {resource_type}",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'correlation_id': correlation_id,
                    'strategy': 'fail_closed'
                }
            )

            return False, {
                'allowed': False,
                'reason': 'cache_failure_critical_resource',
                'critical_resource': True,
                'retry_after': 300,  # 5 minutes
                'correlation_id': correlation_id
            }

        # For non-critical resources, use in-memory fallback
        fallback_key = f"{resource_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"

        # Get current count from fallback cache
        current_count = self.fallback_cache.get(fallback_key, 0)

        # Conservative limits for fallback (lower than normal)
        fallback_limit = 50  # Fallback limit per hour

        if current_count >= fallback_limit:
            logger.warning(
                f"Fallback rate limit exceeded for user {user_identifier}",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'current_count': current_count,
                    'fallback_limit': fallback_limit,
                    'correlation_id': correlation_id
                }
            )

            return False, {
                'allowed': False,
                'reason': 'fallback_limit_exceeded',
                'current_usage': current_count,
                'limit': fallback_limit,
                'window': 'hourly_fallback',
                'retry_after': 3600,
                'correlation_id': correlation_id
            }

        # Increment fallback count
        self.fallback_cache[fallback_key] = current_count + 1

        # Clean old fallback entries (keep last 100 entries)
        if len(self.fallback_cache) > 100:
            # Remove oldest 20 entries
            keys_to_remove = list(self.fallback_cache.keys())[:20]
            for key in keys_to_remove:
                del self.fallback_cache[key]

        logger.info(
            f"Fallback rate limit check passed for {user_identifier}",
            extra={
                'user_identifier': user_identifier,
                'resource_type': resource_type,
                'current_count': current_count + 1,
                'fallback_limit': fallback_limit,
                'correlation_id': correlation_id
            }
        )

        return True, {
            'allowed': True,
            'reason': 'fallback_cache_passed',
            'current_usage': current_count + 1,
            'limit': fallback_limit,
            'window': 'hourly_fallback',
            'warning': 'Using fallback rate limiting',
            'correlation_id': correlation_id
        }


class ContentDeduplicator:
    """
    Content deduplication service with hash-based duplicate detection
    """

    def __init__(self):
        self.cache = cache
        self.cache_timeout = 3600  # 1 hour

    def check_duplicate_content(self, content: str, content_hash: str = None) -> Dict[str, Any]:
        """
        Check if content already exists in the knowledge base

        Args:
            content: Document content
            content_hash: Pre-computed SHA-256 hash (optional)

        Returns:
            Dict with duplicate check results
        """
        if not content:
            return {'is_duplicate': False, 'duplicate_info': None}

        # Calculate hash if not provided
        if not content_hash:
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        try:
            from apps.onboarding.models import AuthoritativeKnowledge

            # Check for exact hash match
            existing_docs = AuthoritativeKnowledge.objects.filter(
                doc_checksum=content_hash,
                is_current=True
            )

            if existing_docs.exists():
                existing_doc = existing_docs.first()
                return {
                    'is_duplicate': True,
                    'duplicate_info': {
                        'existing_doc_id': str(existing_doc.knowledge_id),
                        'existing_title': existing_doc.document_title,
                        'existing_version': existing_doc.document_version,
                        'hash_match': 'exact',
                        'should_reject': True,
                        'recommendation': 'Content already exists. Consider version update instead.'
                    }
                }

            # Check for similar content (fuzzy matching)
            similar_docs = self._find_similar_content(content, content_hash)
            if similar_docs:
                return {
                    'is_duplicate': False,
                    'similar_content': similar_docs,
                    'recommendation': 'Similar content found. Review for potential duplication.'
                }

            return {
                'is_duplicate': False,
                'duplicate_info': None,
                'content_hash': content_hash
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error checking duplicate content: {str(e)}")
            return {
                'is_duplicate': False,
                'duplicate_info': None,
                'error': str(e)
            }

    def should_allow_duplicate(self, existing_doc_info: Dict, new_doc_info: Dict) -> bool:
        """
        Determine if duplicate content should be allowed (e.g., version bump)

        Args:
            existing_doc_info: Information about existing document
            new_doc_info: Information about new document

        Returns:
            True if duplicate should be allowed
        """
        # Allow if version is different
        existing_version = existing_doc_info.get('existing_version', '')
        new_version = new_doc_info.get('document_version', '')

        if existing_version != new_version and new_version:
            return True

        # Allow if source organization is different (different perspective)
        existing_org = existing_doc_info.get('source_organization', '')
        new_org = new_doc_info.get('source_organization', '')

        if existing_org != new_org:
            return True

        # Allow if jurisdiction is different
        existing_jurisdiction = existing_doc_info.get('jurisdiction', '')
        new_jurisdiction = new_doc_info.get('jurisdiction', '')

        if existing_jurisdiction != new_jurisdiction and new_jurisdiction:
            return True

        return False

    def _find_similar_content(self, content: str, content_hash: str) -> List[Dict[str, Any]]:
        """Find similar content using fuzzy matching"""
        try:
            from apps.onboarding.models import AuthoritativeKnowledge

            # Simple similarity check based on content length and first/last characters
            content_length = len(content)
            content_prefix = content[:100] if len(content) > 100 else content
            content_suffix = content[-100:] if len(content) > 100 else content

            # Find documents with similar characteristics
            similar_candidates = AuthoritativeKnowledge.objects.filter(
                is_current=True
            ).exclude(doc_checksum=content_hash)

            similar_docs = []
            for doc in similar_candidates:
                similarity_score = self._calculate_similarity_score(content, doc.content_summary)
                if similarity_score > 0.7:  # 70% similarity threshold
                    similar_docs.append({
                        'doc_id': str(doc.knowledge_id),
                        'title': doc.document_title,
                        'similarity_score': similarity_score,
                        'reason': 'high_content_similarity'
                    })

            return similar_docs[:5]  # Return top 5 similar documents

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error finding similar content: {str(e)}")
            return []

    def _calculate_similarity_score(self, content1: str, content2: str) -> float:
        """Calculate simple similarity score between two texts"""
        if not content1 or not content2:
            return 0.0

        # Simple word-based similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0


class LicenseValidator:
    """
    License and redistribution validation service
    """

    def __init__(self):
        # Common license patterns and restrictions
        self.restricted_licenses = {
            'copyright_reserved': {
                'patterns': [r'all rights reserved', r'copyright.*reserved', r'proprietary'],
                'redistribution_allowed': False,
                'attribution_required': True
            },
            'creative_commons_nc': {
                'patterns': [r'creative commons.*non-commercial', r'cc.*nc'],
                'redistribution_allowed': False,
                'attribution_required': True
            },
            'confidential': {
                'patterns': [r'confidential', r'internal use only', r'proprietary'],
                'redistribution_allowed': False,
                'attribution_required': True
            }
        }

        self.permissive_licenses = {
            'public_domain': {
                'patterns': [r'public domain', r'no rights reserved'],
                'redistribution_allowed': True,
                'attribution_required': False
            },
            'creative_commons_open': {
                'patterns': [r'creative commons.*attribution', r'cc.*by'],
                'redistribution_allowed': True,
                'attribution_required': True
            },
            'government_work': {
                'patterns': [r'government work', r'official.*document', r'nist\.gov', r'uscis\.gov'],
                'redistribution_allowed': True,
                'attribution_required': True
            }
        }

    def validate_document_license(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate document license and redistribution rights

        Args:
            content: Document content to analyze
            metadata: Additional metadata from document source

        Returns:
            Dict with license validation results
        """
        validation_result = {
            'license_detected': None,
            'redistribution_allowed': False,
            'attribution_required': True,
            'restrictions': [],
            'warnings': [],
            'license_metadata': {}
        }

        try:
            content_lower = content.lower()

            # Check for restricted licenses
            for license_name, license_info in self.restricted_licenses.items():
                for pattern in license_info['patterns']:
                    if re.search(pattern, content_lower):
                        validation_result.update({
                            'license_detected': license_name,
                            'redistribution_allowed': license_info['redistribution_allowed'],
                            'attribution_required': license_info['attribution_required']
                        })

                        if not license_info['redistribution_allowed']:
                            validation_result['restrictions'].append({
                                'type': 'redistribution_prohibited',
                                'description': f'License {license_name} prohibits redistribution',
                                'detected_pattern': pattern
                            })

                        logger.info(f"Detected restricted license: {license_name}")
                        return validation_result

            # Check for permissive licenses
            for license_name, license_info in self.permissive_licenses.items():
                for pattern in license_info['patterns']:
                    if re.search(pattern, content_lower):
                        validation_result.update({
                            'license_detected': license_name,
                            'redistribution_allowed': license_info['redistribution_allowed'],
                            'attribution_required': license_info['attribution_required']
                        })

                        logger.info(f"Detected permissive license: {license_name}")
                        return validation_result

            # No specific license detected
            validation_result['warnings'].append({
                'type': 'no_license_detected',
                'description': 'No explicit license information found',
                'recommendation': 'Verify redistribution rights with source'
            })

            # Default to conservative approach
            validation_result.update({
                'license_detected': 'unknown',
                'redistribution_allowed': False,
                'attribution_required': True
            })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error validating license: {str(e)}")
            validation_result['warnings'].append({
                'type': 'validation_error',
                'description': f'License validation failed: {str(e)}'
            })

        return validation_result

    def should_quarantine_document(self, license_validation: Dict[str, Any], pii_scan_result: Dict[str, Any]) -> bool:
        """
        Determine if document should be quarantined based on license and PII concerns

        Args:
            license_validation: Results from license validation
            pii_scan_result: Results from PII scanning

        Returns:
            True if document should be quarantined
        """
        # Quarantine if redistribution is prohibited
        if not license_validation.get('redistribution_allowed', False):
            logger.info("Quarantining document: redistribution prohibited")
            return True

        # Quarantine if high-sensitivity PII detected
        pii_redactions = pii_scan_result.get('redactions', [])
        high_sensitivity_pii = [r for r in pii_redactions if r.get('sensitivity') == 'high']

        if high_sensitivity_pii:
            logger.info(f"Quarantining document: {len(high_sensitivity_pii)} high-sensitivity PII items detected")
            return True

        # Quarantine if too much PII (indicates personal document)
        if len(pii_redactions) > 5:
            logger.info(f"Quarantining document: excessive PII detected ({len(pii_redactions)} items)")
            return True

        return False

    def create_quarantine_record(self, document_info: Dict[str, Any], quarantine_reason: str) -> Dict[str, Any]:
        """Create quarantine record for blocked document"""
        quarantine_record = {
            'quarantine_id': str(uuid.uuid4()),
            'document_title': document_info.get('title', 'Unknown'),
            'source_url': document_info.get('source_url', ''),
            'content_hash': document_info.get('content_hash', ''),
            'quarantine_reason': quarantine_reason,
            'quarantined_at': datetime.now().isoformat(),
            'requires_manual_review': True,
            'auto_release_eligible': False
        }

        # Store in cache for admin review
        cache_key = f"quarantine:{quarantine_record['quarantine_id']}"
        self.cache.set(cache_key, quarantine_record, 86400 * 7)  # 7 days

        logger.warning(f"Document quarantined: {quarantine_reason}")
        return quarantine_record


class ContentDeduplicator:
    """
    Enhanced content deduplication with version awareness
    """

    def __init__(self):
        pass

    def check_duplicate_with_versioning(self, content_hash: str, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for duplicates considering version bumps

        Args:
            content_hash: SHA-256 hash of content
            document_info: Document metadata including version info

        Returns:
            Dict with deduplication results
        """
        try:
            from apps.onboarding.models import AuthoritativeKnowledge

            dedup_result = {
                'is_duplicate': False,
                'allow_duplicate': False,
                'existing_documents': [],
                'version_conflict': False,
                'recommendations': []
            }

            # Find documents with same hash
            exact_matches = AuthoritativeKnowledge.objects.filter(
                doc_checksum=content_hash,
                is_current=True
            )

            if not exact_matches.exists():
                return dedup_result

            # Analyze each match
            for existing_doc in exact_matches:
                match_info = {
                    'doc_id': str(existing_doc.knowledge_id),
                    'title': existing_doc.document_title,
                    'version': existing_doc.document_version,
                    'source_org': existing_doc.source_organization,
                    'jurisdiction': existing_doc.jurisdiction,
                    'industry': existing_doc.industry
                }

                dedup_result['existing_documents'].append(match_info)

                # Check if this is a legitimate version update
                if self._is_version_update(existing_doc, document_info):
                    dedup_result['allow_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Version update detected: {existing_doc.document_version} → {document_info.get('version', 'unknown')}"
                    )
                # Check if different jurisdiction/industry
                elif self._is_different_context(existing_doc, document_info):
                    dedup_result['allow_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Different context: {existing_doc.jurisdiction}/{existing_doc.industry}"
                    )
                else:
                    dedup_result['is_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Exact duplicate found: {existing_doc.document_title}"
                    )

            return dedup_result

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error checking duplicates: {str(e)}")
            return {'is_duplicate': False, 'error': str(e)}

    def _is_version_update(self, existing_doc, new_doc_info: Dict[str, Any]) -> bool:
        """Check if this is a legitimate version update"""
        existing_version = existing_doc.document_version
        new_version = new_doc_info.get('document_version', '')
        existing_org = existing_doc.source_organization
        new_org = new_doc_info.get('source_organization', '')

        # Same organization with different version
        if existing_org == new_org and existing_version != new_version and new_version:
            return True

        return False

    def _is_different_context(self, existing_doc, new_doc_info: Dict[str, Any]) -> bool:
        """Check if document has different jurisdiction/industry context"""
        existing_jurisdiction = existing_doc.jurisdiction
        new_jurisdiction = new_doc_info.get('jurisdiction', '')
        existing_industry = existing_doc.industry
        new_industry = new_doc_info.get('industry', '')

        # Different jurisdiction or industry
        if (existing_jurisdiction != new_jurisdiction and new_jurisdiction) or \
           (existing_industry != new_industry and new_industry):
            return True

        return False

    def retire_superseded_versions(self, document_info: Dict[str, Any]) -> List[str]:
        """
        Retire superseded versions when a new version is ingested

        Args:
            document_info: New document information

        Returns:
            List of retired document IDs
        """
        try:
            from apps.onboarding.models import AuthoritativeKnowledge

            # Find older versions from same source organization
            older_versions = AuthoritativeKnowledge.objects.filter(
                source_organization=document_info.get('source_organization'),
                document_title__iexact=document_info.get('document_title', ''),
                is_current=True
            ).exclude(
                document_version=document_info.get('document_version', '')
            )

            retired_ids = []
            for old_doc in older_versions:
                old_doc.is_current = False
                old_doc.tags['superseded_by'] = document_info.get('knowledge_id', '')
                old_doc.tags['superseded_at'] = datetime.now().isoformat()
                old_doc.save()
                retired_ids.append(str(old_doc.knowledge_id))

            if retired_ids:
                logger.info(f"Retired {len(retired_ids)} superseded document versions")

            return retired_ids

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error retiring superseded versions: {str(e)}")
            return []


class LicenseValidator:
    """
    License compliance and redistribution validation service
    """

    def __init__(self):
        # Load blocked license patterns from settings
        self.blocked_patterns = getattr(settings, 'KB_BLOCKED_LICENSE_PATTERNS', [
            r'proprietary',
            r'internal use only',
            r'confidential',
            r'trade secret'
        ])

        # Load required attribution patterns
        self.attribution_patterns = getattr(settings, 'KB_ATTRIBUTION_PATTERNS', [
            r'creative commons',
            r'attribution required',
            r'cite as',
            r'reference as'
        ])

    def validate_redistribution_rights(self, content: str, source_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate if content can be redistributed in knowledge base

        Args:
            content: Document content
            source_metadata: Metadata from document source

        Returns:
            Dict with validation results
        """
        validation = {
            'redistribution_allowed': True,
            'attribution_required': False,
            'license_restrictions': [],
            'compliance_requirements': [],
            'risk_assessment': 'low'
        }

        try:
            content_lower = content.lower()

            # Check for blocked license patterns
            for pattern in self.blocked_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    validation.update({
                        'redistribution_allowed': False,
                        'risk_assessment': 'high'
                    })
                    validation['license_restrictions'].append({
                        'type': 'blocked_license',
                        'pattern': pattern,
                        'description': f'Content contains blocked license pattern: {pattern}'
                    })

            # Check for attribution requirements
            for pattern in self.attribution_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    validation['attribution_required'] = True
                    validation['compliance_requirements'].append({
                        'type': 'attribution_required',
                        'pattern': pattern,
                        'description': f'Content requires attribution: {pattern}'
                    })

            # Check source-specific restrictions
            if source_metadata:
                source_restrictions = self._check_source_restrictions(source_metadata)
                validation['license_restrictions'].extend(source_restrictions)

            # Update risk assessment
            if validation['license_restrictions']:
                validation['risk_assessment'] = 'medium' if validation['redistribution_allowed'] else 'high'

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error validating redistribution rights: {str(e)}")
            validation.update({
                'redistribution_allowed': False,
                'risk_assessment': 'high',
                'license_restrictions': [{'type': 'validation_error', 'description': str(e)}]
            })

        return validation

    def _check_source_restrictions(self, source_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for source-specific license restrictions"""
        restrictions = []

        # Check for known restrictive sources
        source_url = source_metadata.get('source_url', '').lower()
        server_header = source_metadata.get('server', '').lower()

        # Commercial platforms often have restrictions
        restrictive_domains = ['proprietary.com', 'internal.company.com', 'private.org']
        for domain in restrictive_domains:
            if domain in source_url:
                restrictions.append({
                    'type': 'restrictive_source',
                    'description': f'Source {domain} may have redistribution restrictions',
                    'source': domain
                })

        # Check for copyright headers
        if 'copyright' in str(source_metadata).lower():
            restrictions.append({
                'type': 'copyright_notice',
                'description': 'Copyright notice detected in source metadata',
                'recommendation': 'Verify redistribution rights'
            })

        return restrictions

    def create_attribution_record(self, document_info: Dict[str, Any], license_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create attribution record for compliant use"""
        attribution = {
            'attribution_id': str(uuid.uuid4()),
            'document_title': document_info.get('title', ''),
            'source_organization': document_info.get('source_organization', ''),
            'source_url': document_info.get('source_url', ''),
            'license_type': license_info.get('license_detected', 'unknown'),
            'attribution_text': self._generate_attribution_text(document_info, license_info),
            'created_at': datetime.now().isoformat()
        }

        return attribution

    def _generate_attribution_text(self, document_info: Dict[str, Any], license_info: Dict[str, Any]) -> str:
        """Generate proper attribution text"""
        title = document_info.get('title', 'Unknown Document')
        org = document_info.get('source_organization', 'Unknown Organization')
        url = document_info.get('source_url', '')

        attribution = f"Source: {title} by {org}"
        if url:
            attribution += f" ({url})"

        license_type = license_info.get('license_detected')
        if license_type and license_type != 'unknown':
            attribution += f" - License: {license_type}"

        attribution += f" - Accessed: {datetime.now().strftime('%Y-%m-%d')}"

        return attribution


class SecurityGuardian:
    """
    Comprehensive security service for onboarding API
    Enhanced with document content security and license validation
    """

    def __init__(self):
        self.pii_redactor = PIIRedactor()
        self.rate_limiter = RateLimiter()
        self.source_allowlist = self._load_source_allowlist()
        self.content_deduplicator = ContentDeduplicator()
        self.license_validator = LicenseValidator()

    def sanitize_prompt(self, prompt: str, user_id: str, context: str = 'prompt') -> Tuple[str, Dict[str, Any]]:
        """
        Sanitize prompt before sending to LLM

        Returns:
            Tuple of (sanitized_prompt, security_metadata)
        """
        # Redact PII
        sanitized_prompt, redaction_meta = self.pii_redactor.redact_text(prompt, context)

        # Check rate limits
        rate_allowed, rate_info = self.rate_limiter.check_rate_limit(user_id, 'llm_calls', 'requests')

        security_metadata = {
            'pii_redacted': len(redaction_meta.get('redactions', [])) > 0,
            'redaction_metadata': redaction_meta,
            'rate_limit_check': rate_info,
            'rate_limited': not rate_allowed,
            'sanitized_at': datetime.now().isoformat()
        }

        if not rate_allowed:
            raise RateLimitExceeded(f"Rate limit exceeded: {rate_info}")

        return sanitized_prompt, security_metadata

    def sanitize_response(self, response: Dict[str, Any], context: str = 'response') -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Sanitize response before returning to user
        """
        # Redact any PII that might have been in the response
        sanitized_response, redaction_meta = self.pii_redactor.redact_dict(response, context)

        security_metadata = {
            'response_sanitized': True,
            'redaction_metadata': redaction_meta,
            'sanitized_at': datetime.now().isoformat()
        }

        return sanitized_response, security_metadata

    def validate_source_url(self, url: str) -> bool:
        """
        Validate if URL is from an allowed source
        """
        if not self.source_allowlist:
            return False  # Default deny if no allowlist configured

        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            return any(
                domain == allowed_domain or domain.endswith('.' + allowed_domain)
                for allowed_domain in self.source_allowlist
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.warning(f"Error validating source URL {url}: {str(e)}")
            return False

    def _load_source_allowlist(self) -> List[str]:
        """Load allowed source domains"""
        default_allowlist = [
            # Common safe domains for documentation
            'docs.python.org',
            'developer.mozilla.org',
            'stackoverflow.com',
            'github.com',
            'djangoproject.com'
        ]

        custom_allowlist = getattr(settings, 'ONBOARDING_SOURCE_ALLOWLIST', [])

        return default_allowlist + custom_allowlist

    def validate_document_security(self, content: str, document_info: Dict[str, Any], source_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Comprehensive document security validation

        Args:
            content: Document content
            document_info: Document metadata
            source_metadata: Source fetch metadata

        Returns:
            Dict with comprehensive security validation results
        """
        security_validation = {
            'overall_risk': 'low',
            'security_passed': True,
            'violations': [],
            'recommendations': [],
            'quarantine_required': False,
            'validation_timestamp': datetime.now().isoformat()
        }

        try:
            # 1. PII Scanning
            _, pii_scan = self.pii_redactor.redact_text(content, 'document_ingestion')

            # 2. License Validation
            license_validation = self.license_validator.validate_document_license(content, source_metadata)

            # 3. Content Deduplication
            content_hash = document_info.get('content_hash') or hashlib.sha256(content.encode()).hexdigest()
            dedup_result = self.content_deduplicator.check_duplicate_with_versioning(content_hash, document_info)

            # 4. Determine quarantine requirement
            quarantine_required = self.license_validator.should_quarantine_document(license_validation, pii_scan)

            # Aggregate results
            security_validation.update({
                'pii_scan_result': pii_scan,
                'license_validation': license_validation,
                'deduplication_result': dedup_result,
                'quarantine_required': quarantine_required
            })

            # Calculate overall risk
            risk_factors = []
            if pii_scan.get('redactions', []):
                risk_factors.append('pii_detected')
            if not license_validation.get('redistribution_allowed', True):
                risk_factors.append('redistribution_restricted')
            if dedup_result.get('is_duplicate', False) and not dedup_result.get('allow_duplicate', False):
                risk_factors.append('duplicate_content')

            if len(risk_factors) >= 2:
                security_validation['overall_risk'] = 'high'
                security_validation['security_passed'] = False
            elif len(risk_factors) == 1:
                security_validation['overall_risk'] = 'medium'
            else:
                security_validation['overall_risk'] = 'low'

            # Generate recommendations
            if quarantine_required:
                security_validation['recommendations'].append('Document requires quarantine and manual review')
            if license_validation.get('attribution_required', False):
                security_validation['recommendations'].append('Attribution required for this content')
            if dedup_result.get('similar_content'):
                security_validation['recommendations'].append('Review for potential content overlap')

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in document security validation: {str(e)}")
            security_validation.update({
                'overall_risk': 'high',
                'security_passed': False,
                'violations': [{'type': 'validation_error', 'description': str(e)}]
            })

        return security_validation

    def check_rbac_permissions(self, user, action: str, resource: str = None) -> Dict[str, Any]:
        """
        Check role-based access control permissions

        Args:
            user: User object
            action: Action to check (ingest, publish, review, etc.)
            resource: Optional resource identifier

        Returns:
            Dict with permission check results
        """
        permission_result = {
            'allowed': False,
            'user_roles': [],
            'required_roles': [],
            'permission_source': 'denied'
        }

        try:
            # Get user roles and capabilities
            user_capabilities = getattr(user, 'capabilities', {})
            is_staff = getattr(user, 'is_staff', False)

            # Determine user roles
            user_roles = []
            if is_staff:
                user_roles.append('staff')
            if user_capabilities.get('knowledge_curator', False):
                user_roles.append('knowledge_curator')
            if user_capabilities.get('admin', False):
                user_roles.append('admin')

            permission_result['user_roles'] = user_roles

            # Define required roles for actions
            action_requirements = {
                'ingest': ['knowledge_curator', 'admin'],
                'publish': ['knowledge_curator', 'admin'],
                'review': ['knowledge_curator', 'admin', 'staff'],
                'search': ['staff'],  # Basic search allowed for all staff
                'read': ['staff']     # Read access for all staff
            }

            required_roles = action_requirements.get(action, ['admin'])
            permission_result['required_roles'] = required_roles

            # Check permissions
            if any(role in user_roles for role in required_roles):
                permission_result['allowed'] = True
                permission_result['permission_source'] = f"role_{action}"

            logger.info(f"RBAC check: user {user.email} action {action} - {'allowed' if permission_result['allowed'] else 'denied'}")

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error checking RBAC permissions: {str(e)}")
            permission_result['error'] = str(e)

        return permission_result


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    pass


# =============================================================================
# SERVICE FACTORY
# =============================================================================


def get_pii_redactor() -> PIIRedactor:
    """Factory function to get PII redactor"""
    return PIIRedactor()


def get_rate_limiter() -> RateLimiter:
    """Factory function to get rate limiter"""
    return RateLimiter()


def get_security_guardian() -> SecurityGuardian:
    """Factory function to get security guardian"""
    return SecurityGuardian()


def get_content_deduplicator() -> ContentDeduplicator:
    """Factory function to get content deduplicator"""
    return ContentDeduplicator()


def get_license_validator() -> LicenseValidator:
    """Factory function to get license validator"""
    return LicenseValidator()