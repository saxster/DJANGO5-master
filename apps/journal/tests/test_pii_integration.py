"""
Integration Tests for End-to-End PII Protection

Comprehensive integration tests that validate PII protection across the entire stack:
- HTTP request → middleware → view → serializer → response
- Logging sanitization in real request workflows
- Exception handling with PII redaction
- Audit trail creation
- Performance validation

Author: Claude Code
Date: 2025-10-01
"""

import pytest
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.journal.models.pii_access_log import PIIAccessLog, PIIRedactionEvent
from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestEndToEndPIIProtection(TestCase):
    """Test complete request-response cycle with PII protection"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        # Create users
        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="John Doe",
            tenant=self.tenant
        )
        self.owner.set_password("password123")
        self.owner.save()

        self.other_user = User.objects.create_user(
            loginid="other",
            email="other@test.com",
            peoplename="Jane Smith",
            tenant=self.tenant
        )
        self.other_user.set_password("password123")
        self.other_user.save()

        self.admin = User.objects.create_superuser(
            loginid="admin",
            email="admin@test.com",
            peoplename="Admin User",
            tenant=self.tenant
        )
        self.admin.set_password("password123")
        self.admin.save()

        # Create journal entry
        self.entry = JournalEntry.objects.create(
            user=self.owner,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="My Private Thoughts",
            content="I am feeling anxious about work today",
            mood_rating=5,
            stress_level=4,
            gratitude_items=["My family", "My health"],
            affirmations=["I am enough"],
            privacy_scope='private'
        )

        # API client
        self.client = APIClient()

    def test_owner_api_access_full_data(self):
        """Test that owner gets full data via API"""
        # Authenticate as owner
        self.client.force_authenticate(user=self.owner)

        # Make API request
        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Should get full data
        assert response.status_code == 200
        data = response.json()
        assert data['title'] == self.entry.title
        assert data['content'] == self.entry.content
        assert data['gratitude_items'] == self.entry.gratitude_items

    def test_non_owner_api_access_redacted_data(self):
        """Test that non-owner gets redacted data via API"""
        # Authenticate as other user
        self.client.force_authenticate(user=self.other_user)

        # Make API request
        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Should get redacted data
        assert response.status_code == 200
        data = response.json()
        assert data['title'] == '[REDACTED]' or data['title'] == '[TITLE]'
        assert data['content'] == '[REDACTED]'

    def test_redaction_header_present(self):
        """Test that X-PII-Redacted header is added when redaction occurs"""
        self.client.force_authenticate(user=self.other_user)

        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Check for transparency header
        assert response.has_header('X-PII-Redacted')
        assert response['X-PII-Redacted'] == 'true'

    def test_admin_api_access_partial_redaction(self):
        """Test that admin gets partially redacted data"""
        self.client.force_authenticate(user=self.admin)

        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Admin should see title markers
        assert data['title'] == '[TITLE]'
        # But content should still be redacted
        assert data['content'] == '[REDACTED]'

    def test_list_endpoint_redaction(self):
        """Test that list endpoints properly redact multiple entries"""
        # Create multiple entries
        for i in range(3):
            JournalEntry.objects.create(
                user=self.owner,
                tenant=self.tenant,
                entry_type='PERSONAL_REFLECTION',
                title=f"Entry {i}",
                content=f"Content {i}",
                privacy_scope='private'
            )

        self.client.force_authenticate(user=self.other_user)

        url = '/journal/entries/'
        response = self.client.get(url)

        assert response.status_code == 200
        data = response.json()

        # All entries should be redacted
        if isinstance(data, list):
            for entry in data:
                assert entry['title'] == '[REDACTED]'
        elif 'results' in data:  # Paginated response
            for entry in data['results']:
                assert entry['title'] == '[REDACTED]'

    def test_audit_log_created_on_redacted_access(self):
        """Test that audit logs are created when redacted data is accessed"""
        # Clear existing logs
        PIIAccessLog.objects.all().delete()

        self.client.force_authenticate(user=self.other_user)

        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Check audit log was created
        logs = PIIAccessLog.objects.filter(
            user=self.other_user,
            accessed_user=self.owner,
            model_type='JournalEntry'
        )

        assert logs.exists()
        log = logs.first()
        assert log.was_redacted == True
        assert log.access_type == 'read'

    def test_redaction_event_logged(self):
        """Test that redaction events are logged"""
        # Clear existing events
        PIIRedactionEvent.objects.all().delete()

        self.client.force_authenticate(user=self.other_user)

        url = f'/journal/entries/{self.entry.id}/'
        response = self.client.get(url)

        # Check redaction event was logged
        events = PIIRedactionEvent.objects.filter(
            model_type='JournalEntry',
            instance_id=self.entry.id
        )

        assert events.exists()
        event = events.first()
        assert 'content' in event.fields_redacted or 'title' in event.fields_redacted


@pytest.mark.django_db
class TestExceptionHandlingPII(TestCase):
    """Test that exceptions don't leak PII"""

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
        self.user.set_password("password123")
        self.user.save()

        self.client = APIClient()

    def test_validation_error_no_pii_leak(self):
        """Test that validation errors don't leak PII"""
        self.client.force_authenticate(user=self.user)

        # Try to create entry with invalid data
        url = '/journal/entries/'
        data = {
            'title': 'My private thoughts about sensitive topic',
            'content': 'I am john@example.com and my SSN is 123-45-6789',
            'entry_type': 'INVALID_TYPE',  # This will cause validation error
        }

        response = self.client.post(url, data, format='json')

        # Should get error response
        assert response.status_code == 400

        # Error message should not contain the PII from content
        response_text = str(response.content)
        assert 'john@example.com' not in response_text
        assert '123-45-6789' not in response_text

    def test_permission_denied_no_entry_details(self):
        """Test that permission denied errors don't reveal entry details"""
        # Create entry as user
        entry = JournalEntry.objects.create(
            user=self.user,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="Secret Entry",
            content="Very secret content",
            privacy_scope='private'
        )

        # Create another user
        other_user = User.objects.create_user(
            loginid="other",
            email="other@test.com",
            peoplename="Other User",
            tenant=self.tenant
        )

        self.client.force_authenticate(user=other_user)

        # Try to update the entry (should be denied)
        url = f'/journal/entries/{entry.id}/'
        data = {'title': 'Changed Title'}

        response = self.client.patch(url, data, format='json')

        # Should be forbidden or not found
        assert response.status_code in [403, 404]

        # Error message should not reveal entry title
        response_text = str(response.content)
        assert 'Secret Entry' not in response_text

    def test_500_error_sanitized(self):
        """Test that 500 errors don't leak PII in stack traces"""
        # This test would require triggering an actual 500 error
        # For now, we verify the exception middleware is in place
        from django.conf import settings

        middleware = settings.MIDDLEWARE
        assert 'apps.journal.exceptions.pii_safe_exception_handler.PIISafeExceptionMiddleware' in middleware


@pytest.mark.django_db
class TestLoggingIntegration(TestCase):
    """Test that logging is properly sanitized in real workflows"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user = User.objects.create_user(
            loginid="testuser",
            email="test@test.com",
            peoplename="John Doe",
            tenant=self.tenant
        )
        self.user.set_password("password123")
        self.user.save()

        self.client = APIClient()

    def test_entry_creation_logs_sanitized(self, caplog):
        """Test that entry creation logs are sanitized"""
        self.client.force_authenticate(user=self.user)

        url = '/journal/entries/'
        data = {
            'title': 'My anxious thoughts',
            'content': 'I am feeling very anxious today',
            'entry_type': 'PERSONAL_REFLECTION',
            'privacy_scope': 'private'
        }

        response = self.client.post(url, data, format='json')

        # Check that logs don't contain raw PII
        # Note: This depends on logging configuration
        for record in caplog.records:
            message = record.message
            # Titles should be sanitized in logs
            if 'anxious thoughts' in message.lower():
                # If the title appears, it should be with a redaction marker
                assert '[TITLE]' in message or '[REDACTED]' in message


@pytest.mark.django_db
class TestWellnessIntegration(TestCase):
    """Test wellness endpoints have PII protection"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user1 = User.objects.create_user(
            loginid="user1",
            email="user1@test.com",
            peoplename="Alice Smith",
            tenant=self.tenant
        )
        self.user1.set_password("password123")
        self.user1.save()

        self.user2 = User.objects.create_user(
            loginid="user2",
            email="user2@test.com",
            peoplename="Bob Jones",
            tenant=self.tenant
        )
        self.user2.set_password("password123")
        self.user2.save()

        self.admin = User.objects.create_superuser(
            loginid="admin",
            email="admin@test.com",
            peoplename="Admin User",
            tenant=self.tenant
        )

        # Create wellness content
        self.content = WellnessContent.objects.create(
            title="Stress Management",
            summary="Stress tips",
            content="Detailed content",
            category='MENTAL_HEALTH',
            created_by=self.admin,
            tenant=self.tenant
        )

        # Create interaction with feedback
        self.interaction = WellnessContentInteraction.objects.create(
            user=self.user1,
            content=self.content,
            tenant=self.tenant,
            interaction_type='completed',
            user_feedback="This helped me with my anxiety issues"
        )

        self.client = APIClient()

    def test_wellness_interaction_feedback_redacted_for_others(self):
        """Test that wellness feedback is redacted for non-owners"""
        self.client.force_authenticate(user=self.user2)

        url = f'/wellness/interactions/{self.interaction.id}/'
        response = self.client.get(url)

        if response.status_code == 200:
            data = response.json()
            # Feedback should be redacted
            assert data['user_feedback'] == '[REDACTED]'

    def test_wellness_interaction_feedback_visible_to_owner(self):
        """Test that wellness feedback is visible to owner"""
        self.client.force_authenticate(user=self.user1)

        url = f'/wellness/interactions/{self.interaction.id}/'
        response = self.client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['user_feedback'] == self.interaction.user_feedback


@pytest.mark.django_db
class TestPerformanceIntegration(TestCase):
    """Test that PII protection doesn't significantly impact performance"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="Test User",
            tenant=self.tenant
        )

        self.other_user = User.objects.create_user(
            loginid="other",
            email="other@test.com",
            peoplename="Other User",
            tenant=self.tenant
        )

        # Create 20 entries
        for i in range(20):
            JournalEntry.objects.create(
                user=self.owner,
                tenant=self.tenant,
                entry_type='PERSONAL_REFLECTION',
                title=f"Entry {i}",
                content=f"Content {i}",
                gratitude_items=[f"Item {i}"],
                privacy_scope='private'
            )

        self.client = APIClient()

    def test_list_endpoint_performance_with_redaction(self):
        """Test that list endpoint with redaction completes in reasonable time"""
        import time

        self.client.force_authenticate(user=self.other_user)

        url = '/journal/entries/'

        start_time = time.time()
        response = self.client.get(url)
        elapsed_time = time.time() - start_time

        # Should complete in < 200ms even with redaction
        assert elapsed_time < 0.2, f"Request too slow: {elapsed_time:.3f}s"
        assert response.status_code == 200

    def test_detail_endpoint_performance_with_redaction(self):
        """Test that detail endpoint with redaction is fast"""
        import time

        entry = JournalEntry.objects.filter(user=self.owner).first()
        self.client.force_authenticate(user=self.other_user)

        url = f'/journal/entries/{entry.id}/'

        start_time = time.time()
        response = self.client.get(url)
        elapsed_time = time.time() - start_time

        # Should complete in < 100ms
        assert elapsed_time < 0.1, f"Request too slow: {elapsed_time:.3f}s"
        assert response.status_code == 200
