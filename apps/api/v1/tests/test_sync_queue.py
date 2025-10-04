"""
Comprehensive Tests for Offline Queue Management

Following .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
import json
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.api.v1.views.sync_queue_views import (
    QueueStatusAPIView,
    PartialSyncAPIView,
    OptimalSyncTimeAPIView
)
from apps.core.models.sync_idempotency import SyncIdempotencyKey
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.unit
class TestQueueStatusView(TestCase):
    """Test queue status API endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

        for i in range(15):
            SyncIdempotencyKey.objects.create(
                key=f"key-{i}",
                user=self.user,
                status='pending',
                metadata={'priority': 'high' if i < 5 else 'low'}
            )

    def test_queue_status_returns_correct_counts(self):
        """Test queue status endpoint returns accurate counts."""
        request = self.factory.get('/api/v1/sync/queue-status')
        request.user = self.user

        view = QueueStatusAPIView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['pending_items'], 15)
        self.assertEqual(data['high_priority'], 5)
        self.assertIsInstance(data['estimated_sync_time_sec'], int)
        self.assertIsInstance(data['queue_healthy'], bool)

    def test_queue_healthy_threshold(self):
        """Test queue health status calculation."""
        request = self.factory.get('/api/v1/sync/queue-status')
        request.user = self.user

        view = QueueStatusAPIView.as_view()
        response = view(request)

        data = json.loads(response.content)

        self.assertTrue(data['queue_healthy'])


@pytest.mark.unit
class TestPartialSyncView(TestCase):
    """Test partial sync API endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

        for i in range(20):
            SyncIdempotencyKey.objects.create(
                key=f"key-{i}",
                user=self.user,
                status='pending',
                metadata={'priority': 'high'}
            )

    def test_partial_sync_processes_limited_items(self):
        """Test partial sync respects max_items limit."""
        body = json.dumps({
            'priority': 'high',
            'max_items': 10,
            'network_quality': 'good'
        })

        request = self.factory.post(
            '/api/v1/sync/partial',
            data=body,
            content_type='application/json'
        )
        request.user = self.user

        view = PartialSyncAPIView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data['synced_items']), 10)
        self.assertEqual(data['remaining'], 10)

    def test_partial_sync_updates_item_status(self):
        """Test partial sync marks items as processed."""
        body = json.dumps({
            'priority': 'high',
            'max_items': 5
        })

        request = self.factory.post(
            '/api/v1/sync/partial',
            data=body,
            content_type='application/json'
        )
        request.user = self.user

        view = PartialSyncAPIView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

        processed_count = SyncIdempotencyKey.objects.filter(
            user=self.user,
            status='processed'
        ).count()

        self.assertEqual(processed_count, 5)


@pytest.mark.unit
class TestOptimalSyncTimeView(TestCase):
    """Test optimal sync time recommendation endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

    def test_optimal_time_recommendation_low_load(self):
        """Test recommendation with low server load."""
        for i in range(100):
            SyncIdempotencyKey.objects.create(
                key=f"key-{i}",
                user=self.user,
                status='pending'
            )

        request = self.factory.get('/api/v1/sync/optimal-time')
        request.user = self.user

        view = OptimalSyncTimeAPIView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn('recommendation', data)
        self.assertIn('server_load', data)
        self.assertEqual(data['server_load'], 'low')

    def test_optimal_time_recommendation_high_load(self):
        """Test recommendation with high server load."""
        for i in range(1500):
            SyncIdempotencyKey.objects.create(
                key=f"key-{i}",
                user=self.user,
                status='pending'
            )

        request = self.factory.get('/api/v1/sync/optimal-time')
        request.user = self.user

        view = OptimalSyncTimeAPIView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['server_load'], 'high')
        self.assertEqual(data['recommendation'], 'sync_in_30min')


@pytest.mark.integration
class TestQueueManagementIntegration(TestCase):
    """Integration tests for queue management."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

    def test_end_to_end_queue_workflow(self):
        """Test complete queue management workflow."""
        for i in range(50):
            SyncIdempotencyKey.objects.create(
                key=f"key-{i}",
                user=self.user,
                status='pending',
                metadata={'priority': 'high' if i < 20 else 'low'}
            )

        request = self.factory.get('/api/v1/sync/queue-status')
        request.user = self.user
        status_view = QueueStatusAPIView.as_view()
        status_response = status_view(request)
        status_data = json.loads(status_response.content)

        self.assertEqual(status_data['pending_items'], 50)

        body = json.dumps({'max_items': 10})
        sync_request = self.factory.post(
            '/api/v1/sync/partial',
            data=body,
            content_type='application/json'
        )
        sync_request.user = self.user
        partial_view = PartialSyncAPIView.as_view()
        partial_response = partial_view(sync_request)
        partial_data = json.loads(partial_response.content)

        self.assertEqual(len(partial_data['synced_items']), 10)
        self.assertEqual(partial_data['remaining'], 40)

        optimal_request = self.factory.get('/api/v1/sync/optimal-time')
        optimal_request.user = self.user
        optimal_view = OptimalSyncTimeAPIView.as_view()
        optimal_response = optimal_view(optimal_request)
        optimal_data = json.loads(optimal_response.content)

        self.assertIn('recommendation', optimal_data)