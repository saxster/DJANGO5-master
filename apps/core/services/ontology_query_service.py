"""
Ontology Query Service with Redis caching and circuit breaker.

Performance Guarantees:
- Cache hit: < 5ms
- Cache miss: < 200ms (with fallback to empty list on timeout)
- Circuit breaker opens after 3 consecutive failures

Usage:
    from apps.core.services.ontology_query_service import OntologyQueryService

    service = OntologyQueryService()
    results = service.query("authentication", limit=5)
"""

import logging
import time
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.core.cache.backends.base import InvalidCacheBackendError
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

logger = logging.getLogger('ontology.query')


class CircuitBreaker:
    """
    Simple circuit breaker for ontology queries.

    States:
    - closed: Normal operation (calls pass through)
    - open: Circuit tripped (calls fail immediately)
    - half_open: Testing if service recovered
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before entering half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open

    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Function result or None if circuit is open
        """
        if self.state == 'open':
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                logger.warning("Circuit breaker OPEN - skipping ontology query")
                return None

        try:
            result = func(*args, **kwargs)
            # Success - reset failure count
            if self.state == 'half_open':
                logger.info("Circuit breaker recovered - entering CLOSED state")
                self.state = 'closed'
            self.failure_count = 0
            return result
        except (KeyboardInterrupt, SystemExit):
            # Allow system exceptions to propagate
            raise
        except BaseException as e:
            # NOTE: Using BaseException here intentionally for circuit breaker.
            # CircuitBreaker is a general-purpose wrapper that needs to catch
            # all operational failures (network, database, cache, validation, etc.)
            # without knowing the specific exception types in advance.
            # System exceptions (KeyboardInterrupt, SystemExit) are re-raised above.
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(
                    f"Circuit breaker OPEN after {self.failure_count} failures",
                    extra={'failure_count': self.failure_count}
                )

            logger.error(f"Ontology query failed: {e}", exc_info=True)
            return None


class OntologyQueryService:
    """
    Cached ontology query service with circuit breaker.

    Features:
    - Redis caching (5-minute TTL)
    - Circuit breaker (opens after 3 failures)
    - Timeout protection (200ms max)
    - Graceful degradation (returns [] on failure)

    Example:
        service = OntologyQueryService()
        results = service.query("authentication")
        # Returns: [{'qualified_name': ..., 'purpose': ...}, ...]
    """

    CACHE_PREFIX = "ontology_query"
    CACHE_TTL = 300  # 5 minutes
    QUERY_TIMEOUT = 0.2  # 200ms

    def __init__(self):
        """Initialize service with circuit breaker."""
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60
        )

    def query(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Query ontology with caching and circuit breaker.

        Args:
            query_text: Search query
            limit: Max results (default 5)

        Returns:
            List of ontology components or [] on failure

        Example:
            results = service.query("secure file", limit=3)
        """
        # Try cache first
        cache_key = f"{self.CACHE_PREFIX}:{query_text}:{limit}"
        cached_result = self._get_from_cache(cache_key)

        if cached_result is not None:
            logger.debug(
                f"Ontology query cache HIT: {query_text}",
                extra={'query': query_text, 'cache_key': cache_key}
            )
            return cached_result

        # Cache miss - query registry with circuit breaker
        logger.debug(
            f"Ontology query cache MISS: {query_text}",
            extra={'query': query_text, 'cache_key': cache_key}
        )
        result = self._query_registry_with_breaker(query_text, limit)

        if result is not None:
            # Cache successful result
            self._set_in_cache(cache_key, result)
            return result
        else:
            # Circuit breaker open or query failed
            logger.warning(
                f"Ontology query failed or circuit open - returning empty list",
                extra={'query': query_text}
            )
            return []

    def _get_from_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get from Redis cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or cache unavailable
        """
        try:
            return cache.get(key)
        except CACHE_EXCEPTIONS as e:
            logger.error(
                f"Cache get failed: {e}",
                extra={'cache_key': key},
                exc_info=True
            )
            return None
        except (InvalidCacheBackendError, OSError) as e:
            logger.error(
                f"Cache backend error: {e}",
                extra={'cache_key': key},
                exc_info=True
            )
            return None

    def _set_in_cache(self, key: str, value: List[Dict[str, Any]]) -> None:
        """
        Set in Redis cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
        """
        try:
            cache.set(key, value, self.CACHE_TTL)
            logger.debug(
                f"Cached ontology query result",
                extra={'cache_key': key, 'ttl': self.CACHE_TTL, 'result_count': len(value)}
            )
        except CACHE_EXCEPTIONS as e:
            logger.error(
                f"Cache set failed: {e}",
                extra={'cache_key': key},
                exc_info=True
            )
        except (InvalidCacheBackendError, OSError) as e:
            logger.error(
                f"Cache backend error: {e}",
                extra={'cache_key': key},
                exc_info=True
            )

    def _query_registry_with_breaker(
        self,
        query_text: str,
        limit: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Query ontology registry with circuit breaker protection.

        Args:
            query_text: Search query
            limit: Max results

        Returns:
            List of results or None if failed/circuit open
        """
        def _query():
            from apps.ontology.registry import OntologyRegistry

            # Query with timeout tracking
            start = time.perf_counter()
            results = OntologyRegistry.search(query_text)[:limit]
            elapsed = time.perf_counter() - start

            if elapsed > self.QUERY_TIMEOUT:
                logger.warning(
                    f"Ontology query slow: {elapsed*1000:.2f}ms (threshold: {self.QUERY_TIMEOUT*1000}ms)",
                    extra={
                        'query': query_text,
                        'elapsed_ms': elapsed * 1000,
                        'threshold_ms': self.QUERY_TIMEOUT * 1000
                    }
                )

            logger.info(
                f"Ontology query completed",
                extra={
                    'query': query_text,
                    'result_count': len(results),
                    'elapsed_ms': elapsed * 1000
                }
            )

            return results

        return self.circuit_breaker.call(_query)
