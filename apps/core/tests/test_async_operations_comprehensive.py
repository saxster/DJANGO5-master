"""
Comprehensive Tests for Async Operations

Tests all components of the async performance remediation system:
- PDF generation service and tasks
- External API service and tasks
- Task monitoring and status tracking
- Performance monitoring middleware
- Caching layer functionality
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, RequestFactory, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.utils import timezone
from celery import current_app
from celery.result import AsyncResult

from apps.core.services.async_pdf_service import AsyncPDFGenerationService
from apps.core.services.async_api_service import AsyncExternalAPIService
from apps.core.middleware.performance_monitoring import PerformanceMonitoringMiddleware
from apps.core.middleware.smart_caching_middleware import SmartCachingMiddleware
from background_tasks.tasks import generate_pdf_async, external_api_call_async


User = get_user_model()


class AsyncPDFServiceTests(TestCase):
    """Test async PDF generation service."""

    def setUp(self):
        self.pdf_service = AsyncPDFGenerationService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    def test_initiate_pdf_generation_success(self):
        """Test successful PDF generation initiation."""
        template_name = 'test_template.html'
        context_data = {'title': 'Test Report', 'data': [1, 2, 3]}
        filename = 'test_report.pdf'

        result = self.pdf_service.initiate_pdf_generation(
            template_name=template_name,
            context_data=context_data,
            user_id=self.user.id,
            filename=filename
        )

        self.assertEqual(result['status'], 'pending')
        self.assertIn('task_id', result)
        self.assertIn('estimated_completion', result)
        self.assertEqual(result['message'], 'PDF generation started')

        # Verify task data is stored
        task_data = self.pdf_service._get_task_data(result['task_id'])
        self.assertIsNotNone(task_data)
        self.assertEqual(task_data['template_name'], template_name)
        self.assertEqual(task_data['user_id'], self.user.id)

    def test_initiate_pdf_generation_invalid_input(self):
        """Test PDF generation with invalid input."""
        with self.assertRaises(ValueError):
            self.pdf_service.initiate_pdf_generation(
                template_name='',  # Invalid empty template
                context_data={},
                user_id=self.user.id
            )

        with self.assertRaises(ValueError):
            self.pdf_service.initiate_pdf_generation(
                template_name='test.html',
                context_data='invalid',  # Should be dict
                user_id=self.user.id
            )

    @patch('apps.core.services.async_pdf_service.render_to_string')
    @patch('apps.core.services.async_pdf_service.default_storage')
    def test_generate_pdf_content_success(self, mock_storage, mock_render):
        """Test successful PDF content generation."""
        # Setup mocks
        mock_render.return_value = '<html><body>Test PDF</body></html>'
        mock_storage.save.return_value = 'generated_pdfs/2024/01/01/test.pdf'

        task_id = str(uuid.uuid4())
        template_name = 'test_template.html'
        context_data = {'title': 'Test Report'}

        # Store initial task data
        self.pdf_service._store_task_data(task_id, {
            'template_name': template_name,
            'context_data': context_data,
            'filename': 'test.pdf',
            'status': 'pending'
        })

        with patch('weasyprint.HTML') as mock_html:
            mock_html.return_value.write_pdf.return_value = b'fake_pdf_content'

            result = self.pdf_service.generate_pdf_content(
                task_id=task_id,
                template_name=template_name,
                context_data=context_data
            )

            self.assertEqual(result['status'], 'completed')
            self.assertIn('file_path', result)
            self.assertIn('file_size', result)

    def test_get_task_status(self):
        """Test task status retrieval."""
        task_id = str(uuid.uuid4())

        # Test non-existent task
        status = self.pdf_service.get_task_status(task_id)
        self.assertEqual(status['status'], 'not_found')

        # Test existing task
        task_data = {
            'status': 'processing',
            'progress': 50,
            'message': 'Generating PDF',
            'created_at': timezone.now()
        }
        self.pdf_service._store_task_data(task_id, task_data)

        status = self.pdf_service.get_task_status(task_id)
        self.assertEqual(status['status'], 'processing')
        self.assertEqual(status['progress'], 50)

    def test_task_progress_updates(self):
        """Test task progress tracking."""
        task_id = str(uuid.uuid4())

        # Initialize task
        self.pdf_service._store_task_data(task_id, {'status': 'pending'})

        # Update progress
        self.pdf_service._update_task_progress(task_id, 25, 'Processing template')

        task_data = self.pdf_service._get_task_data(task_id)
        self.assertEqual(task_data['progress'], 25)
        self.assertEqual(task_data['message'], 'Processing template')


class AsyncAPIServiceTests(TestCase):
    """Test async external API service."""

    def setUp(self):
        self.api_service = AsyncExternalAPIService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    def test_initiate_api_call_success(self):
        """Test successful API call initiation."""
        url = 'https://api.example.com/data'
        method = 'GET'
        headers = {'Authorization': 'Bearer token'}

        with patch('background_tasks.tasks.external_api_call_async.apply_async') as mock_apply:
            mock_apply.return_value.id = 'test-task-id'

            result = self.api_service.initiate_api_call(
                url=url,
                method=method,
                headers=headers,
                user_id=self.user.id
            )

            self.assertEqual(result['status'], 'pending')
            self.assertIn('task_id', result)
            self.assertEqual(result['url'], url)
            self.assertEqual(result['method'], 'GET')

    def test_url_validation(self):
        """Test URL validation."""
        # Invalid URLs
        invalid_urls = [
            '',
            'not-a-url',
            'ftp://example.com',  # Unsupported scheme
            'http://localhost',   # Private IP
            'https://127.0.0.1',  # Loopback
        ]

        for url in invalid_urls:
            with self.assertRaises(ValueError):
                self.api_service.initiate_api_call(url=url, user_id=self.user.id)

    def test_header_sanitization(self):
        """Test header sanitization for security."""
        dangerous_headers = {
            'Authorization': 'Bearer secret',
            'Cookie': 'session=abc123',
            'X-API-Key': 'secret-key',
            'Safe-Header': 'safe-value'
        }

        sanitized = self.api_service._sanitize_headers(dangerous_headers)

        # Dangerous headers should be removed
        self.assertNotIn('authorization', sanitized)
        self.assertNotIn('cookie', sanitized)
        self.assertNotIn('x-api-key', sanitized)

        # Safe headers should remain
        self.assertIn('Safe-Header', sanitized)

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        url = 'https://api.example.com/test'

        # First request should pass
        self.assertTrue(self.api_service._check_rate_limit(url, self.user.id))

        # Simulate hitting rate limit
        cache_key = f"api_rate_limit_{url}_{self.user.id}"
        cache.set(cache_key, 100, timeout=3600)  # Set to limit

        # Next request should be blocked
        self.assertFalse(self.api_service._check_rate_limit(url, self.user.id))

    @patch('celery.result.AsyncResult')
    def test_get_task_status_completed(self, mock_result):
        """Test getting status of completed API task."""
        task_id = str(uuid.uuid4())

        # Mock completed Celery task
        mock_celery_result = Mock()
        mock_celery_result.ready.return_value = True
        mock_celery_result.successful.return_value = True
        mock_celery_result.result = {
            'status': 'success',
            'data': {'key': 'value'},
            'status_code': 200
        }
        mock_result.return_value = mock_celery_result

        # Store task data
        task_data = {
            'url': 'https://api.example.com/test',
            'method': 'GET',
            'created_at': timezone.now()
        }
        self.api_service._store_task_data(task_id, task_data)

        status = self.api_service.get_task_status(task_id)

        self.assertEqual(status['status'], 'completed')
        self.assertIn('data', status)
        self.assertEqual(status['url'], task_data['url'])

    def test_bulk_api_calls(self):
        """Test bulk API call functionality."""
        requests = [
            {'url': 'https://api.example.com/1'},
            {'url': 'https://api.example.com/2', 'method': 'POST'},
            {'url': 'https://api.example.com/3', 'timeout': 60}
        ]

        with patch.object(self.api_service, 'initiate_api_call') as mock_initiate:
            mock_initiate.return_value = {'task_id': 'test-task-id'}

            result = self.api_service.bulk_api_calls(
                requests=requests,
                user_id=self.user.id
            )

            self.assertEqual(result['total_requests'], 3)
            self.assertIn('batch_id', result)
            self.assertEqual(len(result['task_ids']), 3)
            self.assertEqual(mock_initiate.call_count, 3)


class CeleryTaskTests(TransactionTestCase):
    """Test Celery tasks."""

    def setUp(self):
        # Use eager mode for testing
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    @patch('apps.core.services.async_pdf_service.AsyncPDFGenerationService.generate_pdf_content')
    def test_generate_pdf_async_success(self, mock_generate):
        """Test PDF generation Celery task."""
        mock_generate.return_value = {
            'status': 'completed',
            'file_path': 'test.pdf',
            'file_size': 1024
        }

        task_id = str(uuid.uuid4())
        template_name = 'test_template.html'
        context_data = {'title': 'Test Report'}

        result = generate_pdf_async.apply(
            args=[task_id, template_name, context_data, self.user.id],
            task_id=task_id
        )

        self.assertTrue(result.successful())
        self.assertEqual(result.result['status'], 'completed')

    @patch('requests.Session.request')
    def test_external_api_call_async_success(self, mock_request):
        """Test external API call Celery task."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        url = 'https://api.example.com/test'
        method = 'GET'

        result = external_api_call_async.apply(
            args=[url, method, {}, None, 30, self.user.id]
        )

        self.assertTrue(result.successful())
        self.assertEqual(result.result['status'], 'success')
        self.assertEqual(result.result['status_code'], 200)

    @patch('requests.Session.request')
    def test_external_api_call_async_timeout(self, mock_request):
        """Test API call task with timeout."""
        import requests
        mock_request.side_effect = requests.exceptions.Timeout()

        url = 'https://api.example.com/test'

        result = external_api_call_async.apply(
            args=[url, 'GET', {}, None, 1, self.user.id]
        )

        self.assertTrue(result.successful())
        self.assertEqual(result.result['status'], 'error')
        self.assertEqual(result.result['error'], 'timeout')


class PerformanceMonitoringMiddlewareTests(TestCase):
    """Test performance monitoring middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = PerformanceMonitoringMiddleware(lambda x: HttpResponse())
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    def test_request_performance_tracking(self):
        """Test basic request performance tracking."""
        request = self.factory.get('/test-path/')
        request.user = self.user

        # Process request
        self.middleware.process_request(request)

        # Simulate some processing time
        time.sleep(0.1)

        # Process response
        response = HttpResponse('Test response')
        response = self.middleware.process_response(request, response)

        # Check that performance data was created
        self.assertTrue(hasattr(request, 'performance_data'))
        self.assertIn('request_id', request.performance_data)
        self.assertIn('start_time', request.performance_data)

        # Check response headers in debug mode
        with patch('django.conf.settings.DEBUG', True):
            response = self.middleware.process_response(request, response)
            self.assertIn('X-Request-Duration', response)

    def test_slow_request_detection(self):
        """Test detection and logging of slow requests."""
        request = self.factory.get('/slow-endpoint/')
        request.user = self.user

        self.middleware.process_request(request)

        # Mock slow processing
        with patch('time.time', side_effect=[0, 3.0]):  # 3 second duration
            response = HttpResponse('Slow response')

            with patch.object(self.middleware, '_log_slow_request') as mock_log:
                self.middleware.process_response(request, response)
                mock_log.assert_called_once()

    def test_performance_classification(self):
        """Test performance issue classification."""
        # Test good performance
        classification = self.middleware._classify_performance(0.5, 10, 0.1)
        self.assertEqual(classification['overall'], 'good')

        # Test slow response
        classification = self.middleware._classify_performance(3.0, 10, 0.1)
        self.assertEqual(classification['overall'], 'warning')
        self.assertIn('slow_response', classification['issues'])

        # Test very slow response
        classification = self.middleware._classify_performance(6.0, 10, 0.1)
        self.assertEqual(classification['overall'], 'critical')
        self.assertIn('very_slow_response', classification['issues'])

        # Test high query count
        classification = self.middleware._classify_performance(1.0, 100, 0.1)
        self.assertEqual(classification['overall'], 'warning')
        self.assertIn('high_query_count', classification['issues'])

    def test_performance_stats_aggregation(self):
        """Test aggregation of performance statistics."""
        # Clear existing stats
        cache.delete(self.middleware.PERFORMANCE_STATS_KEY)

        # Simulate multiple requests
        for i in range(5):
            metrics = {
                'request_id': f'test-{i}',
                'duration': 1.0 + i * 0.5,
                'query_count': 10 + i,
                'query_time': 0.1,
                'timestamp': timezone.now(),
                'classification': {'overall': 'good' if i < 3 else 'warning'}
            }
            self.middleware._update_performance_stats(metrics)

        # Check aggregated stats
        stats = self.middleware.get_performance_stats()
        self.assertEqual(stats['total_requests'], 5)
        self.assertEqual(stats['slow_requests'], 2)


class SmartCachingMiddlewareTests(TestCase):
    """Test smart caching middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SmartCachingMiddleware(lambda x: HttpResponse('Test response'))
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    def test_cacheable_request_detection(self):
        """Test detection of cacheable requests."""
        # GET request should be cacheable
        request = self.factory.get('/api/reports/')
        self.assertTrue(self.middleware._is_cacheable_request(request))

        # POST request should not be cacheable
        request = self.factory.post('/api/reports/')
        self.assertFalse(self.middleware._is_cacheable_request(request))

        # Admin paths should not be cacheable
        request = self.factory.get('/admin/users/')
        self.assertFalse(self.middleware._is_cacheable_request(request))

    def test_cache_key_generation(self):
        """Test cache key generation."""
        request = self.factory.get('/api/reports/?start=2024-01-01&end=2024-01-31')
        request.user = self.user

        cache_key = self.middleware._generate_cache_key(request)
        self.assertIsNotNone(cache_key)
        self.assertTrue(cache_key.startswith('smart_cache_'))

        # Same request should generate same key
        cache_key2 = self.middleware._generate_cache_key(request)
        self.assertEqual(cache_key, cache_key2)

    def test_cache_hit_and_miss(self):
        """Test cache hit and miss scenarios."""
        request = self.factory.get('/api/test/')

        # First request should be a miss
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # No cached response

        # Create and cache a response
        test_response = HttpResponse('Cached response', content_type='application/json')
        response = self.middleware.process_response(request, test_response)

        # Second identical request should be a hit
        request2 = self.factory.get('/api/test/')
        cached_response = self.middleware.process_request(request2)

        self.assertIsNotNone(cached_response)
        self.assertEqual(cached_response['X-Cache-Status'], 'HIT')

    def test_cache_timeout_determination(self):
        """Test cache timeout calculation."""
        request = self.factory.get('/api/reports/')
        response = HttpResponse()

        # API endpoints should have short timeout
        timeout = self.middleware._get_cache_timeout(request, response)
        self.assertEqual(timeout, self.middleware.SHORT_CACHE_TIMEOUT)

        # Reports should have longer timeout
        request = self.factory.get('/reports/monthly/')
        timeout = self.middleware._get_cache_timeout(request, response)
        self.assertEqual(timeout, self.middleware.LONG_CACHE_TIMEOUT)

    def test_cache_invalidation(self):
        """Test cache invalidation functionality."""
        # This is a basic test - full implementation would require Redis
        pattern = 'test_pattern_*'
        result = SmartCachingMiddleware.invalidate_cache_pattern(pattern)
        self.assertIsInstance(result, int)

    def test_response_cacheability(self):
        """Test response cacheability checks."""
        request = self.factory.get('/api/test/')

        # Successful JSON response should be cacheable
        response = HttpResponse('{"data": "test"}', content_type='application/json')
        response.status_code = 200
        self.assertTrue(self.middleware._is_cacheable_response(request, response))

        # Response with Set-Cookie should not be cacheable
        response['Set-Cookie'] = 'session=abc123'
        self.assertFalse(self.middleware._is_cacheable_response(request, response))

        # Error response should not be cacheable
        response = HttpResponse('Error', status=500)
        self.assertFalse(self.middleware._is_cacheable_response(request, response))


class IntegrationTests(TransactionTestCase):
    """Integration tests for the complete async system."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def tearDown(self):
        cache.clear()

    def test_end_to_end_pdf_generation(self):
        """Test complete PDF generation workflow."""
        # Initialize service
        pdf_service = AsyncPDFGenerationService()

        # Initiate PDF generation
        result = pdf_service.initiate_pdf_generation(
            template_name='test_template.html',
            context_data={'title': 'Integration Test'},
            user_id=self.user.id,
            filename='integration_test.pdf'
        )

        task_id = result['task_id']

        # Check initial status
        status = pdf_service.get_task_status(task_id)
        self.assertEqual(status['status'], 'pending')

        # Simulate task processing
        with patch('apps.core.services.async_pdf_service.render_to_string') as mock_render:
            mock_render.return_value = '<html><body>Test</body></html>'

            with patch('weasyprint.HTML') as mock_html, \
                 patch('apps.core.services.async_pdf_service.default_storage') as mock_storage:

                mock_html.return_value.write_pdf.return_value = b'fake_pdf_content'
                mock_storage.save.return_value = 'test_path.pdf'

                # Generate PDF content
                result = pdf_service.generate_pdf_content(
                    task_id=task_id,
                    template_name='test_template.html',
                    context_data={'title': 'Integration Test'}
                )

                self.assertEqual(result['status'], 'completed')

    def test_monitoring_and_caching_integration(self):
        """Test integration between monitoring and caching."""
        # Setup middlewares
        performance_middleware = PerformanceMonitoringMiddleware(lambda x: HttpResponse())
        cache_middleware = SmartCachingMiddleware(lambda x: HttpResponse('Test response'))

        request = self.factory.get('/api/reports/test/')
        request.user = self.user

        # Process through performance monitoring
        performance_middleware.process_request(request)

        # Process through caching (should miss first time)
        cached_response = cache_middleware.process_request(request)
        self.assertIsNone(cached_response)

        # Create response and cache it
        response = HttpResponse('{"data": "test"}', content_type='application/json')
        response = cache_middleware.process_response(request, response)

        # Process through performance monitoring
        response = performance_middleware.process_response(request, response)

        # Verify performance data was captured
        self.assertTrue(hasattr(request, 'performance_data'))

        # Second request should hit cache
        request2 = self.factory.get('/api/reports/test/')
        request2.user = self.user

        cached_response = cache_middleware.process_request(request2)
        self.assertIsNotNone(cached_response)
        self.assertEqual(cached_response['X-Cache-Status'], 'HIT')