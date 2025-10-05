"""
Tests for API v2 Serializers

Validates type safety, Pydantic integration, and error handling.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Rule #13: Validation pattern testing
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from django.utils import timezone
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError
from pydantic import ValidationError as PydanticValidationError

from apps.api.v2.serializers import (
    VoiceSyncRequestSerializer,
    VoiceSyncResponseSerializer,
    BatchSyncRequestSerializer,
    BatchSyncResponseSerializer,
)
from apps.api.v2.pydantic_models import (
    VoiceSyncDataModel,
    BatchSyncDataModel,
)


@pytest.mark.unit
class TestVoiceSyncRequestSerializer(TestCase):
    """Test VoiceSyncRequestSerializer validation."""

    def setUp(self):
        """Set up test data."""
        self.valid_data = {
            'device_id': 'test-device-123',
            'voice_data': [
                {
                    'verification_id': 'ver-001',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidence_score': 0.95,
                    'quality_score': 0.88,
                    'processing_time_ms': 250,
                    'metadata': {'model': 'v2'}
                }
            ],
            'timestamp': timezone.now().isoformat(),
            'idempotency_key': 'key-' + str(uuid4()),
        }

    def test_valid_voice_sync_request(self):
        """Test serializer accepts valid data."""
        serializer = VoiceSyncRequestSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        validated = serializer.validated_data
        self.assertEqual(validated['device_id'], 'test-device-123')
        self.assertEqual(len(validated['voice_data']), 1)

    def test_missing_device_id(self):
        """Test serializer rejects missing device_id."""
        data = self.valid_data.copy()
        del data['device_id']
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('device_id', serializer.errors)

    def test_invalid_device_id_format(self):
        """Test serializer rejects invalid device_id format."""
        data = self.valid_data.copy()
        data['device_id'] = 'invalid device with spaces!'
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_device_id_too_short(self):
        """Test serializer rejects device_id < 5 chars."""
        data = self.valid_data.copy()
        data['device_id'] = 'abc'
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_empty_voice_data(self):
        """Test serializer rejects empty voice_data."""
        data = self.valid_data.copy()
        data['voice_data'] = []
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_too_many_voice_records(self):
        """Test serializer rejects > 100 voice records."""
        data = self.valid_data.copy()
        data['voice_data'] = [data['voice_data'][0]] * 101
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_timestamp_in_future(self):
        """Test serializer rejects future timestamps."""
        data = self.valid_data.copy()
        future = timezone.now() + timedelta(days=1)
        data['voice_data'][0]['timestamp'] = future.isoformat()
        serializer = VoiceSyncRequestSerializer(data=data)
        # Pydantic validation should catch this
        self.assertFalse(serializer.is_valid())

    def test_confidence_score_out_of_range(self):
        """Test serializer rejects confidence_score outside 0.0-1.0."""
        data = self.valid_data.copy()
        data['voice_data'][0]['confidence_score'] = 1.5
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_negative_processing_time(self):
        """Test serializer rejects negative processing_time_ms."""
        data = self.valid_data.copy()
        data['voice_data'][0]['processing_time_ms'] = -100
        serializer = VoiceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())


@pytest.mark.unit
class TestBatchSyncRequestSerializer(TestCase):
    """Test BatchSyncRequestSerializer validation."""

    def setUp(self):
        """Set up test data."""
        self.valid_data = {
            'device_id': 'test-device-456',
            'items': [
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'task',
                    'operation': 'create',
                    'version': 1,
                    'data': {'title': 'Test Task'},
                    'client_timestamp': timezone.now().isoformat(),
                }
            ],
            'idempotency_key': 'batch-' + str(uuid4()),
            'client_timestamp': timezone.now().isoformat(),
            'full_sync': False,
        }

    def test_valid_batch_sync_request(self):
        """Test serializer accepts valid batch data."""
        serializer = BatchSyncRequestSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        validated = serializer.validated_data
        self.assertEqual(validated['device_id'], 'test-device-456')
        self.assertEqual(len(validated['items']), 1)

    def test_missing_idempotency_key(self):
        """Test serializer rejects missing idempotency_key."""
        data = self.valid_data.copy()
        del data['idempotency_key']
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('idempotency_key', serializer.errors)

    def test_idempotency_key_too_short(self):
        """Test serializer rejects idempotency_key < 16 chars."""
        data = self.valid_data.copy()
        data['idempotency_key'] = 'short'
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_empty_items_list(self):
        """Test serializer rejects empty items list."""
        data = self.valid_data.copy()
        data['items'] = []
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_too_many_items(self):
        """Test serializer rejects > 1000 items."""
        data = self.valid_data.copy()
        data['items'] = [data['items'][0].copy() for _ in range(1001)]
        # Update mobile_ids to be unique
        for item in data['items']:
            item['mobile_id'] = str(uuid4())
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_invalid_entity_type(self):
        """Test serializer rejects invalid entity_type."""
        data = self.valid_data.copy()
        data['items'][0]['entity_type'] = 'invalid_type'
        serializer = BatchSyncRequestSerializer(data=data)
        # Pydantic validation should catch this
        self.assertFalse(serializer.is_valid())

    def test_invalid_operation(self):
        """Test serializer rejects invalid operation."""
        data = self.valid_data.copy()
        data['items'][0]['operation'] = 'invalid_op'
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_version_less_than_one(self):
        """Test serializer rejects version < 1."""
        data = self.valid_data.copy()
        data['items'][0]['version'] = 0
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_multiple_entity_types(self):
        """Test serializer handles multiple entity types in batch."""
        data = self.valid_data.copy()
        data['items'].extend([
            {
                'mobile_id': str(uuid4()),
                'entity_type': 'attendance',
                'operation': 'update',
                'version': 2,
                'data': {'status': 'checked_in'},
                'client_timestamp': timezone.now().isoformat(),
            },
            {
                'mobile_id': str(uuid4()),
                'entity_type': 'journal',
                'operation': 'delete',
                'version': 1,
                'data': {},
                'client_timestamp': timezone.now().isoformat(),
            },
        ])
        serializer = BatchSyncRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(len(serializer.validated_data['items']), 3)


@pytest.mark.unit
class TestPydanticModelValidation(TestCase):
    """Test Pydantic model validation directly."""

    def test_voice_sync_data_model_valid(self):
        """Test VoiceSyncDataModel accepts valid data."""
        data = {
            'device_id': 'test-device-789',
            'voice_data': [
                {
                    'verification_id': 'ver-002',
                    'timestamp': timezone.now(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now(),
        }
        model = VoiceSyncDataModel(**data)
        self.assertEqual(model.device_id, 'test-device-789')

    def test_voice_sync_data_model_invalid_device_id(self):
        """Test VoiceSyncDataModel rejects invalid device_id."""
        data = {
            'device_id': 'invalid device!',
            'voice_data': [
                {
                    'verification_id': 'ver-003',
                    'timestamp': timezone.now(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now(),
        }
        with self.assertRaises(PydanticValidationError):
            VoiceSyncDataModel(**data)

    def test_batch_sync_data_model_valid(self):
        """Test BatchSyncDataModel accepts valid data."""
        data = {
            'device_id': 'test-device-101',
            'items': [
                {
                    'mobile_id': uuid4(),
                    'entity_type': 'task',
                    'operation': 'create',
                    'version': 1,
                    'data': {},
                    'client_timestamp': timezone.now(),
                }
            ],
            'idempotency_key': 'key-' + str(uuid4()),
            'client_timestamp': timezone.now(),
        }
        model = BatchSyncDataModel(**data)
        self.assertEqual(len(model.items), 1)

    def test_batch_sync_data_model_entity_type_normalization(self):
        """Test BatchSyncDataModel normalizes entity_type to lowercase."""
        data = {
            'device_id': 'test-device-102',
            'items': [
                {
                    'mobile_id': uuid4(),
                    'entity_type': 'TASK',  # Uppercase
                    'operation': 'create',
                    'version': 1,
                    'data': {},
                    'client_timestamp': timezone.now(),
                }
            ],
            'idempotency_key': 'key-' + str(uuid4()),
            'client_timestamp': timezone.now(),
        }
        model = BatchSyncDataModel(**data)
        self.assertEqual(model.items[0].entity_type, 'task')  # Lowercased
