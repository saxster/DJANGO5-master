"""
Performance benchmarking tests for Information Architecture implementation
Tests performance across URL routing, template rendering, analytics, and system load
"""
import pytest
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template import loader
from django.utils import timezone
from unittest.mock import patch, MagicMock
import time
import statistics
import concurrent.futures
import threading
import gc
import psutil
import os
from datetime import datetime, timedelta

User = get_user_model()


@pytest.mark.performance
class TestURLRoutingPerformance(TestCase):
    """Test URL routing and redirect performance (8 tests)"""
    
    def setUp(self):
        self.client = Client()
        cache.clear()
        
        # Force garbage collection for consistent memory testing
        gc.collect()
    
    def test_url_redirect_latency(self):
        """Test that URL redirects meet latency requirements (<50ms)"""
        legacy_urls = [
            'schedhuler/jobneedtasks/',
            'activity/asset/',
            'peoples/people/',
            'helpdesk/ticket/',
            'reports/get_reports/',
            'onboarding/bu/',
            'activity/ppm/',
            'attendance/attendance_view/',
            'work_order_management/workorder/',
            'clientbilling/listclient/'
        ]
        
        latencies = []
        
        for url in legacy_urls:
            # Warm up
            self.client.get(f'/{url}', follow=False)
            
            # Measure latency
            start_time = time.perf_counter()
            response = self.client.get(f'/{url}', follow=False)
            elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
            
            latencies.append(elapsed)
            
            # Individual redirect should be fast
            self.assertLess(elapsed, 50.0,
                f"Redirect for /{url} too slow: {elapsed:.1f}ms")
        
        # Statistical analysis
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 5 else max(latencies)
        p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 10 else max(latencies)
        
        self.assertLess(avg_latency, 25.0,
            f"Average redirect latency too high: {avg_latency:.1f}ms")
        self.assertLess(p95_latency, 40.0,
            f"95th percentile latency too high: {p95_latency:.1f}ms")
        self.assertLess(p99_latency, 50.0,
            f"99th percentile latency too high: {p99_latency:.1f}ms")
    
    def test_url_routing_throughput(self):
        """Test URL routing throughput (requests per second)"""
        url = 'schedhuler/jobneedtasks/'
        duration = 5.0  # Test for 5 seconds
        
        start_time = time.perf_counter()
        request_count = 0
        
        while (time.perf_counter() - start_time) < duration:
            response = self.client.get(f'/{url}', follow=False)
            self.assertEqual(response.status_code, 301)
            request_count += 1
        
        elapsed = time.perf_counter() - start_time
        throughput = request_count / elapsed
        
        # Should handle at least 100 requests per second
        self.assertGreater(throughput, 100,
            f"URL routing throughput too low: {throughput:.1f} req/s")
    
    def test_concurrent_url_routing(self):
        """Test URL routing under concurrent load"""
        legacy_url = 'activity/asset/'
        num_threads = 20
        requests_per_thread = 10
        
        results = []
        errors = []
        
        def make_concurrent_requests(thread_id):
            thread_results = []
            try:
                for i in range(requests_per_thread):
                    start_time = time.perf_counter()
                    response = self.client.get(f'/{legacy_url}', follow=False)
                    elapsed = (time.perf_counter() - start_time) * 1000
                    
                    thread_results.append({
                        'thread_id': thread_id,
                        'request_id': i,
                        'elapsed_ms': elapsed,
                        'status_code': response.status_code
                    })
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")
            return thread_results
        
        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_concurrent_requests, i) for i in range(num_threads)]
            
            for future in concurrent.futures.as_completed(futures):
                thread_results = future.result()
                results.extend(thread_results)
        
        # Analyze results
        self.assertEqual(len(errors), 0, f"Concurrent request errors: {errors}")
        self.assertEqual(len(results), num_threads * requests_per_thread)
        
        # All requests should succeed
        successful_requests = [r for r in results if r['status_code'] == 301]
        success_rate = len(successful_requests) / len(results)
        self.assertGreater(success_rate, 0.95,
            f"Success rate too low under concurrent load: {success_rate:.2%}")
        
        # Performance should remain reasonable
        latencies = [r['elapsed_ms'] for r in successful_requests]
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        self.assertLess(avg_latency, 100.0,
            f"Average latency under concurrent load too high: {avg_latency:.1f}ms")
        self.assertLess(max_latency, 200.0,
            f"Max latency under concurrent load too high: {max_latency:.1f}ms")
    
    def test_url_mapping_lookup_performance(self):
        """Test URL mapping dictionary lookup performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        mappings = OptimizedURLRouter.URL_MAPPINGS
        test_urls = list(mappings.keys())[:50]  # Test first 50 mappings
        
        # Test lookup performance
        start_time = time.perf_counter()
        
        for _ in range(1000):  # 1000 iterations
            for url in test_urls:
                new_url = mappings.get(url)
                self.assertIsNotNone(new_url)
        
        elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        # 50,000 lookups should be very fast
        self.assertLess(elapsed, 100.0,
            f"URL mapping lookups too slow: {elapsed:.1f}ms for 50,000 lookups")
        
        # Calculate lookups per millisecond
        lookups_per_ms = 50000 / elapsed
        self.assertGreater(lookups_per_ms, 500,
            f"Lookup performance too low: {lookups_per_ms:.0f} lookups/ms")
    
    def test_redirect_view_creation_performance(self):
        """Test redirect view creation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        test_mappings = list(OptimizedURLRouter.URL_MAPPINGS.items())[:20]
        
        start_time = time.perf_counter()
        
        views = []
        for old_url, new_url in test_mappings:
            view = OptimizedURLRouter._create_smart_redirect(old_url, new_url)
            views.append(view)
            self.assertIsNotNone(view)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # Creating 20 redirect views should be fast
        self.assertLess(elapsed, 50.0,
            f"Redirect view creation too slow: {elapsed:.1f}ms for 20 views")
        
        # Views should be callable
        for view in views:
            self.assertTrue(callable(view))
    
    def test_pattern_generation_performance(self):
        """Test URL pattern generation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        start_time = time.perf_counter()
        patterns = OptimizedURLRouter.get_optimized_patterns()
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # Pattern generation should be fast
        self.assertLess(elapsed, 500.0,
            f"Pattern generation too slow: {elapsed:.1f}ms")
        
        # Should generate patterns for all mappings
        self.assertGreater(len(patterns), 100,
            f"Expected >100 patterns, got {len(patterns)}")
    
    def test_memory_usage_url_routing(self):
        """Test memory usage during URL routing operations"""
        process = psutil.Process(os.getpid())
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many URL routing operations
        for i in range(1000):
            url = f'schedhuler/jobneedtasks/?page={i}'
            response = self.client.get(f'/{url}', follow=False)
            
            # Periodically check memory growth
            if i % 200 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Memory growth should be reasonable
                self.assertLess(memory_growth, 50.0,
                    f"Excessive memory growth during URL routing: {memory_growth:.1f}MB")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        self.assertLess(total_growth, 100.0,
            f"Total memory growth too high: {total_growth:.1f}MB")
    
    def test_cache_efficiency_url_routing(self):
        """Test caching efficiency in URL routing"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Clear analytics
        OptimizedURLRouter.URL_USAGE_ANALYTICS.clear()
        cache.clear()
        
        url = 'activity/asset/'
        
        # First requests (cold cache)
        cold_times = []
        for _ in range(10):
            start_time = time.perf_counter()
            response = self.client.get(f'/{url}', follow=False)
            elapsed = (time.perf_counter() - start_time) * 1000
            cold_times.append(elapsed)
        
        # Subsequent requests (warm cache)
        warm_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            response = self.client.get(f'/{url}', follow=False)
            elapsed = (time.perf_counter() - start_time) * 1000
            warm_times.append(elapsed)
        
        # Analyze cache efficiency
        cold_avg = statistics.mean(cold_times)
        warm_avg = statistics.mean(warm_times)
        
        # Warm requests should generally be faster
        if cold_avg > 1.0:  # Only test if there's measurable difference
            cache_improvement = (cold_avg - warm_avg) / cold_avg
            self.assertGreater(cache_improvement, -0.5,  # Allow some variance
                f"Cache should not significantly slow down requests")


@pytest.mark.performance
class TestNavigationAnalyticsPerformance(TestCase):
    """Test navigation analytics performance (5 tests)"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='perfuser',
            password='perfpass123'
        )
        cache.clear()
        
        from apps.core.url_router_optimized import OptimizedURLRouter
        OptimizedURLRouter.URL_USAGE_ANALYTICS.clear()
    
    def test_analytics_tracking_performance(self):
        """Test analytics tracking performance overhead"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        mock_request = MagicMock()
        mock_request.user = self.user
        mock_request.user.is_authenticated = True
        mock_request.user.loginid = 'perfuser'
        
        # Test tracking performance
        start_time = time.perf_counter()
        
        for i in range(1000):
            url = f'test/url/{i}/'
            OptimizedURLRouter._track_url_usage(url, f'new/url/{i}/', mock_request)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # 1000 tracking operations should be fast
        self.assertLess(elapsed, 100.0,
            f"Analytics tracking too slow: {elapsed:.1f}ms for 1000 operations")
        
        # Verify data was tracked
        self.assertEqual(len(OptimizedURLRouter.URL_USAGE_ANALYTICS), 1000)
    
    def test_migration_report_generation_performance(self):
        """Test migration report generation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Set up large analytics dataset
        for i in range(500):
            OptimizedURLRouter.URL_USAGE_ANALYTICS[f'url_{i}/'] = {
                'count': i + 1,
                'users': {f'user{j}' for j in range(min(i % 10 + 1, 5))},
                'last_accessed': datetime.now() - timedelta(hours=i % 24),
                'new_url': f'new_url_{i}/'
            }
        
        # Test report generation performance
        start_time = time.perf_counter()
        report = OptimizedURLRouter.get_migration_report()
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # Report generation should be fast even with large dataset
        self.assertLess(elapsed, 200.0,
            f"Migration report generation too slow: {elapsed:.1f}ms")
        
        # Verify report completeness
        self.assertIn('summary', report)
        self.assertIn('top_legacy_urls', report)
        self.assertEqual(report['summary']['used_legacy_urls'], 500)
    
    def test_breadcrumb_generation_performance(self):
        """Test breadcrumb generation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        test_urls = [
            '/operations/tasks/create/',
            '/assets/maintenance/schedule/pending/',
            '/people/attendance/reports/monthly/',
            '/help-desk/tickets/escalation/urgent/',
            '/reports/download/schedule/weekly/',
            '/admin/business-units/configuration/advanced/'
        ]
        
        start_time = time.perf_counter()
        
        breadcrumbs_list = []
        for _ in range(200):  # Generate 200 sets of breadcrumbs
            for url in test_urls:
                breadcrumbs = OptimizedURLRouter.get_breadcrumbs(url)
                breadcrumbs_list.append(breadcrumbs)
                self.assertGreater(len(breadcrumbs), 1)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # 1200 breadcrumb generations should be fast
        self.assertLess(elapsed, 100.0,
            f"Breadcrumb generation too slow: {elapsed:.1f}ms for 1200 generations")
    
    def test_navigation_menu_generation_performance(self):
        """Test navigation menu generation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        users = [
            self.user,
            User.objects.create_user(username='staff', is_staff=True),
            User.objects.create_superuser(username='admin')
        ]
        
        start_time = time.perf_counter()
        
        menus = []
        for _ in range(100):  # Generate 100 sets of menus
            for user in users:
                main_menu = OptimizedURLRouter.get_navigation_menu(user=user, menu_type='main')
                admin_menu = OptimizedURLRouter.get_navigation_menu(user=user, menu_type='admin')
                menus.extend([main_menu, admin_menu])
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # 600 menu generations should be fast
        self.assertLess(elapsed, 200.0,
            f"Menu generation too slow: {elapsed:.1f}ms for 600 generations")
        
        # Verify menu structure
        self.assertEqual(len(menus), 600)
        for menu in menus[:10]:  # Spot check first 10
            self.assertIsInstance(menu, list)
    
    def test_url_structure_validation_performance(self):
        """Test URL structure validation performance"""
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        start_time = time.perf_counter()
        
        # Run validation multiple times
        for _ in range(10):
            validation = OptimizedURLRouter.validate_url_structure()
            
            self.assertIn('naming_inconsistencies', validation)
            self.assertIn('deep_nesting', validation)
            self.assertIn('duplicate_targets', validation)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # 10 validations should be reasonably fast
        self.assertLess(elapsed, 500.0,
            f"URL structure validation too slow: {elapsed:.1f}ms for 10 validations")


@pytest.mark.performance
class TestTemplateRenderingPerformance(TestCase):
    """Test template rendering performance (4 tests)"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='templateuser',
            password='templatepass123'
        )
        self.client = Client()
        cache.clear()
    
    def test_sidebar_template_rendering_performance(self):
        """Test sidebar template rendering performance"""
        try:
            template = loader.get_template('globals/sidebar_clean.html')
        except:
            self.skipTest("Sidebar template not found")
        
        from django.template import Context
        context = Context({
            'user': self.user,
            'request': MagicMock(),
            'navigation_menu': []
        })
        
        # Warm up template cache
        template.render(context)
        
        start_time = time.perf_counter()
        
        # Render template multiple times
        for _ in range(100):
            rendered = template.render(context)
            self.assertIsInstance(rendered, str)
            self.assertGreater(len(rendered), 0)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        
        # 100 sidebar renders should be fast
        self.assertLess(elapsed, 500.0,
            f"Sidebar template rendering too slow: {elapsed:.1f}ms for 100 renders")
    
    def test_template_compilation_cache_performance(self):
        """Test template compilation caching performance"""
        template_name = 'globals/sidebar_clean.html'
        
        # First load (compilation)
        start_time = time.perf_counter()
        try:
            template1 = loader.get_template(template_name)
            first_load_time = (time.perf_counter() - start_time) * 1000
        except:
            self.skipTest("Template not found")
        
        # Subsequent loads (cached)
        cached_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            template = loader.get_template(template_name)
            elapsed = (time.perf_counter() - start_time) * 1000
            cached_times.append(elapsed)
            
            self.assertEqual(template, template1)  # Should be same object
        
        avg_cached_time = statistics.mean(cached_times)
        
        # Cached loads should be much faster
        self.assertLess(avg_cached_time, first_load_time / 2,
            f"Template caching not effective: first={first_load_time:.1f}ms, avg_cached={avg_cached_time:.1f}ms")
        
        # Cached loads should be very fast
        self.assertLess(avg_cached_time, 1.0,
            f"Cached template loads too slow: {avg_cached_time:.1f}ms")
    
    def test_concurrent_template_rendering(self):
        """Test template rendering under concurrent load"""
        try:
            template = loader.get_template('globals/sidebar_clean.html')
        except:
            self.skipTest("Template not found")
        
        from django.template import Context
        
        def render_template(thread_id):
            results = []
            context = Context({
                'user': self.user,
                'request': MagicMock(),
                'thread_id': thread_id
            })
            
            for i in range(10):
                start_time = time.perf_counter()
                rendered = template.render(context)
                elapsed = (time.perf_counter() - start_time) * 1000
                
                results.append({
                    'thread_id': thread_id,
                    'render_id': i,
                    'elapsed_ms': elapsed,
                    'length': len(rendered)
                })
            
            return results
        
        # Run concurrent rendering
        num_threads = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(render_template, i) for i in range(num_threads)]
            all_results = []
            
            for future in concurrent.futures.as_completed(futures):
                results = future.result()
                all_results.extend(results)
        
        # Analyze concurrent performance
        render_times = [r['elapsed_ms'] for r in all_results]
        avg_time = statistics.mean(render_times)
        max_time = max(render_times)
        
        self.assertLess(avg_time, 50.0,
            f"Average concurrent render time too high: {avg_time:.1f}ms")
        self.assertLess(max_time, 100.0,
            f"Max concurrent render time too high: {max_time:.1f}ms")
        
        # All renders should succeed
        self.assertEqual(len(all_results), num_threads * 10)
    
    def test_template_memory_usage(self):
        """Test template rendering memory usage"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            template = loader.get_template('globals/sidebar_clean.html')
        except:
            self.skipTest("Template not found")
        
        from django.template import Context
        
        # Render template many times
        for i in range(500):
            context = Context({
                'user': self.user,
                'request': MagicMock(),
                'iteration': i,
                'large_data': list(range(100))  # Some data to render
            })
            
            rendered = template.render(context)
            
            # Periodically check memory
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                self.assertLess(memory_growth, 100.0,
                    f"Excessive memory growth during template rendering: {memory_growth:.1f}MB")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        self.assertLess(total_growth, 150.0,
            f"Total memory growth too high: {total_growth:.1f}MB")


@pytest.mark.performance
class TestSystemLoadPerformance(TestCase):
    """Test system performance under load (3 tests)"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='loaduser',
            password='loadpass123'
        )
        cache.clear()
    
    def test_mixed_workload_performance(self):
        """Test performance under mixed workload (redirects + pages + analytics)"""
        operations = [
            ('redirect', 'schedhuler/jobneedtasks/'),
            ('redirect', 'activity/asset/'),
            ('redirect', 'peoples/people/'),
            ('page', '/'),
            ('page', '/dashboard/'),
            ('analytics', 'migration_report'),
            ('analytics', 'breadcrumbs'),
        ]
        
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        results = []
        
        start_time = time.perf_counter()
        
        for i in range(100):  # 100 iterations of mixed workload
            for op_type, op_data in operations:
                op_start = time.perf_counter()
                
                if op_type == 'redirect':
                    response = self.client.get(f'/{op_data}', follow=False)
                    success = response.status_code == 301
                elif op_type == 'page':
                    response = self.client.get(op_data)
                    success = response.status_code in [200, 302, 403]  # Allow various success codes
                elif op_type == 'analytics':
                    if op_data == 'migration_report':
                        report = OptimizedURLRouter.get_migration_report()
                        success = 'summary' in report
                    elif op_data == 'breadcrumbs':
                        breadcrumbs = OptimizedURLRouter.get_breadcrumbs('/operations/tasks/create/')
                        success = len(breadcrumbs) > 1
                
                elapsed = (time.perf_counter() - op_start) * 1000
                results.append({
                    'operation': f"{op_type}_{op_data}",
                    'elapsed_ms': elapsed,
                    'success': success
                })
        
        total_elapsed = (time.perf_counter() - start_time) * 1000
        
        # Analyze mixed workload performance
        successful_ops = [r for r in results if r['success']]
        success_rate = len(successful_ops) / len(results)
        
        self.assertGreater(success_rate, 0.9,
            f"Success rate too low under mixed workload: {success_rate:.2%}")
        
        avg_op_time = statistics.mean([r['elapsed_ms'] for r in successful_ops])
        self.assertLess(avg_op_time, 100.0,
            f"Average operation time too high: {avg_op_time:.1f}ms")
        
        # Total throughput should be reasonable
        total_ops = len(results)
        throughput = total_ops / (total_elapsed / 1000)  # ops per second
        self.assertGreater(throughput, 50,
            f"Mixed workload throughput too low: {throughput:.1f} ops/s")
    
    def test_sustained_load_performance(self):
        """Test performance under sustained load"""
        test_duration = 10.0  # 10 seconds
        urls_to_test = [
            'schedhuler/jobneedtasks/',
            'activity/asset/',
            'peoples/people/',
            'helpdesk/ticket/',
        ]
        
        start_time = time.perf_counter()
        request_count = 0
        response_times = []
        errors = 0
        
        while (time.perf_counter() - start_time) < test_duration:
            url = urls_to_test[request_count % len(urls_to_test)]
            
            request_start = time.perf_counter()
            try:
                response = self.client.get(f'/{url}', follow=False)
                request_elapsed = (time.perf_counter() - request_start) * 1000
                
                if response.status_code == 301:
                    response_times.append(request_elapsed)
                else:
                    errors += 1
                    
            except Exception:
                errors += 1
            
            request_count += 1
        
        total_elapsed = time.perf_counter() - start_time
        
        # Analyze sustained load results
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 5 else max(response_times)
            
            throughput = len(response_times) / total_elapsed
            error_rate = errors / request_count
            
            self.assertLess(avg_response_time, 100.0,
                f"Average response time degraded under load: {avg_response_time:.1f}ms")
            self.assertLess(p95_response_time, 200.0,
                f"95th percentile response time too high: {p95_response_time:.1f}ms")
            self.assertGreater(throughput, 20,
                f"Throughput too low under sustained load: {throughput:.1f} req/s")
            self.assertLess(error_rate, 0.05,
                f"Error rate too high under sustained load: {error_rate:.2%}")
        else:
            self.fail("No successful responses during sustained load test")
    
    def test_memory_stability_under_load(self):
        """Test memory stability under extended load"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = []
        
        # Run load test with memory monitoring
        for i in range(1000):
            # Mix of operations
            if i % 4 == 0:
                self.client.get('/schedhuler/jobneedtasks/', follow=False)
            elif i % 4 == 1:
                self.client.get('/activity/asset/', follow=False)
            elif i % 4 == 2:
                from apps.core.url_router_optimized import OptimizedURLRouter
                OptimizedURLRouter.get_migration_report()
            else:
                OptimizedURLRouter.get_breadcrumbs('/operations/tasks/create/')
            
            # Sample memory every 100 operations
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append({
                    'iteration': i,
                    'memory_mb': current_memory,
                    'growth_mb': current_memory - initial_memory
                })
        
        # Analyze memory stability
        memory_growths = [s['growth_mb'] for s in memory_samples]
        max_growth = max(memory_growths)
        final_growth = memory_growths[-1]
        
        # Memory growth should be bounded
        self.assertLess(max_growth, 200.0,
            f"Maximum memory growth too high: {max_growth:.1f}MB")
        
        # Final memory growth should be reasonable
        self.assertLess(final_growth, 150.0,
            f"Final memory growth too high: {final_growth:.1f}MB")
        
        # Memory should not continuously grow (detect leaks)
        if len(memory_samples) > 5:
            early_avg = statistics.mean([s['growth_mb'] for s in memory_samples[:3]])
            late_avg = statistics.mean([s['growth_mb'] for s in memory_samples[-3:]])
            
            growth_trend = late_avg - early_avg
            self.assertLess(growth_trend, 100.0,
                f"Memory appears to be leaking: growth trend {growth_trend:.1f}MB")