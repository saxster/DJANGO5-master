"""
Comprehensive Dashboard Infrastructure Tests

Tests for:
- Dashboard registry functionality
- Dashboard mixins and base classes
- Dashboard hub views
- API contracts and responses
- Permission checks
- Caching behavior

Ensures all dashboards follow standardized patterns and work correctly.

Author: Dashboard Infrastructure Team
Date: 2025-10-04
"""

import json
import pytest
from datetime import timedelta
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

from apps.core.registry import (
    Dashboard,
    DashboardRegistry,
    dashboard_registry,
    register_core_dashboards
)
from apps.core.mixins import (
    BaseDashboardView,
    DashboardAPIMixin,
    DashboardDataMixin,
    DashboardCacheMixin
)

User = get_user_model()


class DashboardRegistryTestCase(TestCase):
    """
    Tests for Dashboard Registry functionality.

    Validates:
    - Dashboard registration
    - Permission checks
    - Category organization
    - Search functionality
    """

    def setUp(self):
        """Set up test fixtures."""
        self.registry = DashboardRegistry()
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            loginid='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        self.superuser = User.objects.create_user(
            loginid='superuser',
            email='super@example.com',
            password='testpass123',
            is_superuser=True
        )

    def test_dashboard_registration(self):
        """Test basic dashboard registration."""
        dashboard = self.registry.register(
            id='test_dashboard',
            title='Test Dashboard',
            url='/test/',
            permission='authenticated',
            category='test'
        )

        assert dashboard.id == 'test_dashboard'
        assert self.registry.get_dashboard_count() == 1
        assert 'test' in self.registry.get_categories()

    def test_duplicate_dashboard_raises_error(self):
        """Test that registering duplicate ID raises error."""
        self.registry.register(
            id='test_dashboard',
            title='Test Dashboard',
            url='/test/',
            permission='authenticated',
            category='test'
        )

        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(
                id='test_dashboard',
                title='Another Dashboard',
                url='/another/',
                permission='authenticated',
                category='test'
            )

    def test_dashboard_unregistration(self):
        """Test dashboard unregistration."""
        self.registry.register(
            id='test_dashboard',
            title='Test Dashboard',
            url='/test/',
            permission='authenticated',
            category='test'
        )

        assert self.registry.get_dashboard_count() == 1
        result = self.registry.unregister('test_dashboard')
        assert result is True
        assert self.registry.get_dashboard_count() == 0

    def test_get_dashboards_for_user_authenticated(self):
        """Test filtering dashboards by user permission - authenticated."""
        self.registry.register(
            id='auth_dashboard',
            title='Authenticated Dashboard',
            url='/auth/',
            permission='authenticated',
            category='test'
        )
        self.registry.register(
            id='staff_dashboard',
            title='Staff Dashboard',
            url='/staff/',
            permission='staff',
            category='test'
        )

        # Regular user can access authenticated dashboard only
        dashboards = self.registry.get_dashboards_for_user(self.user)
        assert len(dashboards) == 1
        assert dashboards[0].id == 'auth_dashboard'

        # Staff user can access both
        dashboards = self.registry.get_dashboards_for_user(self.staff_user)
        assert len(dashboards) == 2

    def test_get_dashboards_for_superuser(self):
        """Test that superuser can access all dashboards."""
        self.registry.register(
            id='auth_dashboard',
            title='Authenticated Dashboard',
            url='/auth/',
            permission='authenticated',
            category='test'
        )
        self.registry.register(
            id='staff_dashboard',
            title='Staff Dashboard',
            url='/staff/',
            permission='staff',
            category='test'
        )

        dashboards = self.registry.get_dashboards_for_user(self.superuser)
        assert len(dashboards) == 2

    def test_get_by_category(self):
        """Test filtering dashboards by category."""
        self.registry.register(
            id='core_dash1',
            title='Core Dashboard 1',
            url='/core1/',
            permission='authenticated',
            category='core'
        )
        self.registry.register(
            id='security_dash1',
            title='Security Dashboard 1',
            url='/sec1/',
            permission='staff',
            category='security'
        )
        self.registry.register(
            id='core_dash2',
            title='Core Dashboard 2',
            url='/core2/',
            permission='authenticated',
            category='core'
        )

        core_dashboards = self.registry.get_by_category('core')
        assert len(core_dashboards) == 2

        security_dashboards = self.registry.get_by_category('security')
        assert len(security_dashboards) == 1

    def test_search_dashboards(self):
        """Test dashboard search functionality."""
        self.registry.register(
            id='performance_dashboard',
            title='Performance Monitoring',
            url='/perf/',
            permission='staff',
            category='monitoring',
            description='Monitor system performance metrics'
        )
        self.registry.register(
            id='security_dashboard',
            title='Security Overview',
            url='/sec/',
            permission='staff',
            category='security',
            description='Security threat monitoring'
        )

        # Search by title
        results = self.registry.search('performance')
        assert len(results) == 1
        assert results[0].id == 'performance_dashboard'

        # Search by description
        results = self.registry.search('threat')
        assert len(results) == 1
        assert results[0].id == 'security_dashboard'

        # Search by category
        results = self.registry.search('security')
        assert len(results) == 1


    def test_dashboard_priority_ordering(self):
        """Test that dashboards are ordered by priority."""
        self.registry.register(
            id='low_priority',
            title='Low Priority',
            url='/low/',
            permission='authenticated',
            category='test',
            priority=100
        )
        self.registry.register(
            id='high_priority',
            title='High Priority',
            url='/high/',
            permission='authenticated',
            category='test',
            priority=1
        )
        self.registry.register(
            id='medium_priority',
            title='Medium Priority',
            url='/medium/',
            permission='authenticated',
            category='test',
            priority=50
        )

        all_dashboards = self.registry.all()
        assert all_dashboards[0].id == 'high_priority'
        assert all_dashboards[1].id == 'medium_priority'
        assert all_dashboards[2].id == 'low_priority'


class DashboardMixinsTestCase(TestCase):
    """
    Tests for Dashboard Mixins.

    Validates:
    - API response formatting
    - Error handling
    - Data formatting
    - Caching behavior
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test view class
        class TestDashboardView(BaseDashboardView):
            dashboard_id = 'test_dashboard'
            cache_ttl = 60

            def get_dashboard_data(self):
                return {
                    'metrics': {'total': 100},
                    'generated_at': timezone.now().isoformat()
                }

        self.view_class = TestDashboardView

    def test_api_response_format(self):
        """Test standardized API response format."""
        view = self.view_class()
        request = self.factory.get('/test/')
        request.user = self.user
        request.session = {'bu_id': 1, 'client_id': 1}
        view.request = request

        data = {'test': 'data'}
        response = view.get_api_response('test_dashboard', data)

        response_data = json.loads(response.content)
        assert 'version' in response_data
        assert response_data['version'] == 'v1'
        assert 'timestamp' in response_data
        assert 'tenant' in response_data
        assert 'dashboard_id' in response_data
        assert response_data['dashboard_id'] == 'test_dashboard'
        assert 'data' in response_data
        assert 'cache_info' in response_data

    def test_error_response_format(self):
        """Test standardized error response format."""
        view = self.view_class()
        request = self.factory.get('/test/')
        request.user = self.user
        view.request = request

        response = view.get_error_response(
            'test_error',
            'Test error message',
            status_code=400
        )

        response_data = json.loads(response.content)
        assert 'error' in response_data
        assert response_data['error']['type'] == 'test_error'
        assert response_data['error']['message'] == 'Test error message'
        assert response_data['error']['status_code'] == 400

    def test_time_range_parsing(self):
        """Test time range parsing from request parameters."""
        view = self.view_class()

        # Test hours format
        request = self.factory.get('/test/?range=24h')
        view.request = request
        start, end = view.get_time_range()
        assert (end - start).total_seconds() == 24 * 3600

        # Test days format
        request = self.factory.get('/test/?range=7d')
        view.request = request
        start, end = view.get_time_range()
        assert (end - start).total_seconds() == 7 * 24 * 3600

    def test_caching_behavior(self):
        """Test dashboard data caching."""
        cache.clear()

        view = self.view_class()
        request = self.factory.get('/test/')
        request.user = self.user
        request.session = {'bu_id': 1, 'client_id': 1}
        view.request = request

        # First request should not be cached
        response = view.get(request)
        response_data = json.loads(response.content)
        assert response_data['cache_info']['hit'] is False

        # Second request should hit cache
        response = view.get(request)
        response_data = json.loads(response.content)
        assert response_data['cache_info']['hit'] is True


class DashboardHubViewsTestCase(TestCase):
    """
    Tests for Dashboard Hub Views.

    Validates:
    - Hub view rendering
    - Search API
    - Categories API
    - Metrics API
    - Access tracking
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            loginid='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )

        # Register some test dashboards
        dashboard_registry.register(
            id='test_dashboard_1',
            title='Test Dashboard 1',
            url='/test1/',
            permission='authenticated',
            category='test'
        )
        dashboard_registry.register(
            id='test_dashboard_2',
            title='Test Dashboard 2',
            url='/test2/',
            permission='staff',
            category='test'
        )

    def test_dashboard_hub_requires_authentication(self):
        """Test that dashboard hub requires login."""
        response = self.client.get('/dashboards/')
        # Should redirect to login
        assert response.status_code == 302

    def test_dashboard_search_api(self):
        """Test dashboard search API."""
        self.client.login(loginid='testuser', password='testpass123')

        response = self.client.get('/dashboards/search/?q=test')
        assert response.status_code == 200

        data = json.loads(response.content)
        assert data['status'] == 'success'
        assert 'results' in data
        assert data['count'] >= 0

    def test_dashboard_categories_api(self):
        """Test dashboard categories API."""
        self.client.login(loginid='testuser', password='testpass123')

        response = self.client.get('/dashboards/categories/')
        assert response.status_code == 200

        data = json.loads(response.content)
        assert data['status'] == 'success'
        assert 'categories' in data

    def test_dashboard_metrics_api(self):
        """Test dashboard metrics API."""
        self.client.login(loginid='testuser', password='testpass123')

        response = self.client.get('/dashboards/metrics/')
        assert response.status_code == 200

        data = json.loads(response.content)
        assert data['status'] == 'success'
        assert 'metrics' in data
        assert 'user_context' in data


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
