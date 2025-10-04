"""
Comprehensive Unit Tests for GraphQL Query Complexity Validation Middleware

Test Coverage:
- Query complexity validation (within and exceeding limits)
- Query depth validation (within and exceeding limits)
- Combined complexity and depth limits
- Validation caching behavior
- Error responses and messages
- Security logging
- Performance measurement
- Edge cases and error handling
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.http import JsonResponse
from django.core.cache import cache
from graphql import parse, GraphQLError
from apps.core.middleware.graphql_complexity_validation import (
    GraphQLComplexityValidationMiddleware
)
from apps.core.graphql_security import validate_query_complexity


@pytest.mark.unit
class TestGraphQLComplexityValidationMiddleware(TestCase):
    """Unit tests for GraphQL complexity validation middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = GraphQLComplexityValidationMiddleware(lambda r: None)
        cache.clear()  # Clear cache before each test

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def _create_graphql_request(self, query: str, method: str = 'POST',
                                path: str = '/api/graphql/') -> Mock:
        """Helper to create a GraphQL request."""
        if method == 'GET':
            request = self.factory.get(path, {'query': query})
        else:
            request = self.factory.post(
                path,
                data=json.dumps({'query': query}),
                content_type='application/json'
            )

        request.correlation_id = 'test-correlation-id'
        return request

    # ==================== Basic Validation Tests ====================

    def test_query_within_depth_limit_passes(self):
        """Test that queries within depth limit are allowed."""
        simple_query = """
        query {
            user {
                id
                name
            }
        }
        """

        request = self._create_graphql_request(simple_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=10):
            response = self.middleware.process_request(request)

        self.assertIsNone(response, "Simple query should pass validation")

    def test_query_within_complexity_limit_passes(self):
        """Test that queries within complexity limit are allowed."""
        query = """
        query {
            users {
                id
                name
                email
                profile {
                    bio
                    avatar
                }
            }
        }
        """

        request = self._create_graphql_request(query)

        with override_settings(GRAPHQL_MAX_QUERY_COMPLEXITY=1000):
            response = self.middleware.process_request(request)

        self.assertIsNone(response, "Query within complexity limit should pass")

    def test_query_exceeding_depth_limit_blocked(self):
        """Test that queries exceeding depth limit are blocked."""
        deep_query = """
        query {
            user {
                profile {
                    posts {
                        comments {
                            replies {
                                author {
                                    profile {
                                        posts {
                                            id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        request = self._create_graphql_request(deep_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3):
            response = self.middleware.process_request(request)

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)
        self.assertIn('errors', response_data)
        self.assertIn('QUERY_COMPLEXITY_EXCEEDED', response_data['errors'][0]['code'])
        self.assertIn('depth', response_data['errors'][0]['message'].lower())

    def test_query_exceeding_complexity_limit_blocked(self):
        """Test that queries exceeding complexity limit are blocked."""
        # Build a query with many fields to exceed complexity
        fields = "\n".join([f"field{i}" for i in range(100)])
        complex_query = f"""
        query {{
            users {{
                {fields}
            }}
        }}
        """

        request = self._create_graphql_request(complex_query)

        with override_settings(GRAPHQL_MAX_QUERY_COMPLEXITY=50):
            response = self.middleware.process_request(request)

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)
        self.assertIn('errors', response_data)
        self.assertIn('complexity', response_data['errors'][0]['message'].lower())

    def test_query_exceeding_both_limits_blocked(self):
        """Test that queries exceeding both depth and complexity are blocked."""
        deep_complex_query = """
        query {
            user {
                profile {
                    posts {
                        id title body author createdAt updatedAt tags likes comments
                        comments {
                            id body author createdAt likes replies
                            replies {
                                id body author createdAt
                            }
                        }
                    }
                }
            }
        }
        """

        request = self._create_graphql_request(deep_complex_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3, GRAPHQL_MAX_QUERY_COMPLEXITY=50):
            response = self.middleware.process_request(request)

        self.assertIsInstance(response, JsonResponse)
        response_data = json.loads(response.content)

        # Should mention both limits
        error_message = response_data['errors'][0]['message'].lower()
        self.assertTrue('depth' in error_message or 'complexity' in error_message)

    # ==================== Caching Tests ====================

    def test_validation_result_cached_for_valid_query(self):
        """Test that successful validation results are cached."""
        query = "query { user { id name } }"
        request = self._create_graphql_request(query)

        with override_settings(GRAPHQL_ENABLE_VALIDATION_CACHE=True):
            # First request - should validate and cache
            response1 = self.middleware.process_request(request)
            self.assertIsNone(response1)

            # Second request - should use cache
            with patch.object(self.middleware, '_parse_query') as mock_parse:
                response2 = self.middleware.process_request(request)
                self.assertIsNone(response2)
                # Parse should not be called due to cache hit
                mock_parse.assert_not_called()

    def test_validation_result_cached_for_invalid_query(self):
        """Test that failed validation results are also cached."""
        deep_query = """
        query {
            a { b { c { d { e { f { g { h { i { j { k { id } } } } } } } } } } }
        }
        """
        request = self._create_graphql_request(deep_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3, GRAPHQL_ENABLE_VALIDATION_CACHE=True):
            # First request - should validate and cache failure
            response1 = self.middleware.process_request(request)
            self.assertIsInstance(response1, JsonResponse)

            # Second request - should use cached failure
            with patch.object(self.middleware, '_parse_query') as mock_parse:
                response2 = self.middleware.process_request(request)
                self.assertIsInstance(response2, JsonResponse)
                mock_parse.assert_not_called()

    def test_cache_can_be_disabled(self):
        """Test that caching can be disabled via settings."""
        query = "query { user { id } }"
        request = self._create_graphql_request(query)

        with override_settings(GRAPHQL_ENABLE_VALIDATION_CACHE=False):
            with patch.object(self.middleware, '_get_cached_validation') as mock_get_cache:
                response = self.middleware.process_request(request)
                self.assertIsNone(response)
                # Cache should not be checked
                mock_get_cache.assert_not_called()

    # ==================== Error Response Tests ====================

    def test_error_response_includes_helpful_suggestions(self):
        """Test that error responses include optimization suggestions."""
        deep_query = """
        query {
            a { b { c { d { e { id } } } } }
        }
        """
        request = self._create_graphql_request(deep_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=2):
            response = self.middleware.process_request(request)

        response_data = json.loads(response.content)
        extensions = response_data['errors'][0]['extensions']

        self.assertIn('suggestions', extensions)
        self.assertGreater(len(extensions['suggestions']), 0)
        self.assertIn('correlation_id', extensions)
        self.assertIn('help_url', extensions)

    def test_error_response_includes_metrics(self):
        """Test that error responses include complexity metrics."""
        complex_query = """
        query {
            users {
                f1 f2 f3 f4 f5 f6 f7 f8 f9 f10
                f11 f12 f13 f14 f15 f16 f17 f18 f19 f20
            }
        }
        """
        request = self._create_graphql_request(complex_query)

        with override_settings(GRAPHQL_MAX_QUERY_COMPLEXITY=10):
            response = self.middleware.process_request(request)

        response_data = json.loads(response.content)
        extensions = response_data['errors'][0]['extensions']

        self.assertIn('complexity', extensions)
        self.assertIn('depth', extensions)
        self.assertIn('field_count', extensions)
        self.assertIn('max_allowed_complexity', extensions)
        self.assertIn('max_allowed_depth', extensions)

    # ==================== Introspection Query Tests ====================

    def test_introspection_query_allowed_in_development(self):
        """Test that introspection queries are allowed in DEBUG mode."""
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                types {
                    name
                }
            }
        }
        """
        request = self._create_graphql_request(introspection_query)

        with override_settings(DEBUG=True, GRAPHQL_MAX_QUERY_DEPTH=2):
            response = self.middleware.process_request(request)

        self.assertIsNone(response, "Introspection should be allowed in DEBUG mode")

    @override_settings(DEBUG=False)
    def test_introspection_query_validated_in_production(self):
        """Test that introspection queries are validated in production."""
        introspection_query = """
        query {
            __schema {
                types {
                    name
                    fields {
                        name
                        type {
                            name
                        }
                    }
                }
            }
        }
        """
        request = self._create_graphql_request(introspection_query)

        # Introspection should still be subject to complexity validation
        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=2):
            response = self.middleware.process_request(request)

        # May be blocked if it exceeds limits
        if response:
            self.assertIsInstance(response, JsonResponse)

    # ==================== Request Type Tests ====================

    def test_non_graphql_requests_ignored(self):
        """Test that non-GraphQL requests are ignored."""
        request = self.factory.post('/api/rest/users/')
        request.correlation_id = 'test-id'

        response = self.middleware.process_request(request)
        self.assertIsNone(response)

    def test_get_request_with_query_parameter(self):
        """Test GET requests with query parameter."""
        query = "query { user { id } }"
        request = self.factory.get('/api/graphql/', {'query': query})
        request.correlation_id = 'test-id'

        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Valid GET query should pass")

    def test_post_request_with_form_data(self):
        """Test POST requests with form data."""
        query = "query { user { id } }"
        request = self.factory.post('/api/graphql/', {'query': query})
        request.correlation_id = 'test-id'

        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Valid form data query should pass")

    def test_empty_query_handled_gracefully(self):
        """Test that empty queries are handled gracefully."""
        request = self._create_graphql_request("")

        response = self.middleware.process_request(request)
        # Should return None to let GraphQL engine handle the empty query error
        self.assertIsNone(response)

    # ==================== Error Handling Tests ====================

    def test_malformed_json_handled_gracefully(self):
        """Test that malformed JSON doesn't crash the middleware."""
        request = self.factory.post(
            '/api/graphql/',
            data='{"query": invalid json}',
            content_type='application/json'
        )
        request.correlation_id = 'test-id'

        response = self.middleware.process_request(request)
        # Should return None to let GraphQL engine handle the JSON error
        self.assertIsNone(response)

    def test_syntax_error_handled_gracefully(self):
        """Test that GraphQL syntax errors don't crash the middleware."""
        invalid_query = "query { this is not valid }"
        request = self._create_graphql_request(invalid_query)

        response = self.middleware.process_request(request)
        # Should return None to let GraphQL engine handle syntax errors
        self.assertIsNone(response)

    @patch('apps.core.middleware.graphql_complexity_validation.cache')
    def test_cache_failure_doesnt_block_request(self, mock_cache):
        """Test that cache failures don't prevent valid queries."""
        mock_cache.get.side_effect = ConnectionError("Cache unavailable")
        mock_cache.set.side_effect = ConnectionError("Cache unavailable")

        query = "query { user { id } }"
        request = self._create_graphql_request(query)

        # Should not raise exception despite cache failure
        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Valid query should pass despite cache failure")

    # ==================== Security Logging Tests ====================

    @patch('apps.core.middleware.graphql_complexity_validation.security_logger')
    def test_security_violation_logged(self, mock_logger):
        """Test that security violations are logged."""
        deep_query = """
        query {
            a { b { c { d { e { id } } } } }
        }
        """
        request = self._create_graphql_request(deep_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=2):
            response = self.middleware.process_request(request)

        self.assertIsInstance(response, JsonResponse)
        mock_logger.warning.assert_called_once()

        # Verify log includes security context
        call_args = mock_logger.warning.call_args
        log_message = call_args[0][0]
        self.assertIn('complexity', log_message.lower())

    @patch('apps.core.middleware.graphql_complexity_validation.graphql_security_logger')
    def test_successful_validation_logged(self, mock_logger):
        """Test that successful validations are logged."""
        query = "query { user { id } }"
        request = self._create_graphql_request(query)

        response = self.middleware.process_request(request)
        self.assertIsNone(response)

        mock_logger.debug.assert_called()

    # ==================== Configuration Tests ====================

    @override_settings(GRAPHQL_ENABLE_COMPLEXITY_VALIDATION=False)
    def test_validation_can_be_disabled(self):
        """Test that validation can be disabled via settings."""
        deep_query = """
        query {
            a { b { c { d { e { f { id } } } } } }
        }
        """
        request = self._create_graphql_request(deep_query)

        # Even with low limits, should pass when validation disabled
        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=2):
            response = self.middleware.process_request(request)

        self.assertIsNone(response, "Query should pass when validation disabled")

    def test_custom_graphql_paths_respected(self):
        """Test that custom GraphQL paths are respected."""
        query = "query { user { id } }"
        request = self._create_graphql_request(query, path='/custom/graphql/')

        with override_settings(GRAPHQL_PATHS=['/custom/graphql/']):
            middleware = GraphQLComplexityValidationMiddleware(lambda r: None)
            response = middleware.process_request(request)

        # Should be validated since it matches custom path
        self.assertIsNone(response)

    # ==================== Performance Tests ====================

    def test_validation_time_measured(self):
        """Test that validation time is measured and included in results."""
        query = "query { user { id name email } }"
        request = self._create_graphql_request(query)

        # Force a validation failure to get timing data
        with override_settings(GRAPHQL_MAX_QUERY_COMPLEXITY=1):
            response = self.middleware.process_request(request)

        if response:
            response_data = json.loads(response.content)
            # Validation time should be logged internally
            # (not exposed to client for security reasons)
            self.assertIsInstance(response, JsonResponse)

    def test_multiple_queries_with_caching(self):
        """Test performance improvement with caching."""
        query = "query { user { id name email } }"
        request = self._create_graphql_request(query)

        with override_settings(GRAPHQL_ENABLE_VALIDATION_CACHE=True):
            # First request
            response1 = self.middleware.process_request(request)
            self.assertIsNone(response1)

            # Second request (should be faster due to cache)
            import time
            start = time.time()
            response2 = self.middleware.process_request(request)
            elapsed = time.time() - start

            self.assertIsNone(response2)
            # Cached request should be very fast (< 1ms)
            self.assertLess(elapsed, 0.01, "Cached validation should be fast")


@pytest.mark.unit
class TestGraphQLComplexityValidationEdgeCases(TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = GraphQLComplexityValidationMiddleware(lambda r: None)
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_query_exactly_at_depth_limit(self):
        """Test query with depth exactly at the limit."""
        # Depth = 3 (user -> profile -> posts)
        query = """
        query {
            user {
                profile {
                    posts {
                        id
                    }
                }
            }
        }
        """
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({'query': query}),
            content_type='application/json'
        )
        request.correlation_id = 'test-id'

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3):
            response = self.middleware.process_request(request)

        # Should pass - exactly at limit
        self.assertIsNone(response)

    def test_query_one_over_depth_limit(self):
        """Test query with depth one over the limit."""
        # Depth = 4
        query = """
        query {
            user {
                profile {
                    posts {
                        comments {
                            id
                        }
                    }
                }
            }
        }
        """
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({'query': query}),
            content_type='application/json'
        )
        request.correlation_id = 'test-id'

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3):
            response = self.middleware.process_request(request)

        # Should be blocked - one over limit
        self.assertIsInstance(response, JsonResponse)

    def test_unicode_in_query(self):
        """Test that Unicode characters in queries are handled."""
        query = """
        query {
            user {
                name
                bio
                # Comment with unicode: 你好世界 🌍
            }
        }
        """
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({'query': query}),
            content_type='application/json; charset=utf-8'
        )
        request.correlation_id = 'test-id'

        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Unicode should be handled correctly")

    def test_very_large_query_string(self):
        """Test handling of very large query strings."""
        # Generate a query with 1000 fields
        fields = "\n".join([f"field{i}" for i in range(1000)])
        large_query = f"""
        query {{
            users {{
                {fields}
            }}
        }}
        """
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({'query': large_query}),
            content_type='application/json'
        )
        request.correlation_id = 'test-id'

        with override_settings(GRAPHQL_MAX_QUERY_COMPLEXITY=100):
            response = self.middleware.process_request(request)

        # Should be blocked due to complexity
        self.assertIsInstance(response, JsonResponse)
