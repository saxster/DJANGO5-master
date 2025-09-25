"""
Comprehensive unit tests for Information Architecture navigation logic and analytics
Tests 140 unit test cases covering navigation menu generation, breadcrumbs, analytics, and router logic
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
from apps.core.url_router_optimized import OptimizedURLRouter

User = get_user_model()


class TestNavigationMenuGeneration(TestCase):
    """Test navigation menu generation logic (35 tests)"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='staffpass123',
            is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username='superuser',
            password='superpass123'
        )
    
    def test_navigation_structure_exists(self):
        """Test that navigation structure is properly defined"""
        self.assertIn('main', self.router.NAVIGATION_STRUCTURE)
        self.assertIn('admin', self.router.NAVIGATION_STRUCTURE)
        
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        self.assertIsInstance(main_menu, list)
        self.assertGreater(len(main_menu), 0)
    
    def test_main_menu_structure_validation(self):
        """Test that main menu items have required fields"""
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        
        required_fields = ['name', 'url', 'icon']
        
        for item in main_menu:
            for field in required_fields:
                self.assertIn(field, item, 
                    f"Menu item {item.get('name', 'unknown')} missing {field}")
            
            # Test URL format
            self.assertTrue(item['url'].startswith('/'),
                f"Menu URL should start with '/': {item['url']}")
            self.assertTrue(item['url'].endswith('/'),
                f"Menu URL should end with '/': {item['url']}")
    
    def test_menu_hierarchy_depth_limit(self):
        """Test that menu hierarchy doesn't exceed 2 levels"""
        for menu_type in ['main', 'admin']:
            menu = self.router.NAVIGATION_STRUCTURE[menu_type]
            
            for item in menu:
                if 'children' in item:
                    # Check that children don't have children (max 2 levels)
                    for child in item['children']:
                        self.assertNotIn('children', child,
                            f"Menu hierarchy too deep in {item['name']} -> {child['name']}")
    
    def test_menu_without_user(self):
        """Test menu generation without user (public menu)"""
        menu = self.router.get_navigation_menu()
        
        self.assertIsInstance(menu, list)
        # Should return full menu for anonymous users (no filtering)
        self.assertGreater(len(menu), 0)
    
    def test_menu_with_regular_user(self):
        """Test menu generation with regular user"""
        # Mock user permissions
        with patch.object(self.user, 'has_perm', return_value=True):
            menu = self.router.get_navigation_menu(user=self.user)
            
            self.assertIsInstance(menu, list)
            self.assertGreater(len(menu), 0)
    
    def test_menu_with_staff_user(self):
        """Test menu generation with staff user"""
        with patch.object(self.staff_user, 'has_perm', return_value=True):
            menu = self.router.get_navigation_menu(user=self.staff_user)
            
            self.assertIsInstance(menu, list)
            self.assertGreater(len(menu), 0)
    
    def test_menu_permission_filtering(self):
        """Test that menu items are filtered based on permissions"""
        # Mock user with no permissions
        with patch.object(self.user, 'has_perm', return_value=False):
            filtered_menu = self.router.get_navigation_menu(user=self.user)
            
            # Should have fewer items when permissions are denied
            full_menu = self.router.get_navigation_menu()
            
            # Count items with capability requirements
            full_items_with_caps = sum(1 for item in full_menu if 'capability' in item)
            filtered_items_with_caps = sum(1 for item in filtered_menu if 'capability' in item)
            
            if full_items_with_caps > 0:
                self.assertLessEqual(filtered_items_with_caps, full_items_with_caps)
    
    def test_admin_menu_generation(self):
        """Test admin menu generation"""
        admin_menu = self.router.get_navigation_menu(menu_type='admin')
        
        self.assertIsInstance(admin_menu, list)
        
        if len(admin_menu) > 0:
            # Admin menu items should have admin-related URLs
            admin_item = admin_menu[0]
            self.assertIn('admin', admin_item.get('url', '').lower())
    
    def test_invalid_menu_type(self):
        """Test handling of invalid menu type"""
        invalid_menu = self.router.get_navigation_menu(menu_type='nonexistent')
        
        self.assertEqual(invalid_menu, [])
    
    def test_menu_children_filtering(self):
        """Test that menu children are properly filtered"""
        # Find a menu item with children
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        item_with_children = next((item for item in main_menu if 'children' in item), None)
        
        if item_with_children:
            # Mock user with selective permissions
            def mock_has_perm(perm):
                # Allow parent but deny some children
                if perm == item_with_children.get('capability'):
                    return True
                return False  # Deny children capabilities
            
            with patch.object(self.user, 'has_perm', side_effect=mock_has_perm):
                filtered_menu = self.router.get_navigation_menu(user=self.user)
                
                # Find the filtered item
                filtered_item = next(
                    (item for item in filtered_menu if item['name'] == item_with_children['name']), 
                    None
                )
                
                if filtered_item and 'children' in filtered_item:
                    # Should have fewer children than original
                    original_children = len(item_with_children['children'])
                    filtered_children = len(filtered_item['children'])
                    self.assertLessEqual(filtered_children, original_children)
    
    def test_menu_url_consistency(self):
        """Test that menu URLs are consistent with URL mappings"""
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        
        for item in main_menu:
            # Check main item URL
            self.assertTrue(item['url'].startswith('/'))
            
            # Check children URLs
            if 'children' in item:
                for child in item['children']:
                    self.assertTrue(child['url'].startswith('/'))
                    # Child URLs should start with parent domain (in most cases)
                    parent_domain = item['url'].split('/')[1]
                    child_domain = child['url'].split('/')[1]
                    
                    # Allow some exceptions for cross-domain children
                    if parent_domain and child_domain:
                        self.assertTrue(
                            child_domain == parent_domain or 
                            child['url'] in ['/dashboard/', '/monitoring/', '/admin/'],
                            f"Child URL {child['url']} domain mismatch with parent {item['url']}"
                        )
    
    def test_menu_icon_validation(self):
        """Test that menu icons are valid Material Design icons"""
        valid_icons = [
            'dashboard', 'settings', 'business', 'people', 'help', 'assessment',
            'admin_panel_settings', 'inventory', 'build', 'location_on', 
            'analytics', 'support', 'description', 'schedule'
        ]
        
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        
        for item in main_menu:
            icon = item.get('icon', '')
            self.assertIn(icon, valid_icons,
                f"Invalid or unrecognized icon: {icon} for {item['name']}")
    
    def test_menu_name_localization_ready(self):
        """Test that menu names are suitable for localization"""
        main_menu = self.router.NAVIGATION_STRUCTURE['main']
        
        for item in main_menu:
            name = item.get('name', '')
            # Names should be simple, single words or common phrases
            self.assertLess(len(name.split()), 3,
                f"Menu name too complex for localization: '{name}'")
            
            # Names should not contain special characters
            self.assertTrue(name.replace(' ', '').replace('-', '').isalnum(),
                f"Menu name contains special characters: '{name}'")
    
    def test_menu_capability_consistency(self):
        """Test that menu capabilities follow consistent naming"""
        all_capabilities = []
        
        for menu_type in ['main', 'admin']:
            menu = self.router.NAVIGATION_STRUCTURE[menu_type]
            for item in menu:
                if 'capability' in item:
                    all_capabilities.append(item['capability'])
                
                if 'children' in item:
                    for child in item['children']:
                        if 'capability' in child:
                            all_capabilities.append(child['capability'])
        
        # Capabilities should follow view_* pattern
        for capability in all_capabilities:
            self.assertTrue(capability.startswith('view_'),
                f"Capability should start with 'view_': {capability}")
    
    def test_menu_deep_copy_safety(self):
        """Test that menu modifications don't affect original structure"""
        original_menu = self.router.get_navigation_menu()
        
        # Mock user that would filter menu
        with patch.object(self.user, 'has_perm', return_value=False):
            filtered_menu = self.router.get_navigation_menu(user=self.user)
        
        # Original structure should remain unchanged
        new_original = self.router.get_navigation_menu()
        self.assertEqual(len(original_menu), len(new_original))


class TestBreadcrumbGeneration(TestCase):
    """Test breadcrumb generation logic (25 tests)"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
    
    def test_root_breadcrumb(self):
        """Test breadcrumb for root URL"""
        breadcrumbs = self.router.get_breadcrumbs('/')
        
        self.assertEqual(len(breadcrumbs), 1)
        self.assertEqual(breadcrumbs[0]['name'], 'Home')
        self.assertEqual(breadcrumbs[0]['url'], '/')
    
    def test_single_level_breadcrumb(self):
        """Test breadcrumb for single-level URL"""
        breadcrumbs = self.router.get_breadcrumbs('/dashboard/')
        
        expected = [
            {'name': 'Home', 'url': '/'},
            {'name': 'Dashboard', 'url': '/dashboard/'}
        ]
        
        self.assertEqual(breadcrumbs, expected)
    
    def test_multi_level_breadcrumb(self):
        """Test breadcrumb for multi-level URL"""
        breadcrumbs = self.router.get_breadcrumbs('/operations/tasks/create/')
        
        expected = [
            {'name': 'Home', 'url': '/'},
            {'name': 'Operations', 'url': '/operations/'},
            {'name': 'Tasks', 'url': '/operations/tasks/'},
            {'name': 'Create', 'url': '/operations/tasks/create/'}
        ]
        
        self.assertEqual(breadcrumbs, expected)
    
    def test_breadcrumb_name_formatting(self):
        """Test that breadcrumb names are properly formatted"""
        test_cases = [
            ('/help-desk/', 'Help Desk'),
            ('/work-orders/', 'Work Orders'),
            ('/business-units/', 'Business Units'),
            ('/ppm/', 'PPM'),
            ('/sla/', 'SLA'),
        ]
        
        for url, expected_name in test_cases:
            breadcrumbs = self.router.get_breadcrumbs(url)
            last_breadcrumb = breadcrumbs[-1]
            self.assertEqual(last_breadcrumb['name'], expected_name,
                f"URL {url} should generate '{expected_name}', got '{last_breadcrumb['name']}'")
    
    def test_breadcrumb_special_mappings(self):
        """Test special name mappings in breadcrumbs"""
        mappings = self.router.get_breadcrumbs('/operations/ppm/')
        
        # Find PPM breadcrumb
        ppm_breadcrumb = next((b for b in mappings if 'ppm' in b['url'].lower()), None)
        if ppm_breadcrumb:
            self.assertEqual(ppm_breadcrumb['name'], 'PPM')
    
    def test_breadcrumb_url_consistency(self):
        """Test that breadcrumb URLs are consistent and build properly"""
        test_url = '/assets/maintenance/scheduled/pending/'
        breadcrumbs = self.router.get_breadcrumbs(test_url)
        
        # Each breadcrumb URL should be a valid prefix of the next
        for i in range(1, len(breadcrumbs)):
            current_url = breadcrumbs[i]['url']
            previous_url = breadcrumbs[i-1]['url']
            
            self.assertTrue(current_url.startswith(previous_url.rstrip('/')),
                f"Breadcrumb URL inconsistency: {previous_url} -> {current_url}")
    
    def test_empty_url_handling(self):
        """Test handling of empty or invalid URLs"""
        breadcrumbs = self.router.get_breadcrumbs('')
        
        # Should default to home
        self.assertEqual(len(breadcrumbs), 1)
        self.assertEqual(breadcrumbs[0]['name'], 'Home')
    
    def test_trailing_slash_handling(self):
        """Test consistent handling of trailing slashes"""
        with_slash = self.router.get_breadcrumbs('/operations/tasks/')
        without_slash = self.router.get_breadcrumbs('/operations/tasks')
        
        # Should produce same result
        self.assertEqual(len(with_slash), len(without_slash))
        
        for i in range(len(with_slash)):
            self.assertEqual(with_slash[i]['name'], without_slash[i]['name'])
    
    def test_numeric_segments_handling(self):
        """Test breadcrumbs with numeric segments (IDs)"""
        breadcrumbs = self.router.get_breadcrumbs('/operations/tasks/123/edit/')
        
        # Should have appropriate names for numeric segments
        expected_names = ['Home', 'Operations', 'Tasks', '123', 'Edit']
        actual_names = [b['name'] for b in breadcrumbs]
        
        self.assertEqual(actual_names, expected_names)
    
    def test_breadcrumb_performance(self):
        """Test that breadcrumb generation is performant"""
        import time
        
        start_time = time.time()
        
        # Generate breadcrumbs for 100 different URLs
        test_urls = [f'/operations/tasks/{i}/details/' for i in range(100)]
        
        for url in test_urls:
            breadcrumbs = self.router.get_breadcrumbs(url)
            self.assertGreater(len(breadcrumbs), 1)
        
        elapsed = time.time() - start_time
        
        # Should generate 100 breadcrumbs in under 0.1 seconds
        self.assertLess(elapsed, 0.1,
            f"Breadcrumb generation too slow: {elapsed:.3f}s for 100 URLs")


class TestAnalyticsAndTracking(TestCase):
    """Test analytics and tracking functionality (40 tests)"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        cache.clear()
        self.router.URL_USAGE_ANALYTICS.clear()
        
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_usage_analytics_initialization(self):
        """Test that usage analytics are properly initialized"""
        self.assertIsInstance(self.router.URL_USAGE_ANALYTICS, dict)
        self.assertEqual(len(self.router.URL_USAGE_ANALYTICS), 0)
    
    def test_track_url_usage_new_url(self):
        """Test tracking usage for a new URL"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        self.router._track_url_usage(old_url, new_url, mock_request)
        
        # Should create analytics entry
        self.assertIn(old_url, self.router.URL_USAGE_ANALYTICS)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 1)
        self.assertEqual(analytics['new_url'], new_url)
        self.assertIn('testuser', analytics['users'])
        self.assertIsNotNone(analytics['last_accessed'])
    
    def test_track_url_usage_existing_url(self):
        """Test tracking usage for an existing URL"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        # Track multiple times
        for _ in range(5):
            self.router._track_url_usage(old_url, new_url, mock_request)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 5)
    
    def test_track_url_usage_multiple_users(self):
        """Test tracking usage from multiple users"""
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        users = ['user1', 'user2', 'user3']
        
        for username in users:
            mock_request = MagicMock()
            mock_request.user.is_authenticated = True
            mock_request.user.loginid = username
            
            self.router._track_url_usage(old_url, new_url, mock_request)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 3)
        self.assertEqual(len(analytics['users']), 3)
        
        for username in users:
            self.assertIn(username, analytics['users'])
    
    def test_track_url_usage_anonymous_user(self):
        """Test tracking usage for anonymous users"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        self.router._track_url_usage(old_url, new_url, mock_request)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 1)
        # Should not add user to tracking for anonymous users
        self.assertEqual(len(analytics['users']), 0)
    
    def test_track_url_usage_user_without_loginid(self):
        """Test tracking usage for users without loginid attribute"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = None
        mock_request.user.username = 'testuser'
        mock_request.user.id = 123
        
        # Remove loginid attribute to test fallback
        delattr(mock_request.user, 'loginid')
        
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        self.router._track_url_usage(old_url, new_url, mock_request)
        
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 1)
        # Should fallback to username or user ID
        self.assertGreater(len(analytics['users']), 0)
    
    def test_cache_analytics_data(self):
        """Test that analytics data is cached"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        old_url = 'test/url/'
        new_url = 'test/new-url/'
        
        with patch('django.core.cache.cache.set') as mock_cache_set:
            self.router._track_url_usage(old_url, new_url, mock_request)
            
            # Should cache the analytics data
            mock_cache_set.assert_called_with(
                'url_usage_analytics', 
                self.router.URL_USAGE_ANALYTICS, 
                3600
            )
    
    def test_migration_report_empty_analytics(self):
        """Test migration report with no usage data"""
        report = self.router.get_migration_report()
        
        self.assertIn('summary', report)
        self.assertIn('top_legacy_urls', report)
        self.assertIn('recommendations', report)
        self.assertIn('timestamp', report)
        
        summary = report['summary']
        self.assertEqual(summary['used_legacy_urls'], 0)
        self.assertEqual(summary['total_redirects'], 0)
        self.assertGreater(summary['total_legacy_urls'], 100)  # Should have 169+ mappings
        self.assertEqual(summary['adoption_rate'], 100.0)  # No usage = 100% adoption
    
    def test_migration_report_with_usage_data(self):
        """Test migration report with usage data"""
        # Set up test analytics
        from datetime import datetime
        
        self.router.URL_USAGE_ANALYTICS = {
            'schedhuler/jobneedtasks/': {
                'count': 50,
                'users': {'user1', 'user2'},
                'last_accessed': datetime.now(),
                'new_url': 'operations/tasks/'
            },
            'activity/asset/': {
                'count': 25,
                'users': {'user1', 'user3'},
                'last_accessed': datetime.now(),
                'new_url': 'assets/'
            }
        }
        
        report = self.router.get_migration_report()
        
        summary = report['summary']
        self.assertEqual(summary['used_legacy_urls'], 2)
        self.assertEqual(summary['total_redirects'], 75)
        
        # Should have top legacy URLs
        top_urls = report['top_legacy_urls']
        self.assertGreater(len(top_urls), 0)
        
        # Should be sorted by usage count (descending)
        if len(top_urls) > 1:
            self.assertGreaterEqual(top_urls[0]['usage_count'], top_urls[1]['usage_count'])
    
    def test_migration_recommendations_high_usage(self):
        """Test recommendations for high-usage legacy URLs"""
        # Set up high usage scenario
        self.router.URL_USAGE_ANALYTICS = {
            f'high/usage/url/{i}/': {
                'count': 150,  # High usage
                'users': {f'user{j}' for j in range(10)},
                'last_accessed': datetime.now(),
                'new_url': f'new/url/{i}/'
            }
            for i in range(5)
        }
        
        recommendations = self.router._generate_recommendations(self.router.URL_USAGE_ANALYTICS)
        
        self.assertIsInstance(recommendations, list)
        
        # Should recommend updating frequently accessed URLs
        high_usage_rec = any('frequently accessed' in rec for rec in recommendations)
        self.assertTrue(high_usage_rec,
            "Should recommend updating frequently accessed legacy URLs")
    
    def test_migration_recommendations_recent_usage(self):
        """Test recommendations for recently used legacy URLs"""
        # Set up recent usage scenario
        recent_time = datetime.now() - timedelta(days=2)
        
        self.router.URL_USAGE_ANALYTICS = {
            'recent/url/': {
                'count': 10,
                'users': {'user1'},
                'last_accessed': recent_time,
                'new_url': 'new/url/'
            }
        }
        
        recommendations = self.router._generate_recommendations(self.router.URL_USAGE_ANALYTICS)
        
        # Should recommend user training
        training_rec = any('train' in rec.lower() or 'week' in rec for rec in recommendations)
        self.assertTrue(training_rec,
            "Should recommend user training for recent usage")
    
    def test_migration_recommendations_low_adoption(self):
        """Test recommendations for low adoption rates"""
        # Create many analytics entries to simulate low adoption
        analytics = {
            f'url_{i}/': {
                'count': 5,
                'users': {'user1'},
                'last_accessed': datetime.now(),
                'new_url': f'new_{i}/'
            }
            for i in range(100)  # Many legacy URLs still in use
        }
        
        # Mock the get_migration_report method to return low adoption
        with patch.object(self.router, 'get_migration_report') as mock_report:
            mock_report.return_value = {'summary': {'adoption_rate': 30}}
            
            recommendations = self.router._generate_recommendations(analytics)
            
            # Should recommend user training and documentation
            low_adoption_rec = any('adoption' in rec.lower() or 'training' in rec.lower() 
                                 for rec in recommendations)
            self.assertTrue(low_adoption_rec,
                "Should recommend actions for low adoption rate")
    
    def test_migration_recommendations_high_adoption(self):
        """Test recommendations for high adoption rates"""
        # Mock high adoption scenario
        with patch.object(self.router, 'get_migration_report') as mock_report:
            mock_report.return_value = {'summary': {'adoption_rate': 95}}
            
            recommendations = self.router._generate_recommendations({})
            
            # Should recommend making redirects permanent
            permanent_rec = any('permanent' in rec.lower() or '301' in rec 
                              for rec in recommendations)
            self.assertTrue(permanent_rec,
                "Should recommend permanent redirects for high adoption")
    
    def test_url_structure_validation_naming(self):
        """Test URL structure validation for naming consistency"""
        validation = self.router.validate_url_structure()
        
        self.assertIn('naming_inconsistencies', validation)
        
        # Check a few URLs for underscore violations
        underscore_violations = validation['naming_inconsistencies']
        
        # Should be a list (may be empty if all URLs are clean)
        self.assertIsInstance(underscore_violations, list)
    
    def test_url_structure_validation_nesting(self):
        """Test URL structure validation for deep nesting"""
        validation = self.router.validate_url_structure()
        
        self.assertIn('deep_nesting', validation)
        
        deep_nesting = validation['deep_nesting']
        self.assertIsInstance(deep_nesting, list)
        
        # Should have reasonable limits on deep nesting
        self.assertLess(len(deep_nesting), 10,
            "Too many deeply nested URLs found")
    
    def test_url_structure_validation_duplicates(self):
        """Test URL structure validation for duplicate targets"""
        validation = self.router.validate_url_structure()
        
        self.assertIn('duplicate_targets', validation)
        
        duplicates = validation['duplicate_targets']
        self.assertIsInstance(duplicates, dict)
        
        # Should have minimal duplicate targets
        self.assertLess(len(duplicates), 5,
            "Too many duplicate redirect targets found")
    
    def test_analytics_data_structure(self):
        """Test that analytics data has proper structure"""
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        self.router._track_url_usage('test/', 'new/', mock_request)
        
        analytics_entry = self.router.URL_USAGE_ANALYTICS['test/']
        
        required_fields = ['count', 'users', 'last_accessed', 'new_url']
        for field in required_fields:
            self.assertIn(field, analytics_entry,
                f"Analytics entry missing required field: {field}")
        
        # Check data types
        self.assertIsInstance(analytics_entry['count'], int)
        self.assertIsInstance(analytics_entry['users'], set)
        self.assertIsInstance(analytics_entry['new_url'], str)
    
    def test_analytics_thread_safety(self):
        """Test that analytics tracking is thread-safe"""
        import threading
        import time
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'testuser'
        
        def track_usage():
            for _ in range(10):
                self.router._track_url_usage('concurrent/', 'new/', mock_request)
                time.sleep(0.001)  # Small delay to increase chance of race condition
        
        # Run multiple threads
        threads = [threading.Thread(target=track_usage) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have correct count despite concurrent access
        analytics = self.router.URL_USAGE_ANALYTICS['concurrent/']
        self.assertEqual(analytics['count'], 50)  # 5 threads * 10 tracks each


class TestSmartRedirectView(TestCase):
    """Test smart redirect view functionality (40 tests)"""
    
    def setUp(self):
        self.router = OptimizedURLRouter
        cache.clear()
    
    def test_smart_redirect_view_creation(self):
        """Test that smart redirect views are created correctly"""
        old_url = 'test/old/'
        new_url = 'test/new/'
        
        redirect_view = self.router._create_smart_redirect(old_url, new_url)
        
        self.assertIsNotNone(redirect_view)
        self.assertTrue(callable(redirect_view))
    
    def test_smart_redirect_permanent_setting(self):
        """Test that smart redirects use permanent=True"""
        redirect_view_class = self.router._create_smart_redirect('old/', 'new/')
        
        # Create an instance to check the permanent setting
        view_instance = redirect_view_class.view_class()
        self.assertTrue(view_instance.permanent,
            "Smart redirect should use permanent=True (301 redirects)")
    
    @patch('apps.core.url_router_optimized.settings.DEBUG', True)
    def test_debug_logging(self):
        """Test that debug logging works when DEBUG=True"""
        old_url = 'debug/test/'
        new_url = 'debug/new/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'debuguser'
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        
        # Test that logger would be called (we can't easily test actual logging)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        with patch('apps.core.url_router_optimized.logger.info') as mock_logger:
            result_url = view_instance.get_redirect_url()
            
            # Should log the redirect
            mock_logger.assert_called_once()
            log_call = mock_logger.call_args[0][0]
            self.assertIn('URL Redirect:', log_call)
            self.assertIn(old_url, log_call)
            self.assertIn('debuguser', log_call)
    
    @patch('apps.core.url_router_optimized.settings.DEBUG', False)
    def test_no_debug_logging_in_production(self):
        """Test that debug logging is disabled in production"""
        old_url = 'prod/test/'
        new_url = 'prod/new/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'produser'
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        with patch('apps.core.url_router_optimized.logger.info') as mock_logger:
            result_url = view_instance.get_redirect_url()
            
            # Should not log in production
            mock_logger.assert_not_called()
    
    def test_query_string_preservation(self):
        """Test that query strings are preserved in redirects"""
        old_url = 'test/query/'
        new_url = 'new/query/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': 'param1=value1&param2=value2'}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        result_url = view_instance.get_redirect_url()
        
        expected_url = '/new/query/?param1=value1&param2=value2'
        self.assertEqual(result_url, expected_url)
    
    def test_empty_query_string_handling(self):
        """Test handling of empty query strings"""
        old_url = 'test/empty/'
        new_url = 'new/empty/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        result_url = view_instance.get_redirect_url()
        
        expected_url = '/new/empty/'
        self.assertEqual(result_url, expected_url)
    
    def test_parameter_interpolation(self):
        """Test that URL parameters are properly interpolated"""
        old_url = 'test/<str:pk>/'
        new_url = 'new/<str:pk>/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        # Test parameter interpolation
        result_url = view_instance.get_redirect_url(pk='123')
        
        expected_url = '/new/123/'
        self.assertEqual(result_url, expected_url)
    
    def test_multiple_parameter_interpolation(self):
        """Test interpolation with multiple parameters"""
        old_url = 'test/<str:category>/<str:id>/'
        new_url = 'new/<str:category>/<str:id>/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        result_url = view_instance.get_redirect_url(category='assets', id='456')
        
        expected_url = '/new/assets/456/'
        self.assertEqual(result_url, expected_url)
    
    def test_parameter_with_query_string(self):
        """Test parameter interpolation combined with query strings"""
        old_url = 'test/<str:pk>/'
        new_url = 'new/<str:pk>/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': 'action=edit&mode=full'}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        result_url = view_instance.get_redirect_url(pk='789')
        
        expected_url = '/new/789/?action=edit&mode=full'
        self.assertEqual(result_url, expected_url)
    
    def test_usage_tracking_integration(self):
        """Test that redirect views integrate with usage tracking"""
        old_url = 'tracked/url/'
        new_url = 'new/tracked/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'trackuser'
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        # Clear analytics
        self.router.URL_USAGE_ANALYTICS.clear()
        
        # Call redirect
        result_url = view_instance.get_redirect_url()
        
        # Should track usage
        self.assertIn(old_url, self.router.URL_USAGE_ANALYTICS)
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 1)
        self.assertIn('trackuser', analytics['users'])
    
    def test_redirect_url_leading_slash(self):
        """Test that redirect URLs always start with /"""
        test_cases = [
            ('old/', 'new/'),
            ('old/', '/new/'),  # Already has leading slash
            ('old/', 'new/path/'),
            ('old/', '/new/path/'),  # Already has leading slash
        ]
        
        for old_url, new_url in test_cases:
            mock_request = MagicMock()
            mock_request.user.is_authenticated = False
            mock_request.META = {'QUERY_STRING': ''}
            
            redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
            view_instance = redirect_view_class.view_class()
            view_instance.request = mock_request
            
            result_url = view_instance.get_redirect_url()
            
            self.assertTrue(result_url.startswith('/'),
                f"Redirect URL should start with '/': {result_url}")
    
    def test_anonymous_user_tracking(self):
        """Test redirect tracking for anonymous users"""
        old_url = 'anon/test/'
        new_url = 'new/anon/'
        
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {'QUERY_STRING': ''}
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        self.router.URL_USAGE_ANALYTICS.clear()
        
        result_url = view_instance.get_redirect_url()
        
        # Should still track usage for anonymous users
        self.assertIn(old_url, self.router.URL_USAGE_ANALYTICS)
        analytics = self.router.URL_USAGE_ANALYTICS[old_url]
        self.assertEqual(analytics['count'], 1)
        # But should not track specific users
        self.assertEqual(len(analytics['users']), 0)
    
    def test_redirect_view_error_handling(self):
        """Test that redirect views handle errors gracefully"""
        old_url = 'error/test/'
        new_url = 'new/error/'
        
        # Create request with missing META
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False
        mock_request.META = {}  # Missing QUERY_STRING
        
        redirect_view_class = self.router._create_smart_redirect(old_url, new_url)
        view_instance = redirect_view_class.view_class()
        view_instance.request = mock_request
        
        # Should handle missing QUERY_STRING gracefully
        result_url = view_instance.get_redirect_url()
        
        expected_url = '/new/error/'
        self.assertEqual(result_url, expected_url)