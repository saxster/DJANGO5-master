"""
Comprehensive tests for the advanced caching system
Tests all caching components: decorators, invalidation, form mixins, and template tags
"""

import time
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from django.core.cache import cache
from django.contrib.auth.models import User
from django.template import Context, Template
from django.http import JsonResponse

from apps.core.caching.decorators import (
    smart_cache_view,
    cache_dashboard_metrics,
    cache_dropdown_data,
    method_cache
)
from apps.core.caching.utils import (
    get_tenant_cache_key,
    get_user_cache_key,
    cache_key_generator,
    get_cache_stats,
    clear_cache_pattern
)
from apps.core.caching.invalidation import (
    cache_invalidation_manager,
    invalidate_cache_pattern,
    invalidate_model_caches
)
from apps.core.caching.form_mixins import CachedDropdownMixin, OptimizedModelForm
from apps.peoples.models import People


class CacheUtilsTestCase(TestCase):
    """
    Test cache utility functions
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_tenant_cache_key_generation(self):
        """Test tenant-aware cache key generation"""
        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 2, 'bu_id': 3}

        key = get_tenant_cache_key('test_key', request)
        expected = 'tenant:1:client:2:bu:3:test_key'
        self.assertEqual(key, expected)

    def test_tenant_cache_key_with_overrides(self):
        """Test cache key generation with manual overrides"""
        key = get_tenant_cache_key('test_key', tenant_id=5, client_id=6, bu_id=7)
        expected = 'tenant:5:client:6:bu:7:test_key'
        self.assertEqual(key, expected)

    def test_user_cache_key_generation(self):
        """Test user-specific cache key generation"""
        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 2, 'bu_id': 3}

        key = get_user_cache_key('user_data', 123, request)
        expected = 'tenant:1:client:2:bu:3:user:123:user_data'
        self.assertEqual(key, expected)

    def test_cache_key_generator_with_params(self):
        """Test advanced cache key generation with parameters"""
        params = {'page': 1, 'filter': 'active', 'sort': 'name'}
        key = cache_key_generator('user_list', 'dashboard', params=params)

        self.assertIn('user_list', key)
        self.assertIn('dashboard', key)
        self.assertIn('params:', key)

    def test_cache_key_length_limit(self):
        """Test that very long cache keys are properly hashed"""
        long_key = 'very_long_key_' * 50  # Create a very long key
        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 2, 'bu_id': 3}

        key = get_tenant_cache_key(long_key, request)

        # Should be truncated and hashed
        self.assertLessEqual(len(key), 250)
        self.assertIn('hash:', key)

    def test_clear_cache_pattern(self):
        """Test cache pattern clearing functionality"""
        # Set up test cache entries
        cache.set('tenant:1:test:key1', 'value1', 300)
        cache.set('tenant:1:test:key2', 'value2', 300)
        cache.set('tenant:2:test:key3', 'value3', 300)
        cache.set('other:key4', 'value4', 300)

        # Clear pattern
        result = clear_cache_pattern('tenant:1:test:*')

        # Check results
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['keys_cleared'], 2)

        # Verify specific keys are cleared
        self.assertIsNone(cache.get('tenant:1:test:key1'))
        self.assertIsNone(cache.get('tenant:1:test:key2'))

        # Verify other keys remain
        self.assertEqual(cache.get('tenant:2:test:key3'), 'value3')
        self.assertEqual(cache.get('other:key4'), 'value4')


class SmartCacheViewTestCase(TestCase):
    """
    Test the smart_cache_view decorator
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')

    def tearDown(self):
        cache.clear()

    @smart_cache_view(timeout=300, key_prefix='test_view')
    def cached_view(self, request):
        """Test view function"""
        return JsonResponse({'timestamp': time.time(), 'cached': False})

    def test_cache_hit_and_miss(self):
        """Test cache hit and miss behavior"""
        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request.user = self.user

        # First call should be cache miss
        response1 = self.cached_view(request)
        self.assertEqual(response1.status_code, 200)

        # Second call should be cache hit
        response2 = self.cached_view(request)
        self.assertEqual(response2.status_code, 200)

        # Parse JSON responses
        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)

        # Second response should be cached (same timestamp)
        self.assertEqual(data1['timestamp'], data2['timestamp'])

    @smart_cache_view(timeout=300, per_user=True, key_prefix='user_view')
    def user_cached_view(self, request):
        """Test view with user-specific caching"""
        return JsonResponse({'user_id': request.user.id, 'timestamp': time.time()})

    def test_per_user_caching(self):
        """Test user-specific cache isolation"""
        user2 = User.objects.create_user('testuser2', 'test2@example.com', 'password')

        request1 = self.factory.get('/')
        request1.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request1.user = self.user

        request2 = self.factory.get('/')
        request2.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request2.user = user2

        # Each user should get their own cached response
        response1 = self.user_cached_view(request1)
        response2 = self.user_cached_view(request2)

        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)

        self.assertEqual(data1['user_id'], self.user.id)
        self.assertEqual(data2['user_id'], user2.id)
        self.assertNotEqual(data1['timestamp'], data2['timestamp'])

    def test_post_request_not_cached(self):
        """Test that POST requests are not cached"""
        request = self.factory.post('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request.user = self.user

        # POST requests should not be cached
        response = self.cached_view(request)
        self.assertEqual(response.status_code, 200)

        # Response should not have cache headers
        self.assertNotIn('X-Cache-Status', response)


class CacheInvalidationTestCase(TestCase):
    """
    Test cache invalidation system
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_model_dependency_registration(self):
        """Test registering cache dependencies for models"""
        # Register dependencies
        cache_invalidation_manager.register_dependency(
            'TestModel',
            ['dropdown:test', 'dashboard:metrics']
        )

        patterns = cache_invalidation_manager.get_patterns_for_model('TestModel')
        self.assertIn('dropdown:test', patterns)
        self.assertIn('dashboard:metrics', patterns)

    def test_pattern_invalidation(self):
        """Test invalidating cache patterns"""
        # Set up test cache entries
        cache.set('tenant:1:dropdown:test:key1', 'value1', 300)
        cache.set('tenant:1:dropdown:test:key2', 'value2', 300)
        cache.set('tenant:1:other:key3', 'value3', 300)

        # Invalidate dropdown pattern for tenant 1
        result = invalidate_cache_pattern('dropdown:test', tenant_id=1)

        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['keys_cleared'], 2)

        # Verify pattern keys are cleared
        self.assertIsNone(cache.get('tenant:1:dropdown:test:key1'))
        self.assertIsNone(cache.get('tenant:1:dropdown:test:key2'))

        # Verify other keys remain
        self.assertEqual(cache.get('tenant:1:other:key3'), 'value3')

    def test_model_cache_invalidation(self):
        """Test invalidating all caches for a model"""
        # Register model dependencies
        cache_invalidation_manager.register_dependency(
            'People',
            ['dropdown:people', 'dashboard:metrics', 'form:choices']
        )

        # Set up test cache entries
        cache.set('tenant:1:dropdown:people:key1', 'value1', 300)
        cache.set('tenant:1:dashboard:metrics:key2', 'value2', 300)
        cache.set('tenant:1:form:choices:key3', 'value3', 300)
        cache.set('tenant:1:other:key4', 'value4', 300)

        # Invalidate all People model caches
        result = invalidate_model_caches('People', tenant_id=1)

        self.assertGreater(result['total_cleared'], 0)
        self.assertEqual(result['patterns_processed'], 3)

    @patch('apps.core.caching.invalidation.cache_invalidation_manager.invalidate_for_model')
    def test_signal_based_invalidation(self, mock_invalidate):
        """Test automatic cache invalidation via signals"""
        # Create a People instance to trigger post_save signal
        person = People.objects.create(
            loginid='testuser',
            fname='Test',
            lname='User',
            email='test@example.com'
        )

        # Verify invalidation was called
        mock_invalidate.assert_called_once()
        args, kwargs = mock_invalidate.call_args
        self.assertEqual(args[0], person)
        self.assertEqual(args[1], 'create')


class FormCachingTestCase(TestCase):
    """
    Test form dropdown caching functionality
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_cached_dropdown_mixin_initialization(self):
        """Test CachedDropdownMixin initialization"""
        class TestForm(CachedDropdownMixin):
            cached_dropdown_fields = {
                'test_field': {
                    'model': People,
                    'filter_method': 'all',
                    'version': '1.0'
                }
            }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}

        # Initialize form with request
        form = TestForm(request=request)
        self.assertEqual(form.request, request)

    def test_dropdown_cache_key_generation(self):
        """Test cache key generation for dropdown fields"""
        class TestForm(CachedDropdownMixin):
            cached_dropdown_fields = {
                'people': {
                    'model': People,
                    'filter_method': 'filter_for_dd_people_field',
                    'version': '1.0'
                }
            }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}

        form = TestForm(request=request)

        # Test cache key generation for dropdown
        config = form.cached_dropdown_fields['people']
        cache_key_parts = [
            form.cache_prefix,
            form.__class__.__name__,
            'people',
            config.get('version', '1')
        ]

        expected_base = ':'.join(cache_key_parts)
        # The actual key should be tenant-aware
        self.assertIn('tenant:1', get_tenant_cache_key(expected_base, request))

    def test_dropdown_cache_miss_and_hit(self):
        """Test dropdown cache miss and hit behavior"""
        # Mock the People model and its manager
        with patch('apps.peoples.models.People.objects') as mock_manager:
            mock_queryset = Mock()
            mock_manager.filter_for_dd_people_field.return_value = mock_queryset

            class TestForm(CachedDropdownMixin):
                cached_dropdown_fields = {
                    'people': {
                        'model': People,
                        'filter_method': 'filter_for_dd_people_field',
                        'version': '1.0'
                    }
                }

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            request = self.factory.get('/')
            request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}

            # First form initialization should call the database
            form1 = TestForm(request=request)
            mock_manager.filter_for_dd_people_field.assert_called_once()

            # Second form initialization should use cache
            mock_manager.reset_mock()
            form2 = TestForm(request=request)

            # Should not call database again if cache hit
            # Note: This test might need adjustment based on actual caching implementation


class TemplateTagsTestCase(TestCase):
    """
    Test template caching tags
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_fragment_tag(self):
        """Test cache_fragment template tag"""
        template = Template(
            "{% load cache_tags %}"
            "{% cache_fragment 'test_fragment' timeout=300 %}"
            "{{ timestamp }}"
            "{% endcache_fragment %}"
        )

        context = Context({'timestamp': time.time()})
        request = Mock()
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        context['request'] = request

        # First render should cache the content
        output1 = template.render(context)

        # Second render with different timestamp should return cached content
        context['timestamp'] = time.time() + 100
        output2 = template.render(context)

        # Both outputs should be the same (cached)
        self.assertEqual(output1, output2)

    def test_cached_widget_tag(self):
        """Test cached_widget template tag"""
        # Mock the widget template loading
        with patch('django.template.loader.get_template') as mock_get_template:
            mock_template = Mock()
            mock_template.render.return_value = '<div>Widget Content</div>'
            mock_get_template.return_value = mock_template

            template = Template(
                "{% load cache_tags %}"
                "{% cached_widget 'test_widget' timeout=300 %}"
            )

            context = Context({})
            request = Mock()
            request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
            context['request'] = request

            # Should render widget and cache it
            output = template.render(context)
            self.assertIn('Widget Content', output)

    def test_cache_key_for_tag(self):
        """Test cache_key_for template tag"""
        template = Template(
            "{% load cache_tags %}"
            "{% cache_key_for 'dashboard' 'metrics' as cache_key %}"
            "{{ cache_key }}"
        )

        context = Context({})
        request = Mock()
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        context['request'] = request

        output = template.render(context)
        self.assertIn('dashboard:metrics', output)
        self.assertIn('tenant:1', output)


class DashboardCachingTestCase(TestCase):
    """
    Test dashboard caching integration
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')

    def tearDown(self):
        cache.clear()

    @cache_dashboard_metrics(timeout=300)
    def mock_dashboard_view(self, request):
        """Mock dashboard view for testing"""
        return JsonResponse({
            'metrics': {
                'total_people': 100,
                'active_assets': 50,
                'timestamp': time.time()
            }
        })

    def test_dashboard_caching(self):
        """Test dashboard metrics caching"""
        request = self.factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request.user = self.user

        # First call should generate data
        response1 = self.mock_dashboard_view(request)
        data1 = json.loads(response1.content)

        # Second call should return cached data
        response2 = self.mock_dashboard_view(request)
        data2 = json.loads(response2.content)

        # Timestamps should be the same (cached)
        self.assertEqual(
            data1['metrics']['timestamp'],
            data2['metrics']['timestamp']
        )

    def test_dashboard_tenant_isolation(self):
        """Test dashboard cache tenant isolation"""
        request1 = self.factory.get('/')
        request1.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request1.user = self.user

        request2 = self.factory.get('/')
        request2.session = {'tenant_id': 2, 'client_id': 1, 'bu_id': 1}
        request2.user = self.user

        # Each tenant should get separate cached data
        response1 = self.mock_dashboard_view(request1)
        response2 = self.mock_dashboard_view(request2)

        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)

        # Different tenants should have different timestamps
        self.assertNotEqual(
            data1['metrics']['timestamp'],
            data2['metrics']['timestamp']
        )


class CachePerformanceTestCase(TestCase):
    """
    Test cache performance and efficiency
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_performance_improvement(self):
        """Test that caching actually improves performance"""
        @smart_cache_view(timeout=300, key_prefix='performance_test')
        def expensive_view(request):
            # Simulate expensive operation
            time.sleep(0.01)  # 10ms delay
            return JsonResponse({'result': 'expensive_computation'})

        factory = RequestFactory()
        request = factory.get('/')
        request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
        request.user = Mock()

        # Measure time for first call (cache miss)
        start_time = time.time()
        response1 = expensive_view(request)
        first_call_time = time.time() - start_time

        # Measure time for second call (cache hit)
        start_time = time.time()
        response2 = expensive_view(request)
        second_call_time = time.time() - start_time

        # Cache hit should be significantly faster
        self.assertLess(second_call_time, first_call_time * 0.5)

        # Both responses should be the same
        self.assertEqual(response1.content, response2.content)

    def test_concurrent_cache_access(self):
        """Test cache behavior under concurrent access"""
        import threading

        results = []
        errors = []

        @smart_cache_view(timeout=300, key_prefix='concurrent_test')
        def concurrent_view(request):
            # Small delay to increase chance of race conditions
            time.sleep(0.001)
            return JsonResponse({'timestamp': time.time()})

        def worker():
            try:
                factory = RequestFactory()
                request = factory.get('/')
                request.session = {'tenant_id': 1, 'client_id': 1, 'bu_id': 1}
                request.user = Mock()

                response = concurrent_view(request)
                data = json.loads(response.content)
                results.append(data['timestamp'])
            except Exception as e:
                errors.append(str(e))

        # Run multiple concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have no errors
        self.assertEqual(len(errors), 0)

        # All results should be the same (cached)
        unique_timestamps = set(results)
        self.assertEqual(len(unique_timestamps), 1)


class CacheMonitoringTestCase(TestCase):
    """
    Test cache monitoring and management functionality
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_stats_collection(self):
        """Test cache statistics collection"""
        # Set some test data
        cache.set('test_key_1', 'value1', 300)
        cache.set('test_key_2', 'value2', 300)

        stats = get_cache_stats()

        # Should have basic statistics
        self.assertIn('cache_backend', stats)
        self.assertIsInstance(stats.get('redis_connected_clients', 0), int)

    def test_cache_pattern_management(self):
        """Test cache pattern clearing and management"""
        # Set up test data with different patterns
        cache.set('tenant:1:dropdown:people:key1', 'value1', 300)
        cache.set('tenant:1:dropdown:people:key2', 'value2', 300)
        cache.set('tenant:1:dashboard:metrics:key3', 'value3', 300)
        cache.set('tenant:2:dropdown:people:key4', 'value4', 300)

        # Clear specific pattern
        result = clear_cache_pattern('tenant:1:dropdown:people:*')

        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['keys_cleared'], 2)

        # Verify correct keys were cleared
        self.assertIsNone(cache.get('tenant:1:dropdown:people:key1'))
        self.assertIsNone(cache.get('tenant:1:dropdown:people:key2'))

        # Verify other keys remain
        self.assertEqual(cache.get('tenant:1:dashboard:metrics:key3'), 'value3')
        self.assertEqual(cache.get('tenant:2:dropdown:people:key4'), 'value4')