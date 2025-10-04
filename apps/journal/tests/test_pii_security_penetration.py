"""
Security Penetration Tests for PII Protection

Adversarial tests that attempt to extract PII through various attack vectors:
- Parameter tampering
- SQL injection attempts in search queries
- XSS attempts in error messages
- Header manipulation
- Timing attacks for PII enumeration
- Cache poisoning attempts
- Error message mining
- Log injection attempts

Author: Claude Code
Date: 2025-10-01
"""

import pytest
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.security
class TestPIIExtractionAttempts(TestCase):
    """Test attempts to extract PII through various attack vectors"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="John Doe",
            tenant=self.tenant
        )

        self.attacker = User.objects.create_user(
            loginid="attacker",
            email="attacker@test.com",
            peoplename="Attacker User",
            tenant=self.tenant
        )

        # Create entry with sensitive data
        self.sensitive_entry = JournalEntry.objects.create(
            user=self.owner,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="My medical diagnosis",
            content="I was diagnosed with cancer today. My doctor john@hospital.com said...",
            mood_rating=2,
            privacy_scope='private'
        )

        self.client = APIClient()

    def test_parameter_tampering_user_id(self):
        """Test that attackers can't access PII by tampering with user_id parameter"""
        self.client.force_authenticate(user=self.attacker)

        # Try various parameter tampering techniques
        url = f'/journal/entries/{self.sensitive_entry.id}/'

        # Attempt 1: Add user_id parameter
        response = self.client.get(url, {'user_id': self.owner.id})
        assert response.status_code in [200, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert data['content'] == '[REDACTED]'
            assert 'cancer' not in str(data)

        # Attempt 2: Try to spoof owner in headers
        response = self.client.get(
            url,
            HTTP_X_USER_ID=str(self.owner.id),
            HTTP_X_OWNER=str(self.owner.id)
        )
        if response.status_code == 200:
            data = response.json()
            assert data['content'] == '[REDACTED]'

    def test_sql_injection_in_search(self):
        """Test that SQL injection attempts in search queries don't leak PII"""
        self.client.force_authenticate(user=self.attacker)

        url = '/journal/entries/'

        # SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE journal_entry; --",
            "' UNION SELECT * FROM journal_entry WHERE user_id = %s --" % self.owner.id,
            "cancer' OR title LIKE '%medical%",
        ]

        for payload in sql_payloads:
            response = self.client.get(url, {'search': payload})

            # Should either error safely or return redacted results
            if response.status_code == 200:
                data = response.json()
                # Should not contain raw PII
                response_text = str(data)
                assert 'cancer' not in response_text
                assert 'john@hospital.com' not in response_text

    def test_xss_in_error_messages(self):
        """Test that XSS attempts in input don't appear in error messages"""
        self.client.force_authenticate(user=self.attacker)

        url = '/journal/entries/'
        xss_payload = '<script>alert(document.cookie)</script>'

        data = {
            'title': xss_payload,
            'content': xss_payload,
            'entry_type': 'INVALID_TYPE',  # Force validation error
        }

        response = self.client.post(url, data, format='json')

        # Error message should not contain the raw XSS payload
        response_text = str(response.content)
        assert '<script>' not in response_text or '&lt;script&gt;' in response_text

    def test_error_message_mining_for_pii(self):
        """Test that error messages don't leak PII"""
        self.client.force_authenticate(user=self.attacker)

        # Try to trigger various errors
        url = f'/journal/entries/{self.sensitive_entry.id}/'

        # Attempt to update with malformed data
        data = {
            'title': 'x' * 10000,  # Very long title
            'mood_rating': 999,  # Invalid rating
        }

        response = self.client.patch(url, data, format='json')

        # Error message should not reveal entry details
        response_text = str(response.content)
        assert 'medical diagnosis' not in response_text
        assert 'cancer' not in response_text

    def test_timing_attack_for_entry_existence(self):
        """Test that timing attacks can't determine if entries exist"""
        import time
        self.client.force_authenticate(user=self.attacker)

        # Measure response time for existing entry
        url_exists = f'/journal/entries/{self.sensitive_entry.id}/'
        start = time.time()
        response_exists = self.client.get(url_exists)
        time_exists = time.time() - start

        # Measure response time for non-existing entry
        import uuid
        fake_id = uuid.uuid4()
        url_not_exists = f'/journal/entries/{fake_id}/'
        start = time.time()
        response_not_exists = self.client.get(url_not_exists)
        time_not_exists = time.time() - start

        # Time difference should be minimal (< 50ms)
        time_diff = abs(time_exists - time_not_exists)
        assert time_diff < 0.05, f"Timing attack possible: {time_diff:.3f}s difference"

    def test_cache_poisoning_attempt(self):
        """Test that cache poisoning can't expose PII"""
        self.client.force_authenticate(user=self.attacker)

        url = f'/journal/entries/{self.sensitive_entry.id}/'

        # Try various cache manipulation headers
        headers = {
            'HTTP_X_FORWARDED_FOR': '1.1.1.1',
            'HTTP_VIA': 'proxy',
            'HTTP_CACHE_CONTROL': 'no-cache',
        }

        response = self.client.get(url, **headers)

        if response.status_code == 200:
            data = response.json()
            assert data['content'] == '[REDACTED]'

    def test_header_injection_for_privilege_escalation(self):
        """Test that header injection can't grant access to PII"""
        self.client.force_authenticate(user=self.attacker)

        url = f'/journal/entries/{self.sensitive_entry.id}/'

        # Try to inject headers that might grant privileges
        malicious_headers = {
            'HTTP_X_IS_SUPERUSER': 'true',
            'HTTP_X_IS_OWNER': 'true',
            'HTTP_X_USER_ROLE': 'admin',
            'HTTP_AUTHORIZATION': f'Bearer fake_token_for_{self.owner.id}',
        }

        response = self.client.get(url, **malicious_headers)

        if response.status_code == 200:
            data = response.json()
            # Should still be redacted
            assert data['content'] == '[REDACTED]'


@pytest.mark.django_db
@pytest.mark.security
class TestLogInjectionPrevention(TestCase):
    """Test that log injection attempts are prevented"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user = User.objects.create_user(
            loginid="testuser",
            email="test@test.com",
            peoplename="Test User",
            tenant=self.tenant
        )

        self.client = APIClient()

    def test_log_injection_in_journal_entry(self, caplog):
        """Test that log injection attempts are sanitized"""
        self.client.force_authenticate(user=self.user)

        url = '/journal/entries/'

        # Log injection payload
        log_injection = "Normal title\n[ERROR] Fake error message\nUser: admin\nPassword: admin123"

        data = {
            'title': log_injection,
            'content': 'Normal content',
            'entry_type': 'PERSONAL_REFLECTION',
        }

        response = self.client.post(url, data, format='json')

        # Check that logs don't contain the injected newlines/fake errors
        for record in caplog.records:
            message = record.message
            # Newlines should be sanitized
            assert '\n[ERROR]' not in message
            assert 'Password: admin123' not in message


@pytest.mark.django_db
@pytest.mark.security
class TestBypassAttempts(TestCase):
    """Test attempts to bypass PII redaction"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="Alice Smith",
            tenant=self.tenant
        )

        self.attacker = User.objects.create_user(
            loginid="attacker",
            email="attacker@test.com",
            peoplename="Bob Hacker",
            tenant=self.tenant
        )

        self.entry = JournalEntry.objects.create(
            user=self.owner,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="My secret thoughts",
            content="Private content about my health issues",
            privacy_scope='private'
        )

        self.client = APIClient()

    def test_middleware_bypass_attempt_with_custom_path(self):
        """Test that middleware can't be bypassed with path manipulation"""
        self.client.force_authenticate(user=self.attacker)

        # Try various path manipulation techniques
        paths = [
            f'/journal/entries/{self.entry.id}/',
            f'/journal/../journal/entries/{self.entry.id}/',
            f'//journal/entries/{self.entry.id}/',
            f'/journal/entries/{self.entry.id}/../{self.entry.id}/',
        ]

        for path in paths:
            response = self.client.get(path)
            if response.status_code == 200:
                data = response.json()
                # Should still be redacted
                assert data['content'] == '[REDACTED]'

    def test_content_type_manipulation(self):
        """Test that changing content type doesn't bypass redaction"""
        self.client.force_authenticate(user=self.attacker)

        url = f'/journal/entries/{self.entry.id}/'

        # Try different content types
        content_types = [
            'application/json',
            'text/plain',
            'text/html',
            'application/xml',
        ]

        for content_type in content_types:
            response = self.client.get(
                url,
                HTTP_ACCEPT=content_type
            )

            if response.status_code == 200:
                # Content should still be redacted regardless of format
                response_text = str(response.content)
                assert 'health issues' not in response_text

    def test_bulk_endpoint_bypass_attempt(self):
        """Test that bulk endpoints don't leak PII"""
        self.client.force_authenticate(user=self.attacker)

        url = '/journal/entries/'

        # Try to get all entries in bulk
        response = self.client.get(url)

        if response.status_code == 200:
            data = response.json()
            # All entries should be redacted
            if isinstance(data, list):
                for entry in data:
                    if str(entry.get('id')) == str(self.entry.id):
                        assert entry['content'] == '[REDACTED]'


@pytest.mark.django_db
@pytest.mark.security
class TestWellnessPIIAttacks(TestCase):
    """Test PII attack vectors specific to wellness module"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user = User.objects.create_user(
            loginid="user",
            email="user@test.com",
            peoplename="User One",
            tenant=self.tenant
        )

        self.attacker = User.objects.create_user(
            loginid="attacker",
            email="attacker@test.com",
            peoplename="Attacker",
            tenant=self.tenant
        )

        self.admin = User.objects.create_superuser(
            loginid="admin",
            email="admin@test.com",
            peoplename="Admin",
            tenant=self.tenant
        )

        # Create wellness content
        self.content = WellnessContent.objects.create(
            title="Mental Health Support",
            content="Support content",
            category='MENTAL_HEALTH',
            created_by=self.admin,
            tenant=self.tenant
        )

        # Create interaction with sensitive feedback
        self.interaction = WellnessContentInteraction.objects.create(
            user=self.user,
            content=self.content,
            tenant=self.tenant,
            interaction_type='completed',
            user_feedback="This helped me cope with my depression after losing my job"
        )

        self.client = APIClient()

    def test_feedback_extraction_attempt(self):
        """Test that user feedback can't be extracted by attackers"""
        self.client.force_authenticate(user=self.attacker)

        url = f'/wellness/interactions/{self.interaction.id}/'
        response = self.client.get(url)

        if response.status_code == 200:
            data = response.json()
            # Feedback should be redacted
            assert data['user_feedback'] == '[REDACTED]'
            assert 'depression' not in str(data)
            assert 'losing my job' not in str(data)

    def test_recommendation_reason_mining(self):
        """Test that recommendation reasons don't leak journal content"""
        # This would test if recommendations leak info about user's journal entries
        # Implementation depends on actual recommendation API
        pass


@pytest.mark.django_db
@pytest.mark.security
class TestAuditLogSecurity(TestCase):
    """Test that audit logs themselves don't leak PII"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user = User.objects.create_user(
            loginid="user",
            email="user@test.com",
            peoplename="Test User",
            tenant=self.tenant
        )

        self.entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="Sensitive title with PII: john@example.com",
            content="Content with SSN: 123-45-6789",
            privacy_scope='private'
        )

        self.client = APIClient()

    def test_audit_log_fields_sanitized(self):
        """Test that audit logs don't store raw PII"""
        from apps.journal.models.pii_access_log import PIIAccessLog

        # Access the entry to trigger audit logging
        self.client.force_authenticate(user=self.user)
        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Check audit logs
        logs = PIIAccessLog.objects.filter(
            accessed_user=self.user,
            model_type='JournalEntry'
        )

        for log in logs:
            # Audit logs should not contain raw PII
            log_str = str(log.__dict__)
            assert 'john@example.com' not in log_str
            assert '123-45-6789' not in log_str
