"""
Comprehensive Idempotency Service Tests

Tests batch and item-level idempotency for mobile sync operations.
Validates that retries don't create duplicates.

Following .claude/rules.md testing patterns.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.api.v1.services.idempotency_service import IdempotencyService
from apps.core.models.sync_idempotency import SyncIdempotencyRecord


@pytest.mark.django_db
class IdempotencyServiceTests(TestCase):
    """Test idempotency service for sync operations"""

    def setUp(self):
        """Set up test data"""
        self.idempotency_service = IdempotencyService()
        self.user_id = 'user-123'
        self.device_id = 'device-456'

    def test_generate_idempotency_key_consistency(self):
        """Test that same input generates same idempotency key"""
        # Arrange
        operation = 'sync_voice'
        data = {
            'voice_data': [
                {'verification_id': 'v1', 'verified': True}
            ]
        }
        context = {'user_id': self.user_id, 'device_id': self.device_id}

        # Act
        key1 = self.idempotency_service.generate_idempotency_key(operation, data, context)
        key2 = self.idempotency_service.generate_idempotency_key(operation, data, context)

        # Assert
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 64)  # SHA256 truncated to 64 chars

    def test_generate_idempotency_key_uniqueness(self):
        """Test that different inputs generate different keys"""
        # Arrange
        base_data = {'voice_data': [{'verification_id': 'v1'}]}

        # Act
        key1 = self.idempotency_service.generate_idempotency_key('sync_voice', base_data)
        key2 = self.idempotency_service.generate_idempotency_key('sync_behavioral', base_data)
        key3 = self.idempotency_service.generate_idempotency_key(
            'sync_voice',
            {'voice_data': [{'verification_id': 'v2'}]}
        )

        # Assert - All different
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key2, key3)

    def test_check_duplicate_returns_none_for_first_request(self):
        """Test that first request is not detected as duplicate"""
        # Arrange
        idempotency_key = 'test-key-001'

        # Act
        result = self.idempotency_service.check_duplicate(idempotency_key)

        # Assert
        self.assertIsNone(result)

    def test_store_and_retrieve_idempotency_record(self):
        """Test storing and retrieving idempotency response"""
        # Arrange
        idempotency_key = 'test-key-002'
        request_hash = 'hash-002'
        response_data = {
            'synced_items': 5,
            'failed_items': 0,
            'timestamp': timezone.now().isoformat()
        }

        # Act - Store
        stored = self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_data=response_data,
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/api/v1/sync/voice',
            scope='batch'
        )

        # Assert - Storage succeeded
        self.assertTrue(stored)

        # Act - Retrieve
        cached_response = self.idempotency_service.check_duplicate(idempotency_key)

        # Assert - Response matches
        self.assertIsNotNone(cached_response)
        self.assertEqual(cached_response['synced_items'], 5)
        self.assertEqual(cached_response['failed_items'], 0)

    def test_duplicate_request_returns_cached_response(self):
        """Test that duplicate request returns cached response without reprocessing"""
        # Arrange
        idempotency_key = 'test-key-003'
        original_response = {'result': 'success', 'items': 10}

        self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='hash-003',
            response_data=original_response,
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/api/v1/sync/tasks'
        )

        # Act - Make duplicate request
        cached_response = self.idempotency_service.check_duplicate(idempotency_key)

        # Assert
        self.assertEqual(cached_response, original_response)

        # Verify hit count incremented
        record = SyncIdempotencyRecord.objects.get(idempotency_key=idempotency_key)
        self.assertEqual(record.hit_count, 1)
        self.assertIsNotNone(record.last_hit_at)

    def test_multiple_duplicate_requests_increment_hit_count(self):
        """Test that multiple duplicate requests increment hit counter"""
        # Arrange
        idempotency_key = 'test-key-004'
        self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='hash-004',
            response_data={'result': 'test'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/test'
        )

        # Act - Make 5 duplicate requests
        for _ in range(5):
            self.idempotency_service.check_duplicate(idempotency_key)

        # Assert - Hit count is 5
        record = SyncIdempotencyRecord.objects.get(idempotency_key=idempotency_key)
        self.assertEqual(record.hit_count, 5)

    def test_expired_idempotency_record_not_returned(self):
        """Test that expired records are not returned as duplicates"""
        # Arrange - Create expired record
        idempotency_key = 'test-key-expired'
        record = SyncIdempotencyRecord.objects.create(
            idempotency_key=idempotency_key,
            request_hash='hash-expired',
            response_data={'result': 'old'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/test',
            expires_at=timezone.now() - timedelta(hours=1)  # Expired 1 hour ago
        )

        # Act
        result = self.idempotency_service.check_duplicate(idempotency_key)

        # Assert - Expired record not returned
        self.assertIsNone(result)

    def test_cleanup_expired_records(self):
        """Test automatic cleanup of expired idempotency records"""
        # Arrange - Create 3 expired and 2 valid records
        for i in range(3):
            SyncIdempotencyRecord.objects.create(
                idempotency_key=f'expired-{i}',
                request_hash=f'hash-{i}',
                response_data={'result': 'test'},
                user_id=self.user_id,
                device_id=self.device_id,
                endpoint='/test',
                expires_at=timezone.now() - timedelta(hours=1)
            )

        for i in range(2):
            SyncIdempotencyRecord.objects.create(
                idempotency_key=f'valid-{i}',
                request_hash=f'hash-valid-{i}',
                response_data={'result': 'test'},
                user_id=self.user_id,
                device_id=self.device_id,
                endpoint='/test',
                expires_at=timezone.now() + timedelta(hours=23)
            )

        # Act
        removed_count = self.idempotency_service.cleanup_expired_records()

        # Assert
        self.assertEqual(removed_count, 3)
        self.assertEqual(SyncIdempotencyRecord.objects.count(), 2)

    def test_idempotency_key_format_json_serializable(self):
        """Test that idempotency keys handle complex JSON-serializable data"""
        # Arrange - Complex nested data structure
        complex_data = {
            'items': [
                {'id': 1, 'data': {'nested': True, 'values': [1, 2, 3]}},
                {'id': 2, 'data': {'nested': False}}
            ],
            'metadata': {
                'timestamp': timezone.now().isoformat(),
                'version': 2
            }
        }

        # Act
        key = self.idempotency_service.generate_idempotency_key(
            'sync_complex',
            complex_data,
            {'user': self.user_id}
        )

        # Assert - Key generated successfully
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 64)

    def test_batch_level_idempotency(self):
        """Test batch-level idempotency scope"""
        # Arrange
        batch_data = {
            'entries': [
                {'id': 1, 'value': 'a'},
                {'id': 2, 'value': 'b'}
            ]
        }
        idempotency_key = self.idempotency_service.generate_idempotency_key(
            'batch_sync',
            batch_data
        )

        # Act
        self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='batch-hash',
            response_data={'batch_result': 'success'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/api/v1/sync/batch',
            scope='batch'
        )

        # Assert
        record = SyncIdempotencyRecord.objects.get(idempotency_key=idempotency_key)
        self.assertEqual(record.scope, 'batch')

    def test_item_level_idempotency(self):
        """Test item-level idempotency scope"""
        # Arrange
        item_data = {'mobile_id': 'item-uuid-001', 'version': 1}
        idempotency_key = self.idempotency_service.generate_idempotency_key(
            'item_sync',
            item_data
        )

        # Act
        self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='item-hash',
            response_data={'item_result': 'created'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/api/v1/sync/item',
            scope='item'
        )

        # Assert
        record = SyncIdempotencyRecord.objects.get(idempotency_key=idempotency_key)
        self.assertEqual(record.scope, 'item')

    def test_concurrent_duplicate_store_handles_gracefully(self):
        """Test that concurrent attempts to store same key handle gracefully"""
        # Arrange
        idempotency_key = 'concurrent-key-001'

        # Act - Store twice (simulating concurrent requests)
        result1 = self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='hash-concurrent',
            response_data={'result': 'first'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/test'
        )

        result2 = self.idempotency_service.store_response(
            idempotency_key=idempotency_key,
            request_hash='hash-concurrent',
            response_data={'result': 'second'},
            user_id=self.user_id,
            device_id=self.device_id,
            endpoint='/test'
        )

        # Assert - First succeeded, second failed gracefully
        self.assertTrue(result1)
        self.assertFalse(result2)

        # Only one record exists
        self.assertEqual(
            SyncIdempotencyRecord.objects.filter(idempotency_key=idempotency_key).count(),
            1
        )