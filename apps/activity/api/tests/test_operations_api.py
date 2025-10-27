"""
Operations API Tests

Tests for CRUD operations, cron scheduling, and jobneed generation.

Compliance with .claude/rules.md:
- Comprehensive test coverage
- Specific assertions
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.peoples.models import People
from apps.activity.models import Job, Jobneed
from datetime import datetime, timedelta, timezone as dt_timezone


@pytest.mark.django_db
class TestJobViewSet:
    """Test cases for JobViewSet."""

    def setup_method(self):
        """Set up test client and data."""
        self.client = APIClient()

        self.user = People.objects.create_user(
            username='testuser@example.com',
            password='Test123!',
            client_id=1,
            bu_id=1
        )

        self.job = Job.objects.create(
            job_number='JOB-001',
            job_type='maintenance',
            status='pending',
            client_id=1,
            bu_id=1,
            assigned_to=self.user,
            created_by=self.user,
            scheduled_date=datetime.now(dt_timezone.utc)
        )

        self.list_url = reverse('api_v1:operations:jobs-list')

    def test_list_jobs_authenticated(self):
        """Test listing jobs requires authentication."""
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_jobs_success(self):
        """Test listing jobs with authentication."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_create_job_success(self):
        """Test creating new job."""
        self.client.force_authenticate(user=self.user)

        data = {
            'job_number': 'JOB-002',
            'job_type': 'inspection',
            'status': 'pending',
            'assigned_to': self.user.id,
            'scheduled_date': (datetime.now(dt_timezone.utc) + timedelta(days=1)).isoformat()
        }

        response = self.client.post(self.list_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Job.objects.filter(job_number='JOB-002').exists()

    def test_retrieve_job_detail(self):
        """Test retrieving specific job."""
        self.client.force_authenticate(user=self.user)

        url = reverse('api_v1:operations:jobs-detail', kwargs={'pk': self.job.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['job_number'] == 'JOB-001'

    def test_complete_job_action(self):
        """Test marking job as complete."""
        self.client.force_authenticate(user=self.user)

        url = reverse('api_v1:operations:jobs-complete', kwargs={'pk': self.job.pk})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        self.job.refresh_from_db()
        assert self.job.status == 'completed'
        assert self.job.completed_date is not None


@pytest.mark.django_db
class TestJobneedViewSet:
    """Test cases for JobneedViewSet."""

    def setup_method(self):
        """Set up test client and data."""
        self.client = APIClient()

        self.user = People.objects.create_user(
            username='testuser@example.com',
            password='Test123!',
            client_id=1,
            bu_id=1
        )

        self.jobneed = Jobneed.objects.create(
            jobneed_number='JN-001',
            jobneed_type='ppm',
            status='active',
            client_id=1,
            bu_id=1,
            created_by=self.user,
            frequency='weekly',
            is_active=True
        )

        self.list_url = reverse('api_v1:operations:jobneeds-list')

    def test_list_jobneeds_success(self):
        """Test listing jobneeds."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_create_jobneed_success(self):
        """Test creating new jobneed."""
        self.client.force_authenticate(user=self.user)

        data = {
            'jobneed_number': 'JN-002',
            'jobneed_type': 'inspection',
            'status': 'active',
            'frequency': 'monthly',
            'is_active': True
        }

        response = self.client.post(self.list_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_update_cron_schedule(self):
        """Test updating jobneed cron schedule."""
        self.client.force_authenticate(user=self.user)

        url = reverse('api_v1:operations:jobneeds-schedule', kwargs={'pk': self.jobneed.pk})
        data = {
            'cron_expression': '0 9 * * 1',  # Every Monday at 9 AM
            'frequency': 'weekly'
        }

        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK

        self.jobneed.refresh_from_db()
        assert self.jobneed.cron_expression == '0 9 * * 1'
        assert self.jobneed.next_generation_date is not None

    def test_invalid_cron_expression(self):
        """Test invalid cron expression is rejected."""
        self.client.force_authenticate(user=self.user)

        url = reverse('api_v1:operations:jobneeds-schedule', kwargs={'pk': self.jobneed.pk})
        data = {
            'cron_expression': 'invalid cron',
        }

        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


__all__ = [
    'TestJobViewSet',
    'TestJobneedViewSet',
]
