"""
Tests for Webhook Dispatcher Service.

Tests DLQ (Dead Letter Queue) functionality including:
- Entry storage
- Entry retrieval with pattern matching
- Pagination
- Retry functionality
"""

import pytest
import uuid
from datetime import datetime
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.services.webhook_dispatcher import WebhookDispatcher


@pytest.fixture
def cleanup_cache():
    """Clean up cache after each test."""
    yield
    # Clear all webhook_dlq keys
    try:
        redis_client = cache.client.get_client()
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match="webhook_dlq:*", count=100)
            for key in keys:
                cache.delete(key.decode('utf-8') if isinstance(key, bytes) else key)
            if cursor == 0:
                break
    except Exception:
        pass  # Cache might not be Redis


@pytest.fixture
def sample_dlq_entry():
    """Create a sample DLQ entry."""
    return {
        'webhook_config': {
            'id': 'webhook_test_123',
            'url': 'https://example.com/webhook',
            'events': ['test.event'],
            'secret': 'test_secret'
        },
        'event_envelope': {
            'event': 'test.event',
            'data': {'test': 'data'},
            'timestamp': timezone.now().isoformat()
        },
        'correlation_id': str(uuid.uuid4()),
        'timestamp': timezone.now().isoformat(),
        'failure_reason': 'Connection timeout',
        'attempt_count': 3
    }


@pytest.mark.django_db
class TestWebhookDispatcherDLQ:
    """Test Dead Letter Queue functionality."""

    def test_get_dlq_entries_empty(self, cleanup_cache):
        """Test retrieving DLQ entries when queue is empty."""
        entries = WebhookDispatcher.get_dead_letter_queue_entries('webhook_test_123')

        assert isinstance(entries, list)
        assert len(entries) == 0

    def test_get_dlq_entries_single_entry(self, cleanup_cache, sample_dlq_entry):
        """Test retrieving a single DLQ entry."""
        webhook_id = sample_dlq_entry['webhook_config']['id']
        correlation_id = sample_dlq_entry['correlation_id']

        # Store entry in DLQ
        dlq_key = f"webhook_dlq:{webhook_id}:{correlation_id}"
        cache.set(dlq_key, sample_dlq_entry, timeout=3600)

        # Retrieve entries
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_id)

        assert len(entries) == 1
        assert entries[0]['correlation_id'] == correlation_id
        assert entries[0]['dlq_key'] == dlq_key
        assert entries[0]['failure_reason'] == 'Connection timeout'

    def test_get_dlq_entries_multiple_webhooks(self, cleanup_cache, sample_dlq_entry):
        """Test that DLQ retrieval filters by webhook ID."""
        # Store entries for two different webhooks
        webhook_1_id = 'webhook_test_123'
        webhook_2_id = 'webhook_test_456'

        # Webhook 1 entry
        dlq_key_1 = f"webhook_dlq:{webhook_1_id}:correlation_1"
        entry_1 = {**sample_dlq_entry, 'webhook_config': {**sample_dlq_entry['webhook_config'], 'id': webhook_1_id}}
        cache.set(dlq_key_1, entry_1, timeout=3600)

        # Webhook 2 entry
        dlq_key_2 = f"webhook_dlq:{webhook_2_id}:correlation_2"
        entry_2 = {**sample_dlq_entry, 'webhook_config': {**sample_dlq_entry['webhook_config'], 'id': webhook_2_id}}
        cache.set(dlq_key_2, entry_2, timeout=3600)

        # Retrieve only webhook 1 entries
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_1_id)

        assert len(entries) == 1
        assert entries[0]['webhook_config']['id'] == webhook_1_id

    def test_get_dlq_entries_pagination(self, cleanup_cache, sample_dlq_entry):
        """Test DLQ pagination with limit parameter."""
        webhook_id = sample_dlq_entry['webhook_config']['id']

        # Store 150 entries
        for i in range(150):
            dlq_key = f"webhook_dlq:{webhook_id}:correlation_{i}"
            entry = {
                **sample_dlq_entry,
                'correlation_id': f"correlation_{i}",
                'timestamp': timezone.now().isoformat()
            }
            cache.set(dlq_key, entry, timeout=3600)

        # Retrieve with default limit (100)
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_id)
        assert len(entries) == 100

        # Retrieve with custom limit
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_id, limit=50)
        assert len(entries) == 50

    def test_get_dlq_entries_sorting(self, cleanup_cache, sample_dlq_entry):
        """Test that DLQ entries are sorted by timestamp (newest first)."""
        import time
        webhook_id = sample_dlq_entry['webhook_config']['id']

        # Store 3 entries with different timestamps
        timestamps = []
        for i in range(3):
            time.sleep(0.01)  # Ensure different timestamps
            timestamp = timezone.now()
            timestamps.append(timestamp)

            dlq_key = f"webhook_dlq:{webhook_id}:correlation_{i}"
            entry = {
                **sample_dlq_entry,
                'correlation_id': f"correlation_{i}",
                'timestamp': timestamp.isoformat()
            }
            cache.set(dlq_key, entry, timeout=3600)

        # Retrieve entries
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_id)

        # Verify sorting (newest first)
        assert len(entries) == 3
        assert entries[0]['correlation_id'] == 'correlation_2'  # Most recent
        assert entries[1]['correlation_id'] == 'correlation_1'
        assert entries[2]['correlation_id'] == 'correlation_0'  # Oldest

    def test_retry_dead_letter_entry_not_found(self, cleanup_cache):
        """Test retrying a non-existent DLQ entry."""
        result = WebhookDispatcher.retry_dead_letter_entry('webhook_dlq:nonexistent:key')

        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_get_dlq_entries_error_handling(self, cleanup_cache):
        """Test that DLQ retrieval handles errors gracefully."""
        # This test verifies that exceptions return empty list
        # rather than crashing
        entries = WebhookDispatcher.get_dead_letter_queue_entries('invalid_webhook_id')

        assert isinstance(entries, list)
        # Should return empty list even if errors occur

    def test_dlq_key_format(self, cleanup_cache, sample_dlq_entry):
        """Test that DLQ key is included in retrieved entries."""
        webhook_id = sample_dlq_entry['webhook_config']['id']
        correlation_id = sample_dlq_entry['correlation_id']

        # Store entry
        dlq_key = f"webhook_dlq:{webhook_id}:{correlation_id}"
        cache.set(dlq_key, sample_dlq_entry, timeout=3600)

        # Retrieve
        entries = WebhookDispatcher.get_dead_letter_queue_entries(webhook_id)

        assert len(entries) == 1
        assert 'dlq_key' in entries[0]
        assert entries[0]['dlq_key'] == dlq_key
