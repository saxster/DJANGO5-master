"""
Correlation ID Tracking Service

Provides centralized correlation ID management for end-to-end request tracking.

Features:
- Correlation ID generation and validation
- End-to-end tracking across services
- Correlation ID propagation to metrics/logs
- Request flow visualization support

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger('monitoring.correlation')

__all__ = ['CorrelationTrackingService', 'CorrelationContext']


class CorrelationContext:
    """
    Represents a correlation context with tracking metadata.

    Stores correlation ID and associated request metadata.
    """

    def __init__(self, correlation_id: str, metadata: Optional[Dict[str, Any]] = None):
        self.correlation_id = correlation_id
        self.created_at = datetime.now()
        self.metadata = metadata or {}
        self.events: List[Dict[str, Any]] = []

    def add_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Add an event to this correlation context."""
        self.events.append({
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data or {}
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'correlation_id': self.correlation_id,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
            'events': self.events
        }


class CorrelationTrackingService:
    """
    Service for managing correlation IDs across requests.

    Provides correlation ID generation, storage, and retrieval.
    Rule #7 compliant: < 150 lines
    """

    CACHE_PREFIX = 'correlation'
    DEFAULT_TTL = SECONDS_IN_HOUR  # 1 hour

    @classmethod
    def generate_correlation_id(cls) -> str:
        """
        Generate a new correlation ID.

        Returns:
            str: UUID-based correlation ID
        """
        return str(uuid.uuid4())

    @classmethod
    def is_valid_correlation_id(cls, correlation_id: str) -> bool:
        """
        Validate correlation ID format.

        Args:
            correlation_id: ID to validate

        Returns:
            bool: True if valid UUID format
        """
        try:
            uuid.UUID(correlation_id)
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    @classmethod
    def create_context(
        cls,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CorrelationContext:
        """
        Create a new correlation context.

        Args:
            correlation_id: Optional existing correlation ID
            metadata: Optional context metadata

        Returns:
            CorrelationContext: New context
        """
        if not correlation_id:
            correlation_id = cls.generate_correlation_id()

        context = CorrelationContext(correlation_id, metadata)

        # Store context in cache
        cls.store_context(context)

        logger.debug(
            f"Created correlation context: {correlation_id}",
            extra={'correlation_id': correlation_id}
        )

        return context

    @classmethod
    def store_context(cls, context: CorrelationContext, ttl: Optional[int] = None):
        """
        Store correlation context in cache.

        Args:
            context: Context to store
            ttl: Optional time-to-live in seconds
        """
        cache_key = f"{cls.CACHE_PREFIX}:{context.correlation_id}"
        ttl = ttl or cls.DEFAULT_TTL

        try:
            cache.set(cache_key, context.to_dict(), ttl)
        except (ConnectionError, ValueError) as e:
            logger.warning(
                f"Failed to store correlation context: {e}",
                extra={'correlation_id': context.correlation_id}
            )

    @classmethod
    def get_context(cls, correlation_id: str) -> Optional[CorrelationContext]:
        """
        Retrieve correlation context from cache.

        Args:
            correlation_id: Correlation ID to retrieve

        Returns:
            Optional[CorrelationContext]: Context if found
        """
        if not cls.is_valid_correlation_id(correlation_id):
            return None

        cache_key = f"{cls.CACHE_PREFIX}:{correlation_id}"

        try:
            data = cache.get(cache_key)
            if not data:
                return None

            # Reconstruct context from cached data
            context = CorrelationContext(
                correlation_id=data['correlation_id'],
                metadata=data['metadata']
            )
            context.events = data['events']
            # Note: created_at is not restored to avoid datetime parsing

            return context

        except (ConnectionError, ValueError, KeyError) as e:
            logger.warning(
                f"Failed to retrieve correlation context: {e}",
                extra={'correlation_id': correlation_id}
            )
            return None

    @classmethod
    def add_event_to_context(
        cls,
        correlation_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Add an event to an existing correlation context.

        Args:
            correlation_id: Correlation ID
            event_type: Type of event (e.g., 'query', 'cache_hit', 'error')
            data: Optional event data
        """
        context = cls.get_context(correlation_id)

        if not context:
            # Create new context if not found
            context = cls.create_context(correlation_id)

        context.add_event(event_type, data)
        cls.store_context(context)

        logger.debug(
            f"Added event '{event_type}' to correlation {correlation_id}",
            extra={'correlation_id': correlation_id, 'event_type': event_type}
        )
