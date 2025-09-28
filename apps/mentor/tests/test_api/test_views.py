"""
Tests for Mentor API views.
"""

from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class TestPlanViewSet(APITestCase):
    """Test plan generation API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.PlanGenerator')
    def test_create_plan_success(self, mock_plan_generator):
        """Test successful plan creation."""
        mock_plan = MagicMock()
        mock_plan.plan_id = "test_plan_123"
        mock_plan.request = "Add user authentication"
        mock_plan.steps = []
        mock_plan.impacted_files = set()
        mock_plan.required_tests = []
        mock_plan.migration_needed = False
        mock_plan.overall_risk = "medium"
        mock_plan.estimated_total_time = 120
        mock_plan.prerequisites = []
        mock_plan.rollback_plan = []

        mock_generator = MagicMock()
        mock_generator.generate_plan.return_value = mock_plan
        mock_plan_generator.return_value = mock_generator

        url = reverse('mentor_api:mentor-plan-list')
        data = {
            'request': 'Add user authentication',
            'scope': ['apps/users/'],
            'format': 'json'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['plan_id'], "test_plan_123")
        self.assertEqual(response.data['request'], "Add user authentication")

    def test_create_plan_invalid_data(self):
        """Test plan creation with invalid data."""
        url = reverse('mentor_api:mentor-plan-list')
        data = {}  # Missing required 'request' field

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('request', response.data)

    def test_create_plan_unauthenticated(self):
        """Test plan creation without authentication."""
        self.client.force_authenticate(user=None)

        url = reverse('mentor_api:mentor-plan-list')
        data = {'request': 'Add user authentication'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.mentor_api.views.PlanGenerator')
    def test_plan_generation_error(self, mock_plan_generator):
        """Test handling of plan generation errors."""
        mock_generator = MagicMock()
        mock_generator.generate_plan.side_effect = Exception("Plan generation failed")
        mock_plan_generator.return_value = mock_generator

        url = reverse('mentor_api:mentor-plan-list')
        data = {'request': 'Add user authentication'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)


class TestPatchViewSet(APITestCase):
    """Test patch generation API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.PatchOrchestrator')
    def test_create_patch_dry_run(self, mock_orchestrator_class):
        """Test patch creation in dry-run mode."""
        mock_patch = MagicMock()
        mock_patch.type.value = "fix_security"
        mock_patch.priority.value = "high"
        mock_patch.description = "Fix XSS vulnerability"
        mock_patch.file_path = "apps/users/views.py"
        mock_patch.original_code = "original code"
        mock_patch.modified_code = "fixed code"
        mock_patch.line_start = 10
        mock_patch.line_end = 10
        mock_patch.confidence = 0.9

        mock_orchestrator = MagicMock()
        mock_orchestrator.generate_patches.return_value = [mock_patch]
        mock_orchestrator_class.return_value = mock_orchestrator

        url = reverse('mentor_api:mentor-patch-list')
        data = {
            'request': 'Fix security issues',
            'type': 'security',
            'dry_run': True
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['patches']), 1)
        self.assertEqual(response.data['patches'][0]['type'], "fix_security")

    @patch('apps.mentor_api.views.PatchOrchestrator')
    def test_patch_preview_action(self, mock_orchestrator_class):
        """Test patch preview action."""
        mock_patch = MagicMock()
        mock_patch.type.value = "improvement"
        mock_patch.priority.value = "medium"
        mock_patch.description = "Code improvement"
        mock_patch.file_path = "apps/core/utils.py"
        mock_patch.original_code = "old code"
        mock_patch.modified_code = "new code"
        mock_patch.line_start = 5
        mock_patch.line_end = 5
        mock_patch.confidence = 0.8

        mock_orchestrator = MagicMock()
        mock_orchestrator.generate_patches.return_value = [mock_patch]
        mock_orchestrator_class.return_value = mock_orchestrator

        url = reverse('mentor_api:mentor-patch-preview')
        data = {
            'request': 'Improve code quality',
            'type': 'improvement'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['patches']), 1)


class TestTestViewSet(APITestCase):
    """Test test execution API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.TestSelector')
    @patch('apps.mentor_api.views.TestRunner')
    def test_create_test_execution(self, mock_runner_class, mock_selector_class):
        """Test test execution with targets."""
        # Mock test selection
        mock_selector = MagicMock()
        mock_selector.select_tests_for_changes.return_value = {'test1', 'test2'}
        mock_selector_class.return_value = mock_selector

        # Mock test execution
        mock_session = MagicMock()
        mock_session.session_id = "session_123"
        mock_session.total_tests = 2
        mock_session.passed = 2
        mock_session.failed = 0
        mock_session.skipped = 0
        mock_session.errors = 0
        mock_session.total_duration = 5.5
        mock_session.coverage_percentage = 85.5
        mock_session.results = []

        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = mock_session
        mock_runner_class.return_value = mock_runner

        url = reverse('mentor_api:mentor-test-list')
        data = {
            'targets': ['apps/users/models.py'],
            'coverage': True,
            'parallel': True
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session_id'], "session_123")
        self.assertEqual(response.data['total_tests'], 2)
        self.assertEqual(response.data['passed'], 2)
        self.assertEqual(response.data['coverage_percentage'], 85.5)

    def test_test_execution_no_selection(self):
        """Test test execution when no tests are selected."""
        url = reverse('mentor_api:mentor-test-list')
        data = {'targets': ['nonexistent_file.py']}

        with patch('apps.mentor_api.views.TestSelector') as mock_selector_class:
            mock_selector = MagicMock()
            mock_selector.select_tests_for_changes.return_value = set()
            mock_selector_class.return_value = mock_selector

            response = self.client.post(url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('No tests selected', response.data['message'])


class TestGuardViewSet(APITestCase):
    """Test guard validation API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.PreCommitGuard')
    def test_guard_validation(self, mock_guard_class):
        """Test guard validation execution."""
        # Mock guard report
        mock_report = MagicMock()
        mock_report.overall_status = "PASS"
        mock_report.total_checks = 5
        mock_report.passed_checks = 5
        mock_report.failed_checks = 0
        mock_report.blocking_issues = []
        mock_report.results = []

        mock_guard = MagicMock()
        mock_guard.run_all_checks.return_value = mock_report
        mock_guard_class.return_value = mock_guard

        url = reverse('mentor_api:mentor-guard-list')
        data = {
            'validate': True,
            'files': ['apps/users/models.py']
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_status'], "PASS")
        self.assertEqual(response.data['total_checks'], 5)
        self.assertEqual(response.data['blocking_issues'], 0)

    def test_guard_validation_invalid_data(self):
        """Test guard validation with invalid data."""
        url = reverse('mentor_api:mentor-guard-list')
        data = {}  # No action specified

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestExplainViewSet(APITestCase):
    """Test code explanation API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.CodeExplainer')
    def test_explain_symbol(self, mock_explainer_class):
        """Test symbol explanation."""
        mock_explanation = {
            'symbol': {
                'name': 'test_function',
                'kind': 'function',
                'file': 'apps/utils/helpers.py',
                'signature': 'def test_function(arg1, arg2)',
                'docstring': 'This function does something useful'
            },
            'relationships': {'calls': [], 'imports': []},
            'tests': []
        }

        mock_explainer = MagicMock()
        mock_explainer.explain_symbol.return_value = mock_explanation
        mock_explainer_class.return_value = mock_explainer

        url = reverse('mentor_api:mentor-explain-list')
        data = {
            'target': 'apps/utils/helpers.py:test_function',
            'type': 'symbol',
            'include_usage': True
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['target'], 'apps/utils/helpers.py:test_function')
        self.assertEqual(response.data['type'], 'symbol')
        self.assertIn('explanation', response.data)

    @patch('apps.mentor_api.views.CodeExplainer')
    def test_explain_not_found(self, mock_explainer_class):
        """Test explanation for non-existent target."""
        mock_explainer = MagicMock()
        mock_explainer.explain_file.return_value = {'error': 'File not found'}
        mock_explainer_class.return_value = mock_explainer

        url = reverse('mentor_api:mentor-explain-list')
        data = {
            'target': 'nonexistent/file.py',
            'type': 'file'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_explain_invalid_data(self):
        """Test explanation with invalid data."""
        url = reverse('mentor_api:mentor-explain-list')
        data = {}  # Missing required 'target' field

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('target', response.data)


class TestMentorStatusView(APITestCase):
    """Test mentor status API endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.MentorMetrics')
    def test_get_status_healthy(self, mock_metrics_class):
        """Test getting healthy system status."""
        mock_dashboard_data = MagicMock()
        mock_dashboard_data.index_health = {
            'is_healthy': True,
            'indexed_files': 150,
            'coverage_percentage': 85.5,
            'last_update': '2024-01-15T10:30:00Z'
        }
        mock_dashboard_data.usage_statistics = {
            'operations_last_24h': 25,
            'most_used_operation': 'analyze'
        }
        mock_dashboard_data.quality_metrics = {
            'overall_quality_score': 92.5,
            'total_symbols_analyzed': 1500
        }

        mock_metrics = MagicMock()
        mock_metrics.generate_dashboard_data.return_value = mock_dashboard_data
        mock_metrics_class.return_value = mock_metrics

        url = reverse('mentor_api:mentor-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['index_health']['indexed_files'], 150)

    @patch('apps.mentor_api.views.MentorMetrics')
    def test_get_status_degraded(self, mock_metrics_class):
        """Test getting degraded system status."""
        mock_dashboard_data = MagicMock()
        mock_dashboard_data.index_health = {
            'is_healthy': False,
            'indexed_files': 50,
            'coverage_percentage': 45.0,
            'commits_behind': 15
        }
        mock_dashboard_data.usage_statistics = {}
        mock_dashboard_data.quality_metrics = {}

        mock_metrics = MagicMock()
        mock_metrics.generate_dashboard_data.return_value = mock_dashboard_data
        mock_metrics_class.return_value = mock_metrics

        url = reverse('mentor_api:mentor-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'degraded')

    def test_status_unauthenticated(self):
        """Test status endpoint without authentication."""
        self.client.force_authenticate(user=None)

        url = reverse('mentor_api:mentor-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestMentorHealthView(APITestCase):
    """Test mentor health check API endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('apps.mentor_api.views.IndexMetadata')
    @patch('apps.mentor_api.views.MentorMetrics')
    def test_health_check_healthy(self, mock_metrics_class, mock_index_metadata):
        """Test health check with healthy system."""
        # Mock database check
        mock_index_metadata.objects.count.return_value = 10

        # Mock index health
        mock_health = {
            'is_healthy': True,
            'indexed_files': 200,
            'commits_behind': 0
        }
        mock_metrics = MagicMock()
        mock_metrics.get_index_health.return_value = mock_health
        mock_metrics_class.return_value = mock_metrics

        url = reverse('mentor_api:mentor-health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_health'], 'healthy')
        self.assertEqual(response.data['issues_found'], 0)

        # Check components
        components = {check['component']: check for check in response.data['component_checks']}
        self.assertEqual(components['Database']['status'], 'healthy')
        self.assertEqual(components['Index']['status'], 'healthy')

    @patch('apps.mentor_api.views.IndexMetadata')
    def test_health_check_database_error(self, mock_index_metadata):
        """Test health check with database connectivity issues."""
        mock_index_metadata.objects.count.side_effect = Exception("Database connection failed")

        url = reverse('mentor_api:mentor-health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_health'], 'unhealthy')
        self.assertGreater(response.data['issues_found'], 0)

        # Check that database component shows as unhealthy
        components = {check['component']: check for check in response.data['component_checks']}
        self.assertEqual(components['Database']['status'], 'unhealthy')

    def test_health_check_unauthenticated(self):
        """Test health check without authentication."""
        self.client.force_authenticate(user=None)

        url = reverse('mentor_api:mentor-health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)