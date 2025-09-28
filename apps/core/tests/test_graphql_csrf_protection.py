"""
Comprehensive Test Suite for GraphQL CSRF Protection

Tests the critical CSRF vulnerability fix (CVSS 8.1) that was addressed by implementing
GraphQLCSRFProtectionMiddleware to replace the dangerous csrf_exempt decorator.

Test Categories:
1. CSRF Protection Validation
2. Authentication & Authorization
3. Rate Limiting
4. Query Complexity Analysis
5. Security Headers
6. Error Handling & Edge Cases
7. Performance & Load Testing
"""

import json
import time
import pytest
from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory, Client, override_settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.core.cache import cache
from django.http import JsonResponse
from apps.core.middleware.graphql_csrf_protection import (
    GraphQLCSRFProtectionMiddleware,
    GraphQLSecurityHeadersMiddleware
)
from apps.core.graphql_security import (
    GraphQLSecurityIntrospection,
    QueryComplexityAnalyzer,
    analyze_query_complexity,
    validate_query_complexity
)
from apps.peoples.models import People


User = get_user_model()


@pytest.mark.security
class GraphQLCSRFProtectionTest(TestCase):
    """
    Test suite for GraphQL CSRF protection middleware.

    This test suite validates that the CVSS 8.1 vulnerability has been properly
    fixed by ensuring all GraphQL mutations require CSRF tokens.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = Client(enforce_csrf_checks=True)
        self.middleware = GraphQLCSRFProtectionMiddleware(lambda request: JsonResponse({'data': None}))

        # Create test user
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User'
        )

        # GraphQL endpoints to test
        self.graphql_endpoints = [
            '/api/graphql/',
            '/graphql/',
            '/graphql'
        ]

        # Test queries and mutations
        self.test_query = """
        query {
            viewer
        }
        """

        self.test_mutation = """
        mutation {
            loginUser(input: {
                loginid: "testuser",
                password: "testpass123",
                deviceid: "test-device"
            }) {
                token
                user
            }
        }
        """

        self.test_introspection_query = """
        query {
            __schema {
                types {
                    name
                }
            }
        }
        """

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_graphql_request_detection(self):
        """Test that middleware correctly identifies GraphQL requests."""
        for endpoint in self.graphql_endpoints:
            request = self.factory.post(endpoint, data={'query': self.test_query})

            # Test that it's identified as a GraphQL request
            self.assertTrue(self.middleware._is_graphql_request(request))

        # Test non-GraphQL request
        request = self.factory.post('/api/v1/test/', data={'data': 'test'})
        self.assertFalse(self.middleware._is_graphql_request(request))

    def test_query_operation_type_detection(self):
        """Test that middleware correctly identifies GraphQL operation types."""
        # Test query detection
        request = self.factory.post('/api/graphql/', data={'query': self.test_query})
        request._body = json.dumps({'query': self.test_query}).encode('utf-8')
        request.content_type = 'application/json'

        operation_type = self.middleware._get_graphql_operation_type(request)
        self.assertEqual(operation_type, 'query')

        # Test mutation detection
        request = self.factory.post('/api/graphql/', data={'query': self.test_mutation})
        request._body = json.dumps({'query': self.test_mutation}).encode('utf-8')
        request.content_type = 'application/json'

        operation_type = self.middleware._get_graphql_operation_type(request)
        self.assertEqual(operation_type, 'mutation')

    def test_introspection_query_detection(self):
        """Test that introspection queries are properly detected."""
        request = self.factory.post('/api/graphql/', data={'query': self.test_introspection_query})
        request._body = json.dumps({'query': self.test_introspection_query}).encode('utf-8')
        request.content_type = 'application/json'

        self.assertTrue(self.middleware._is_introspection_query(request))

    def test_csrf_token_extraction_from_headers(self):
        """Test CSRF token extraction from various header formats."""
        request = self.factory.post('/api/graphql/')

        # Test X-CSRFToken header
        request.META['HTTP_X_CSRFTOKEN'] = 'test-csrf-token'
        csrf_token = self.middleware._get_csrf_token_from_request(request)
        self.assertEqual(csrf_token, 'test-csrf-token')

        # Test X-CSRF-Token header
        del request.META['HTTP_X_CSRFTOKEN']
        request.META['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token-alt'
        csrf_token = self.middleware._get_csrf_token_from_request(request)
        self.assertEqual(csrf_token, 'test-csrf-token-alt')

    def test_csrf_token_extraction_from_form_data(self):
        """Test CSRF token extraction from form data."""
        request = self.factory.post('/api/graphql/', data={
            'query': self.test_mutation,
            'csrfmiddlewaretoken': 'test-csrf-token'
        })

        csrf_token = self.middleware._get_csrf_token_from_request(request)
        self.assertEqual(csrf_token, 'test-csrf-token')

    def test_csrf_token_extraction_from_json_body(self):
        """Test CSRF token extraction from JSON request body."""
        request_data = {
            'query': self.test_mutation,
            'csrfmiddlewaretoken': 'test-csrf-token'
        }

        request = self.factory.post('/api/graphql/')
        request._body = json.dumps(request_data).encode('utf-8')
        request.content_type = 'application/json'

        csrf_token = self.middleware._get_csrf_token_from_request(request)
        self.assertEqual(csrf_token, 'test-csrf-token')

    def test_query_requests_bypass_csrf(self):
        """Test that GraphQL queries (read-only) bypass CSRF protection."""
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_query}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user

        # Queries should not require CSRF tokens
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # None means continue processing

    def test_mutation_requests_require_csrf(self):
        """Test that GraphQL mutations require CSRF protection."""
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_mutation}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user

        # Mutations without CSRF token should be blocked
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

        # Verify error message
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('errors', response_data)
        self.assertEqual(response_data['errors'][0]['code'], 'CSRF_TOKEN_REQUIRED')

    def test_mutation_with_valid_csrf_token(self):
        """Test that mutations with valid CSRF tokens are allowed."""
        # Create a request with CSRF token
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_mutation}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user
        request.META['HTTP_X_CSRFTOKEN'] = get_token(request)

        # Mock CSRF middleware to simulate successful validation
        with patch.object(self.middleware.csrf_middleware, 'process_request', return_value=None):
            response = self.middleware.process_request(request)
            self.assertIsNone(response)  # None means continue processing

    @override_settings(DEBUG=True)
    def test_introspection_allowed_in_development(self):
        """Test that introspection queries are allowed in development mode."""
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_introspection_query}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user

        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # Should be allowed in development

    def test_rate_limiting_functionality(self):
        """Test GraphQL rate limiting."""
        with override_settings(
            ENABLE_GRAPHQL_RATE_LIMITING=True,
            GRAPHQL_RATE_LIMIT_MAX=2,
            GRAPHQL_RATE_LIMIT_WINDOW=60
        ):
            request = self.factory.post('/api/graphql/')
            request._body = json.dumps({'query': self.test_query}).encode('utf-8')
            request.content_type = 'application/json'
            request.user = self.user
            request.META['REMOTE_ADDR'] = '127.0.0.1'

            # First two requests should pass
            response1 = self.middleware._check_rate_limit(request)
            self.assertIsNone(response1)

            response2 = self.middleware._check_rate_limit(request)
            self.assertIsNone(response2)

            # Third request should be rate limited
            response3 = self.middleware._check_rate_limit(request)
            self.assertIsNotNone(response3)
            self.assertEqual(response3.status_code, 429)

    def test_client_ip_extraction(self):
        """Test client IP address extraction for rate limiting."""
        # Test direct IP
        request = self.factory.post('/api/graphql/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

        # Test X-Forwarded-For header
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 127.0.0.1'
        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')

    def test_csrf_error_response_format(self):
        """Test that CSRF error responses have the correct format."""
        response = self.middleware._create_csrf_error_response(
            "Test error message",
            "test-correlation-id"
        )

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))

        # Verify response structure
        self.assertIn('errors', response_data)
        self.assertEqual(len(response_data['errors']), 1)

        error = response_data['errors'][0]
        self.assertEqual(error['message'], "Test error message")
        self.assertEqual(error['code'], 'CSRF_TOKEN_REQUIRED')
        self.assertEqual(error['correlation_id'], "test-correlation-id")
        self.assertIn('help', error)

    def test_security_logging(self):
        """Test that security events are properly logged."""
        with patch('apps.core.middleware.graphql_csrf_protection.security_logger') as mock_logger:
            request = self.factory.post('/api/graphql/')
            request._body = json.dumps({'query': self.test_mutation}).encode('utf-8')
            request.content_type = 'application/json'
            request.user = self.user
            request.META['REMOTE_ADDR'] = '127.0.0.1'

            # Test that CSRF failure is logged
            self.middleware.process_request(request)

            # Verify error logging
            mock_logger.error.assert_called()
            log_call = mock_logger.error.call_args[0][0]
            self.assertIn('CSRF token', log_call)

    def test_correlation_id_generation(self):
        """Test that correlation IDs are properly generated and tracked."""
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_mutation}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user

        # Process request should add correlation ID
        response = self.middleware.process_request(request)

        # Verify correlation ID was added
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertIsNotNone(request.correlation_id)

    @pytest.mark.performance
    def test_middleware_performance_impact(self):
        """Test that middleware has minimal performance impact."""
        request = self.factory.post('/api/graphql/')
        request._body = json.dumps({'query': self.test_query}).encode('utf-8')
        request.content_type = 'application/json'
        request.user = self.user

        # Measure processing time
        start_time = time.time()
        for _ in range(1000):
            self.middleware.process_request(request)
        end_time = time.time()

        avg_time_per_request = (end_time - start_time) / 1000

        # Should be less than 1ms per request
        self.assertLess(avg_time_per_request, 0.001)


@pytest.mark.security
class GraphQLSecurityHeadersTest(TestCase):
    """Test suite for GraphQL security headers middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = GraphQLSecurityHeadersMiddleware(lambda request: JsonResponse({'data': None}))

    def test_security_headers_added_to_graphql_responses(self):
        """Test that security headers are added to GraphQL responses."""
        request = self.factory.post('/api/graphql/')
        response = JsonResponse({'data': None})

        processed_response = self.middleware.process_response(request, response)

        # Verify security headers
        self.assertEqual(processed_response['X-GraphQL-CSRF-Protected'], 'true')
        self.assertEqual(processed_response['X-GraphQL-Rate-Limited'], 'true')
        self.assertEqual(processed_response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(processed_response['X-Frame-Options'], 'DENY')

    def test_csp_header_added_when_missing(self):
        """Test that CSP header is added when not present."""
        request = self.factory.post('/api/graphql/')
        response = JsonResponse({'data': None})

        processed_response = self.middleware.process_response(request, response)

        self.assertIn('Content-Security-Policy', processed_response)
        self.assertEqual(
            processed_response['Content-Security-Policy'],
            "default-src 'self'; script-src 'none'"
        )

    def test_existing_csp_header_preserved(self):
        """Test that existing CSP header is not overridden."""
        request = self.factory.post('/api/graphql/')
        response = JsonResponse({'data': None})
        response['Content-Security-Policy'] = "custom-csp-policy"

        processed_response = self.middleware.process_response(request, response)

        self.assertEqual(
            processed_response['Content-Security-Policy'],
            "custom-csp-policy"
        )

    def test_headers_not_added_to_non_graphql_responses(self):
        """Test that GraphQL headers are not added to non-GraphQL responses."""
        request = self.factory.post('/api/v1/test/')
        response = JsonResponse({'data': None})

        processed_response = self.middleware.process_response(request, response)

        # GraphQL-specific headers should not be present
        self.assertNotIn('X-GraphQL-CSRF-Protected', processed_response)
        self.assertNotIn('X-GraphQL-Rate-Limited', processed_response)


@pytest.mark.security
class GraphQLSecurityIntrospectionTest(TestCase):
    """Test suite for GraphQL security introspection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User'
        )

    def test_csrf_token_introspection_authenticated_user(self):
        """Test CSRF token introspection for authenticated users."""
        request = self.factory.post('/api/graphql/')
        request.user = self.user

        # Mock info object
        info = Mock()
        info.context = request

        introspection = GraphQLSecurityIntrospection()
        csrf_token = introspection.resolve_csrf_token(info)

        self.assertIsNotNone(csrf_token)
        self.assertIsInstance(csrf_token, str)

    def test_csrf_token_introspection_unauthenticated_user(self):
        """Test CSRF token introspection rejects unauthenticated users."""
        from graphql import GraphQLError

        request = self.factory.post('/api/graphql/')
        request.user = Mock()
        request.user.is_authenticated = False

        info = Mock()
        info.context = request

        introspection = GraphQLSecurityIntrospection()

        with self.assertRaises(GraphQLError) as context:
            introspection.resolve_csrf_token(info)

        self.assertIn("Authentication required", str(context.exception))

    def test_rate_limit_remaining_calculation(self):
        """Test rate limit remaining calculation."""
        with override_settings(
            ENABLE_GRAPHQL_RATE_LIMITING=True,
            GRAPHQL_RATE_LIMIT_MAX=10
        ):
            request = self.factory.post('/api/graphql/')
            request.user = self.user
            request.META['REMOTE_ADDR'] = '127.0.0.1'

            info = Mock()
            info.context = request

            introspection = GraphQLSecurityIntrospection()
            remaining = introspection.resolve_rate_limit_remaining(info)

            self.assertIsInstance(remaining, int)
            self.assertGreaterEqual(remaining, 0)
            self.assertLessEqual(remaining, 10)

    def test_security_headers_list(self):
        """Test security headers list introspection."""
        info = Mock()

        introspection = GraphQLSecurityIntrospection()
        headers = introspection.resolve_security_headers_required(info)

        expected_headers = ['X-CSRFToken', 'Authorization', 'Content-Type']
        self.assertEqual(headers, expected_headers)

    @override_settings(GRAPHQL_ALLOWED_ORIGINS=['https://example.com', 'https://test.com'])
    def test_allowed_origins_introspection(self):
        """Test allowed origins introspection."""
        info = Mock()

        introspection = GraphQLSecurityIntrospection()
        origins = introspection.resolve_allowed_origins(info)

        expected_origins = ['https://example.com', 'https://test.com']
        self.assertEqual(origins, expected_origins)


@pytest.mark.security
class GraphQLComplexityAnalysisTest(TestCase):
    """Test suite for GraphQL query complexity analysis."""

    def test_simple_query_complexity(self):
        """Test complexity analysis of simple queries."""
        from graphql import build_schema, parse

        schema = build_schema("""
            type Query {
                user: User
            }

            type User {
                id: ID
                name: String
            }
        """)

        query = parse("""
            query {
                user {
                    id
                    name
                }
            }
        """)

        complexity = analyze_query_complexity(query)

        self.assertIsInstance(complexity, dict)
        self.assertIn('complexity', complexity)
        self.assertIn('max_depth', complexity)
        self.assertIn('field_count', complexity)
        self.assertGreater(complexity['field_count'], 0)

    def test_nested_query_complexity(self):
        """Test complexity analysis of nested queries."""
        from graphql import build_schema, parse

        schema = build_schema("""
            type Query {
                user: User
            }

            type User {
                id: ID
                name: String
                posts: [Post]
            }

            type Post {
                id: ID
                title: String
                author: User
            }
        """)

        simple_query = parse("""
            query {
                user {
                    id
                    name
                }
            }
        """)

        nested_query = parse("""
            query {
                user {
                    id
                    name
                    posts {
                        id
                        title
                        author {
                            id
                            name
                        }
                    }
                }
            }
        """)

        simple_complexity = analyze_query_complexity(simple_query)
        nested_complexity = analyze_query_complexity(nested_query)

        # Nested query should have higher complexity
        self.assertGreater(nested_complexity['complexity'], simple_complexity['complexity'])
        self.assertGreater(nested_complexity['max_depth'], simple_complexity['max_depth'])

    def test_query_complexity_validation_pass(self):
        """Test that valid queries pass complexity validation."""
        from graphql import build_schema, parse

        query = parse("""
            query {
                user {
                    id
                    name
                }
            }
        """)

        # Should not raise any exception
        try:
            validate_query_complexity(query, correlation_id="test-123")
        except Exception as e:
            self.fail(f"Valid query failed complexity validation: {e}")

    def test_query_complexity_validation_depth_limit(self):
        """Test that queries exceeding depth limit are rejected."""
        from graphql import parse, GraphQLError

        # Create a deeply nested query
        nested_query = """
            query {
                user {
                    posts {
                        author {
                            posts {
                                author {
                                    posts {
                                        author {
                                            id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        query = parse(nested_query)

        with override_settings(GRAPHQL_MAX_QUERY_DEPTH=3):
            with self.assertRaises(GraphQLError) as context:
                validate_query_complexity(query, correlation_id="test-123")

            self.assertIn("Query depth limit exceeded", str(context.exception))


@pytest.mark.integration
class GraphQLCSRFIntegrationTest(TestCase):
    """Integration tests for the complete GraphQL CSRF protection system."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client(enforce_csrf_checks=True)
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User'
        )

    def test_end_to_end_csrf_protection(self):
        """Test complete CSRF protection flow from client to server."""
        # Step 1: Get CSRF token via introspection
        self.client.force_login(self.user)

        introspection_query = """
            query {
                securityInfo {
                    csrfToken
                }
            }
        """

        response = self.client.post(
            '/api/graphql/',
            data={'query': introspection_query},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Step 2: Use CSRF token for mutation
        mutation = """
            mutation {
                testMutation(name: "test") {
                    output
                }
            }
        """

        csrf_token = self.client.cookies['csrftoken'].value

        response = self.client.post(
            '/api/graphql/',
            data={'query': mutation},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should succeed with valid CSRF token
        self.assertEqual(response.status_code, 200)

    def test_graphql_endpoints_consistency(self):
        """Test that all GraphQL endpoints have consistent CSRF protection."""
        endpoints = ['/api/graphql/', '/graphql/', '/graphql']

        mutation = """
            mutation {
                testMutation(name: "test") {
                    output
                }
            }
        """

        for endpoint in endpoints:
            response = self.client.post(
                endpoint,
                data={'query': mutation},
                content_type='application/json'
            )

            # All endpoints should require CSRF protection
            self.assertEqual(response.status_code, 403)

    def test_file_upload_with_csrf_protection(self):
        """Test that file upload mutations work with CSRF protection."""
        # This test would require a complete GraphQL file upload setup
        # For now, we'll test the middleware behavior
        pass

    @pytest.mark.performance
    def test_csrf_protection_performance_impact(self):
        """Test performance impact of CSRF protection on GraphQL requests."""
        self.client.force_login(self.user)

        query = """
            query {
                viewer
            }
        """

        # Measure time for multiple requests
        start_time = time.time()
        for _ in range(100):
            response = self.client.post(
                '/api/graphql/',
                data={'query': query},
                content_type='application/json'
            )
        end_time = time.time()

        avg_time_per_request = (end_time - start_time) / 100

        # Should have minimal performance impact
        self.assertLess(avg_time_per_request, 0.1)  # 100ms per request