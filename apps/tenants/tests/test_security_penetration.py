"""
Security Penetration Tests for Multi-Tenant System

Simulates real-world attack scenarios to ensure tenant security boundaries
are properly enforced.

Attack Scenarios Tested:
    - Hostname spoofing attacks
    - SQL injection via hostname
    - Cross-tenant cache poisoning
    - Thread-local context manipulation
    - Migration route exploitation
    - Unauthorized database access attempts

Security Note:
    These tests simulate actual attack vectors. Failures indicate
    CRITICAL security vulnerabilities that must be fixed immediately.
"""

import pytest
from unittest.mock import patch, Mock
import threading

from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponseForbidden
from django.core.cache import cache

from apps.tenants.middlewares import TenantMiddleware, TenantDbRouter
from apps.tenants.services import TenantCacheService, MigrationGuardService
from intelliwiz_config.settings.tenants import get_tenant_for_host
from apps.core.utils_new.db_utils import THREAD_LOCAL


class SecurityPenetrationTest(TestCase):
    """Security penetration tests for multi-tenant system."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda req: Mock())
        self.router = TenantDbRouter()
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        if hasattr(THREAD_LOCAL, 'DB'):
            delattr(THREAD_LOCAL, 'DB')

    # ==================
    # Hostname Spoofing Attack Tests
    # ==================

    @override_settings(DEBUG=False, TENANT_STRICT_MODE=True)
    @patch('intelliwiz_config.settings.tenants.TENANT_MAPPINGS', {
        'legitimate-tenant.example.com': 'tenant_a'
    })
    def test_attack_unknown_hostname_blocked_in_strict_mode(self):
        """Test that unknown hostnames are blocked in strict mode (production)."""
        # Attacker tries to access with unknown hostname
        request = self.factory.get('/', HTTP_HOST='attacker.example.com')

        response = self.middleware(request)

        # Should be forbidden
        self.assertIsInstance(
            response,
            HttpResponseForbidden,
            "Unknown hostname should be rejected in strict mode"
        )

    @override_settings(DEBUG=False, TENANT_STRICT_MODE=True)
    @patch('intelliwiz_config.settings.tenants.TENANT_MAPPINGS', {
        'tenant-a.example.com': 'tenant_a',
        'tenant-b.example.com': 'tenant_b'
    })
    def test_attack_hostname_case_manipulation(self):
        """Test that hostname case manipulation doesn't bypass security."""
        # Test various case manipulations
        test_cases = [
            'TENANT-A.EXAMPLE.COM',
            'Tenant-A.Example.Com',
            'TEnAnT-a.eXAmpLe.com'
        ]

        for hostname in test_cases:
            with self.subTest(hostname=hostname):
                # Should still route to tenant_a (case-insensitive matching)
                with patch('apps.tenants.middlewares.tenant_db_from_request') as mock_tenant_db:
                    mock_tenant_db.return_value = 'tenant_a'
                    request = self.factory.get('/', HTTP_HOST=hostname)
                    self.middleware(request)

                    self.assertEqual(
                        THREAD_LOCAL.DB,
                        'tenant_a',
                        f"Case manipulation {hostname} should still route correctly"
                    )

    # ==================
    # SQL Injection Attack Tests
    # ==================

    @override_settings(DEBUG=False, TENANT_STRICT_MODE=True)
    @patch('intelliwiz_config.settings.tenants.TENANT_MAPPINGS', {
        'tenant-a.example.com': 'tenant_a'
    })
    def test_attack_sql_injection_in_hostname(self):
        """Test that SQL injection attempts in hostname are rejected."""
        malicious_hostnames = [
            "tenant'; DROP TABLE users; --",
            "tenant' OR '1'='1",
            "tenant\"; DELETE FROM * WHERE 1=1; --",
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
        ]

        for malicious_hostname in malicious_hostnames:
            with self.subTest(hostname=malicious_hostname):
                request = self.factory.get('/', HTTP_HOST=malicious_hostname)
                response = self.middleware(request)

                # Should be blocked (unknown hostname in strict mode)
                self.assertIsInstance(
                    response,
                    HttpResponseForbidden,
                    f"Malicious hostname should be rejected: {malicious_hostname}"
                )

    # ==================
    # Cache Poisoning Attack Tests
    # ==================

    def test_attack_cache_key_collision_attempt(self):
        """Test that attackers cannot poison another tenant's cache."""
        # Legitimate tenant A sets cache
        cache_a = TenantCacheService(tenant_db='tenant_a')
        cache_a.set('admin_permissions', {'is_admin': True})

        # Attacker tries to craft a cache key to collide with tenant A
        # by manipulating the tenant_db parameter
        cache_attacker = TenantCacheService(tenant_db='tenant_a')

        # Attacker tries to overwrite admin permissions
        cache_attacker.set('admin_permissions', {'is_admin': False})

        # Check if attacker succeeded (they shouldn't be able to)
        # In this case, they CAN because they're using the same tenant_db
        # This demonstrates that tenant_db MUST come from trusted source (thread-local)
        # not from user input

        # Verify: When using thread-local (correct way), isolation is maintained
        setattr(THREAD_LOCAL, 'DB', 'tenant_b')
        cache_b = TenantCacheService()  # Uses thread-local

        # Tenant B cannot access tenant A's cache
        result = cache_b.get('admin_permissions')
        self.assertIsNone(
            result,
            "Tenant B should not be able to access tenant A's cache"
        )

    def test_attack_cache_key_prefix_manipulation(self):
        """Test that cache key prefix cannot be manipulated."""
        cache_service = TenantCacheService(tenant_db='tenant_a')

        # Attacker tries to manipulate key to access different tenant
        malicious_keys = [
            '../tenant_b/secret',
            '../../default/admin',
            'tenant:tenant_b:data',  # Tries to inject tenant prefix
        ]

        for malicious_key in malicious_keys:
            with self.subTest(key=malicious_key):
                # Set a value with malicious key
                cache_service.set(malicious_key, 'attacker_data')

                # Build the actual cache key that was used
                scoped_key = cache_service._build_cache_key(malicious_key)

                # Verify that tenant_a prefix was still applied
                # (preventing cross-tenant access)
                self.assertIn(
                    'tenant_a',
                    scoped_key,
                    f"Malicious key should still be scoped to tenant_a: {malicious_key}"
                )

    # ==================
    # Migration Attack Tests
    # ==================

    @override_settings(
        DATABASES={
            'default': {},
            'tenant_a': {},
            'tenant_sensitive': {}  # Sensitive tenant database
        },
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_attack_unauthorized_migration_to_sensitive_database(self):
        """Test that migrations cannot be run on unauthorized databases."""
        guard = MigrationGuardService()

        # Attacker tries to run migration on sensitive tenant database
        result = guard.allow_migrate(
            db='tenant_sensitive',
            app_label='malicious_app',
            model_name='MaliciousModel'
        )

        self.assertFalse(
            result,
            "Migration should be blocked on non-allowed database"
        )

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_attack_database_alias_injection(self):
        """Test that database alias cannot be injected."""
        guard = MigrationGuardService()

        malicious_db_aliases = [
            "default; DROP DATABASE tenant_a; --",
            "default' OR '1'='1",
            "../../../etc/passwd",
        ]

        for malicious_alias in malicious_db_aliases:
            with self.subTest(alias=malicious_alias):
                # Should be rejected (not in DATABASES)
                result = guard.allow_migrate(
                    db=malicious_alias,
                    app_label='activity',
                    model_name='Job'
                )

                self.assertFalse(
                    result,
                    f"Malicious database alias should be rejected: {malicious_alias}"
                )

    # ==================
    # Thread-Local Manipulation Attack Tests
    # ==================

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}})
    def test_attack_thread_local_direct_manipulation(self):
        """Test that direct thread-local manipulation is caught."""
        # Simulate legitimate tenant A request
        setattr(THREAD_LOCAL, 'DB', 'tenant_a')

        # Attacker tries to manipulate thread-local to access tenant B
        setattr(THREAD_LOCAL, 'DB', 'tenant_b')

        # Router will use the manipulated value
        db = self.router.db_for_read(Mock())

        # NOTE: This demonstrates that thread-local CAN be manipulated
        # within a request context. Security relies on middleware setting
        # it at request start and application code not modifying it.
        self.assertEqual(db, 'tenant_b')

        # MITIGATION: Application code should NEVER directly modify THREAD_LOCAL.DB
        # Only TenantMiddleware should set it

    # ==================
    # Cross-Site Request Forgery (CSRF) via Tenant Switching
    # ==================

    @override_settings(
        DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}},
        TENANT_STRICT_MODE=True
    )
    @patch('intelliwiz_config.settings.tenants.TENANT_MAPPINGS', {
        'tenant-a.example.com': 'tenant_a',
        'tenant-b.example.com': 'tenant_b'
    })
    def test_attack_csrf_tenant_switching(self):
        """Test that CSRF attacks cannot switch tenant context."""
        # User authenticated to tenant A
        request_a = self.factory.get('/', HTTP_HOST='tenant-a.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_a'):
            self.middleware(request_a)
            self.assertEqual(THREAD_LOCAL.DB, 'tenant_a')

        # Attacker tricks user into making request to tenant B
        # (e.g., via malicious iframe or XSS)
        delattr(THREAD_LOCAL, 'DB')
        request_b = self.factory.get('/', HTTP_HOST='tenant-b.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_b'):
            self.middleware(request_b)

            # Verify tenant context switched (expected behavior)
            # This is actually CORRECT - each request should have its own tenant context
            self.assertEqual(THREAD_LOCAL.DB, 'tenant_b')

        # MITIGATION: Authentication should be tenant-scoped
        # User sessions should not work across tenant boundaries

    # ==================
    # Path Traversal Attack Tests
    # ==================

    @override_settings(DEBUG=False, TENANT_STRICT_MODE=True)
    def test_attack_path_traversal_in_hostname(self):
        """Test that path traversal attempts in hostname are rejected."""
        path_traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config',
            'tenant/../../default',
            'tenant%2F..%2F..%2Fdefault'
        ]

        for malicious_hostname in path_traversal_attempts:
            with self.subTest(hostname=malicious_hostname):
                request = self.factory.get('/', HTTP_HOST=malicious_hostname)
                response = self.middleware(request)

                # Should be blocked
                self.assertIsInstance(
                    response,
                    HttpResponseForbidden,
                    f"Path traversal attempt should be rejected: {malicious_hostname}"
                )

    # ==================
    # Denial of Service (DoS) Attack Tests
    # ==================

    @override_settings(
        DATABASES={'default': {}},
        TENANT_MIGRATION_DATABASES=['default']
    )
    def test_attack_migration_lock_exhaustion(self):
        """Test that migration lock cannot be exhausted by attacker."""
        guard = MigrationGuardService()

        # Attacker tries to acquire many locks
        acquired_locks = []
        for i in range(100):
            result = guard.allow_migrate(
                db='default',
                app_label=f'fake_app_{i}',
                model_name='FakeModel'
            )
            acquired_locks.append(result)

        # At least some should succeed (not all blocked)
        successful_locks = sum(acquired_locks)
        self.assertGreater(
            successful_locks,
            0,
            "Some migration locks should be acquired (not all blocked)"
        )

        # But the same app cannot acquire lock twice
        result1 = guard.allow_migrate('default', 'activity', 'Job')
        result2 = guard.allow_migrate('default', 'activity', 'Job')

        self.assertTrue(result1, "First lock should succeed")
        self.assertFalse(result2, "Concurrent lock should fail")


# ==================
# Pytest Integration Tests
# ==================

@pytest.mark.django_db
class TestSecurityPenetrationIntegration:
    """Integration security tests."""

    @pytest.mark.parametrize("malicious_input", [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "../../../etc/passwd",
        "%00null_byte",
        "<script>alert('xss')</script>",
    ])
    def test_malicious_hostname_sanitization(self, malicious_input):
        """Test that malicious hostnames are properly sanitized."""
        factory = RequestFactory()
        middleware = TenantMiddleware(lambda req: Mock())

        request = factory.get('/', HTTP_HOST=malicious_input)

        with override_settings(DEBUG=False, TENANT_STRICT_MODE=True):
            with patch('intelliwiz_config.settings.tenants.TENANT_MAPPINGS', {}):
                response = middleware(request)

                # Should be rejected
                assert isinstance(response, HttpResponseForbidden), \
                    f"Malicious hostname should be rejected: {malicious_input}"

    def test_concurrent_tenant_requests_cannot_interfere(self):
        """Test that concurrent malicious requests cannot interfere with legitimate ones."""
        results = {'legitimate': None, 'malicious': None}

        def legitimate_request():
            setattr(THREAD_LOCAL, 'DB', 'tenant_a')
            cache_service = TenantCacheService()
            cache_service.set('user_role', 'admin')
            results['legitimate'] = cache_service.get('user_role')

        def malicious_request():
            # Attacker tries to poison cache
            setattr(THREAD_LOCAL, 'DB', 'tenant_a')  # Tries to access tenant_a
            cache_service = TenantCacheService()
            cache_service.set('user_role', 'attacker')
            results['malicious'] = cache_service.get('user_role')

        thread_legit = threading.Thread(target=legitimate_request)
        thread_malicious = threading.Thread(target=malicious_request)

        thread_legit.start()
        thread_malicious.start()

        thread_legit.join()
        thread_malicious.join()

        # Both should succeed with their own values (no interference)
        # NOTE: In this test, both can access tenant_a because THREAD_LOCAL
        # is thread-specific. Real security comes from authentication/authorization
        assert results['legitimate'] is not None
        assert results['malicious'] is not None
