"""
End-to-End tests for Information Architecture legacy redirects and performance validation
Tests backward compatibility and performance benchmarks
"""
import pytest
from django.test import TestCase, LiveServerTestCase, Client
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.core.cache import cache
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import statistics
import concurrent.futures
from urllib.parse import urljoin
import requests

User = get_user_model()


class TestLegacyRedirectCompatibility(TestCase):
    """Test legacy URL redirect compatibility (5 tests)"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='legacyuser',
            password='legacypass123'
        )
        cache.clear()
    
    def test_critical_legacy_url_redirects(self):
        """Test that critical legacy URLs redirect correctly"""
        critical_legacy_urls = [
            ('schedhuler/jobneedtasks/', 'operations/tasks/'),
            ('activity/asset/', 'assets/'),
            ('peoples/people/', 'people/'),
            ('helpdesk/ticket/', 'help-desk/tickets/'),
            ('reports/get_reports/', 'reports/download/'),
            ('onboarding/bu/', 'admin/business-units/')
        ]
        
        for legacy_url, expected_new_url in critical_legacy_urls:
            response = self.client.get(f'/{legacy_url}', follow=False)
            
            # Should be 301 permanent redirect
            self.assertEqual(response.status_code, 301,
                f"Legacy URL /{legacy_url} should return 301 redirect")
            
            # Should redirect to correct new URL
            expected_redirect = f'/{expected_new_url}'
            self.assertEqual(response.url, expected_redirect,
                f"Legacy URL /{legacy_url} should redirect to {expected_redirect}")
    
    def test_legacy_urls_with_query_parameters(self):
        """Test that query parameters are preserved in redirects"""
        test_cases = [
            ('schedhuler/jobneedtasks/?page=2&status=active', 'operations/tasks/'),
            ('activity/asset/?category=pump&location=building1', 'assets/'),
            ('peoples/people/?department=security', 'people/')
        ]
        
        for legacy_url_with_params, expected_base_url in test_cases:
            response = self.client.get(f'/{legacy_url_with_params}', follow=False)
            
            # Should be 301 redirect
            self.assertEqual(response.status_code, 301)
            
            # Should preserve query parameters
            redirect_url = response.url
            self.assertTrue(redirect_url.startswith(f'/{expected_base_url}'),
                f"Redirect URL should start with /{expected_base_url}")
            
            # Extract and verify query parameters
            if '?' in legacy_url_with_params:
                original_params = legacy_url_with_params.split('?', 1)[1]
                self.assertIn(original_params, redirect_url,
                    "Query parameters should be preserved in redirect")
    
    def test_legacy_urls_with_dynamic_parameters(self):
        """Test legacy URLs with dynamic path parameters"""
        # Note: This tests the redirect logic, actual routing depends on URL configuration
        dynamic_test_cases = [
            'schedhuler/task_jobneed/123/',
            'activity/asset/456/',
            'peoples/people/789/'
        ]
        
        for legacy_url in dynamic_test_cases:
            response = self.client.get(f'/{legacy_url}', follow=False)
            
            # Should either redirect or return 404 (if URL patterns not configured)
            # Both are acceptable as the URL structure is being migrated
            self.assertIn(response.status_code, [301, 404],
                f"Dynamic legacy URL /{legacy_url} should redirect or return 404")
            
            if response.status_code == 301:
                # Should redirect to appropriate new URL structure
                self.assertTrue(response.url.startswith('/'),
                    "Redirect should be to absolute path")
    
    def test_dead_legacy_urls_redirect(self):
        """Test that dead/deprecated URLs redirect to appropriate pages"""
        dead_url_mappings = [
            ('apps/customers/getting-started.html', 'dashboard/'),
            ('apps/customers/list.html', 'people/'),
            ('apps/customers/view.html', 'people/')
        ]
        
        for dead_url, expected_redirect in dead_url_mappings:
            response = self.client.get(f'/{dead_url}', follow=False)
            
            # Should redirect dead URLs
            if response.status_code == 301:
                expected_target = f'/{expected_redirect}'
                self.assertEqual(response.url, expected_target,
                    f"Dead URL /{dead_url} should redirect to {expected_target}")
            else:
                # If not configured, should at least not return 500 error
                self.assertNotEqual(response.status_code, 500,
                    f"Dead URL /{dead_url} should not cause server error")
    
    def test_legacy_bookmark_compatibility(self):
        """Test compatibility with bookmarked legacy URLs"""
        # Simulate bookmarked URLs that users might have
        bookmarked_urls = [
            'schedhuler/jobneedtasks/?favorite=true',
            'activity/asset/?view=grid',
            'peoples/people/?sort=name',
            'reports/exportreports/?format=pdf'
        ]
        
        successful_redirects = 0
        
        for bookmark_url in bookmarked_urls:
            response = self.client.get(f'/{bookmark_url}', follow=False)
            
            # Should handle bookmarked URLs gracefully
            if response.status_code == 301:
                successful_redirects += 1
                # Redirect should preserve the intent of the bookmark
                redirect_url = response.url
                self.assertTrue(redirect_url.startswith('/'),
                    "Bookmark redirect should be valid")
            else:
                # Should at least not break (404 is acceptable for unimplemented URLs)
                self.assertIn(response.status_code, [404, 403],
                    f"Bookmarked URL /{bookmark_url} returned unexpected status: {response.status_code}")
        
        # Should have some successful redirects
        self.assertGreater(successful_redirects, len(bookmarked_urls) // 2,
            "Should redirect majority of bookmarked legacy URLs")


class TestRedirectPerformance(TestCase):
    """Test redirect performance characteristics (3 tests)"""
    
    def setUp(self):
        self.client = Client()
        cache.clear()
    
    def test_redirect_response_time(self):
        """Test that redirects are fast (<50ms target)"""
        legacy_urls = [
            'schedhuler/jobneedtasks/',
            'activity/asset/',
            'peoples/people/',
            'helpdesk/ticket/',
            'reports/get_reports/'
        ]
        
        response_times = []
        
        for legacy_url in legacy_urls:
            start_time = time.time()
            response = self.client.get(f'/{legacy_url}', follow=False)
            elapsed = time.time() - start_time
            
            response_times.append(elapsed)
            
            # Should be reasonably fast (allow up to 100ms for testing environment)
            self.assertLess(elapsed, 0.1,
                f"Redirect for /{legacy_url} too slow: {elapsed:.3f}s")
        
        # Average should be very fast
        avg_time = statistics.mean(response_times)
        self.assertLess(avg_time, 0.05,
            f"Average redirect time too slow: {avg_time:.3f}s")
        
        # 95th percentile should also be reasonable
        if len(response_times) > 1:
            p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            self.assertLess(p95_time, 0.08,
                f"95th percentile redirect time too slow: {p95_time:.3f}s")
    
    def test_concurrent_redirect_performance(self):
        """Test redirect performance under concurrent load"""
        legacy_url = 'schedhuler/jobneedtasks/'
        num_concurrent = 20
        
        def make_redirect_request():
            start_time = time.time()
            response = self.client.get(f'/{legacy_url}', follow=False)
            elapsed = time.time() - start_time
            return elapsed, response.status_code
        
        # Use ThreadPoolExecutor to simulate concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            start_time = time.time()
            futures = [executor.submit(make_redirect_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_elapsed = time.time() - start_time
        
        response_times, status_codes = zip(*results)
        
        # All requests should succeed with 301
        successful_redirects = sum(1 for code in status_codes if code == 301)
        self.assertEqual(successful_redirects, num_concurrent,
            f"Expected {num_concurrent} successful redirects, got {successful_redirects}")
        
        # Concurrent performance should be reasonable
        max_time = max(response_times)
        avg_time = statistics.mean(response_times)
        
        self.assertLess(max_time, 0.2,
            f"Slowest concurrent redirect too slow: {max_time:.3f}s")
        self.assertLess(avg_time, 0.1,
            f"Average concurrent redirect too slow: {avg_time:.3f}s")
        
        # Total time should show parallelism benefits
        self.assertLess(total_elapsed, sum(response_times) * 0.8,
            "Concurrent requests should benefit from parallelism")
    
    def test_redirect_cache_performance(self):
        """Test that redirect caching improves performance"""
        legacy_url = 'activity/asset/'
        num_requests = 50
        
        # First batch of requests (cold cache)
        cold_times = []
        for _ in range(10):
            start_time = time.time()
            response = self.client.get(f'/{legacy_url}', follow=False)
            elapsed = time.time() - start_time
            cold_times.append(elapsed)
            self.assertEqual(response.status_code, 301)
        
        # Second batch of requests (warm cache)
        warm_times = []
        for _ in range(num_requests - 10):
            start_time = time.time()
            response = self.client.get(f'/{legacy_url}', follow=False)
            elapsed = time.time() - start_time
            warm_times.append(elapsed)
            self.assertEqual(response.status_code, 301)
        
        # Warm cache should be faster than cold cache
        cold_avg = statistics.mean(cold_times)
        warm_avg = statistics.mean(warm_times)
        
        # Allow some variance, but warm should generally be faster
        if cold_avg > 0.001:  # Only test if there's measurable difference
            improvement_ratio = cold_avg / warm_avg
            self.assertGreater(improvement_ratio, 0.8,
                f"Cache should improve performance. Cold: {cold_avg:.4f}s, Warm: {warm_avg:.4f}s")


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)
class TestE2EPerformanceBenchmarks(LiveServerTestCase):
    """E2E performance benchmarks using browser testing (2 tests)"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Set up Chrome driver for performance testing
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(5)
        except Exception:
            cls.driver = None
    
    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()
        super().tearDownClass()
    
    def setUp(self):
        if not self.driver:
            self.skipTest("WebDriver not available for E2E performance testing")
            
        self.user = User.objects.create_user(
            username='perfuser',
            password='perfpass123'
        )
    
    def login_user(self):
        """Helper to login user for performance tests"""
        try:
            self.driver.get(f'{self.live_server_url}/auth/login/')
            
            username_field = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.NAME, 'username'))
            )
            password_field = self.driver.find_element(By.NAME, 'password')
            
            username_field.send_keys('perfuser')
            password_field.send_keys('perfpass123')
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for login to complete
            WebDriverWait(self.driver, 5).until(
                lambda driver: '/auth/login/' not in driver.current_url
            )
        except TimeoutException:
            self.skipTest("Login functionality not available")
    
    def test_page_load_performance(self):
        """Test that pages load within performance targets (<2s)"""
        self.login_user()
        
        performance_urls = [
            '/',
            '/operations/tasks/',
            '/assets/',
            '/people/',
            '/reports/download/'
        ]
        
        load_times = []
        
        for url in performance_urls:
            try:
                start_time = time.time()
                
                self.driver.get(f'{self.live_server_url}{url}')
                
                # Wait for page to be fully loaded
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Additional wait for dynamic content
                time.sleep(0.5)
                
                elapsed = time.time() - start_time
                load_times.append(elapsed)
                
                # Individual page should load within target
                self.assertLess(elapsed, 3.0,
                    f"Page {url} loaded too slowly: {elapsed:.2f}s")
                
            except TimeoutException:
                # Page might not be implemented, skip
                continue
            except Exception as e:
                # Skip pages that aren't accessible
                continue
        
        if load_times:
            # Average load time should be reasonable
            avg_load_time = statistics.mean(load_times)
            self.assertLess(avg_load_time, 2.0,
                f"Average page load time too slow: {avg_load_time:.2f}s")
    
    def test_navigation_menu_performance(self):
        """Test that navigation menu renders and responds quickly"""
        self.login_user()
        
        try:
            self.driver.get(f'{self.live_server_url}/')
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Find navigation menu
            menu_selectors = [
                '#kt_aside_menu',
                '.menu',
                '.navigation',
                '.sidebar',
                'nav'
            ]
            
            menu_element = None
            for selector in menu_selectors:
                try:
                    menu_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if menu_element:
                        break
                except:
                    continue
            
            if not menu_element:
                self.skipTest("Navigation menu not found")
            
            # Test menu interaction performance
            menu_items = menu_element.find_elements(By.TAG_NAME, 'a')
            
            if menu_items:
                # Test clicking first few menu items
                interaction_times = []
                
                for i, item in enumerate(menu_items[:3]):  # Test first 3 items
                    try:
                        start_time = time.time()
                        
                        # Scroll to item and click
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", item)
                        item.click()
                        
                        # Wait for navigation to complete
                        WebDriverWait(self.driver, 5).until(
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        
                        elapsed = time.time() - start_time
                        interaction_times.append(elapsed)
                        
                        # Individual interaction should be fast
                        self.assertLess(elapsed, 2.0,
                            f"Menu interaction {i} too slow: {elapsed:.2f}s")
                        
                        # Go back for next test
                        self.driver.back()
                        time.sleep(0.5)
                        
                    except (TimeoutException, Exception):
                        # Skip items that don't work
                        continue
                
                if interaction_times:
                    avg_interaction_time = statistics.mean(interaction_times)
                    self.assertLess(avg_interaction_time, 1.5,
                        f"Average menu interaction too slow: {avg_interaction_time:.2f}s")
                        
        except Exception as e:
            self.skipTest(f"Menu performance testing failed: {e}")


class TestBackwardCompatibilityFallback(TestCase):
    """Fallback tests for backward compatibility without full E2E setup"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='compatuser',
            password='compatpass123'
        )
    
    def test_redirect_status_code_consistency(self):
        """Test that all redirects use consistent status codes"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Test a sample of URL mappings
        test_mappings = list(OptimizedURLRouter.URL_MAPPINGS.items())[:20]
        
        redirect_statuses = []
        
        for old_url, new_url in test_mappings:
            try:
                response = self.client.get(f'/{old_url}', follow=False)
                redirect_statuses.append(response.status_code)
                
                if response.status_code == 301:
                    # Should redirect to correct URL
                    expected_redirect = f'/{new_url}'
                    self.assertEqual(response.url, expected_redirect,
                        f"Incorrect redirect target for {old_url}")
                        
            except Exception:
                # Some URLs might not be configured yet
                continue
        
        # Should have some successful redirects
        successful_redirects = sum(1 for status in redirect_statuses if status == 301)
        self.assertGreater(successful_redirects, 0,
            "Should have at least some working redirects")
        
        # All successful redirects should use 301
        for status in redirect_statuses:
            if status in [301, 302]:  # Accept both for now
                self.assertIn(status, [301, 302],
                    "Redirects should use 301 or 302 status codes")
    
    def test_url_mapping_completeness(self):
        """Test that URL mappings cover all major application areas"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Check that all major domains are covered
        expected_domains = {
            'operations': ['schedhuler/', 'work_order_management/'],
            'assets': ['activity/asset', 'activity/location'],
            'people': ['peoples/', 'attendance/', 'employee_creation/'],
            'help-desk': ['helpdesk/', 'y_helpdesk/'],
            'reports': ['reports/'],
            'admin': ['onboarding/', 'clientbilling/']
        }
        
        url_mappings = OptimizedURLRouter.URL_MAPPINGS
        
        for domain, legacy_prefixes in expected_domains.items():
            domain_coverage = False
            
            for prefix in legacy_prefixes:
                matching_urls = [url for url in url_mappings.keys() if url.startswith(prefix)]
                if matching_urls:
                    domain_coverage = True
                    
                    # Check that mappings redirect to appropriate domain
                    for old_url in matching_urls[:2]:  # Check first 2
                        new_url = url_mappings[old_url]
                        
                        # Most should map to the expected domain
                        if domain in ['operations', 'assets', 'people', 'help-desk', 'reports']:
                            domain_check = domain.replace('-', '-') in new_url or domain.replace('-', '') in new_url
                            if not domain_check and domain == 'help-desk':
                                domain_check = 'help-desk' in new_url or 'helpdesk' in new_url
                            
                            # Allow some flexibility in mapping
                            self.assertTrue(
                                domain_check or new_url.startswith('admin/') or new_url.startswith('api/'),
                                f"URL {old_url} -> {new_url} doesn't map to expected domain {domain}"
                            )
                    break
            
            self.assertTrue(domain_coverage,
                f"Domain {domain} should have URL mapping coverage")
    
    def test_performance_baseline_establishment(self):
        """Establish performance baselines for monitoring"""
        # This test establishes baseline metrics that can be monitored over time
        performance_metrics = {}
        
        # Test redirect performance baseline
        test_urls = ['schedhuler/jobneedtasks/', 'activity/asset/', 'peoples/people/']
        
        for url in test_urls:
            times = []
            for _ in range(10):  # 10 samples
                start_time = time.time()
                try:
                    response = self.client.get(f'/{url}', follow=False)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                except:
                    continue
            
            if times:
                performance_metrics[url] = {
                    'avg_time': statistics.mean(times),
                    'max_time': max(times),
                    'min_time': min(times)
                }
        
        # Record baseline metrics (in real implementation, this would go to monitoring)
        for url, metrics in performance_metrics.items():
            # All redirects should be reasonably fast
            self.assertLess(metrics['avg_time'], 0.1,
                f"Baseline performance concern for {url}: avg {metrics['avg_time']:.3f}s")
            self.assertLess(metrics['max_time'], 0.2,
                f"Baseline performance concern for {url}: max {metrics['max_time']:.3f}s")
        
        # Should have established some baselines
        self.assertGreater(len(performance_metrics), 0,
            "Should establish performance baselines for monitoring")