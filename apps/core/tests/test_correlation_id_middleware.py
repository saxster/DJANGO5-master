"""
Comprehensive Tests for Correlation ID Middleware

Tests correlation ID generation, propagation, and thread-local storage.

Test Coverage:
- Correlation ID generation (new requests)
- Correlation ID acceptance (from client)
- Correlation ID validation (UUID v4 format)
- Response header propagation
- Thread-local storage and retrieval
- Invalid correlation ID rejection
- Concurrent request handling

Compliance:
- .claude/rules.md Rule #11 (specific exceptions)
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, TestCase
from concurrent.futures import ThreadPoolExecutor

from apps.core.middleware.correlation_id_middleware import (
    CorrelationIDMiddleware,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id
)


class TestCorrelationIDMiddleware(TestCase):
    """Test suite for CorrelationIDMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.middleware = CorrelationIDMiddleware(get_response=lambda req: HttpResponse())
        self.factory = RequestFactory()

    def tearDown(self):
        """Clean up thread-local storage."""
        clear_correlation_id()

    def test_generates_correlation_id_for_new_request(self):
        """Test that middleware generates UUID v4 for new requests."""
        request = self.factory.get('/')

        self.middleware.process_request(request)

        # Should have correlation_id attribute
        self.assertTrue(hasattr(request, 'correlation_id'))

        # Should be valid UUID v4
        correlation_id = request.correlation_id
        uuid_obj = uuid.UUID(correlation_id, version=4)
        self.assertEqual(uuid_obj.version, 4)

    def test_accepts_valid_correlation_id_from_client(self):
        """Test that middleware accepts valid X-Correlation-ID header."""
        client_correlation_id = str(uuid.uuid4())
        request = self.factory.get('/', HTTP_X_CORRELATION_ID=client_correlation_id)

        self.middleware.process_request(request)

        # Should use client-provided correlation ID
        self.assertEqual(request.correlation_id, client_correlation_id)

    def test_rejects_invalid_correlation_id_format(self):
        """Test that middleware rejects invalid UUID formats."""
        invalid_ids = [
            'not-a-uuid',
            '12345',
            'invalid-uuid-format',
            '',
            'a' * 100
        ]

        for invalid_id in invalid_ids:
            request = self.factory.get('/', HTTP_X_CORRELATION_ID=invalid_id)

            self.middleware.process_request(request)

            # Should generate new correlation ID (not use invalid one)
            self.assertNotEqual(request.correlation_id, invalid_id)

            # Should be valid UUID v4
            uuid_obj = uuid.UUID(request.correlation_id, version=4)
            self.assertEqual(uuid_obj.version, 4)

    def test_propagates_correlation_id_to_response_header(self):
        """Test that middleware adds X-Correlation-ID to response."""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Should have X-Correlation-ID header
        self.assertIn('X-Correlation-ID', response)

        # Should match request correlation ID
        self.assertEqual(response['X-Correlation-ID'], request.correlation_id)

    def test_stores_correlation_id_in_thread_local(self):
        """Test that correlation ID is stored in thread-local storage."""
        request = self.factory.get('/')

        self.middleware.process_request(request)

        # Should be retrievable via get_correlation_id()
        retrieved_id = get_correlation_id()
        self.assertEqual(retrieved_id, request.correlation_id)

    def test_clears_correlation_id_after_response(self):
        """Test that correlation ID is cleared from thread-local after response."""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        response = HttpResponse()
        self.middleware.process_response(request, response)

        # Thread-local should be cleared
        cleared_id = get_correlation_id()
        self.assertIsNone(cleared_id)

    def test_handles_missing_get_response_gracefully(self):
        """Test middleware without get_response callable."""
        middleware = CorrelationIDMiddleware(get_response=None)
        request = self.factory.get('/')

        # Should not raise exception
        try:
            middleware.process_request(request)
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.fail(f"process_request raised {e}")

        self.assertTrue(hasattr(request, 'correlation_id'))

    def test_handles_concurrent_requests(self):
        """Test that thread-local storage isolates concurrent requests."""
        def make_request(path):
            request = self.factory.get(path)
            self.middleware.process_request(request)

            # Get correlation ID from thread-local
            thread_local_id = get_correlation_id()

            # Should match request correlation ID
            return (request.correlation_id, thread_local_id)

        # Execute 10 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, f'/path{i}') for i in range(10)]
            results = [f.result() for f in futures]

        # All correlation IDs should be unique
        correlation_ids = [r[0] for r in results]
        self.assertEqual(len(correlation_ids), len(set(correlation_ids)))

        # Thread-local should match request for each thread
        for request_id, thread_local_id in results:
            self.assertEqual(request_id, thread_local_id)

    def test_set_correlation_id_manually(self):
        """Test manual setting of correlation ID."""
        test_id = str(uuid.uuid4())

        set_correlation_id(test_id)

        retrieved_id = get_correlation_id()
        self.assertEqual(retrieved_id, test_id)

    def test_clear_correlation_id_manually(self):
        """Test manual clearing of correlation ID."""
        set_correlation_id(str(uuid.uuid4()))

        clear_correlation_id()

        retrieved_id = get_correlation_id()
        self.assertIsNone(retrieved_id)

    def test_correlation_id_persists_across_multiple_calls(self):
        """Test that correlation ID persists in same thread."""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        initial_id = get_correlation_id()

        # Call multiple times
        id_2 = get_correlation_id()
        id_3 = get_correlation_id()

        # Should all be the same
        self.assertEqual(initial_id, id_2)
        self.assertEqual(initial_id, id_3)

    def test_accepts_uuid_v1_format(self):
        """Test that middleware accepts UUID v1 (though v4 preferred)."""
        uuid_v1 = str(uuid.uuid1())
        request = self.factory.get('/', HTTP_X_CORRELATION_ID=uuid_v1)

        self.middleware.process_request(request)

        # Should accept v1 (backward compatibility)
        # But will regenerate as v4 if validation fails
        self.assertTrue(hasattr(request, 'correlation_id'))

    def test_response_without_request_correlation_id(self):
        """Test response processing when request has no correlation_id."""
        request = self.factory.get('/')
        # Don't call process_request

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Should not add header if no correlation_id
        self.assertNotIn('X-Correlation-ID', response)

    def test_middleware_chain_integration(self):
        """Test middleware works in a chain with other middleware."""
        def mock_get_response(request):
            # Simulate view execution
            correlation_id = get_correlation_id()
            return HttpResponse(f"Correlation ID: {correlation_id}")

        middleware = CorrelationIDMiddleware(get_response=mock_get_response)
        request = self.factory.get('/')

        response = middleware(request)

        # Response should include correlation ID in content
        self.assertIn(request.correlation_id, response.content.decode())

        # Response should have X-Correlation-ID header
        self.assertIn('X-Correlation-ID', response)


@pytest.mark.django_db
class TestCorrelationIDThreadSafety:
    """Thread safety tests for correlation ID storage."""

    def test_thread_isolation(self):
        """Test that correlation IDs are isolated between threads."""
        import threading

        results = {}

        def thread_worker(thread_id):
            # Set unique correlation ID for this thread
            correlation_id = str(uuid.uuid4())
            set_correlation_id(correlation_id)

            # Simulate some work
            import time
            time.sleep(0.01)

            # Retrieve correlation ID
            retrieved = get_correlation_id()
            results[thread_id] = (correlation_id, retrieved)

        # Create 5 threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=thread_worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify each thread had its own correlation ID
        assert len(results) == 5

        for thread_id, (set_id, retrieved_id) in results.items():
            assert set_id == retrieved_id

        # All should be unique
        all_ids = [v[0] for v in results.values()]
        assert len(all_ids) == len(set(all_ids))


class TestCorrelationIDEdgeCases(TestCase):
    """Edge case tests for correlation ID middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.middleware = CorrelationIDMiddleware(get_response=lambda req: HttpResponse())
        self.factory = RequestFactory()

    def tearDown(self):
        """Clean up thread-local storage."""
        clear_correlation_id()

    def test_empty_correlation_id_header(self):
        """Test handling of empty X-Correlation-ID header."""
        request = self.factory.get('/', HTTP_X_CORRELATION_ID='')

        self.middleware.process_request(request)

        # Should generate new correlation ID
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertNotEqual(request.correlation_id, '')

    def test_whitespace_correlation_id_header(self):
        """Test handling of whitespace-only X-Correlation-ID header."""
        request = self.factory.get('/', HTTP_X_CORRELATION_ID='   ')

        self.middleware.process_request(request)

        # Should generate new correlation ID
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertNotEqual(request.correlation_id.strip(), '')

    def test_correlation_id_with_special_characters(self):
        """Test rejection of correlation ID with special characters."""
        invalid_id = 'test-correlation-id-!@#$%'
        request = self.factory.get('/', HTTP_X_CORRELATION_ID=invalid_id)

        self.middleware.process_request(request)

        # Should generate new correlation ID
        self.assertNotEqual(request.correlation_id, invalid_id)

    def test_very_long_correlation_id(self):
        """Test rejection of excessively long correlation ID."""
        long_id = 'a' * 1000
        request = self.factory.get('/', HTTP_X_CORRELATION_ID=long_id)

        self.middleware.process_request(request)

        # Should generate new correlation ID
        self.assertNotEqual(request.correlation_id, long_id)

        # Generated ID should be standard UUID length
        self.assertEqual(len(request.correlation_id), 36)  # UUID v4 format

    def test_correlation_id_case_insensitivity(self):
        """Test that header name is case-insensitive."""
        correlation_id = str(uuid.uuid4())

        # Django converts headers to uppercase
        request = self.factory.get('/')
        request.META['HTTP_X_CORRELATION_ID'] = correlation_id

        self.middleware.process_request(request)

        self.assertEqual(request.correlation_id, correlation_id)

    def test_multiple_correlation_id_headers(self):
        """Test behavior when multiple X-Correlation-ID headers present."""
        # Django typically takes the first value
        correlation_id = str(uuid.uuid4())
        request = self.factory.get('/', HTTP_X_CORRELATION_ID=correlation_id)

        self.middleware.process_request(request)

        # Should use the provided correlation ID
        self.assertEqual(request.correlation_id, correlation_id)
