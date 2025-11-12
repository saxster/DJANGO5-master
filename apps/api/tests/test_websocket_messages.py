"""
Tests for WebSocket Message Validation

Validates Pydantic models for WebSocket messages ensure type safety
for Kotlin/Swift codegen.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Rule #13: Validation pattern testing
"""

import pytest
from datetime import datetime
from uuid import uuid4
from django.test import TestCase
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from apps.api.websocket_messages import (
    ConnectionEstablishedMessage,
    HeartbeatMessage,
    SyncStartMessage,
    SyncDataMessage,
    SyncCompleteMessage,
    ServerDataRequestMessage,
    ServerDataMessage,
    ConflictNotificationMessage,
    ConflictResolutionMessage,
    SyncStatusMessage,
    ErrorMessage,
    parse_websocket_message,
    MESSAGE_TYPE_MAP,
)


@pytest.mark.unit
class TestConnectionMessages(TestCase):
    """Test connection-related WebSocket messages."""

    def test_connection_established_valid(self):
        """Test ConnectionEstablishedMessage accepts valid data."""
        data = {
            'type': 'connection_established',
            'user_id': '12345',
            'device_id': 'android-test-123',
            'server_time': timezone.now().isoformat(),
            'features': {
                'real_time_sync': True,
                'push_notifications': True,
            }
        }
        message = ConnectionEstablishedMessage(**data)
        self.assertEqual(message.type, 'connection_established')
        self.assertEqual(message.user_id, '12345')
        self.assertEqual(message.device_id, 'android-test-123')
        self.assertTrue(message.features['real_time_sync'])

    def test_connection_established_missing_user_id(self):
        """Test ConnectionEstablishedMessage rejects missing user_id."""
        data = {
            'type': 'connection_established',
            'device_id': 'android-test-123',
            'server_time': timezone.now().isoformat(),
        }
        with self.assertRaises(PydanticValidationError):
            ConnectionEstablishedMessage(**data)

    def test_heartbeat_valid(self):
        """Test HeartbeatMessage accepts valid data."""
        data = {
            'type': 'heartbeat',
            'timestamp': timezone.now().isoformat(),
        }
        message = HeartbeatMessage(**data)
        self.assertEqual(message.type, 'heartbeat')
        self.assertIsNotNone(message.timestamp)

    def test_heartbeat_missing_timestamp(self):
        """Test HeartbeatMessage rejects missing timestamp."""
        data = {'type': 'heartbeat'}
        with self.assertRaises(PydanticValidationError):
            HeartbeatMessage(**data)


@pytest.mark.unit
class TestSyncMessages(TestCase):
    """Test sync-related WebSocket messages."""

    def test_sync_start_valid(self):
        """Test SyncStartMessage accepts valid data."""
        data = {
            'type': 'start_sync',
            'domain': 'task',
            'since_timestamp': timezone.now().isoformat(),
            'full_sync': False,
            'device_id': 'android-456',
        }
        message = SyncStartMessage(**data)
        self.assertEqual(message.type, 'start_sync')
        self.assertEqual(message.domain, 'task')
        self.assertFalse(message.full_sync)

    def test_sync_start_invalid_domain(self):
        """Test SyncStartMessage rejects invalid domain."""
        data = {
            'type': 'start_sync',
            'domain': 'invalid_domain',
            'device_id': 'android-456',
        }
        with self.assertRaises(PydanticValidationError):
            SyncStartMessage(**data)

    def test_sync_start_missing_device_id(self):
        """Test SyncStartMessage rejects missing device_id."""
        data = {
            'type': 'start_sync',
            'domain': 'task',
        }
        with self.assertRaises(PydanticValidationError):
            SyncStartMessage(**data)

    def test_sync_data_valid(self):
        """Test SyncDataMessage accepts valid data."""
        data = {
            'type': 'sync_data',
            'payload': {'items': [{'id': 1, 'title': 'Test Task'}]},
            'idempotency_key': 'key-' + str(uuid4()),
            'domain': 'task',
            'client_timestamp': timezone.now().isoformat(),
        }
        message = SyncDataMessage(**data)
        self.assertEqual(message.type, 'sync_data')
        self.assertIsInstance(message.payload, dict)

    def test_sync_data_idempotency_key_too_short(self):
        """Test SyncDataMessage rejects short idempotency_key."""
        data = {
            'type': 'sync_data',
            'payload': {},
            'idempotency_key': 'short',  # < 16 chars
            'domain': 'task',
            'client_timestamp': timezone.now().isoformat(),
        }
        with self.assertRaises(PydanticValidationError):
            SyncDataMessage(**data)

    def test_sync_complete_valid(self):
        """Test SyncCompleteMessage accepts valid data."""
        data = {
            'type': 'sync_complete',
            'domain': 'attendance',
            'item_count': 42,
        }
        message = SyncCompleteMessage(**data)
        self.assertEqual(message.item_count, 42)

    def test_sync_complete_negative_item_count(self):
        """Test SyncCompleteMessage rejects negative item_count."""
        data = {
            'type': 'sync_complete',
            'domain': 'task',
            'item_count': -5,
        }
        with self.assertRaises(PydanticValidationError):
            SyncCompleteMessage(**data)


@pytest.mark.unit
class TestServerMessages(TestCase):
    """Test server-to-client WebSocket messages."""

    def test_server_data_request_valid(self):
        """Test ServerDataRequestMessage accepts valid data."""
        data = {
            'type': 'server_data_request',
            'domain': 'task',
            'entity_ids': ['123', '456', '789'],
            'request_id': 'req-' + str(uuid4()),
        }
        message = ServerDataRequestMessage(**data)
        self.assertEqual(len(message.entity_ids), 3)

    def test_server_data_valid(self):
        """Test ServerDataMessage accepts valid data."""
        data = {
            'type': 'server_data',
            'domain': 'journal',
            'data': [
                {'id': 1, 'title': 'Entry 1'},
                {'id': 2, 'title': 'Entry 2'},
            ],
            'next_sync_token': 'token-xyz',
            'server_timestamp': timezone.now().isoformat(),
        }
        message = ServerDataMessage(**data)
        self.assertEqual(len(message.data), 2)
        self.assertEqual(message.next_sync_token, 'token-xyz')

    def test_conflict_notification_valid(self):
        """Test ConflictNotificationMessage accepts valid data."""
        data = {
            'type': 'conflict_notification',
            'conflicts': [
                {'mobile_id': str(uuid4()), 'reason': 'version_mismatch'}
            ],
            'resolution_required': True,
            'conflict_ids': ['conflict-1', 'conflict-2'],
        }
        message = ConflictNotificationMessage(**data)
        self.assertTrue(message.resolution_required)
        self.assertEqual(len(message.conflict_ids), 2)


@pytest.mark.unit
class TestConflictResolution(TestCase):
    """Test conflict resolution messages."""

    def test_conflict_resolution_valid(self):
        """Test ConflictResolutionMessage accepts valid data."""
        data = {
            'type': 'conflict_resolution',
            'conflict_id': 'conflict-123',
            'strategy': 'client_wins',
        }
        message = ConflictResolutionMessage(**data)
        self.assertEqual(message.strategy, 'client_wins')

    def test_conflict_resolution_invalid_strategy(self):
        """Test ConflictResolutionMessage rejects invalid strategy."""
        data = {
            'type': 'conflict_resolution',
            'conflict_id': 'conflict-123',
            'strategy': 'invalid_strategy',
        }
        with self.assertRaises(PydanticValidationError):
            ConflictResolutionMessage(**data)

    def test_conflict_resolution_with_manual_data(self):
        """Test ConflictResolutionMessage with manual resolution data."""
        data = {
            'type': 'conflict_resolution',
            'conflict_id': 'conflict-456',
            'strategy': 'manual',
            'data': {'resolved_value': 'user_choice'},
        }
        message = ConflictResolutionMessage(**data)
        self.assertIsNotNone(message.data)


@pytest.mark.unit
class TestStatusAndErrorMessages(TestCase):
    """Test status and error messages."""

    def test_sync_status_valid(self):
        """Test SyncStatusMessage accepts valid data."""
        data = {
            'type': 'sync_status',
            'domain': 'ticket',
            'status': 'in_progress',
            'progress': {'processed': 5, 'total': 10},
        }
        message = SyncStatusMessage(**data)
        self.assertEqual(message.status, 'in_progress')

    def test_sync_status_invalid_status(self):
        """Test SyncStatusMessage rejects invalid status."""
        data = {
            'type': 'sync_status',
            'domain': 'task',
            'status': 'invalid_status',
        }
        with self.assertRaises(PydanticValidationError):
            SyncStatusMessage(**data)

    def test_error_message_valid(self):
        """Test ErrorMessage accepts valid data."""
        data = {
            'type': 'error',
            'error_code': 'RATE_LIMIT_EXCEEDED',
            'message': 'Too many requests',
            'retryable': True,
            'details': {'retry_after': 60},
        }
        message = ErrorMessage(**data)
        self.assertTrue(message.retryable)
        self.assertEqual(message.error_code, 'RATE_LIMIT_EXCEEDED')

    def test_error_message_defaults(self):
        """Test ErrorMessage uses default values."""
        data = {
            'type': 'error',
            'error_code': 'INTERNAL_ERROR',
            'message': 'Something went wrong',
        }
        message = ErrorMessage(**data)
        self.assertTrue(message.retryable)  # Default is True
        self.assertIsNone(message.details)  # Default is None


@pytest.mark.unit
class TestParseWebSocketMessage(TestCase):
    """Test parse_websocket_message utility function."""

    def test_parse_valid_heartbeat(self):
        """Test parsing valid heartbeat message."""
        raw = {
            'type': 'heartbeat',
            'timestamp': timezone.now().isoformat(),
        }
        message = parse_websocket_message(raw)
        self.assertIsInstance(message, HeartbeatMessage)

    def test_parse_valid_sync_start(self):
        """Test parsing valid sync_start message."""
        raw = {
            'type': 'start_sync',
            'domain': 'voice',
            'device_id': 'test-device',
        }
        message = parse_websocket_message(raw)
        self.assertIsInstance(message, SyncStartMessage)

    def test_parse_missing_type_field(self):
        """Test parsing rejects message without type field."""
        raw = {
            'domain': 'task',
            'device_id': 'test-device',
        }
        with self.assertRaises(KeyError):
            parse_websocket_message(raw)

    def test_parse_unknown_message_type(self):
        """Test parsing rejects unknown message type."""
        raw = {
            'type': 'unknown_type',
            'data': {},
        }
        with self.assertRaises(ValueError):
            parse_websocket_message(raw)

    def test_parse_invalid_message_structure(self):
        """Test parsing rejects invalid message structure."""
        raw = {
            'type': 'sync_data',
            # Missing required fields
        }
        with self.assertRaises(PydanticValidationError):
            parse_websocket_message(raw)

    def test_message_type_map_completeness(self):
        """Test MESSAGE_TYPE_MAP contains all message types."""
        expected_types = [
            'connection_established',
            'heartbeat',
            'start_sync',
            'sync_data',
            'sync_complete',
            'server_data_request',
            'server_data',
            'conflict_notification',
            'conflict_resolution',
            'sync_status',
            'error',
        ]
        for msg_type in expected_types:
            self.assertIn(msg_type, MESSAGE_TYPE_MAP)


@pytest.mark.unit
class TestMessageTypeConsistency(TestCase):
    """Test message type field consistency."""

    @staticmethod
    def _create_message_instance(model_class):
        """Factory method to create minimal valid message instances."""
        if model_class == ConnectionEstablishedMessage:
            return model_class(
                user_id='123',
                device_id='test',
                server_time=timezone.now()
            )
        if model_class == HeartbeatMessage:
            return model_class(timestamp=timezone.now())
        if model_class == SyncStartMessage:
            return model_class(domain='task', device_id='test')
        if model_class == SyncDataMessage:
            return model_class(
                payload={},
                idempotency_key='key-1234567890123456',
                domain='task',
                client_timestamp=timezone.now()
            )
        if model_class == SyncCompleteMessage:
            return model_class(domain='task', item_count=0)
        if model_class == ServerDataRequestMessage:
            return model_class(domain='task', entity_ids=[], request_id='req-1')
        if model_class == ServerDataMessage:
            return model_class(
                domain='task',
                data=[],
                server_timestamp=timezone.now()
            )
        if model_class == ConflictNotificationMessage:
            return model_class(
                conflicts=[],
                resolution_required=False,
                conflict_ids=[]
            )
        if model_class == ConflictResolutionMessage:
            return model_class(conflict_id='c-1', strategy='client_wins')
        if model_class == SyncStatusMessage:
            return model_class(domain='task', status='pending')
        if model_class == ErrorMessage:
            return model_class(error_code='TEST', message='Test error')
        return None

    def test_all_messages_have_type_field(self):
        """Test all message types have correct type field value."""
        test_cases = [
            (ConnectionEstablishedMessage, 'connection_established'),
            (HeartbeatMessage, 'heartbeat'),
            (SyncStartMessage, 'start_sync'),
            (SyncDataMessage, 'sync_data'),
            (SyncCompleteMessage, 'sync_complete'),
            (ServerDataRequestMessage, 'server_data_request'),
            (ServerDataMessage, 'server_data'),
            (ConflictNotificationMessage, 'conflict_notification'),
            (ConflictResolutionMessage, 'conflict_resolution'),
            (SyncStatusMessage, 'sync_status'),
            (ErrorMessage, 'error'),
        ]

        for model_class, expected_type in test_cases:
            instance = self._create_message_instance(model_class)
            self.assertIsNotNone(instance)
            self.assertEqual(instance.type, expected_type)


@pytest.mark.unit
class TestMessageSerialization(TestCase):
    """Test message serialization for WebSocket transmission."""

    def test_sync_start_serialization(self):
        """Test SyncStartMessage serializes to valid JSON."""
        message = SyncStartMessage(
            domain='attendance',
            since_timestamp=timezone.now(),
            full_sync=True,
            device_id='android-789'
        )
        serialized = message.model_dump()
        self.assertEqual(serialized['type'], 'start_sync')
        self.assertEqual(serialized['domain'], 'attendance')
        self.assertTrue(serialized['full_sync'])

    def test_error_message_serialization(self):
        """Test ErrorMessage serializes with all fields."""
        message = ErrorMessage(
            error_code='VALIDATION_ERROR',
            message='Invalid data provided',
            retryable=False,
            details={'field': 'device_id', 'reason': 'too_short'}
        )
        serialized = message.model_dump()
        self.assertFalse(serialized['retryable'])
        self.assertIn('field', serialized['details'])

    def test_server_data_serialization(self):
        """Test ServerDataMessage serializes complex data."""
        message = ServerDataMessage(
            domain='journal',
            data=[
                {'id': 1, 'content': 'Entry 1'},
                {'id': 2, 'content': 'Entry 2'},
            ],
            next_sync_token='token-abc123',
            server_timestamp=timezone.now()
        )
        serialized = message.model_dump()
        self.assertEqual(len(serialized['data']), 2)
        self.assertIsNotNone(serialized['next_sync_token'])


@pytest.mark.unit
class TestParseWebSocketMessageIntegration(TestCase):
    """Test parse_websocket_message integration scenarios."""

    def test_parse_and_dispatch_flow(self):
        """Test complete parse → validate → dispatch flow."""
        raw_messages = [
            {
                'type': 'heartbeat',
                'timestamp': timezone.now().isoformat(),
            },
            {
                'type': 'start_sync',
                'domain': 'task',
                'device_id': 'android-test',
            },
            {
                'type': 'sync_data',
                'payload': {'test': 'data'},
                'idempotency_key': 'key-1234567890123456',
                'domain': 'task',
                'client_timestamp': timezone.now().isoformat(),
            },
        ]

        for raw in raw_messages:
            message = parse_websocket_message(raw)
            self.assertEqual(message.type, raw['type'])

    def test_parse_with_extra_fields(self):
        """Test parsing ignores extra fields (forward compatibility)."""
        raw = {
            'type': 'heartbeat',
            'timestamp': timezone.now().isoformat(),
            'extra_field': 'ignored',  # Should be ignored
            'future_feature': True,  # Should be ignored
        }
        message = parse_websocket_message(raw)
        self.assertIsInstance(message, HeartbeatMessage)
        # Extra fields should not cause errors

    @staticmethod
    def _create_raw_message_data(message_type):
        """Factory method to create minimal valid raw message data for each type."""
        if message_type == 'connection_established':
            return {
                'type': message_type,
                'user_id': '123',
                'device_id': 'test',
                'server_time': timezone.now().isoformat(),
            }
        if message_type == 'heartbeat':
            return {'type': message_type, 'timestamp': timezone.now().isoformat()}
        if message_type == 'start_sync':
            return {'type': message_type, 'domain': 'task', 'device_id': 'test'}
        if message_type == 'sync_data':
            return {
                'type': message_type,
                'payload': {},
                'idempotency_key': '1234567890123456',
                'domain': 'task',
                'client_timestamp': timezone.now().isoformat(),
            }
        if message_type == 'sync_complete':
            return {'type': message_type, 'domain': 'task', 'item_count': 0}
        if message_type == 'server_data_request':
            return {
                'type': message_type,
                'domain': 'task',
                'entity_ids': [],
                'request_id': 'req-1',
            }
        if message_type == 'server_data':
            return {
                'type': message_type,
                'domain': 'task',
                'data': [],
                'server_timestamp': timezone.now().isoformat(),
            }
        if message_type == 'conflict_notification':
            return {
                'type': message_type,
                'conflicts': [],
                'resolution_required': False,
                'conflict_ids': [],
            }
        if message_type == 'conflict_resolution':
            return {'type': message_type, 'conflict_id': 'c-1', 'strategy': 'client_wins'}
        if message_type == 'sync_status':
            return {'type': message_type, 'domain': 'task', 'status': 'pending'}
        if message_type == 'error':
            return {'type': message_type, 'error_code': 'TEST', 'message': 'Test'}
        return {}

    def test_parse_all_registered_types(self):
        """Test all MESSAGE_TYPE_MAP entries are parseable."""
        for message_type, model_class in MESSAGE_TYPE_MAP.items():
            raw = self._create_raw_message_data(message_type)
            message = parse_websocket_message(raw)
            self.assertIsInstance(message, model_class)
