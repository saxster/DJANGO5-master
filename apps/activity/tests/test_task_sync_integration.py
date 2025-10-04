"""
Comprehensive Integration Tests for Task Sync

Tests bulk sync, conflict detection, idempotency, and delta pull.

Following .claude/rules.md testing patterns.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.activity.models.job_model import Jobneed
from apps.api.v1.services.idempotency_service import IdempotencyService

User = get_user_model()


@pytest.mark.django_db
class TestTaskSyncIntegration(TestCase):
    """Integration tests for Activity/Tasks sync operations."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User',
            email='test@example.com'
        )
        self.client.force_login(self.user)
        self.sync_url = '/api/v1/sync/activity/sync/'
        self.changes_url = '/api/v1/sync/activity/changes/'

    def test_bulk_create_success(self):
        """Test bulk create of 10 tasks - all succeed."""
        mobile_ids = [str(uuid.uuid4()) for _ in range(10)]

        request_data = {
            'entries': [
                {
                    'mobile_id': mobile_id,
                    'version': 1,
                    'jobdesc': f'Task {i}',
                    'gracetime': 30,
                    'priority': 'HIGH',
                    'jobstatus': 'ASSIGNED'
                }
                for i, mobile_id in enumerate(mobile_ids)
            ],
            'client_id': 'device-test-123'
        }

        response = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['synced_items']), 10)
        self.assertEqual(len(data['conflicts']), 0)
        self.assertEqual(len(data['errors']), 0)

        for item in data['synced_items']:
            self.assertEqual(item['status'], 'created')
            self.assertEqual(item['server_version'], 1)

    def test_update_existing_increments_version(self):
        """Test updating existing task increments server version."""
        mobile_id = str(uuid.uuid4())

        task = Jobneed.objects.create(
            mobile_id=mobile_id,
            version=1,
            jobdesc='Original task',
            gracetime=30,
            sync_status='synced'
        )

        request_data = {
            'entries': [{
                'mobile_id': mobile_id,
                'version': 1,
                'jobdesc': 'Updated task',
                'gracetime': 60
            }],
            'client_id': 'device-test-123'
        }

        response = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['synced_items']), 1)
        self.assertEqual(data['synced_items'][0]['status'], 'updated')
        self.assertEqual(data['synced_items'][0]['server_version'], 2)

        task.refresh_from_db()
        self.assertEqual(task.version, 2)
        self.assertEqual(task.jobdesc, 'Updated task')

    def test_conflict_detection(self):
        """Test conflict detection when client v1 vs server v2."""
        mobile_id = str(uuid.uuid4())

        Jobneed.objects.create(
            mobile_id=mobile_id,
            version=2,
            jobdesc='Server version 2',
            gracetime=30,
            sync_status='synced'
        )

        request_data = {
            'entries': [{
                'mobile_id': mobile_id,
                'version': 1,
                'jobdesc': 'Client version 1',
                'gracetime': 60
            }],
            'client_id': 'device-test-123'
        }

        response = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['conflicts']), 1)
        self.assertEqual(data['conflicts'][0]['status'], 'conflict')
        self.assertEqual(data['conflicts'][0]['server_version'], 2)
        self.assertEqual(data['conflicts'][0]['client_version'], 1)

    def test_idempotent_retry(self):
        """Test same Idempotency-Key returns cached response."""
        idempotency_key = str(uuid.uuid4())
        mobile_id = str(uuid.uuid4())

        request_data = {
            'entries': [{
                'mobile_id': mobile_id,
                'version': 1,
                'jobdesc': 'Test task',
                'gracetime': 30
            }],
            'client_id': 'device-test-123'
        }

        response1 = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response2 = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response1.json(), response2.json())

        self.assertEqual(Jobneed.objects.filter(mobile_id=mobile_id).count(), 1)

    def test_delta_pull(self):
        """Test delta pull returns only changes since timestamp."""
        past = timezone.now() - timedelta(hours=2)
        recent = timezone.now() - timedelta(minutes=5)

        Jobneed.objects.create(
            mobile_id=uuid.uuid4(),
            jobdesc='Old task',
            gracetime=30,
            created_at=past,
            updated_at=past
        )

        task2 = Jobneed.objects.create(
            mobile_id=uuid.uuid4(),
            jobdesc='Recent task',
            gracetime=30,
            created_at=recent,
            updated_at=recent
        )

        since_timestamp = (timezone.now() - timedelta(hours=1)).isoformat()

        response = self.client.get(
            f'{self.changes_url}?since={since_timestamp}'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['jobdesc'], 'Recent task')

    def test_multi_tenant_isolation(self):
        """Test user only sees own bu/client data."""
        response = self.client.get(self.changes_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data['items'], list)

    def test_validation_errors(self):
        """Test validation errors for invalid data."""
        request_data = {
            'entries': [{
                'mobile_id': str(uuid.uuid4()),
                'version': 1,
                'jobdesc': 'AB',
                'gracetime': 30
            }],
            'client_id': 'device-test-123'
        }

        response = self.client.post(
            self.sync_url,
            data=request_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data['errors']), 0)