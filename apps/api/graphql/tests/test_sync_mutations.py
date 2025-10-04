"""
Comprehensive Tests for GraphQL Sync Mutations

Tests all GraphQL sync functionality:
- Voice data sync
- Batch sync operations
- Conflict resolution
- Idempotency
- Error handling
- Rate limiting
- Security validation

Follows .claude/rules.md:
- Rule #1: GraphQL security protection testing
- Rule #11: Specific exception handling testing
"""

import pytest
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from apps.core.models.sync_idempotency import SyncIdempotencyRecord
from apps.core.models.sync_conflict_policy import TenantConflictPolicy, ConflictResolutionLog
from apps.tenants.models import Tenant
from apps.voice_recognition.models import VoiceVerificationLog

User = get_user_model()


@pytest.mark.django_db
class TestGraphQLSyncVoiceDataMutation(TestCase):
    """Test suite for syncVoiceData GraphQL mutation."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="graphqltest",
            password="GraphQLPass123!",
            email="graphql@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="GraphQL Test Tenant")

        self.client.force_login(self.user)

    def test_sync_voice_data_success(self):
        """Test successful voice data sync via GraphQL."""
        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                syncedItems
                failedItems
                serverTimestamp
                idempotencyKey
            }
        }
        '''

        variables = {
            'data': [{
                'verificationId': 'test-uuid-123',
                'timestamp': timezone.now().isoformat(),
                'verified': True,
                'confidenceScore': 0.95,
                'qualityScore': 0.88,
                'processingTimeMs': 150
            }],
            'idempotencyKey': 'test-idempotency-key-123',
            'deviceId': 'test-device-123'
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertIn('data', data)
        self.assertIn('syncVoiceData', data['data'])

        sync_result = data['data']['syncVoiceData']
        self.assertTrue(sync_result['success'])
        self.assertEqual(sync_result['syncedItems'], 1)
        self.assertEqual(sync_result['failedItems'], 0)

    def test_sync_voice_data_idempotency(self):
        """Test idempotency: duplicate requests return cached response."""
        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                syncedItems
                idempotencyKey
            }
        }
        '''

        idempotency_key = 'duplicate-test-key'

        variables = {
            'data': [{
                'verificationId': 'test-uuid-456',
                'timestamp': timezone.now().isoformat(),
                'verified': True
            }],
            'idempotencyKey': idempotency_key,
            'deviceId': 'test-device-456'
        }

        response1 = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        response2 = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data1 = json.loads(response1.content)['data']['syncVoiceData']
        data2 = json.loads(response2.content)['data']['syncVoiceData']

        self.assertEqual(data1['idempotencyKey'], idempotency_key)
        self.assertEqual(data2['idempotencyKey'], idempotency_key)
        self.assertEqual(data1['syncedItems'], data2['syncedItems'])

        voice_logs = VoiceVerificationLog.objects.filter(verification_id='test-uuid-456')
        self.assertEqual(voice_logs.count(), 1)

    def test_sync_voice_data_validation_error(self):
        """Test validation error handling."""
        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                syncedItems
                failedItems
                errors {
                    code
                    message
                }
            }
        }
        '''

        variables = {
            'data': [],
            'idempotencyKey': 'validation-error-test',
            'deviceId': 'test-device-789'
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data = json.loads(response.content)['data']['syncVoiceData']

        self.assertFalse(data['success'])
        self.assertEqual(data['syncedItems'], 0)
        self.assertGreater(len(data['errors']), 0)
        self.assertEqual(data['errors'][0]['code'], 'VALIDATION_ERROR')

    def test_sync_voice_data_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()

        query = '''
        mutation {
            syncVoiceData(
                data: [{
                    verificationId: "test",
                    timestamp: "2025-09-28T12:00:00Z",
                    verified: true
                }],
                idempotencyKey: "unauth-test",
                deviceId: "device-unauth"
            ) {
                success
            }
        }
        '''

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query}),
            content_type='application/json'
        )

        data = json.loads(response.content)

        self.assertIn('errors', data)


@pytest.mark.django_db
class TestGraphQLSyncBatchMutation(TestCase):
    """Test suite for syncBatch GraphQL mutation."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="batchtest",
            password="BatchPass123!",
            email="batch@example.com"
        )
        self.client.force_login(self.user)

    def test_sync_batch_success(self):
        """Test successful batch sync via GraphQL."""
        query = '''
        mutation SyncBatch($batch: SyncBatchInput!) {
            syncBatch(batch: $batch) {
                success
                voiceSyncResult {
                    syncedItems
                    failedItems
                }
                overallMetrics {
                    totalItems
                    syncedItems
                    failedItems
                    durationMs
                }
            }
        }
        '''

        variables = {
            'batch': {
                'idempotencyKey': 'batch-test-key',
                'deviceId': 'batch-device-123',
                'clientTimestamp': timezone.now().isoformat(),
                'voiceData': [{
                    'verificationId': 'batch-voice-1',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidenceScore': 0.92
                }],
                'behavioralData': [{
                    'sessionId': 'batch-session-1',
                    'events': [{'type': 'click', 'x': 100, 'y': 200}],
                    'durationMs': 5000
                }]
            }
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)['data']['syncBatch']

        self.assertTrue(data['success'])
        self.assertIsNotNone(data['voiceSyncResult'])
        self.assertGreater(data['overallMetrics']['totalItems'], 0)

    def test_sync_batch_empty_data(self):
        """Test batch sync with no data."""
        query = '''
        mutation SyncBatch($batch: SyncBatchInput!) {
            syncBatch(batch: $batch) {
                success
                overallMetrics {
                    totalItems
                    syncedItems
                }
            }
        }
        '''

        variables = {
            'batch': {
                'idempotencyKey': 'empty-batch-key',
                'deviceId': 'empty-device',
                'clientTimestamp': timezone.now().isoformat()
            }
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data = json.loads(response.content)['data']['syncBatch']

        self.assertEqual(data['overallMetrics']['totalItems'], 0)


@pytest.mark.django_db
class TestGraphQLConflictResolutionMutation(TestCase):
    """Test suite for resolveConflict GraphQL mutation."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="conflicttest",
            password="ConflictPass123!",
            email="conflict@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="Conflict Test Tenant")
        self.client.force_login(self.user)

        self.conflict = ConflictResolutionLog.objects.create(
            mobile_id='conflict-uuid',
            domain='journal',
            server_version=5,
            client_version=4,
            resolution_strategy='manual',
            resolution_result='manual_required',
            tenant=self.tenant,
            user=self.user
        )

    def test_resolve_conflict_success(self):
        """Test successful conflict resolution via GraphQL."""
        query = '''
        mutation ResolveConflict($resolution: ConflictResolutionInput!) {
            resolveConflict(resolution: $resolution) {
                success
                conflictId
                resolutionResult
                message
            }
        }
        '''

        variables = {
            'resolution': {
                'conflictId': str(self.conflict.id),
                'resolutionStrategy': 'CLIENT_WINS',
                'chosenVersion': 'client',
                'mergeData': {'resolved_data': 'client_version'},
                'notes': 'Resolved via GraphQL'
            }
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data = json.loads(response.content)['data']['resolveConflict']

        self.assertTrue(data['success'])
        self.assertEqual(str(data['conflictId']), str(self.conflict.id))
        self.assertIsNotNone(data['resolutionResult'])

    def test_resolve_nonexistent_conflict(self):
        """Test resolving a conflict that doesn't exist."""
        query = '''
        mutation ResolveConflict($resolution: ConflictResolutionInput!) {
            resolveConflict(resolution: $resolution) {
                success
                conflictId
                error {
                    code
                    message
                }
            }
        }
        '''

        variables = {
            'resolution': {
                'conflictId': '99999',
                'resolutionStrategy': 'CLIENT_WINS',
                'chosenVersion': 'client',
                'mergeData': {}
            }
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data = json.loads(response.content)['data']['resolveConflict']

        self.assertFalse(data['success'])
        self.assertIsNotNone(data['error'])


@pytest.mark.security
@pytest.mark.django_db
class TestGraphQLSyncSecurity(TestCase):
    """Test security features of GraphQL sync mutations."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="securitytest",
            password="SecurityPass123!",
            email="security@example.com"
        )
        self.client.force_login(self.user)

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented."""
        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                errors {
                    code
                    message
                }
            }
        }
        '''

        variables = {
            'data': [{
                'verificationId': "'; DROP TABLE voice_verification_log;--",
                'timestamp': timezone.now().isoformat(),
                'verified': True
            }],
            'idempotencyKey': 'sql-injection-test',
            'deviceId': 'attack-device'
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(VoiceVerificationLog.objects.exists())

    def test_excessive_payload_size(self):
        """Test that excessively large payloads are rejected."""
        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                errors {
                    code
                }
            }
        }
        '''

        large_data = [{
            'verificationId': f'test-{i}',
            'timestamp': timezone.now().isoformat(),
            'verified': True
        } for i in range(2000)]

        variables = {
            'data': large_data,
            'idempotencyKey': 'large-payload-test',
            'deviceId': 'test-device'
        }

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        data = json.loads(response.content)['data']['syncVoiceData']

        self.assertFalse(data['success'])
        self.assertEqual(data['errors'][0]['code'], 'VALIDATION_ERROR')


@pytest.mark.django_db
class TestGraphQLSyncPerformance(TestCase):
    """Test performance of GraphQL sync mutations."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="perftest",
            password="PerfPass123!",
            email="perf@example.com"
        )
        self.client.force_login(self.user)

    def test_sync_latency(self):
        """Test that sync operations meet latency requirements."""
        import time

        query = '''
        mutation SyncVoiceData($data: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
            syncVoiceData(data: $data, idempotencyKey: $idempotencyKey, deviceId: $deviceId) {
                success
                metrics {
                    durationMs
                }
            }
        }
        '''

        variables = {
            'data': [{
                'verificationId': f'perf-test-{i}',
                'timestamp': timezone.now().isoformat(),
                'verified': True
            } for i in range(10)],
            'idempotencyKey': f'perf-test-{time.time()}',
            'deviceId': 'perf-device'
        }

        start_time = time.time()

        response = self.client.post(
            '/api/graphql/',
            json.dumps({'query': query, 'variables': variables}),
            content_type='application/json'
        )

        latency_ms = (time.time() - start_time) * 1000

        data = json.loads(response.content)['data']['syncVoiceData']

        self.assertTrue(data['success'])
        self.assertLess(latency_ms, 500)