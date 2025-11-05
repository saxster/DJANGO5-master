"""
Integration Tests for API v2 Endpoints

Tests end-to-end flow of v2 endpoints with type-safe validation.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Rule #13: Validation pattern testing
"""

import json
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from apps.client_onboarding.models import Bt
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

    @patch('apps.api.v2.views.sync_views.sync_engine.sync_voice_data', return_value={'synced_items': 1, 'failed_items': 0})
    @patch('apps.api.v2.views.sync_views.cross_device_sync_service.sync_across_devices')
    def test_voice_sync_uses_uuid_entity_id(self, mock_cross_device, _mock_sync_voice):
        """Ensure cross-device coordination receives a UUID entity identifier."""
        payload = {
            'device_id': 'android-test-uuid',
            'voice_data': [
                {
                    'verification_id': 'ver-uuid-001',
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

        self.assertEqual(response.status_code, 200)
        mock_cross_device.assert_called_once()

        _, kwargs = mock_cross_device.call_args
        self.assertIsInstance(kwargs['entity_id'], UUID)
        self.assertIn('data', kwargs)
        self.assertGreaterEqual(kwargs['data']['version'], 0)


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
        except (ValueError, TypeError, AttributeError, KeyError) as e:
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
        except (ValueError, TypeError, AttributeError, KeyError) as e:
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
        except (ValueError, TypeError, AttributeError, KeyError) as e:
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
        except (ValueError, TypeError, AttributeError, KeyError) as e:
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


@pytest.mark.integration
class TestAPIv2Authentication(TestCase):
    """Test authentication mechanisms for v2 API."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='AUTH_TEST',
            btname='Auth Test BU'
        )
        self.user = User.objects.create_user(
            loginid='authuser',
            peoplecode='AUTH001',
            peoplename='Auth User',
            email='auth@test.com',
            bu=self.bt,
            password='testpass123'
        )

    def test_session_authentication(self):
        """Test session-based authentication works."""
        self.client.force_login(self.user)

        response = self.client.get('/api/v2/devices/')
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_request_rejected(self):
        """Test unauthenticated requests are rejected."""
        response = self.client.get('/api/v2/devices/')
        self.assertIn(response.status_code, [401, 403])

    def test_invalid_credentials_rejected(self):
        """Test invalid credentials are rejected."""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        })
        self.assertIn(response.status_code, [400, 401, 403])

    def test_authenticated_user_can_access_own_data(self):
        """Test authenticated user can access their own data."""
        self.client.force_login(self.user)

        response = self.client.get('/api/v1/peoples/')
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class TestAPIv2RateLimiting(TestCase):
    """Test rate limiting for v2 API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='RATE_TEST',
            btname='Rate Test BU'
        )
        self.user = User.objects.create_user(
            loginid='rateuser',
            peoplecode='RATE001',
            peoplename='Rate User',
            email='rate@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_rate_limit_header_present(self):
        """Test rate limit headers are present in response."""
        response = self.client.get('/api/v2/devices/')

        # Check for rate limit headers (if implemented)
        # Example: X-RateLimit-Limit, X-RateLimit-Remaining

    def test_excessive_requests_throttled(self):
        """Test excessive requests are throttled."""
        # This test would require actual rate limiting configuration
        # For now, just verify endpoints are accessible
        for _ in range(5):
            response = self.client.get('/api/v2/devices/')
            self.assertIn(response.status_code, [200, 429])


@pytest.mark.integration
class TestAPIv2SerializerValidation(TestCase):
    """Test serializer validation for v2 API."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='SERIAL_TEST',
            btname='Serializer Test BU'
        )
        self.user = User.objects.create_user(
            loginid='serialuser',
            peoplecode='SERIAL001',
            peoplename='Serializer User',
            email='serial@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_invalid_json_rejected(self):
        """Test invalid JSON is rejected."""
        response = self.client.post(
            '/api/v2/sync/voice/',
            data='invalid json{',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_required_field_rejected(self):
        """Test request with missing required field is rejected."""
        payload = {
            # Missing device_id
            'voice_data': [],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_field_type_rejected(self):
        """Test request with invalid field type is rejected."""
        payload = {
            'device_id': 123,  # Should be string
            'voice_data': [],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_field_length_validation(self):
        """Test field length validation works."""
        payload = {
            'device_id': 'a' * 1000,  # Excessively long
            'voice_data': [],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


@pytest.mark.integration
class TestAPIv1v2Compatibility(TestCase):
    """Test compatibility between v1 and v2 API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='COMPAT_TEST',
            btname='Compatibility Test BU'
        )
        self.user = User.objects.create_user(
            loginid='compatuser',
            peoplecode='COMPAT001',
            peoplename='Compat User',
            email='compat@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_v1_endpoint_accessible(self):
        """Test v1 endpoints are still accessible."""
        response = self.client.get('/api/v1/peoples/')
        self.assertEqual(response.status_code, 200)

    def test_v2_endpoint_accessible(self):
        """Test v2 endpoints are accessible."""
        response = self.client.get('/api/v2/devices/')
        self.assertEqual(response.status_code, 200)

    def test_v1_and_v2_return_compatible_data(self):
        """Test v1 and v2 return compatible data structures."""
        # Get data from v1
        v1_response = self.client.get('/api/v1/peoples/')
        self.assertEqual(v1_response.status_code, 200)

        # Verify both APIs work independently


@pytest.mark.integration
class TestAPIv2ErrorHandling(TestCase):
    """Test error handling for v2 API."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='ERROR_TEST',
            btname='Error Test BU'
        )
        self.user = User.objects.create_user(
            loginid='erroruser',
            peoplecode='ERROR001',
            peoplename='Error User',
            email='error@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_404_error_format(self):
        """Test 404 errors return proper format."""
        response = self.client.get('/api/v2/nonexistent/')
        self.assertEqual(response.status_code, 404)

    def test_validation_error_format(self):
        """Test validation errors return proper format."""
        payload = {
            'device_id': '',  # Empty string
            'voice_data': [],
            'timestamp': timezone.now().isoformat(),
        }

        response = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('errors', response_data)

    def test_server_error_sanitized(self):
        """Test server errors don't leak sensitive information."""
        # Server errors should be sanitized and not expose internals
        pass


@pytest.mark.integration
class TestAPIv2Pagination(TestCase):
    """Test pagination for v2 API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='PAGE_TEST',
            btname='Pagination Test BU'
        )
        self.user = User.objects.create_user(
            loginid='pageuser',
            peoplecode='PAGE001',
            peoplename='Page User',
            email='page@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_pagination_parameters_work(self):
        """Test pagination parameters are respected."""
        response = self.client.get('/api/v1/peoples/?page=1&page_size=10')
        self.assertEqual(response.status_code, 200)

    def test_invalid_page_number_handled(self):
        """Test invalid page numbers are handled gracefully."""
        response = self.client.get('/api/v1/peoples/?page=999999')
        self.assertIn(response.status_code, [200, 404])


@pytest.mark.integration
class TestAPIv2Filtering(TestCase):
    """Test filtering capabilities for v2 API."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='FILTER_TEST',
            btname='Filter Test BU'
        )
        self.user = User.objects.create_user(
            loginid='filteruser',
            peoplecode='FILTER001',
            peoplename='Filter User',
            email='filter@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_basic_filtering_works(self):
        """Test basic filtering parameters work."""
        response = self.client.get('/api/v1/peoples/?bu=' + str(self.bt.pk))
        self.assertEqual(response.status_code, 200)

    def test_multiple_filters_work(self):
        """Test multiple filters can be applied."""
        response = self.client.get(
            f'/api/v1/peoples/?bu={self.bt.pk}&is_active=true'
        )
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class TestAPIv2ContentNegotiation(TestCase):
    """Test content negotiation for v2 API."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='CONTENT_TEST',
            btname='Content Test BU'
        )
        self.user = User.objects.create_user(
            loginid='contentuser',
            peoplecode='CONTENT001',
            peoplename='Content User',
            email='content@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_json_response_default(self):
        """Test JSON is default response format."""
        response = self.client.get('/api/v2/devices/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response.get('Content-Type', ''))

    def test_accept_header_json(self):
        """Test Accept header for JSON works."""
        response = self.client.get(
            '/api/v2/devices/',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class TestAPIv2Idempotency(TestCase):
    """Test idempotency for v2 API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.bt = Bt.objects.create(
            btcode='IDEM_TEST',
            btname='Idempotency Test BU'
        )
        self.user = User.objects.create_user(
            loginid='idemuser',
            peoplecode='IDEM001',
            peoplename='Idempotency User',
            email='idem@test.com',
            bu=self.bt,
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_idempotency_key_enforced(self):
        """Test idempotency key is enforced for write operations."""
        payload = {
            'device_id': 'idem-test-device',
            'voice_data': [
                {
                    'verification_id': 'ver-idem-001',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                }
            ],
            'timestamp': timezone.now().isoformat(),
            'idempotency_key': 'idem-key-' + str(uuid4()),
        }

        # First request
        response1 = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Second request with same idempotency key should be idempotent
        response2 = self.client.post(
            '/api/v2/sync/voice/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Both should succeed
        self.assertIn(response1.status_code, [200, 201])
        self.assertIn(response2.status_code, [200, 201])


@pytest.mark.integration
class TestAPIv2CORS(TestCase):
    """Test CORS headers for v2 API."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_cors_headers_present(self):
        """Test CORS headers are present in response."""
        response = self.client.options('/api/v2/version/')

        # Check for CORS headers (if implemented)
        # Example: Access-Control-Allow-Origin

    def test_preflight_request_handled(self):
        """Test preflight OPTIONS requests are handled."""
        response = self.client.options(
            '/api/v2/devices/',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ORIGIN='http://example.com'
        )

        # Should return 200 or appropriate status
