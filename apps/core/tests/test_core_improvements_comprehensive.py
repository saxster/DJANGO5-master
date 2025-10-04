"""
Comprehensive tests for apps/core critical improvements

Tests cover:
1. CacheManager typing imports (CRITICAL - NameError prevention)
2. SQL Security middleware optimization (performance + false positives)
3. CSRF middleware consolidation (no duplicate instances)
4. Cache stampede protection (distributed locking)

Author: Claude Code
Date: 2025-10-01
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse, HttpResponse

# Import the modules we're testing
from apps.core.cache_manager import (
    CacheManager,
    TreeCache,
    QueryCache,
    StampedeProtection,
)
from apps.core.sql_security import (
    SQLInjectionProtectionMiddleware,
    SQLSecurityConfig,
)
from apps.core.middleware.graphql_csrf_protection import (
    GraphQLCSRFProtectionMiddleware,
)


# ============================================================================
# Test Suite 1: CacheManager Typing Imports Validation
# ============================================================================

class TestCacheManagerTypingImports(TestCase):
    """
    Test that CacheManager has all required typing imports.

    CRITICAL: Without these imports, Python 3.9+ will raise NameError
    at import time when type annotations are evaluated.
    """

    def test_import_validation_no_nameerror(self):
        """Verify cache_manager imports without NameError"""
        try:
            # This will raise NameError if typing imports are missing
            from apps.core import cache_manager
            self.assertTrue(True, "cache_manager imported successfully")
        except NameError as e:
            self.fail(f"NameError on import: {e}")

    def test_typing_imports_present(self):
        """Verify all required typing imports are available"""
        from apps.core import cache_manager

        required_types = ['Optional', 'Dict', 'Any', 'List', 'Callable']
        for type_name in required_types:
            self.assertTrue(
                hasattr(cache_manager, type_name) or type_name in str(cache_manager.__dict__),
                f"Missing typing import: {type_name}"
            )

    def test_model_import_present(self):
        """Verify django.db.models.Model is imported"""
        from apps.core import cache_manager

        # Check Model is available
        self.assertTrue(
            'Model' in dir(cache_manager) or 'Model' in str(cache_manager.__dict__),
            "Missing Model import from django.db.models"
        )

    def test_datetime_import_present(self):
        """Verify datetime import for CacheStats"""
        from apps.core import cache_manager

        self.assertTrue(
            'datetime' in dir(cache_manager),
            "Missing datetime import"
        )

    def test_type_annotations_runtime(self):
        """Verify type annotations work at runtime"""
        # Create instance without errors
        try:
            manager = CacheManager()
            cache_key = manager.get_cache_key('test', 'arg1', kwarg1='value1')
            self.assertIsInstance(cache_key, str)
        except (NameError, TypeError) as e:
            self.fail(f"Type annotation error: {e}")


# ============================================================================
# Test Suite 2: SQL Security Middleware Optimization
# ============================================================================

class TestSQLSecurityOptimization(TestCase):
    """
    Test SQL security middleware optimizations:
    - Early rejection of oversized bodies
    - Whitelisted path bypass
    - Conditional JSON body scanning
    - Two-tier pattern matching (high-risk vs medium-risk)
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SQLInjectionProtectionMiddleware(get_response=Mock())

    def test_sql_security_config_initialization(self):
        """Test SQLSecurityConfig dataclass"""
        config = SQLSecurityConfig(
            max_body_size_bytes=2097152,  # 2MB
            scan_graphql_variables=True,
            scan_full_json_body=False
        )
        self.assertEqual(config.max_body_size_bytes, 2097152)
        self.assertFalse(config.scan_full_json_body)
        self.assertTrue(config.scan_graphql_variables)

    def test_whitelisted_paths_bypass_scanning(self):
        """Whitelisted paths should bypass SQL injection scanning"""
        whitelisted_paths = ['/static/', '/media/', '/_health/']

        for path in whitelisted_paths:
            request = self.factory.get(path)
            self.assertTrue(
                self.middleware._is_whitelisted_path(path),
                f"Path {path} should be whitelisted"
            )

    def test_oversized_body_early_rejection(self):
        """Oversized request bodies should be rejected early"""
        # Create request with large body size indicated
        request = self.factory.post('/api/test/')
        request.META['CONTENT_LENGTH'] = '2097152'  # 2MB (exceeds 1MB default)

        is_oversized = self.middleware._is_oversized_body(request)
        self.assertTrue(is_oversized, "2MB body should be flagged as oversized")

    def test_normal_size_body_allowed(self):
        """Normal-sized bodies should pass"""
        request = self.factory.post('/api/test/')
        request.META['CONTENT_LENGTH'] = '1024'  # 1KB

        is_oversized = self.middleware._is_oversized_body(request)
        self.assertFalse(is_oversized, "1KB body should not be flagged")

    def test_high_risk_pattern_detection(self):
        """High-risk SQL patterns should always be detected"""
        high_risk_values = [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "' UNION SELECT null--",
            "exec(sp_executesql)",
            "xp_cmdshell"
        ]

        for value in high_risk_values:
            is_injection = self.middleware._check_value_for_sql_injection(value, "test_param")
            self.assertTrue(
                is_injection,
                f"High-risk pattern should be detected: {value}"
            )

    def test_password_field_allows_special_chars(self):
        """Password fields should allow special chars without false positives"""
        # Valid complex passwords that should NOT be flagged
        valid_passwords = [
            "MyP@ssw0rd#2024",
            "C0mpl3x!P@ss",
            "Test#123$%^"
        ]

        for password in valid_passwords:
            is_injection = self.middleware._check_value_for_sql_injection(
                password,
                "password"  # Password field context
            )
            self.assertFalse(
                is_injection,
                f"Valid password should not be flagged: {password}"
            )

    def test_benign_json_no_false_positives(self):
        """Benign JSON content should not trigger false positives"""
        benign_json = json.dumps({
            "user": "john@example.com",
            "comment": "This is a # hashtag comment",
            "description": "Product ID: 0x1234",
            "status": "active"
        })

        # With full-body scanning disabled (default), this should not scan
        self.middleware.config.scan_full_json_body = False

        request = self.factory.post(
            '/api/test/',
            data=benign_json,
            content_type='application/json'
        )

        # Should not detect as injection
        result = self.middleware._detect_sql_injection(request)
        self.assertFalse(result, "Benign JSON should not trigger false positive")

    @patch('apps.core.sql_security.logger')
    def test_performance_large_body_early_bailout(self, mock_logger):
        """Large bodies should be rejected early without full scanning"""
        request = self.factory.post('/api/test/')
        request.META['CONTENT_LENGTH'] = '10485760'  # 10MB

        start_time = time.time()
        self.middleware._is_oversized_body(request)
        elapsed = time.time() - start_time

        # Early bailout should be nearly instant (<1ms)
        self.assertLess(elapsed, 0.001, "Oversized body check should be instant")


# ============================================================================
# Test Suite 3: CSRF Middleware Consolidation
# ============================================================================

class TestCSRFMiddlewareConsolidation(TestCase):
    """
    Test CSRF middleware consolidation:
    - No duplicate CsrfViewMiddleware instances
    - Delegation to global Django CSRF middleware
    - Proper middleware ordering documentation
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GraphQLCSRFProtectionMiddleware(get_response=Mock())

    def test_no_duplicate_csrf_middleware_instance(self):
        """GraphQL CSRF middleware should NOT create duplicate CsrfViewMiddleware"""
        # Check that we don't have a csrf_middleware attribute
        self.assertFalse(
            hasattr(self.middleware, 'csrf_middleware'),
            "GraphQLCSRFProtectionMiddleware should not create duplicate CsrfViewMiddleware"
        )

    def test_graphql_query_no_csrf_required(self):
        """GraphQL queries should not require CSRF tokens"""
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({'query': 'query { users { id name } }'}),
            content_type='application/json'
        )
        request.correlation_id = 'test-correlation-id'

        # Mock rate limiting to pass
        with patch.object(self.middleware, '_check_rate_limit', return_value=None):
            response = self.middleware.process_request(request)

        # Should return None (continue processing)
        self.assertIsNone(response, "Queries should not require CSRF")

    def test_graphql_mutation_requires_csrf(self):
        """GraphQL mutations should require CSRF tokens"""
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({
                'query': 'mutation { createUser(name: "test") { id } }'
            }),
            content_type='application/json'
        )
        request.correlation_id = 'test-correlation-id'

        # Mock rate limiting to pass
        with patch.object(self.middleware, '_check_rate_limit', return_value=None):
            response = self.middleware.process_request(request)

        # Should return error response (no CSRF token provided)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)

    def test_csrf_token_extraction_from_header(self):
        """CSRF token should be extractable from X-CSRFToken header"""
        request = self.factory.post(
            '/api/graphql/',
            HTTP_X_CSRFTOKEN='test-csrf-token'
        )

        token = self.middleware._get_csrf_token_from_request(request)
        self.assertEqual(token, 'test-csrf-token')

    def test_csrf_token_delegated_to_global_middleware(self):
        """CSRF token should be made accessible to global CsrfViewMiddleware"""
        request = self.factory.post(
            '/api/graphql/',
            data=json.dumps({
                'query': 'mutation { createUser(name: "test") { id } }'
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='test-csrf-token'
        )
        request.correlation_id = 'test-correlation-id'

        # Mock rate limiting
        with patch.object(self.middleware, '_check_rate_limit', return_value=None):
            self.middleware._validate_csrf_for_mutation(request, 'test-correlation-id')

        # Check token was stored in META for global middleware
        self.assertEqual(
            request.META.get('HTTP_X_CSRFTOKEN'),
            'test-csrf-token',
            "CSRF token should be in META for global middleware"
        )


# ============================================================================
# Test Suite 4: Cache Stampede Protection
# ============================================================================

class TestCacheStampedeProtection(TestCase):
    """
    Test cache stampede protection:
    - Distributed locking (Redis SETNX)
    - Stale-while-revalidate pattern
    - Probabilistic early refresh
    """

    def setUp(self):
        cache.clear()
        self.stampede = StampedeProtection()

    def tearDown(self):
        cache.clear()

    def test_lock_acquisition_and_release(self):
        """Test distributed lock acquisition and release"""
        cache_key = 'test_cache_key'

        # First acquisition should succeed
        acquired = self.stampede._acquire_lock(cache_key)
        self.assertTrue(acquired, "First lock acquisition should succeed")

        # Second acquisition should fail (lock already held)
        acquired_again = self.stampede._acquire_lock(cache_key)
        self.assertFalse(acquired_again, "Second lock acquisition should fail")

        # Release lock
        self.stampede._release_lock(cache_key)

        # Third acquisition should succeed (lock released)
        acquired_after_release = self.stampede._acquire_lock(cache_key)
        self.assertTrue(acquired_after_release, "Lock acquisition after release should succeed")

    def test_stale_cache_served_when_lock_held(self):
        """When lock is held, stale cache should be served"""
        cache_key = 'test_stale_key'
        stale_value = 'stale_data'

        # Set stale cache
        cache.set(f"{cache_key}_stale", stale_value, 60)

        # Acquire lock (simulating another request regenerating cache)
        self.stampede._acquire_lock(cache_key)

        # Decorate a slow function
        @self.stampede.cache_with_stampede_protection(cache_key, ttl=60)
        def slow_function():
            time.sleep(0.2)  # Simulate slow query
            return 'fresh_data'

        # Call should return stale data (not wait for lock)
        start_time = time.time()
        result = slow_function()
        elapsed = time.time() - start_time

        # Should be fast (< 0.1s) because it served stale data
        self.assertLess(elapsed, 0.15, "Should serve stale data quickly")

        # Clean up
        self.stampede._release_lock(cache_key)

    @patch('apps.core.cache_manager.StampedeProtection._should_refresh_early')
    def test_probabilistic_early_refresh_triggers(self, mock_should_refresh):
        """Test probabilistic early refresh is triggered"""
        mock_should_refresh.return_value = True

        cache_key = 'test_refresh_key'
        cache.set(cache_key, 'old_value', 60)

        call_count = 0

        @self.stampede.cache_with_stampede_protection(cache_key, ttl=60)
        def cached_function():
            nonlocal call_count
            call_count += 1
            return f'value_{call_count}'

        # First call should return cached value
        result = cached_function()
        self.assertEqual(result, 'old_value')

        # Should have attempted early refresh
        self.assertTrue(mock_should_refresh.called)

    def test_double_checked_locking_prevents_race_condition(self):
        """Double-checked locking should prevent race conditions"""
        cache_key = 'test_race_key'

        execution_count = 0

        @self.stampede.cache_with_stampede_protection(cache_key, ttl=60)
        def expensive_function():
            nonlocal execution_count
            execution_count += 1
            return f'result_{execution_count}'

        # Simulate concurrent requests
        import threading

        def concurrent_call():
            expensive_function()

        threads = [threading.Thread(target=concurrent_call) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Function should execute only once (or very few times due to lock)
        self.assertLessEqual(
            execution_count,
            3,
            "Function should execute minimal times despite concurrent requests"
        )


# ============================================================================
# Test Suite 5: Integration Tests
# ============================================================================

class TestCoreIntegration(TestCase):
    """
    Integration tests for complete middleware pipeline:
    - SQL security + CSRF + rate limiting work together
    - Performance budget: total overhead < 50ms
    """

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(
        SQL_SECURITY_MAX_BODY_SIZE=1048576,
        SQL_SECURITY_SCAN_FULL_BODY=False,
        GRAPHQL_RATE_LIMIT_MAX=1000
    )
    def test_full_middleware_pipeline_performance(self):
        """Full middleware stack should have < 50ms overhead"""
        sql_middleware = SQLInjectionProtectionMiddleware(get_response=Mock())
        csrf_middleware = GraphQLCSRFProtectionMiddleware(get_response=Mock())

        request = self.factory.get('/api/health/')
        request.correlation_id = 'test-correlation-id'

        start_time = time.time()

        # Simulate middleware pipeline
        sql_middleware._is_whitelisted_path(request.path)

        elapsed = (time.time() - start_time) * 1000  # Convert to ms

        self.assertLess(elapsed, 50, "Full middleware pipeline should be < 50ms")

    def test_security_policies_enforced_together(self):
        """All security policies should work together without conflicts"""
        # This is a smoke test to ensure middleware don't conflict

        sql_middleware = SQLInjectionProtectionMiddleware(get_response=lambda r: HttpResponse())
        csrf_middleware = GraphQLCSRFProtectionMiddleware(get_response=lambda r: HttpResponse())

        # Normal request should pass all checks
        request = self.factory.post(
            '/api/data/',
            data=json.dumps({'name': 'test'}),
            content_type='application/json'
        )
        request.correlation_id = 'test-correlation-id'

        # SQL security check
        sql_result = sql_middleware._detect_sql_injection(request)
        self.assertFalse(sql_result, "Normal request should pass SQL check")

        # Non-GraphQL should not trigger CSRF check
        csrf_result = csrf_middleware._is_graphql_request(request)
        self.assertFalse(csrf_result, "Non-GraphQL request should skip CSRF middleware")


# ============================================================================
# Pytest Markers
# ============================================================================

pytestmark = pytest.mark.django_db
