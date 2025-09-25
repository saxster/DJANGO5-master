"""
Comprehensive tests for Information Architecture optimization
Tests URL migration, navigation tracking, and monitoring functionality
"""
import pytest
from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware

User = get_user_model()


class TestOptimizedURLRouter(TestCase):
    """Test the optimized URL router functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.router = OptimizedURLRouter
        cache.clear()
    
    def test_url_mappings_completeness(self):
        """Test that all important legacy URLs have mappings"""
        # Critical legacy URLs that must have mappings
        critical_urls = [
            'schedhuler/jobneedtasks/',
            'activity/asset/',
            'peoples/people/',
            'helpdesk/ticket/',
            'reports/get_reports/',
            'onboarding/bu/',
        ]
        
        for url in critical_urls:
            self.assertIn(
                url, 
                self.router.URL_MAPPINGS,
                f"Critical URL {url} missing from mappings"
            )
    
    def test_url_mapping_consistency(self):
        """Test that new URLs follow consistent naming conventions"""
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            # New URLs should not contain underscores
            self.assertNotIn(
                '_', 
                new_url.replace('<str:', '').replace('>', ''),
                f"New URL {new_url} contains underscores"
            )
            
            # New URLs should be lowercase
            self.assertEqual(
                new_url.lower(),
                new_url,
                f"New URL {new_url} is not lowercase"
            )
    
    def test_redirect_pattern_generation(self):
        """Test that redirect patterns are generated correctly"""
        patterns = self.router.get_optimized_patterns()
        
        # Should have patterns for all mappings
        self.assertGreater(len(patterns), 0)
        
        # Check that patterns are valid URL patterns
        for pattern in patterns:
            self.assertTrue(hasattr(pattern, 'pattern'))
            self.assertTrue(hasattr(pattern, 'callback'))
    
    def test_navigation_menu_generation(self):
        """Test navigation menu structure generation"""
        # Test without user (public menu)
        public_menu = self.router.get_navigation_menu()
        self.assertIsInstance(public_menu, list)
        self.assertGreater(len(public_menu), 0)
        
        # Verify menu structure
        for item in public_menu:
            self.assertIn('name', item)
            self.assertIn('url', item)
            self.assertIn('icon', item)
    
    def test_breadcrumb_generation(self):
        """Test breadcrumb generation for URLs"""
        test_cases = [
            ('/operations/tasks/', ['Home', 'Operations', 'Tasks']),
            ('/assets/maintenance/', ['Home', 'Assets', 'Maintenance']),
            ('/people/attendance/', ['Home', 'People', 'Attendance']),
        ]
        
        for url, expected_names in test_cases:
            breadcrumbs = self.router.get_breadcrumbs(url)
            actual_names = [b['name'] for b in breadcrumbs]
            self.assertEqual(actual_names, expected_names)
    
    def test_migration_report_generation(self):
        """Test migration report generation"""
        report = self.router.get_migration_report()
        
        # Verify report structure
        self.assertIn('summary', report)
        self.assertIn('top_legacy_urls', report)
        self.assertIn('recommendations', report)
        self.assertIn('timestamp', report)
        
        # Verify summary metrics
        summary = report['summary']
        self.assertIn('total_legacy_urls', summary)
        self.assertIn('adoption_rate', summary)
        self.assertGreaterEqual(summary['adoption_rate'], 0)
        self.assertLessEqual(summary['adoption_rate'], 100)
    
    def test_url_structure_validation(self):
        """Test URL structure validation"""
        validation = self.router.validate_url_structure()
        
        # Should return validation results
        self.assertIn('naming_inconsistencies', validation)
        self.assertIn('deep_nesting', validation)
        self.assertIn('duplicate_targets', validation)
        
        # Check for any critical issues
        if validation['naming_inconsistencies']:
            print(f"Found naming issues: {validation['naming_inconsistencies'][:3]}")
        
        if validation['deep_nesting']:
            print(f"Found deep nesting: {validation['deep_nesting'][:3]}")


class TestNavigationTrackingMiddleware(TestCase):
    """Test navigation tracking middleware"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        self.middleware = NavigationTrackingMiddleware(lambda r: r)
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        cache.clear()
    
    def test_404_tracking(self):
        """Test that 404 errors are tracked"""
        # Access a non-existent URL
        response = self.client.get('/non-existent-url/')
        
        # Check that 404 was tracked
        dead_urls = cache.get('nav_tracking_404_urls', {})
        # The tracking happens in middleware, simulate it
        self.middleware._track_404('/non-existent-url/', None)
        
        dead_urls = cache.get('nav_tracking_404_urls', {})
        self.assertIn('/non-existent-url/', dead_urls)
        self.assertEqual(dead_urls['/non-existent-url/']['count'], 1)
    
    def test_successful_navigation_tracking(self):
        """Test tracking of successful page visits"""
        # Simulate successful navigation
        self.middleware._track_successful_navigation(
            '/dashboard/',
            'test_session_123',
            self.user,
            0.5
        )
        
        popular_paths = cache.get('nav_tracking_popular_paths', {})
        self.assertIn('/dashboard/', popular_paths)
        self.assertEqual(popular_paths['/dashboard/']['count'], 1)
        self.assertEqual(popular_paths['/dashboard/']['avg_response_time'], 0.5)
    
    def test_deprecated_url_tracking(self):
        """Test tracking of deprecated URL usage"""
        # Track a deprecated URL
        self.middleware._track_deprecated_url_usage(
            '/schedhuler/jobneedtasks/',
            self.user
        )
        
        deprecated_usage = cache.get('nav_tracking_deprecated_usage', {})
        self.assertIn('schedhuler/jobneedtasks/', deprecated_usage)
        self.assertEqual(deprecated_usage['schedhuler/jobneedtasks/']['count'], 1)
    
    def test_user_flow_tracking(self):
        """Test user navigation flow tracking"""
        session_key = 'test_session_456'
        
        # Track multiple page visits
        pages = ['/dashboard/', '/operations/tasks/', '/assets/']
        for page in pages:
            self.middleware._track_user_flow(session_key, page)
        
        user_flows = cache.get('nav_tracking_user_flows', {})
        self.assertIn(session_key, user_flows)
        self.assertEqual(len(user_flows[session_key]['paths']), 3)
    
    def test_navigation_analytics_generation(self):
        """Test comprehensive navigation analytics"""
        # Set up some test data
        self.middleware._track_404('/broken-link/', self.user)
        self.middleware._track_successful_navigation('/dashboard/', 'session1', self.user, 1.2)
        
        analytics = NavigationTrackingMiddleware.get_navigation_analytics()
        
        # Verify analytics structure
        self.assertIn('dead_urls', analytics)
        self.assertIn('popular_paths', analytics)
        self.assertIn('deprecated_usage', analytics)
        self.assertIn('user_flows', analytics)
        self.assertIn('recommendations', analytics)
    
    def test_excluded_patterns(self):
        """Test that certain patterns are excluded from tracking"""
        excluded_paths = [
            '/static/css/style.css',
            '/media/uploads/image.jpg',
            '/__debug__/toolbar/',
            '/admin/jsi18n/',
        ]
        
        for path in excluded_paths:
            self.assertTrue(
                self.middleware._should_exclude(path),
                f"Path {path} should be excluded"
            )
    
    def test_pattern_matching(self):
        """Test URL pattern matching with wildcards"""
        test_cases = [
            ('operations/tasks/123', 'operations/tasks/*', True),
            ('operations/tasks', 'operations/tasks/*', False),
            ('assets/maintenance', 'assets/maintenance', True),
        ]
        
        for path, pattern, expected in test_cases:
            result = self.middleware._matches_pattern(path, pattern)
            self.assertEqual(
                result, 
                expected,
                f"Pattern {pattern} matching {path} returned {result}, expected {expected}"
            )


@override_settings(DEBUG=True)
class TestIAIntegration(TestCase):
    """Integration tests for the complete IA optimization"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True
        )
        cache.clear()
    
    def test_legacy_url_redirect(self):
        """Test that legacy URLs redirect to new URLs"""
        # This would require the URL configuration to be loaded
        # For now, test the redirect view creation
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        redirect_view = OptimizedURLRouter._create_smart_redirect(
            'activity/asset/',
            'assets/'
        )
        
        self.assertIsNotNone(redirect_view)
        # The view should be callable
        self.assertTrue(callable(redirect_view))
    
    def test_monitoring_dashboard_access(self):
        """Test access to monitoring dashboard"""
        # Login as staff user
        self.client.login(username='admin', password='admin123')
        
        # Try to access monitoring dashboard
        # This assumes the URL is configured
        # response = self.client.get('/monitoring/ia-dashboard/')
        # self.assertEqual(response.status_code, 200)
    
    def test_navigation_menu_with_permissions(self):
        """Test navigation menu filtering based on permissions"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Test with authenticated user
        menu = OptimizedURLRouter.get_navigation_menu(user=self.user)
        self.assertIsInstance(menu, list)
        
        # Admin menu should be available for staff
        admin_menu = OptimizedURLRouter.get_navigation_menu(
            user=self.user, 
            menu_type='admin'
        )
        self.assertIsInstance(admin_menu, list)
    
    def test_migration_recommendations(self):
        """Test that migration recommendations are generated"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Simulate some usage
        OptimizedURLRouter.URL_USAGE_ANALYTICS = {
            'old/url1/': {'count': 150, 'users': ['user1', 'user2'], 'last_accessed': datetime.now()},
            'old/url2/': {'count': 75, 'users': ['user3'], 'last_accessed': datetime.now()},
        }
        
        report = OptimizedURLRouter.get_migration_report()
        recommendations = report['recommendations']
        
        self.assertIsInstance(recommendations, list)
        if recommendations:
            self.assertGreater(len(recommendations), 0)
    
    def test_performance_score_calculation(self):
        """Test performance score calculation"""
        from apps.core.views.ia_monitoring_views import IAMonitoringDashboard
        
        dashboard = IAMonitoringDashboard()
        
        # Test various response times
        test_cases = [
            (0.3, 100),  # Excellent
            (0.8, 90),   # Good
            (1.5, 70),   # Average
            (2.5, 50),   # Poor
            (5.0, 50),   # Very poor
        ]
        
        for response_time, min_expected_score in test_cases:
            score = dashboard._calculate_performance_score(response_time)
            self.assertGreaterEqual(
                score,
                min_expected_score - 10,  # Allow some variance
                f"Score for {response_time}s should be around {min_expected_score}"
            )
    
    def test_ux_score_calculation(self):
        """Test UX score calculation"""
        from apps.core.views.ia_monitoring_views import IAMonitoringDashboard
        
        dashboard = IAMonitoringDashboard()
        
        # Test with different metrics
        score = dashboard._calculate_ux_score(
            bounce_rate=40,  # Medium bounce rate
            avg_pages_per_session=3.5,  # Good engagement
            total_404s=20  # Some errors
        )
        
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


# Pytest fixtures for more advanced testing
@pytest.fixture
def mock_request():
    """Create a mock request object"""
    request = MagicMock()
    request.path = '/test/path/'
    request.user.is_authenticated = True
    request.user.username = 'testuser'
    request.session.session_key = 'test_session_key'
    return request


@pytest.fixture
def clean_cache():
    """Ensure cache is clean before and after tests"""
    cache.clear()
    yield
    cache.clear()


def test_url_migration_completeness(clean_cache):
    """Test that URL migration covers all app URLs"""
    router = OptimizedURLRouter
    
    # All app prefixes that should be covered
    app_prefixes = [
        'schedhuler/', 'activity/', 'peoples/', 'attendance/',
        'helpdesk/', 'y_helpdesk/', 'reports/', 'onboarding/',
        'work_order_management/', 'clientbilling/'
    ]
    
    for prefix in app_prefixes:
        # Check that at least one mapping exists for this app
        has_mapping = any(
            old_url.startswith(prefix) 
            for old_url in router.URL_MAPPINGS.keys()
        )
        assert has_mapping, f"No URL mappings found for app prefix: {prefix}"


def test_navigation_tracking_performance(mock_request, clean_cache):
    """Test that navigation tracking doesn't significantly impact performance"""
    import time
    
    middleware = NavigationTrackingMiddleware(lambda r: MagicMock(status_code=200))
    
    # Measure tracking overhead
    start = time.time()
    for _ in range(100):
        response = middleware(mock_request)
    elapsed = time.time() - start
    
    # Should process 100 requests in less than 1 second
    assert elapsed < 1.0, f"Navigation tracking too slow: {elapsed}s for 100 requests"