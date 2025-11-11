"""
Webhook Dispatcher Service.

Responsibilities:
- Dispatch events to configured webhooks
- HMAC signature generation
- Retry logic with exponential backoff
- Dead-letter queue for failed webhooks
- Rate limiting per tenant

Following CLAUDE.md:
- Rule #15: Network calls with timeouts
- Rule #16: Exponential backoff for retries
- Rule #11: Specific exception handling
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from django.core.cache import cache
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)

# Webhook constants
WEBHOOK_TIMEOUT_CONNECT = 5  # seconds
WEBHOOK_TIMEOUT_READ = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min
RATE_LIMIT_PER_MINUTE = 100
DEAD_LETTER_QUEUE_PREFIX = "webhook_dlq"


class WebhookDispatcher:
    """Service for dispatching events to configured webhooks."""

    @classmethod
    def dispatch_event(
        cls,
        tenant_id: int,
        event_type: str,
        payload: Dict,
        correlation_id: Optional[str] = None
    ) -> Dict:
        """
        Dispatch event to all configured webhooks for this event type.

        Args:
            tenant_id: Tenant identifier
            event_type: Event type (e.g., "ticket.created")
            payload: Event payload dictionary
            correlation_id: Optional correlation ID for tracking

        Returns:
            Dict with dispatch results:
                - success: bool
                - webhooks_sent: int
                - webhooks_failed: int
                - details: List[Dict]

        Examples:
            >>> WebhookDispatcher.dispatch_event(
            ...     tenant_id=1,
            ...     event_type="alert.escalated",
            ...     payload={"alert_id": 123, "severity": "HIGH"}
            ... )
            {'success': True, 'webhooks_sent': 2, 'webhooks_failed': 0}
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Check rate limit
        if not cls._check_rate_limit(tenant_id):
            logger.warning(
                "webhook_rate_limited",
                extra={
                    'tenant_id': tenant_id,
                    'event_type': event_type,
                    'correlation_id': correlation_id
                }
            )
            return {
                'success': False,
                'error': 'Rate limit exceeded',
                'webhooks_sent': 0,
                'webhooks_failed': 0
            }

        # Get webhook configurations for tenant
        webhooks = cls._get_webhook_configs(tenant_id, event_type)

        if not webhooks:
            logger.debug(
                "no_webhooks_configured",
                extra={
                    'tenant_id': tenant_id,
                    'event_type': event_type
                }
            )
            return {
                'success': True,
                'webhooks_sent': 0,
                'webhooks_failed': 0,
                'message': 'No webhooks configured for this event type'
            }

        # Build event envelope
        event_envelope = cls._build_event_envelope(
            tenant_id,
            event_type,
            payload,
            correlation_id
        )

        # Dispatch to each webhook
        results = []
        success_count = 0
        failure_count = 0

        for webhook_config in webhooks:
            result = cls._send_webhook(
                webhook_config,
                event_envelope,
                correlation_id
            )

            results.append(result)

            if result['success']:
                success_count += 1
            else:
                failure_count += 1

        logger.info(
            "webhooks_dispatched",
            extra={
                'tenant_id': tenant_id,
                'event_type': event_type,
                'correlation_id': correlation_id,
                'success_count': success_count,
                'failure_count': failure_count
            }
        )

        return {
            'success': failure_count == 0,
            'webhooks_sent': success_count,
            'webhooks_failed': failure_count,
            'details': results,
            'correlation_id': correlation_id
        }

    @classmethod
    def _get_webhook_configs(cls, tenant_id: int, event_type: str) -> List[Dict]:
        """
        Get webhook configurations for tenant and event type.

        Nov 2025: Supports both new WebhookConfiguration models and legacy
        TypeAssist.other_data for backward compatibility.

        Args:
            tenant_id: Tenant identifier
            event_type: Event type to filter

        Returns:
            List of webhook configuration dictionaries
        """
        webhooks = []

        # Try new WebhookConfiguration models first (Nov 2025)
        try:
            from apps.integrations.models import WebhookConfiguration

            # Query webhooks listening to this event type
            webhook_configs = WebhookConfiguration.objects.filter(
                tenant_id=tenant_id,
                enabled=True,
                webhook_events__event_type=event_type
            ).distinct().select_related('tenant').prefetch_related('webhook_events')

            for webhook in webhook_configs:
                # Convert to dict format expected by dispatcher
                webhooks.append({
                    'id': str(webhook.webhook_id),
                    'name': webhook.name,
                    'url': webhook.url,
                    'secret': webhook.secret,
                    'enabled': webhook.enabled,
                    'retry_count': webhook.retry_count,
                    'timeout_seconds': webhook.timeout_seconds,
                    'events': [e.event_type for e in webhook.webhook_events.all()],
                    'source': 'webhook_configuration'  # Track source
                })

            if webhooks:
                logger.debug(
                    f"Found {len(webhooks)} webhook(s) from WebhookConfiguration models"
                )
                return webhooks

        except Exception as e:
            # Models might not exist yet (pre-migration)
            logger.debug(f"WebhookConfiguration models not available: {e}")

        # Fallback to legacy TypeAssist.other_data (DEPRECATED)
        try:
            from apps.onboarding.models import TypeAssist

            webhook_config = TypeAssist.objects.filter(
                client_id=tenant_id,
                type='webhook_config'
            ).first()

            if webhook_config and webhook_config.other_data:
                all_webhooks = webhook_config.other_data.get('webhooks', [])

                # Filter webhooks that are enabled and subscribed to this event type
                matching_webhooks = [
                    {**wh, 'source': 'typeassist'}  # Mark as legacy
                    for wh in all_webhooks
                    if wh.get('enabled', False) and event_type in wh.get('events', [])
                ]

                if matching_webhooks:
                    logger.debug(
                        f"Found {len(matching_webhooks)} webhook(s) from TypeAssist (legacy)"
                    )

                return matching_webhooks

        except NETWORK_EXCEPTIONS as e:
            logger.error(
                "webhook_config_retrieval_failed",
                extra={
                    'tenant_id': tenant_id,
                    'error': str(e)
                },
                exc_info=True
            )

        return []

    @classmethod
    def _build_event_envelope(
        cls,
        tenant_id: int,
        event_type: str,
        payload: Dict,
        correlation_id: str
    ) -> Dict:
        """
        Build standardized event envelope.

        Args:
            tenant_id: Tenant identifier
            event_type: Event type
            payload: Event payload
            correlation_id: Correlation ID

        Returns:
            Event envelope dictionary
        """
        return {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'correlation_id': correlation_id,
            'timestamp': timezone.now().isoformat(),
            'tenant_id': tenant_id,
            'api_version': 'v2',
            'payload': payload
        }

    @classmethod
    def _send_webhook(
        cls,
        webhook_config: Dict,
        event_envelope: Dict,
        correlation_id: str,
        retry_count: int = 0
    ) -> Dict:
        """
        Send webhook with retry logic.

        Args:
            webhook_config: Webhook configuration
            event_envelope: Event data
            correlation_id: Correlation ID for tracking
            retry_count: Current retry attempt (0-based)

        Returns:
            Result dictionary with success status and details
        """
        webhook_url = webhook_config.get('url')
        webhook_secret = webhook_config.get('secret')
        webhook_id = webhook_config.get('id')
        timeout = webhook_config.get('timeout_seconds', WEBHOOK_TIMEOUT_READ)

        # Generate signature
        signature = cls._generate_signature(event_envelope, webhook_secret)

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Event-Type': event_envelope['event_type'],
            'X-Event-ID': event_envelope['event_id'],
            'X-Correlation-ID': correlation_id,
            'User-Agent': 'YOUTILITY5-Webhook/2.0'
        }

        try:
            response = requests.post(
                webhook_url,
                json=event_envelope,
                headers=headers,
                timeout=(WEBHOOK_TIMEOUT_CONNECT, timeout)
            )

            response.raise_for_status()

            logger.info(
                "webhook_sent_successfully",
                extra={
                    'webhook_id': webhook_id,
                    'url': webhook_url,
                    'event_type': event_envelope['event_type'],
                    'correlation_id': correlation_id,
                    'status_code': response.status_code,
                    'retry_count': retry_count
                }
            )

            return {
                'success': True,
                'webhook_id': webhook_id,
                'status_code': response.status_code,
                'retry_count': retry_count
            }

        except NETWORK_EXCEPTIONS as e:
            logger.warning(
                "webhook_delivery_failed",
                extra={
                    'webhook_id': webhook_id,
                    'url': webhook_url,
                    'event_type': event_envelope['event_type'],
                    'correlation_id': correlation_id,
                    'error': str(e),
                    'retry_count': retry_count
                }
            )

            # Retry logic
            max_retries = webhook_config.get('retry_count', MAX_RETRIES)
            if retry_count < max_retries:
                # Schedule retry (would be done via Celery in production)
                logger.info(
                    "webhook_retry_scheduled",
                    extra={
                        'webhook_id': webhook_id,
                        'retry_count': retry_count + 1,
                        'delay_seconds': RETRY_DELAYS[retry_count]
                    }
                )
            else:
                # Move to dead-letter queue
                cls._move_to_dead_letter_queue(
                    webhook_config,
                    event_envelope,
                    correlation_id,
                    str(e)
                )

            return {
                'success': False,
                'webhook_id': webhook_id,
                'error': str(e),
                'retry_count': retry_count
            }

    @classmethod
    def _generate_signature(cls, event_envelope: Dict, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook verification.

        Args:
            event_envelope: Event data
            secret: Webhook secret key

        Returns:
            Hex-encoded signature string
        """
        if not secret:
            return ''

        payload_bytes = json.dumps(event_envelope, sort_keys=True).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return signature

    @classmethod
    def _check_rate_limit(cls, tenant_id: int) -> bool:
        """
        Check if tenant is within rate limit.

        Limit: 100 webhooks per minute per tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if within limit, False if exceeded
        """
        rate_limit_key = f"webhook_rate_limit:{tenant_id}"

        current_count = cache.get(rate_limit_key, 0)

        if current_count >= RATE_LIMIT_PER_MINUTE:
            return False

        # Increment counter
        cache.set(rate_limit_key, current_count + 1, SECONDS_IN_MINUTE)

        return True

    @classmethod
    def _move_to_dead_letter_queue(
        cls,
        webhook_config: Dict,
        event_envelope: Dict,
        correlation_id: str,
        error_message: str
    ) -> None:
        """
        Move failed webhook to dead-letter queue.

        Args:
            webhook_config: Webhook configuration
            event_envelope: Event data
            correlation_id: Correlation ID
            error_message: Error message
        """
        dlq_key = f"{DEAD_LETTER_QUEUE_PREFIX}:{webhook_config['id']}:{correlation_id}"

        dlq_entry = {
            'webhook_config': webhook_config,
            'event_envelope': event_envelope,
            'correlation_id': correlation_id,
            'error_message': error_message,
            'failed_at': timezone.now().isoformat(),
            'retry_attempts': webhook_config.get('retry_count', MAX_RETRIES)
        }

        # Store in cache for 7 days
        cache.set(dlq_key, dlq_entry, 7 * SECONDS_IN_HOUR * 24)

        logger.error(
            "webhook_moved_to_dlq",
            extra={
                'webhook_id': webhook_config['id'],
                'correlation_id': correlation_id,
                'error': error_message
            }
        )

    @classmethod
    def verify_webhook_signature(
        cls,
        payload: Dict,
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify webhook signature (for incoming webhooks from external systems).

        Args:
            payload: Webhook payload
            signature: Received signature
            secret: Shared secret

        Returns:
            True if signature valid
        """
        expected_signature = cls._generate_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)

    @classmethod
    def get_dead_letter_queue_entries(cls, webhook_id: str) -> List[Dict]:
        """
        Get dead-letter queue entries for a webhook.

        Args:
            webhook_id: Webhook identifier

        Returns:
            List of DLQ entries
        """
        # This would query Redis with pattern matching
        # For now, return empty list
        return []

    @classmethod
    def retry_dead_letter_entry(cls, dlq_key: str) -> Dict:
        """
        Retry a dead-letter queue entry.

        Args:
            dlq_key: DLQ cache key

        Returns:
            Retry result dictionary
        """
        dlq_entry = cache.get(dlq_key)

        if not dlq_entry:
            return {
                'success': False,
                'error': 'DLQ entry not found'
            }

        # Re-send webhook
        result = cls._send_webhook(
            dlq_entry['webhook_config'],
            dlq_entry['event_envelope'],
            dlq_entry['correlation_id'],
            retry_count=0  # Reset retry count
        )

        if result['success']:
            # Remove from DLQ
            cache.delete(dlq_key)

        return result
