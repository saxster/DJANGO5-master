"""
Task Webhook Service

High-impact feature for automatic notifications when async tasks complete.
Eliminates need for polling and provides real-time updates to clients.

Features:
- Webhook registration for tasks
- Automatic notification on completion
- Retry logic for failed deliveries
- Signature verification for security
- Support for multiple webhook URLs per task
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.services.base_service import BaseService


logger = logging.getLogger(__name__)


class TaskWebhookService(BaseService):
    """
    Service for managing task completion webhooks.

    Provides automatic notifications when async tasks complete,
    improving user experience by eliminating polling.
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = [60, 300, 900]  # 1min, 5min, 15min
    SIGNATURE_HEADER = 'X-Webhook-Signature'
    WEBHOOK_TIMEOUT = 10  # seconds

    def __init__(self):
        super().__init__()

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "TaskWebhookService"

    def register_webhook(
        self,
        task_id: str,
        webhook_url: str,
        events: Optional[List[str]] = None,
        secret: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a webhook for task completion notification.

        Args:
            task_id: Task to monitor
            webhook_url: URL to POST results to
            events: Events to notify (completed, failed, progress)
            secret: Optional secret for signature verification
            metadata: Optional metadata to include in webhook payload

        Returns:
            Dict containing webhook registration details
        """
        try:
            # Validate webhook URL
            self._validate_webhook_url(webhook_url)

            # Default events
            if not events:
                events = ['completed', 'failed']

            # Generate webhook ID
            webhook_id = str(uuid.uuid4())

            # Generate secret if not provided
            if not secret:
                secret = self._generate_webhook_secret()

            # Store webhook registration
            webhook_data = {
                'webhook_id': webhook_id,
                'task_id': task_id,
                'webhook_url': webhook_url,
                'events': events,
                'secret': secret,
                'metadata': metadata or {},
                'status': 'active',
                'retry_count': 0,
                'created_at': timezone.now(),
                'last_attempt': None,
                'last_success': None
            }

            self._store_webhook_data(webhook_id, webhook_data)

            # Index by task_id for lookup
            self._index_webhook_by_task(task_id, webhook_id)

            logger.info(f"Webhook registered: {webhook_id} for task {task_id}")

            return {
                'status': 'success',
                'webhook_id': webhook_id,
                'task_id': task_id,
                'events': events,
                'message': 'Webhook registered successfully'
            }

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to register webhook: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)

    def notify_task_event(
        self,
        task_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Notify registered webhooks of task event.

        This method is called automatically when task events occur.

        Args:
            task_id: Task that triggered event
            event_type: Event type (completed, failed, progress)
            event_data: Event data to send

        Returns:
            Dict containing notification results
        """
        try:
            # Get webhooks for this task
            webhook_ids = self._get_webhooks_for_task(task_id)

            if not webhook_ids:
                logger.debug(f"No webhooks registered for task {task_id}")
                return {
                    'status': 'success',
                    'webhooks_notified': 0
                }

            # Notify each webhook
            results = []
            for webhook_id in webhook_ids:
                webhook_data = self._get_webhook_data(webhook_id)

                if not webhook_data:
                    continue

                # Check if this event is subscribed
                if event_type not in webhook_data.get('events', []):
                    continue

                # Deliver webhook
                delivery_result = self._deliver_webhook(
                    webhook_id,
                    webhook_data,
                    event_type,
                    event_data
                )

                results.append(delivery_result)

            logger.info(f"Webhook notifications sent for task {task_id}: {len(results)} webhooks")

            return {
                'status': 'success',
                'webhooks_notified': len(results),
                'results': results
            }

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to notify webhooks: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return {
                'status': 'error',
                'error': error_msg,
                'webhooks_notified': 0
            }

    def _deliver_webhook(
        self,
        webhook_id: str,
        webhook_data: Dict[str, Any],
        event_type: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deliver webhook notification."""
        try:
            import requests

            # Prepare payload
            payload = {
                'webhook_id': webhook_id,
                'task_id': webhook_data['task_id'],
                'event': event_type,
                'data': event_data,
                'metadata': webhook_data.get('metadata', {}),
                'timestamp': timezone.now().isoformat()
            }

            # Generate signature
            signature = self._generate_signature(
                payload,
                webhook_data['secret']
            )

            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                self.SIGNATURE_HEADER: signature,
                'User-Agent': 'IntelliWiz-Webhooks/1.0'
            }

            # Update webhook data
            webhook_data['last_attempt'] = timezone.now()
            self._store_webhook_data(webhook_id, webhook_data)

            # Deliver webhook
            response = requests.post(
                webhook_data['webhook_url'],
                json=payload,
                headers=headers,
                timeout=self.WEBHOOK_TIMEOUT
            )

            # Check response
            response.raise_for_status()

            # Update success
            webhook_data['last_success'] = timezone.now()
            webhook_data['retry_count'] = 0
            self._store_webhook_data(webhook_id, webhook_data)

            logger.info(f"Webhook delivered successfully: {webhook_id}")

            return {
                'webhook_id': webhook_id,
                'status': 'delivered',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook delivery failed: {webhook_id} - {str(e)}")

            # Handle retry
            return self._handle_webhook_retry(webhook_id, webhook_data, payload, str(e))

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            logger.error(f"Webhook delivery error: {str(e)}")

            return {
                'webhook_id': webhook_id,
                'status': 'error',
                'error': str(e)
            }

    def _handle_webhook_retry(
        self,
        webhook_id: str,
        webhook_data: Dict[str, Any],
        payload: Dict[str, Any],
        error: str
    ) -> Dict[str, Any]:
        """Handle webhook delivery retry."""
        try:
            retry_count = webhook_data.get('retry_count', 0)

            if retry_count < self.MAX_RETRIES:
                # Schedule retry
                webhook_data['retry_count'] = retry_count + 1
                webhook_data['last_error'] = error
                self._store_webhook_data(webhook_id, webhook_data)

                # Queue retry task
                from background_tasks.tasks import retry_webhook_delivery
                retry_delay = self.RETRY_DELAY_SECONDS[retry_count]

                retry_webhook_delivery.apply_async(
                    args=[webhook_id, payload],
                    countdown=retry_delay
                )

                logger.info(f"Webhook retry scheduled: {webhook_id} (attempt {retry_count + 1})")

                return {
                    'webhook_id': webhook_id,
                    'status': 'retry_scheduled',
                    'retry_count': retry_count + 1,
                    'retry_delay': retry_delay
                }
            else:
                # Max retries exceeded
                webhook_data['status'] = 'failed'
                webhook_data['last_error'] = error
                self._store_webhook_data(webhook_id, webhook_data)

                logger.error(f"Webhook delivery failed permanently: {webhook_id}")

                return {
                    'webhook_id': webhook_id,
                    'status': 'failed',
                    'error': error,
                    'retry_count': retry_count
                }

        except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            logger.error(f"Webhook retry handling error: {str(e)}")
            return {
                'webhook_id': webhook_id,
                'status': 'error',
                'error': str(e)
            }

    def _validate_webhook_url(self, url: str) -> None:
        """Validate webhook URL for security."""
        from urllib.parse import urlparse

        parsed = urlparse(url)

        if not parsed.scheme or parsed.scheme not in ['http', 'https']:
            raise ValueError("Invalid webhook URL scheme")

        if not parsed.netloc:
            raise ValueError("Invalid webhook URL domain")

        # Block internal/private IPs
        if parsed.hostname:
            import ipaddress
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback:
                    raise ValueError("Webhook URLs to private IPs not allowed")
            except ValueError:
                pass

    def _generate_webhook_secret(self) -> str:
        """Generate secure webhook secret."""
        import secrets
        return secrets.token_urlsafe(32)

    def _generate_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"

    def _store_webhook_data(self, webhook_id: str, data: Dict[str, Any]) -> None:
        """Store webhook data in cache."""
        cache.set(f"webhook_{webhook_id}", data, timeout=86400 * 7)  # 7 days

    def _get_webhook_data(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve webhook data."""
        return cache.get(f"webhook_{webhook_id}")

    def _index_webhook_by_task(self, task_id: str, webhook_id: str) -> None:
        """Index webhook by task ID for lookup."""
        key = f"task_webhooks_{task_id}"
        webhook_ids = cache.get(key, [])
        webhook_ids.append(webhook_id)
        cache.set(key, webhook_ids, timeout=86400 * 7)

    def _get_webhooks_for_task(self, task_id: str) -> List[str]:
        """Get all webhooks registered for a task."""
        key = f"task_webhooks_{task_id}"
        return cache.get(key, [])