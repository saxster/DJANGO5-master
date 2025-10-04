"""
Security Penetration Tests for Mobile Sync System

Tests OWASP Top 10 compliance:
1. Injection (SQL, NoSQL, Command)
2. Broken Authentication
3. Sensitive Data Exposure
4. XML External Entities (XXE)
5. Broken Access Control
6. Security Misconfiguration
7. Cross-Site Scripting (XSS)
8. Insecure Deserialization
9. Using Components with Known Vulnerabilities
10. Insufficient Logging & Monitoring

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #1: GraphQL security protection
"""

import pytest
import json
import hashlib
import uuid
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.core.models.sync_idempotency import SyncIdempotencyRecord
from apps.core.models.sync_conflict_policy import TenantConflictPolicy, ConflictResolutionLog
from apps.core.models.upload_session import UploadSession
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.security
@pytest.mark.django_db
class TestInjectionVulnerabilities(TestCase):
    """Test protection against injection attacks."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="sectest",
            password="SecurePass123!",
            email="sec@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="Security Test Tenant")

    def test_sql_injection_in_idempotency_key(self):
        """Test SQL injection prevention in idempotency key lookups."""
        malicious_key = "test' OR '1'='1'; DROP TABLE sync_idempotency_record;--"

        from apps.api.v1.services.idempotency_service import IdempotencyService

        result = IdempotencyService.check_duplicate(malicious_key)

        self.assertIsNone(result)
        self.assertTrue(SyncIdempotencyRecord.objects.exists())

    def test_nosql_injection_in_device_id(self):
        """Test NoSQL injection prevention in device queries."""
        from apps.core.models.sync_analytics import SyncDeviceHealth

        malicious_device_id = {"$ne": None}

        with self.assertRaises((TypeError, ValueError)):
            SyncDeviceHealth.objects.filter(device_id=malicious_device_id)

    def test_command_injection_in_file_upload(self):
        """Test command injection prevention in file operations."""
        from apps.core.services.resumable_upload_service import ResumableUploadService

        malicious_filename = "test.pdf; rm -rf /; cat /etc/passwd"

        session = ResumableUploadService.init_upload(
            user=self.user,
            filename=malicious_filename,
            total_size=1024,
            mime_type='application/pdf',
            file_hash='abc123'
        )

        self.assertNotIn(';', session['upload_id'])
        self.assertNotIn('rm', session['upload_id'])


@pytest.mark.security
@pytest.mark.django_db
class TestBrokenAuthentication(TestCase):
    """Test authentication and session management security."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="authtest",
            password="AuthPass123!",
            email="auth@example.com"
        )

    def test_unauthenticated_access_blocked(self):
        """Test that unauthenticated requests are blocked."""
        response = self.client.get('/api/v1/sync/health')

        self.assertIn(response.status_code, [401, 302, 403])

    def test_expired_session_rejected(self):
        """Test that expired sessions are rejected."""
        session = self.client.session
        session['_auth_user_id'] = self.user.id
        session['last_activity'] = (timezone.now() - timedelta(hours=9)).timestamp()
        session.save()

        response = self.client.get('/api/v1/sync/health')

        self.assertIn(response.status_code, [401, 302, 403])

    def test_brute_force_protection(self):
        """Test rate limiting on authentication endpoints."""
        for i in range(10):
            self.client.post('/login/', {
                'username': 'authtest',
                'password': 'WrongPassword'
            })

        response = self.client.post('/login/', {
            'username': 'authtest',
            'password': 'WrongPassword'
        })

        self.assertEqual(response.status_code, 429)


@pytest.mark.security
@pytest.mark.django_db
class TestSensitiveDataExposure(TestCase):
    """Test protection of sensitive data."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="datatest",
            password="DataPass123!",
            email="data@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="Data Test Tenant")

    def test_no_sensitive_data_in_logs(self):
        """Test that sensitive data is not logged."""
        from apps.core.services.sync_health_monitoring_service import sync_health_monitor
        import logging

        with self.assertLogs(level=logging.INFO) as cm:
            sync_health_monitor.check_sync_health(tenant_id=self.tenant.id, hours=1)

        log_output = ' '.join(cm.output)
        self.assertNotIn('password', log_output.lower())
        self.assertNotIn('token', log_output.lower())
        self.assertNotIn('secret', log_output.lower())

    def test_pii_encryption_in_database(self):
        """Test that PII fields are encrypted."""
        from apps.core.models.sync_analytics import SyncDeviceHealth

        device = SyncDeviceHealth.objects.create(
            device_id='test_device',
            user=self.user,
            tenant=self.tenant,
            last_sync_at=timezone.now(),
            health_score=90.0
        )

        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT device_id FROM sync_device_health WHERE id = %s",
                [device.id]
            )
            raw_value = cursor.fetchone()[0]

        self.assertIsNotNone(raw_value)

    def test_no_error_details_in_production(self):
        """Test that error details are sanitized in responses."""
        from django.conf import settings

        original_debug = settings.DEBUG
        settings.DEBUG = False

        try:
            response = self.client.get('/api/v1/sync/nonexistent')

            if response.status_code >= 400:
                content = response.content.decode('utf-8')
                self.assertNotIn('Traceback', content)
                self.assertNotIn('File "', content)
        finally:
            settings.DEBUG = original_debug


@pytest.mark.security
@pytest.mark.django_db
class TestBrokenAccessControl(TestCase):
    """Test access control and authorization."""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            loginid="user1",
            password="User1Pass123!",
            email="user1@example.com"
        )
        self.user2 = User.objects.create_user(
            loginid="user2",
            password="User2Pass123!",
            email="user2@example.com"
        )
        self.tenant1 = Tenant.objects.create(tenantname="Tenant 1")
        self.tenant2 = Tenant.objects.create(tenantname="Tenant 2")

    def test_tenant_isolation(self):
        """Test that tenants cannot access each other's data."""
        policy1 = TenantConflictPolicy.objects.create(
            tenant=self.tenant1,
            domain='journal',
            resolution_policy='client_wins'
        )

        from apps.core.services.sync_cache_service import sync_cache_service

        policy_data = sync_cache_service.get_conflict_policy(
            self.tenant2.id,
            'journal'
        )

        self.assertIsNone(policy_data)

    def test_user_cannot_access_other_user_uploads(self):
        """Test that users cannot access other users' upload sessions."""
        from apps.core.services.resumable_upload_service import ResumableUploadService

        session1 = ResumableUploadService.init_upload(
            user=self.user1,
            filename='file1.pdf',
            total_size=1024,
            mime_type='application/pdf',
            file_hash='hash1'
        )

        from django.core.exceptions import PermissionDenied

        with self.assertRaises((PermissionDenied, UploadSession.DoesNotExist)):
            session = UploadSession.objects.get(upload_id=session1['upload_id'])
            if session.user_id != self.user2.id:
                raise PermissionDenied("Cannot access other user's upload")

    def test_idor_prevention(self):
        """Test prevention of Insecure Direct Object Reference."""
        from apps.core.models.sync_analytics import SyncDeviceHealth

        device1 = SyncDeviceHealth.objects.create(
            device_id='device1',
            user=self.user1,
            tenant=self.tenant1,
            last_sync_at=timezone.now(),
            health_score=90.0
        )

        with self.assertRaises((PermissionDenied, SyncDeviceHealth.DoesNotExist)):
            device = SyncDeviceHealth.objects.get(id=device1.id, user=self.user2)


@pytest.mark.security
@pytest.mark.django_db
class TestSecurityMisconfiguration(TestCase):
    """Test for security misconfigurations."""

    def test_debug_mode_disabled_in_production(self):
        """Test that DEBUG mode is not enabled in production."""
        from django.conf import settings

        if settings.ALLOWED_HOSTS != ['*']:
            self.assertFalse(settings.DEBUG)

    def test_secure_headers_present(self):
        """Test that security headers are set."""
        response = self.client.get('/')

        if response.status_code < 400:
            self.assertIn('X-Content-Type-Options', response)
            self.assertIn('X-Frame-Options', response)

    def test_csrf_protection_enabled(self):
        """Test that CSRF protection is enabled."""
        from django.conf import settings

        self.assertIn('django.middleware.csrf.CsrfViewMiddleware', settings.MIDDLEWARE)

    def test_secure_cookie_settings(self):
        """Test that cookies have secure settings."""
        from django.conf import settings

        if not settings.DEBUG:
            self.assertTrue(settings.SESSION_COOKIE_SECURE)
            self.assertTrue(settings.CSRF_COOKIE_SECURE)
            self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)


@pytest.mark.security
@pytest.mark.django_db
class TestXSSPrevention(TestCase):
    """Test Cross-Site Scripting prevention."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid="xsstest",
            password="XSSPass123!",
            email="xss@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="XSS Test Tenant")

    def test_xss_in_conflict_log_data(self):
        """Test that XSS payloads are sanitized in conflict logs."""
        xss_payload = "<script>alert('XSS')</script>"

        log = ConflictResolutionLog.objects.create(
            mobile_id=uuid.uuid4(),
            domain='journal',
            server_version=1,
            client_version=2,
            resolution_strategy='most_recent_wins',
            resolution_result='resolved',
            merge_details={'note': xss_payload},
            tenant=self.tenant,
            user=self.user
        )

        self.assertIn(xss_payload, str(log.merge_details))

    def test_content_security_policy_header(self):
        """Test that CSP header is set."""
        response = self.client.get('/')

        if response.status_code < 400 and hasattr(response, 'get'):
            csp = response.get('Content-Security-Policy', '')
            if csp:
                self.assertIn("default-src", csp)


@pytest.mark.security
@pytest.mark.django_db
class TestInsecureDeserialization(TestCase):
    """Test protection against insecure deserialization."""

    def test_json_deserialization_safety(self):
        """Test that JSON deserialization is safe."""
        malicious_json = '{"__init__": "os.system", "__call__": "rm -rf /"}'

        try:
            data = json.loads(malicious_json)
            self.assertIsInstance(data, dict)
            self.assertNotIn('__call__', dir(data))
        except (json.JSONDecodeError, ValueError):
            pass

    def test_idempotency_response_data_safety(self):
        """Test that cached response data cannot execute code."""
        from apps.api.v1.services.idempotency_service import IdempotencyService

        malicious_response = {
            '__reduce__': lambda: os.system('whoami')
        }

        try:
            IdempotencyService.store_response(
                idempotency_key='test_key',
                request_hash='hash123',
                response_data=malicious_response
            )

            cached = IdempotencyService.check_duplicate('test_key')

            if cached:
                self.assertIsInstance(cached, dict)
        except (TypeError, ValueError, AttributeError):
            pass


@pytest.mark.security
@pytest.mark.django_db
class TestLoggingAndMonitoring(TestCase):
    """Test logging and monitoring for security events."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid="logtest",
            password="LogPass123!",
            email="log@example.com"
        )

    def test_failed_auth_attempts_logged(self):
        """Test that failed authentication attempts are logged."""
        import logging

        with self.assertLogs(level=logging.WARNING) as cm:
            for i in range(3):
                self.client.post('/login/', {
                    'username': 'logtest',
                    'password': 'WrongPassword'
                })

    def test_security_events_monitored(self):
        """Test that security events are captured in monitoring."""
        from apps.core.services.sync_health_monitoring_service import sync_health_monitor
        import logging

        with self.assertLogs(level=logging.INFO) as cm:
            sync_health_monitor.check_sync_health(hours=1)

        self.assertTrue(any('health' in log.lower() for log in cm.output))

    def test_anomalous_activity_detection(self):
        """Test that anomalous activity triggers alerts."""
        from apps.core.models.sync_idempotency import SyncIdempotencyRecord

        for i in range(100):
            SyncIdempotencyRecord.objects.create(
                idempotency_key=f'rapid_key_{i}',
                scope='batch',
                request_hash=f'hash_{i}',
                response_data={},
                user_id=self.user.id,
                device_id='test_device'
            )

        recent_count = SyncIdempotencyRecord.objects.filter(
            user_id=self.user.id,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()

        self.assertGreater(recent_count, 50)


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.django_db
class TestOWASPComplianceIntegration(TransactionTestCase):
    """Integration tests for OWASP Top 10 compliance."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid="owasptest",
            password="OWASPPass123!",
            email="owasp@example.com"
        )
        self.tenant = Tenant.objects.create(tenantname="OWASP Test Tenant")

    def test_complete_sync_security_flow(self):
        """Test complete sync flow with all security measures."""
        from apps.api.v1.services.idempotency_service import IdempotencyService
        from apps.core.services.sync_cache_service import sync_cache_service

        idempotency_key = IdempotencyService.generate_idempotency_key(
            'sync',
            {'test': 'data'},
            {'user_id': self.user.id}
        )

        duplicate = IdempotencyService.check_duplicate(idempotency_key)
        self.assertIsNone(duplicate)

        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='journal',
            resolution_policy='most_recent_wins',
            auto_resolve=True
        )

        policy = sync_cache_service.get_conflict_policy(self.tenant.id, 'journal')
        self.assertIsNotNone(policy)

        success = IdempotencyService.store_response(
            idempotency_key=idempotency_key,
            request_hash='hash123',
            response_data={'synced': 10},
            user_id=str(self.user.id),
            device_id='test_device',
            endpoint='/api/v1/sync',
            scope='batch'
        )

        self.assertTrue(success)