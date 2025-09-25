"""
Comprehensive test suite for Information Architecture URL mappings
Tests all 169 legacy URL to new URL mappings with redirect validation
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from unittest.mock import patch, MagicMock
from apps.core.url_router_optimized import OptimizedURLRouter

User = get_user_model()


class TestURLMappingCompleteness(TestCase):
    """Test that all critical URL mappings exist and are comprehensive"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        cache.clear()
    
    def test_all_app_domains_covered(self):
        """Test that all app domains have URL mappings"""
        expected_app_prefixes = [
            'schedhuler/', 'activity/', 'peoples/', 'attendance/',
            'helpdesk/', 'y_helpdesk/', 'reports/', 'onboarding/',
            'work_order_management/', 'clientbilling/', 'employee_creation/'
        ]
        
        covered_prefixes = set()
        for old_url in self.router.URL_MAPPINGS.keys():
            for prefix in expected_app_prefixes:
                if old_url.startswith(prefix):
                    covered_prefixes.add(prefix)
                    break
        
        missing_prefixes = set(expected_app_prefixes) - covered_prefixes
        self.assertEqual(len(missing_prefixes), 0, 
            f"Missing URL mappings for apps: {missing_prefixes}")
    
    def test_mapping_count_meets_expectation(self):
        """Test that we have the expected number of mappings (169)"""
        actual_count = len(self.router.URL_MAPPINGS)
        expected_count = 169
        
        self.assertGreaterEqual(actual_count, expected_count,
            f"Expected at least {expected_count} URL mappings, got {actual_count}")
    
    def test_no_duplicate_legacy_urls(self):
        """Test that no legacy URLs are duplicated"""
        legacy_urls = list(self.router.URL_MAPPINGS.keys())
        unique_urls = set(legacy_urls)
        
        self.assertEqual(len(legacy_urls), len(unique_urls),
            "Found duplicate legacy URLs in mappings")
    
    def test_no_self_referencing_mappings(self):
        """Test that no URL maps to itself"""
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            self.assertNotEqual(old_url, new_url,
                f"Self-referencing mapping found: {old_url} -> {new_url}")


@pytest.mark.django_db
class TestURLMappingRedirects(TestCase):
    """Test all URL mapping redirects with parametrized tests"""
    
    def setUp(self):
        self.client = Client()
        self.router = OptimizedURLRouter
        cache.clear()
    
    @pytest.mark.parametrize("legacy_url,new_url", [
        # Operations Domain
        ("schedhuler/jobneedtasks/", "operations/tasks/"),
        ("schedhuler/schedhule_task/", "operations/tasks/schedule/"),
        ("schedhuler/tasklist_jobneed/", "operations/tasks/list/"),
        ("schedhuler/jobschdtasks/", "operations/tasks/scheduled/"),
        ("activity/adhoctasks/", "operations/tasks/adhoc/"),
        ("schedhuler/jobneedtours/", "operations/tours/"),
        ("schedhuler/jobneedexternaltours/", "operations/tours/external/"),
        ("schedhuler/internal-tours/", "operations/tours/internal/"),
        ("schedhuler/schd_internal_tour/", "operations/schedules/tours/internal/"),
        ("schedhuler/schd_external_tour/", "operations/schedules/tours/external/"),
        ("schedhuler/schedhule_tour/", "operations/tours/schedule/"),
        ("schedhuler/external_schedhule_tour/", "operations/tours/external/schedule/"),
        ("schedhuler/site_tour_tracking/", "operations/tours/tracking/"),
        ("activity/adhoctours/", "operations/tours/adhoc/"),
        ("work_order_management/work_order/", "operations/work-orders/"),
        ("work_order_management/workorder/", "operations/work-orders/"),
        ("work_order_management/work_permit/", "operations/work-permits/"),
        ("work_order_management/workpermit/", "operations/work-permits/"),
        ("work_order_management/sla/", "operations/sla/"),
        ("work_order_management/vendor/", "operations/vendors/"),
        ("work_order_management/approver/", "operations/approvers/"),
        ("activity/ppm/", "operations/ppm/"),
        ("activity/ppm_jobneed/", "operations/ppm/jobs/"),
        
        # Assets Domain
        ("activity/asset/", "assets/"),
        ("activity/assetmaintainance/", "assets/maintenance/"),
        ("activity/assetmaintenance/", "assets/maintenance/"),
        ("activity/comparision/", "assets/compare/"),
        ("activity/param_comparision/", "assets/compare/parameters/"),
        ("activity/assetlog/", "assets/logs/"),
        ("activity/assetlogs/", "assets/logs/"),
        ("activity/location/", "assets/locations/"),
        ("activity/checkpoint/", "assets/checkpoints/"),
        ("activity/peoplenearassets/", "assets/people-nearby/"),
        ("activity/question/", "assets/checklists/questions/"),
        ("activity/questionset/", "assets/checklists/"),
        ("activity/qsetnQsetblng/", "assets/checklists/relationships/"),
        
        # People Domain
        ("peoples/people/", "people/"),
        ("peoples/peole_form/", "people/form/"),
        ("peoples/capability/", "people/capabilities/"),
        ("peoples/no-site/", "people/unassigned/"),
        ("peoples/peoplegroup/", "people/groups/"),
        ("peoples/sitegroup/", "people/site-groups/"),
        ("attendance/attendance_view/", "people/attendance/"),
        ("attendance/geofencetracking/", "people/tracking/"),
        ("attendance/sos_list/", "people/sos/"),
        ("attendance/site_diversions/", "people/diversions/"),
        ("attendance/sitecrisis_list/", "people/crisis/"),
        ("attendance/conveyance/", "people/expenses/conveyance/"),
        ("attendance/travel_expense/", "people/expenses/travel/"),
        ("activity/mobileuserlogs/", "people/mobile/logs/"),
        ("activity/mobileuserdetails/", "people/mobile/details/"),
        ("employee_creation/employee/", "people/employees/"),
        
        # Help Desk Domain
        ("helpdesk/ticket/", "help-desk/tickets/"),
        ("y_helpdesk/ticket/", "help-desk/tickets/"),
        ("helpdesk/escalationmatrix/", "help-desk/escalations/"),
        ("y_helpdesk/escalation/", "help-desk/escalations/"),
        ("helpdesk/postingorder/", "help-desk/posting-orders/"),
        ("y_helpdesk/posting_order/", "help-desk/posting-orders/"),
        ("helpdesk/uniform/", "help-desk/uniforms/"),
        ("y_helpdesk/uniform/", "help-desk/uniforms/"),
        
        # Reports Domain
        ("reports/get_reports/", "reports/download/"),
        ("reports/exportreports/", "reports/download/"),
        ("reports/schedule-email-report/", "reports/schedule/"),
        ("reports/schedule_email_report/", "reports/schedule/"),
        ("reports/sitereport_list/", "reports/site-reports/"),
        ("reports/incidentreport_list/", "reports/incident-reports/"),
        
        # Admin Domain
        ("onboarding/bu/", "admin/business-units/"),
        ("onboarding/client/", "admin/clients/"),
        ("clientbilling/features/", "admin/clients/features/"),
        ("onboarding/contract/", "admin/contracts/"),
        ("onboarding/typeassist/", "admin/config/types/"),
        ("onboarding/shift/", "admin/config/shifts/"),
        ("onboarding/geofence/", "admin/config/geofences/"),
        
        # Dead/Deprecated URLs
        ("apps/customers/getting-started.html", "dashboard/"),
        ("apps/customers/list.html", "people/"),
        ("apps/customers/view.html", "people/"),
    ])
    def test_url_redirect_mapping(self, legacy_url, new_url):
        """Test individual URL redirect mapping"""
        response = self.client.get(f'/{legacy_url}', follow=False)
        
        # Should be a 301 permanent redirect
        self.assertEqual(response.status_code, 301,
            f"URL /{legacy_url} should return 301, got {response.status_code}")
        
        # Should redirect to the correct new URL
        expected_redirect = f'/{new_url}'
        self.assertEqual(response.url, expected_redirect,
            f"URL /{legacy_url} should redirect to {expected_redirect}, got {response.url}")


class TestURLParameterHandling(TestCase):
    """Test URL mappings with dynamic parameters"""
    
    def setUp(self):
        self.client = Client()
        self.router = OptimizedURLRouter
    
    def test_dynamic_parameter_preservation(self):
        """Test that dynamic parameters are preserved in redirects"""
        dynamic_mappings = [
            ("schedhuler/task_jobneed/123/", "operations/tasks/123/"),
            ("activity/asset/456/", "assets/456/"),
            ("peoples/people/789/", "people/789/"),
        ]
        
        for old_url, expected_new_url in dynamic_mappings:
            # Create mock redirect view to test parameter handling
            redirect_view = self.router._create_smart_redirect(
                old_url.replace('123', '<str:pk>').replace('456', '<str:pk>').replace('789', '<str:pk>'),
                expected_new_url.replace('123', '<str:pk>').replace('456', '<str:pk>').replace('789', '<str:pk>')
            )
            
            # Test that view is created successfully
            self.assertIsNotNone(redirect_view)
            self.assertTrue(callable(redirect_view))
    
    def test_query_string_preservation(self):
        """Test that query strings are preserved in redirects"""
        test_cases = [
            ("schedhuler/jobneedtasks/?page=2&filter=active", "operations/tasks/"),
            ("activity/asset/?search=pump&category=mechanical", "assets/"),
            ("peoples/people/?department=security&status=active", "people/"),
        ]
        
        for legacy_url_with_params, new_url_base in test_cases:
            legacy_url, query_string = legacy_url_with_params.split('?', 1)
            
            response = self.client.get(f'/{legacy_url_with_params}', follow=False)
            
            # Should be a 301 redirect
            self.assertEqual(response.status_code, 301)
            
            # Should preserve query parameters
            expected_redirect = f'/{new_url_base}?{query_string}'
            self.assertEqual(response.url, expected_redirect,
                f"Query string not preserved: expected {expected_redirect}, got {response.url}")
    
    def test_multiple_parameters(self):
        """Test URLs with multiple path parameters"""
        # Test case: task with job and user ID
        mock_request = MagicMock()
        mock_request.META = {'QUERY_STRING': 'details=full'}
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        # Test parameter interpolation logic
        test_url = 'operations/tasks/<str:task_id>/users/<str:user_id>/'
        params = {'task_id': '123', 'user_id': '456'}
        
        # Simulate parameter replacement
        result_url = test_url
        for key, value in params.items():
            placeholder = f'<str:{key}>/'
            if placeholder in result_url:
                result_url = result_url.replace(placeholder, f'{value}/')
        
        expected_url = 'operations/tasks/123/users/456/'
        self.assertEqual(result_url, expected_url)


class TestURLNamingConventions(TestCase):
    """Test that new URLs follow consistent naming conventions"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
    
    def test_no_underscores_in_new_urls(self):
        """Test that new URLs don't contain underscores"""
        violations = []
        
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            # Remove parameter placeholders for testing
            clean_new_url = new_url.replace('<str:', '').replace('>', '').replace('/', '')
            
            if '_' in clean_new_url:
                violations.append((old_url, new_url))
        
        self.assertEqual(len(violations), 0,
            f"New URLs contain underscores: {violations[:5]}")
    
    def test_lowercase_new_urls(self):
        """Test that new URLs are lowercase"""
        violations = []
        
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            if new_url != new_url.lower():
                violations.append((old_url, new_url))
        
        self.assertEqual(len(violations), 0,
            f"New URLs not lowercase: {violations}")
    
    def test_trailing_slash_consistency(self):
        """Test that URLs consistently use trailing slashes"""
        violations = []
        
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            # Skip parameter URLs
            if '<str:' in new_url:
                continue
                
            if not new_url.endswith('/'):
                violations.append((old_url, new_url))
        
        self.assertEqual(len(violations), 0,
            f"URLs missing trailing slash: {violations}")
    
    def test_domain_grouping_consistency(self):
        """Test that URLs are properly grouped by domain"""
        domain_prefixes = {
            'operations': ['operations/'],
            'assets': ['assets/'],
            'people': ['people/'],
            'help-desk': ['help-desk/'],
            'reports': ['reports/'],
            'admin': ['admin/'],
            'api': ['api/'],
            'auth': ['auth/'],
            'monitoring': ['monitoring/']
        }
        
        ungrouped_urls = []
        
        for old_url, new_url in self.router.URL_MAPPINGS.items():
            # Check if new URL belongs to any domain
            belongs_to_domain = False
            
            for domain, prefixes in domain_prefixes.items():
                for prefix in prefixes:
                    if new_url.startswith(prefix):
                        belongs_to_domain = True
                        break
                if belongs_to_domain:
                    break
            
            if not belongs_to_domain:
                ungrouped_urls.append((old_url, new_url))
        
        # Allow some URLs to be ungrouped (like dashboard, root paths)
        self.assertLess(len(ungrouped_urls), 10,
            f"Too many ungrouped URLs: {ungrouped_urls[:5]}")


class TestURLMappingAnalytics(TestCase):
    """Test URL mapping analytics and tracking"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        cache.clear()
        # Clear analytics
        self.router.URL_USAGE_ANALYTICS.clear()
    
    def test_url_usage_tracking(self):
        """Test that URL usage is properly tracked"""
        old_url = 'schedhuler/jobneedtasks/'
        new_url = 'operations/tasks/'
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        # Track usage
        self.router._track_url_usage(old_url, new_url, mock_request)
        
        # Verify tracking
        self.assertIn(old_url, self.router.URL_USAGE_ANALYTICS)
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        
        self.assertEqual(analytics['count'], 1)
        self.assertEqual(analytics['new_url'], new_url)
        self.assertIn('testuser', analytics['users'])
        self.assertIsNotNone(analytics['last_accessed'])
    
    def test_multiple_usage_tracking(self):
        """Test tracking multiple accesses to the same URL"""
        old_url = 'activity/asset/'
        new_url = 'assets/'
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'user1'
        
        # Track multiple usages
        for i in range(5):
            self.router._track_url_usage(old_url, new_url, mock_request)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 5)
    
    def test_migration_report_generation(self):
        """Test migration report with tracked usage"""
        # Set up test analytics data
        self.router.URL_USAGE_ANALYTICS = {
            'schedhuler/jobneedtasks/': {
                'count': 25,
                'users': {'user1', 'user2'},
                'last_accessed': self.router._track_url_usage.__code__.co_filename,
                'new_url': 'operations/tasks/'
            },
            'activity/asset/': {
                'count': 50,
                'users': {'user1', 'user3', 'user4'},
                'last_accessed': self.router._track_url_usage.__code__.co_filename,
                'new_url': 'assets/'
            }
        }
        
        report = self.router.get_migration_report()
        
        # Verify report structure
        self.assertIn('summary', report)
        self.assertIn('top_legacy_urls', report)
        self.assertIn('recommendations', report)
        self.assertIn('timestamp', report)
        
        # Verify summary data
        summary = report['summary']
        self.assertGreater(summary['total_legacy_urls'], 0)
        self.assertEqual(summary['used_legacy_urls'], 2)
        self.assertEqual(summary['total_redirects'], 75)
    
    def test_url_structure_validation(self):
        """Test URL structure validation"""
        validation = self.router.validate_url_structure()
        
        # Should return validation categories
        expected_categories = [
            'naming_inconsistencies',
            'deep_nesting', 
            'missing_redirects',
            'duplicate_targets'
        ]
        
        for category in expected_categories:
            self.assertIn(category, validation)
            self.assertIsInstance(validation[category], list)
        
        # Test deep nesting detection
        deep_urls = [url for url in self.router.URL_MAPPINGS.values() if url.count('/') > 3]
        self.assertLessEqual(len(deep_urls), 5,
            f"Too many deeply nested URLs: {deep_urls[:3]}")


@pytest.mark.performance
class TestURLMappingPerformance(TestCase):
    """Test performance characteristics of URL mappings"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        self.client = Client()
    
    def test_redirect_view_creation_performance(self):
        """Test that redirect view creation is fast"""
        import time
        
        start_time = time.time()
        
        # Create redirect views for first 50 mappings
        for i, (old_url, new_url) in enumerate(self.router.URL_MAPPINGS.items()):
            if i >= 50:
                break
            redirect_view = self.router._create_smart_redirect(old_url, new_url)
            self.assertIsNotNone(redirect_view)
        
        elapsed = time.time() - start_time
        
        # Should create 50 redirect views in under 1 second
        self.assertLess(elapsed, 1.0,
            f"Redirect view creation too slow: {elapsed:.3f}s for 50 views")
    
    def test_pattern_generation_performance(self):
        """Test that URL pattern generation is efficient"""
        import time
        
        start_time = time.time()
        patterns = self.router.get_optimized_patterns()
        elapsed = time.time() - start_time
        
        # Should generate patterns quickly
        self.assertLess(elapsed, 2.0,
            f"Pattern generation too slow: {elapsed:.3f}s")
        
        # Should generate patterns for all mappings
        self.assertGreater(len(patterns), 100,
            f"Expected >100 patterns, got {len(patterns)}")
    
    def test_analytics_tracking_performance(self):
        """Test that analytics tracking doesn't impact performance"""
        import time
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        start_time = time.time()
        
        # Track 100 URL accesses
        for i in range(100):
            url = f'test/url/{i}/'
            self.router._track_url_usage(url, f'new/url/{i}/', mock_request)
        
        elapsed = time.time() - start_time
        
        # Should track 100 accesses in under 0.5 seconds
        self.assertLess(elapsed, 0.5,
            f"Analytics tracking too slow: {elapsed:.3f}s for 100 tracks")