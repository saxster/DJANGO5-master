"""
Comprehensive Dashboard Integration Tests

Tests all dashboard views and API endpoints created in Phase 3.3:
- Main task dashboard
- Idempotency analysis
- Schedule conflicts
- DLQ management
- Failure taxonomy dashboard
- Retry policy dashboard
- API endpoints (DLQ status, circuit breakers, failure trends)

Coverage:
- View permissions (staff_member_required)
- Context data validation
- Filtering and pagination
- JSON response formats
- Error handling
- URL routing
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from apps.core.models.task_failure_record import TaskFailureRecord
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from background_tasks.dead_letter_queue import DeadLetterQueueService

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def admin_user(db):
    """Create admin user for testing."""
    return User.objects.create_superuser(
        loginid='admin',
        email='admin@test.com',
        password='testpass123',
        peoplename='Admin User'
    )


@pytest.fixture
def regular_user(db):
    """Create regular (non-staff) user for testing."""
    return User.objects.create_user(
        loginid='regular',
        email='regular@test.com',
        password='testpass123',
        peoplename='Regular User',
        is_staff=False
    )


@pytest.fixture
def staff_user(db):
    """Create staff user for testing."""
    return User.objects.create_user(
        loginid='staff',
        email='staff@test.com',
        password='testpass123',
        peoplename='Staff User',
        is_staff=True
    )


@pytest.fixture
def authenticated_client(client, staff_user):
    """Client authenticated as staff user."""
    client.force_login(staff_user)
    return client


@pytest.fixture
def sample_dlq_records(db):
    """Create sample DLQ records for testing."""
    records = []
    
    # PENDING task
    records.append(TaskFailureRecord.objects.create(
        task_id='pending-task-1',
        task_name='background_tasks.email_tasks.send_notification_email',
        task_args=['user@example.com'],
        task_kwargs={'subject': 'Test'},
        exception_type='SMTPException',
        exception_message='Connection timeout',
        failure_type='TRANSIENT_NETWORK',
        status='PENDING',
        retry_count=2,
        max_retries=5
    ))
    
    # RETRYING task
    records.append(TaskFailureRecord.objects.create(
        task_id='retrying-task-1',
        task_name='background_tasks.job_tasks.auto_close_jobs',
        task_args=[],
        task_kwargs={},
        exception_type='OperationalError',
        exception_message='Database connection lost',
        failure_type='TRANSIENT_DATABASE',
        status='RETRYING',
        retry_count=1,
        max_retries=3,
        next_retry_at=timezone.now() + timedelta(minutes=5)
    ))
    
    # RESOLVED task
    records.append(TaskFailureRecord.objects.create(
        task_id='resolved-task-1',
        task_name='background_tasks.report_tasks.create_scheduled_reports',
        task_args=[123],
        task_kwargs={'format': 'pdf'},
        exception_type='ValueError',
        exception_message='Invalid report ID',
        failure_type='PERMANENT_INVALID_INPUT',
        status='RESOLVED',
        retry_count=3,
        max_retries=3,
        resolved_at=timezone.now()
    ))
    
    # ABANDONED task
    records.append(TaskFailureRecord.objects.create(
        task_id='abandoned-task-1',
        task_name='background_tasks.maintenance_tasks.cleanup_old_files',
        task_args=[],
        task_kwargs={},
        exception_type='PermissionError',
        exception_message='Access denied',
        failure_type='CONFIGURATION_PERMISSIONS',
        status='ABANDONED',
        retry_count=5,
        max_retries=5
    ))
    
    return records


# ============================================================================
# Test Main Task Dashboard
# ============================================================================

@pytest.mark.django_db
class TestTaskDashboard:
    """Test main task monitoring dashboard."""
    
    def test_dashboard_requires_staff(self, client, regular_user):
        """Test that regular users cannot access dashboard."""
        client.force_login(regular_user)
        response = client.get(reverse('task_dashboard'))
        
        # Should redirect to login
        assert response.status_code == 302
    
    def test_dashboard_accessible_by_staff(self, authenticated_client):
        """Test that staff users can access dashboard."""
        response = authenticated_client.get(reverse('task_dashboard'))
        
        assert response.status_code == 200
        assert 'task_monitoring/task_dashboard.html' in [t.name for t in response.templates]
    
    @patch('apps.core.views.task_monitoring_dashboard.UniversalIdempotencyService')
    def test_dashboard_idempotency_stats(self, mock_service, authenticated_client):
        """Test idempotency statistics in dashboard."""
        # Mock idempotency stats
        mock_service.return_value.get_statistics.return_value = {
            'hit_rate_24h': 2.5,
            'total_checks_24h': 1000,
            'cache_hits_24h': 25,
            'duplicate_prevented': 25
        }
        
        response = authenticated_client.get(reverse('task_dashboard'))
        
        assert response.status_code == 200
        assert 'idempotency' in response.context
        assert response.context['idempotency']['hit_rate'] == 2.5
    
    def test_dashboard_dlq_stats(self, authenticated_client, sample_dlq_records):
        """Test DLQ statistics in dashboard."""
        response = authenticated_client.get(reverse('task_dashboard'))
        
        assert response.status_code == 200
        assert 'dlq_stats' in response.context
        
        stats = response.context['dlq_stats']
        assert stats['total'] == 4
        assert stats['pending'] == 1
        assert stats['retrying'] == 1
        assert stats['resolved'] == 1
        assert stats['abandoned'] == 1
    
    @patch('apps.core.views.task_monitoring_dashboard.app')
    def test_dashboard_active_tasks(self, mock_celery_app, authenticated_client):
        """Test active task statistics."""
        # Mock Celery inspect
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {
            'worker1': [
                {'name': 'task1', 'id': 'id1'},
                {'name': 'task2', 'id': 'id2'}
            ],
            'worker2': [
                {'name': 'task3', 'id': 'id3'}
            ]
        }
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        response = authenticated_client.get(reverse('task_dashboard'))
        
        assert response.status_code == 200
        assert 'active_tasks' in response.context
        assert response.context['active_tasks']['total'] == 3


# ============================================================================
# Test Idempotency Analysis Dashboard
# ============================================================================

@pytest.mark.django_db
class TestIdempotencyAnalysis:
    """Test idempotency analysis dashboard."""
    
    def test_idempotency_analysis_requires_staff(self, client, regular_user):
        """Test permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('idempotency_analysis'))
        
        assert response.status_code == 302
    
    @patch('apps.core.views.task_monitoring_dashboard.UniversalIdempotencyService')
    def test_idempotency_analysis_statistics(self, mock_service, authenticated_client):
        """Test idempotency statistics rendering."""
        mock_service.return_value.get_statistics.return_value = {
            'hit_rate_24h': 1.2,
            'total_checks_24h': 5000,
            'cache_hits_24h': 60,
            'duplicate_prevented': 60,
            'cache_hit_rate': 98.5
        }
        
        response = authenticated_client.get(reverse('idempotency_analysis'))
        
        assert response.status_code == 200
        assert 'statistics' in response.context
        assert response.context['statistics']['hit_rate_24h'] == 1.2
        assert response.context['statistics']['total_checks_24h'] == 5000
    
    @patch('apps.core.views.task_monitoring_dashboard.UniversalIdempotencyService')
    def test_idempotency_analysis_by_task(self, mock_service, authenticated_client):
        """Test task-level breakdown."""
        mock_service.return_value.get_task_breakdown.return_value = [
            {'task_name': 'auto_close_jobs', 'hit_count': 15, 'check_count': 1000},
            {'task_name': 'send_notification_email', 'hit_count': 10, 'check_count': 2000},
        ]
        
        response = authenticated_client.get(reverse('idempotency_analysis'))
        
        assert response.status_code == 200
        assert 'task_breakdown' in response.context
        assert len(response.context['task_breakdown']) == 2


# ============================================================================
# Test Schedule Conflicts Dashboard
# ============================================================================

@pytest.mark.django_db
class TestScheduleConflicts:
    """Test schedule conflicts dashboard."""
    
    def test_schedule_conflicts_requires_staff(self, client, regular_user):
        """Test permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('schedule_conflicts'))
        
        assert response.status_code == 302
    
    @patch('apps.core.views.task_monitoring_dashboard.ScheduleCoordinator')
    def test_schedule_health_score(self, mock_coordinator, authenticated_client):
        """Test schedule health score calculation."""
        mock_coordinator.return_value.calculate_health_score.return_value = {
            'score': 85,
            'grade': 'B',
            'issues': ['2 hotspots detected']
        }
        
        response = authenticated_client.get(reverse('schedule_conflicts'))
        
        assert response.status_code == 200
        assert 'health_score' in response.context
        assert response.context['health_score']['score'] == 85
    
    @patch('apps.core.views.task_monitoring_dashboard.ScheduleCoordinator')
    def test_schedule_hotspots(self, mock_coordinator, authenticated_client):
        """Test hotspot detection."""
        mock_coordinator.return_value.detect_hotspots.return_value = [
            {
                'time_slot': '02:00',
                'task_count': 15,
                'worker_capacity': 20,
                'utilization': 75
            }
        ]
        
        response = authenticated_client.get(reverse('schedule_conflicts'))
        
        assert response.status_code == 200
        assert 'hotspots' in response.context
        assert len(response.context['hotspots']) == 1


# ============================================================================
# Test DLQ Management Dashboard
# ============================================================================

@pytest.mark.django_db
class TestDLQManagement:
    """Test DLQ management dashboard."""
    
    def test_dlq_management_requires_staff(self, client, regular_user):
        """Test permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('dlq_management'))
        
        assert response.status_code == 302
    
    def test_dlq_management_lists_tasks(self, authenticated_client, sample_dlq_records):
        """Test DLQ task listing."""
        response = authenticated_client.get(reverse('dlq_management'))
        
        assert response.status_code == 200
        assert 'tasks' in response.context
        assert response.context['tasks'].count() == 4
    
    def test_dlq_management_status_filter(self, authenticated_client, sample_dlq_records):
        """Test filtering by status."""
        response = authenticated_client.get(reverse('dlq_management') + '?status=PENDING')
        
        assert response.status_code == 200
        assert 'tasks' in response.context
        assert response.context['tasks'].count() == 1
        assert response.context['tasks'][0].status == 'PENDING'
    
    def test_dlq_management_failure_type_filter(self, authenticated_client, sample_dlq_records):
        """Test filtering by failure type."""
        response = authenticated_client.get(
            reverse('dlq_management') + '?failure_type=TRANSIENT_NETWORK'
        )
        
        assert response.status_code == 200
        assert response.context['tasks'].count() == 1
        assert response.context['tasks'][0].failure_type == 'TRANSIENT_NETWORK'
    
    def test_dlq_management_pagination(self, authenticated_client, db):
        """Test pagination with many records."""
        # Create 25 records
        for i in range(25):
            TaskFailureRecord.objects.create(
                task_id=f'task-{i}',
                task_name=f'test_task_{i}',
                task_args=[],
                task_kwargs={},
                exception_type='Exception',
                exception_message=f'Error {i}',
                failure_type='UNKNOWN',
                status='PENDING'
            )
        
        response = authenticated_client.get(reverse('dlq_management'))
        
        assert response.status_code == 200
        assert 'tasks' in response.context
        # Default page size is 20
        assert response.context['tasks'].count() == 20
        
        # Test page 2
        response = authenticated_client.get(reverse('dlq_management') + '?page=2')
        assert response.status_code == 200
        assert response.context['tasks'].count() == 5


# ============================================================================
# Test Failure Taxonomy Dashboard
# ============================================================================

@pytest.mark.django_db
class TestFailureTaxonomyDashboard:
    """Test failure taxonomy dashboard."""
    
    def test_failure_taxonomy_requires_staff(self, client, regular_user):
        """Test permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('failure_taxonomy_dashboard'))
        
        assert response.status_code == 302
    
    def test_failure_taxonomy_distribution(self, authenticated_client, sample_dlq_records):
        """Test failure type distribution."""
        response = authenticated_client.get(reverse('failure_taxonomy_dashboard'))
        
        assert response.status_code == 200
        assert 'failure_distribution' in response.context
        
        distribution = response.context['failure_distribution']
        assert 'TRANSIENT_NETWORK' in [f['failure_type'] for f in distribution]
        assert 'TRANSIENT_DATABASE' in [f['failure_type'] for f in distribution]
    
    def test_failure_taxonomy_trends(self, authenticated_client, db):
        """Test failure trends over time."""
        # Create records across different time periods
        now = timezone.now()
        
        for hours_ago in [1, 6, 12, 24]:
            TaskFailureRecord.objects.create(
                task_id=f'task-{hours_ago}h',
                task_name='test_task',
                task_args=[],
                task_kwargs={},
                exception_type='Exception',
                exception_message='Error',
                failure_type='TRANSIENT_NETWORK',
                status='PENDING',
                first_failed_at=now - timedelta(hours=hours_ago)
            )
        
        response = authenticated_client.get(reverse('failure_taxonomy_dashboard'))
        
        assert response.status_code == 200
        assert 'failure_trends' in response.context


# ============================================================================
# Test Retry Policy Dashboard
# ============================================================================

@pytest.mark.django_db
class TestRetryPolicyDashboard:
    """Test retry policy dashboard."""
    
    def test_retry_policy_requires_staff(self, client, regular_user):
        """Test permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('retry_policy_dashboard'))
        
        assert response.status_code == 302
    
    @patch('apps.core.views.task_monitoring_dashboard.retry_engine')
    def test_retry_statistics(self, mock_engine, authenticated_client):
        """Test retry statistics."""
        mock_engine.get_statistics.return_value = {
            'total_retries': 150,
            'successful_retries': 120,
            'failed_retries': 30,
            'success_rate': 80.0
        }
        
        response = authenticated_client.get(reverse('retry_policy_dashboard'))
        
        assert response.status_code == 200
        assert 'retry_stats' in response.context
        assert response.context['retry_stats']['success_rate'] == 80.0
    
    def test_retry_policy_by_failure_type(self, authenticated_client, sample_dlq_records):
        """Test retry success rates by failure type."""
        response = authenticated_client.get(reverse('retry_policy_dashboard'))
        
        assert response.status_code == 200
        assert 'retry_by_failure_type' in response.context


# ============================================================================
# Test API Endpoints
# ============================================================================

@pytest.mark.django_db
class TestAPIEndpoints:
    """Test JSON API endpoints."""
    
    def test_api_dlq_status_requires_staff(self, client, regular_user):
        """Test API permission requirement."""
        client.force_login(regular_user)
        response = client.get(reverse('api_dlq_status'))
        
        assert response.status_code == 302
    
    def test_api_dlq_status_json_response(self, authenticated_client, sample_dlq_records):
        """Test DLQ status API returns valid JSON."""
        response = authenticated_client.get(reverse('api_dlq_status'))
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        
        data = json.loads(response.content)
        assert 'total' in data
        assert 'pending' in data
        assert 'retrying' in data
        assert data['total'] == 4
        assert data['pending'] == 1
    
    @patch('apps.core.views.task_monitoring_dashboard.retry_engine')
    def test_api_circuit_breakers_status(self, mock_engine, authenticated_client):
        """Test circuit breaker status API."""
        mock_engine.get_circuit_breaker_status.return_value = {
            'external_api': {'state': 'CLOSED', 'failure_count': 0},
            'email_service': {'state': 'OPEN', 'failure_count': 5}
        }
        
        response = authenticated_client.get(reverse('api_circuit_breakers'))
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'external_api' in data
        assert data['email_service']['state'] == 'OPEN'
    
    def test_api_failure_trends(self, authenticated_client, db):
        """Test failure trends API."""
        # Create records with timestamps
        now = timezone.now()
        for i in range(10):
            TaskFailureRecord.objects.create(
                task_id=f'task-{i}',
                task_name='test_task',
                task_args=[],
                task_kwargs={},
                exception_type='Exception',
                exception_message='Error',
                failure_type='TRANSIENT_NETWORK',
                status='PENDING',
                first_failed_at=now - timedelta(hours=i)
            )
        
        response = authenticated_client.get(reverse('api_failure_trends') + '?hours=24')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'trends' in data
        assert len(data['trends']) > 0
    
    def test_api_failure_trends_invalid_hours(self, authenticated_client):
        """Test API validation for invalid hours parameter."""
        response = authenticated_client.get(reverse('api_failure_trends') + '?hours=invalid')
        
        # Should default to 24 hours
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'trends' in data


# ============================================================================
# Test Error Handling
# ============================================================================

@pytest.mark.django_db
class TestDashboardErrorHandling:
    """Test error handling in dashboards."""
    
    @patch('apps.core.views.task_monitoring_dashboard.UniversalIdempotencyService')
    def test_dashboard_handles_service_error(self, mock_service, authenticated_client):
        """Test graceful handling of service errors."""
        mock_service.return_value.get_statistics.side_effect = Exception("Service error")
        
        response = authenticated_client.get(reverse('task_dashboard'))
        
        # Should still return 200 with fallback data
        assert response.status_code == 200
        assert 'idempotency' in response.context
    
    def test_dlq_management_handles_invalid_filter(self, authenticated_client, sample_dlq_records):
        """Test handling of invalid filter values."""
        response = authenticated_client.get(reverse('dlq_management') + '?status=INVALID')
        
        # Should ignore invalid filter and return all tasks
        assert response.status_code == 200
        assert response.context['tasks'].count() == 4
    
    def test_api_handles_database_error(self, authenticated_client, db):
        """Test API error handling."""
        with patch('apps.core.models.task_failure_record.TaskFailureRecord.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            response = authenticated_client.get(reverse('api_dlq_status'))
            
            # Should return error JSON
            assert response.status_code == 500
            data = json.loads(response.content)
            assert 'error' in data


# ============================================================================
# Test URL Routing
# ============================================================================

@pytest.mark.django_db
class TestURLRouting:
    """Test URL routing for all dashboard views."""
    
    def test_all_dashboard_urls_resolve(self, authenticated_client):
        """Test that all dashboard URLs are properly configured."""
        urls = [
            'task_dashboard',
            'idempotency_analysis',
            'schedule_conflicts',
            'dlq_management',
            'failure_taxonomy_dashboard',
            'retry_policy_dashboard',
            'api_dlq_status',
            'api_circuit_breakers',
            'api_failure_trends',
        ]
        
        for url_name in urls:
            url = reverse(url_name)
            response = authenticated_client.get(url)
            
            # Should not be 404
            assert response.status_code != 404, f"URL {url_name} returned 404"
    
    def test_dashboard_base_url(self, authenticated_client):
        """Test base dashboard URL redirects correctly."""
        response = authenticated_client.get('/admin/tasks/')
        
        # Should redirect to main dashboard or return 200
        assert response.status_code in [200, 301, 302]
