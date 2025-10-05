"""
Integration Tests for API v2 Endpoints

Tests end-to-end flow of v2 endpoints with type-safe validation.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Rule #13: Validation pattern testing
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from uuid import uuid4
import json

from apps.onboarding.models import Bt
from apps.peoples.models import People


User = get_user_model()


@pytest.mark.integration
class TestVoiceSyncViewIntegration(TestCase):
    """Test SyncVoiceView end-to-end with real requests."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()

        # Create test business unit
        self.bt = Bt.objects.create(
            btcode='TEST_BU',
            btname='Test Business Unit'
        )

        # Create test user
        self.user = User.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            bu=self.bt,
            password='testpass123'
        )

        # Authenticate client
        self.client.force_login(self.user)

    def test_voice_sync_valid_request(self):
        """Test voice sync accepts valid request via v2 endpoint."""
        payload = {
            'device_id': 'android-test-123',
            'voice_data': [
                {
                    'verification_id': 'ver-001',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidence_score': 0.95,
                    'quality_score': 0.88,
                    'processing_time_ms': 250,
                }
            ],
            'timestamp': timezone.now().isoformat(),
            'idempotency_key': 'key-' + str(uuid4()),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Should accept valid request
        self.assertIn(response.status_code, [200, 201])

    def test_voice_sync_missing_device_id(self):
        """Test voice sync rejects request without device_id."""
        payload = {
            'voice_data': [
                {
                    'verification_id': 'ver-002',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Should reject with 400 Bad Request
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'error')
        self.assertIn('device_id', response_data['errors'])

    def test_voice_sync_invalid_device_id_format(self):
        """Test voice sync rejects invalid device_id format."""
        payload = {
            'device_id': 'invalid device with spaces!',
            'voice_data': [
                {
                    'verification_id': 'ver-003',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Should reject with 400 Bad Request
        self.assertEqual(response.status_code, 400)

    def test_voice_sync_empty_voice_data(self):
        """Test voice sync rejects empty voice_data array."""
        payload = {
            'device_id': 'android-test-456',
            'voice_data': [],  # Empty
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_voice_sync_confidence_out_of_range(self):
        """Test voice sync rejects confidence_score > 1.0."""
        payload = {
            'device_id': 'android-test-789',
            'voice_data': [
                {
                    'verification_id': 'ver-004',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidence_score': 1.5,  # Invalid
                }
            ],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_voice_sync_unauthenticated(self):
        """Test voice sync rejects unauthenticated requests."""
        self.client.logout()

        payload = {
            'device_id': 'android-test-999',
            'voice_data': [
                {
                    'verification_id': 'ver-005',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Should reject with 401/403
        self.assertIn(response.status_code, [401, 403])


@pytest.mark.integration
class TestBatchSyncViewIntegration(TestCase):
    """Test SyncBatchView end-to-end with real requests."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()

        # Create test business unit
        self.bt = Bt.objects.create(
            btcode='TEST_BU2',
            btname='Test Business Unit 2'
        )

        # Create test user
        self.user = User.objects.create_user(
            loginid='testuser2',
            peoplecode='TEST002',
            peoplename='Test User 2',
            email='test2@example.com',
            bu=self.bt,
            password='testpass123'
        )

        self.client.force_login(self.user)

    def test_batch_sync_valid_request(self):
        """Test batch sync accepts valid multi-entity request."""
        payload = {
            'device_id': 'android-batch-123',
            'items': [
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'task',
                    'operation': 'create',
                    'version': 1,
                    'data': {'title': 'Test Task'},
                    'client_timestamp': timezone.now().isoformat(),
                },
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'attendance',
                    'operation': 'update',
                    'version': 2,
                    'data': {'status': 'checked_in'},
                    'client_timestamp': timezone.now().isoformat(),
                },
            ],
            'idempotency_key': 'batch-' + str(uuid4()),
            'client_timestamp': timezone.now().isoformat(),
            'full_sync': False,
        }

        response = self.client.post(
            '/api/v2/sync/batch/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['total_items'], 2)

    def test_batch_sync_missing_idempotency_key(self):
        """Test batch sync rejects request without idempotency_key."""
        payload = {
            'device_id': 'android-batch-456',
            'items': [
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'task',
                    'operation': 'create',
                    'version': 1,
                    'data': {},
                    'client_timestamp': timezone.now().isoformat(),
                }
            ],
            'client_timestamp': timezone.now().isoformat(),
            # Missing idempotency_key
        }

        response = self.client.post(
            '/api/v2/sync/batch/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('idempotency_key', response_data['errors'])

    def test_batch_sync_invalid_entity_type(self):
        """Test batch sync rejects invalid entity_type."""
        payload = {
            'device_id': 'android-batch-789',
            'items': [
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'invalid_type',  # Invalid
                    'operation': 'create',
                    'version': 1,
                    'data': {},
                    'client_timestamp': timezone.now().isoformat(),
                }
            ],
            'idempotency_key': 'batch-' + str(uuid4()),
            'client_timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/batch/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_batch_sync_too_many_items(self):
        """Test batch sync rejects > 1000 items."""
        payload = {
            'device_id': 'android-batch-large',
            'items': [
                {
                    'mobile_id': str(uuid4()),
                    'entity_type': 'task',
                    'operation': 'create',
                    'version': 1,
                    'data': {},
                    'client_timestamp': timezone.now().isoformat(),
                }
                for _ in range(1001)  # Exceed limit
            ],
            'idempotency_key': 'batch-' + str(uuid4()),
            'client_timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/batch/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)


@pytest.mark.integration
class TestV2EndpointDiscovery(TestCase):
    """Test v2 endpoint metadata and discovery."""

    def test_version_info_endpoint(self):
        """Test /api/v2/version/ returns correct metadata."""
        client = Client()

        response = client.get('/api/v2/version/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['version'], 'v2')
        self.assertIn('features', data)
        self.assertIsInstance(data['features'], list)


@pytest.mark.integration
class TestResponseContractValidation(TestCase):
    """Test that v2 responses match Pydantic contracts."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()

        # Create test business unit
        self.bt = Bt.objects.create(
            btcode='TEST_CONTRACT',
            btname='Test Contract BU'
        )

        # Create test user
        self.user = User.objects.create_user(
            loginid='contractuser',
            peoplecode='CONTRACT001',
            peoplename='Contract Test User',
            email='contract@example.com',
            bu=self.bt,
            password='testpass123'
        )

        self.client.force_login(self.user)

    def test_voice_sync_response_matches_contract(self):
        """Test VoiceSyncView response matches VoiceSyncResponseModel."""
        from apps.api.v2.pydantic_models import VoiceSyncResponseModel

        payload = {
            'device_id': 'contract-test-device',
            'voice_data': [
                {
                    'verification_id': 'ver-contract-001',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidence_score': 0.92,
                }
            ],
            'timestamp': timezone.now().isoformat(),
            'idempotency_key': 'contract-' + str(uuid4()),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        # Verify standard envelope structure
        self.assertIn('success', response_data)
        self.assertIn('data', response_data)
        self.assertIn('meta', response_data)

        # Extract data and validate against Pydantic model
        data = response_data['data']

        # Validate all required fields exist
        self.assertIn('status', data)
        self.assertIn('synced_count', data)
        self.assertIn('error_count', data)
        self.assertIn('conflict_count', data)
        self.assertIn('server_timestamp', data)

        # Validate types match contract
        self.assertIsInstance(data['synced_count'], int)
        self.assertIsInstance(data['error_count'], int)
        self.assertIsInstance(data['conflict_count'], int)
        self.assertIn(data['status'], ['success', 'partial', 'failed'])

        # Validate data can be parsed by Pydantic model
        try:
            validated = VoiceSyncResponseModel.model_validate(data)
            self.assertIsNotNone(validated)
        except Exception as e:
            self.fail(f"Response does not match VoiceSyncResponseModel contract: {e}")

    def test_device_list_response_matches_contract(self):
        """Test DeviceListView response matches DeviceListResponseModel."""
        from apps.api.v2.pydantic_models import DeviceListResponseModel
        from apps.core.services.cross_device_sync_service import cross_device_sync_service

        # Register a test device
        cross_device_sync_service.register_device(
            user=self.user,
            device_id='test-device-list-001',
            device_type='phone',
            device_name='Test Phone'
        )

        response = self.client.get('/api/v2/devices/')

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        # Verify standard envelope structure
        self.assertIn('success', response_data)
        self.assertIn('data', response_data)

        # Extract data and validate against Pydantic model
        data = response_data['data']

        # Validate required fields
        self.assertIn('devices', data)
        self.assertIsInstance(data['devices'], list)

        # Validate data can be parsed by Pydantic model
        try:
            validated = DeviceListResponseModel.model_validate(data)
            self.assertIsNotNone(validated)
        except Exception as e:
            self.fail(f"Response does not match DeviceListResponseModel contract: {e}")

    def test_device_register_response_matches_contract(self):
        """Test DeviceRegisterView response matches DeviceRegisterResponseModel."""
        from apps.api.v2.pydantic_models import DeviceRegisterResponseModel

        payload = {
            'device_id': 'test-device-register-001',
            'device_type': 'tablet',
            'device_name': 'Test Tablet',
            'os_type': 'iOS',
            'os_version': '17.0',
            'app_version': '1.0.0',
        }

        response = self.client.post(
            '/api/v2/devices/register/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        # Verify standard envelope structure
        self.assertIn('success', response_data)
        self.assertIn('data', response_data)

        # Extract data and validate against Pydantic model
        data = response_data['data']

        # Validate required fields
        self.assertIn('device_id', data)
        self.assertIn('priority', data)
        self.assertIn('status', data)

        # Validate types
        self.assertIsInstance(data['priority'], int)
        self.assertIn(data['status'], ['registered', 'updated'])

        # Validate data can be parsed by Pydantic model
        try:
            validated = DeviceRegisterResponseModel.model_validate(data)
            self.assertIsNotNone(validated)
        except Exception as e:
            self.fail(f"Response does not match DeviceRegisterResponseModel contract: {e}")


@pytest.mark.integration
class TestWebSocketContractValidation(TestCase):
    """Test WebSocket message validation against contracts."""

    def test_heartbeat_ack_message_parsing(self):
        """Test HeartbeatAckMessage can be parsed and validated."""
        from apps.api.websocket_messages import parse_websocket_message, HeartbeatAckMessage

        raw_message = {
            'type': 'heartbeat_ack',
            'timestamp': timezone.now().isoformat()
        }

        # Should parse successfully
        try:
            message = parse_websocket_message(raw_message)
            self.assertIsInstance(message, HeartbeatAckMessage)
            self.assertEqual(message.type, 'heartbeat_ack')
        except Exception as e:
            self.fail(f"HeartbeatAckMessage failed to parse: {e}")

    def test_websocket_message_type_registry(self):
        """Test MESSAGE_TYPE_MAP includes all message types."""
        from apps.api.websocket_messages import MESSAGE_TYPE_MAP

        # Verify heartbeat_ack is in registry
        self.assertIn('heartbeat_ack', MESSAGE_TYPE_MAP)

        # Verify all expected message types
        expected_types = [
            'connection_established',
            'heartbeat',
            'heartbeat_ack',
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
            self.assertIn(msg_type, MESSAGE_TYPE_MAP, f"Missing message type: {msg_type}")
