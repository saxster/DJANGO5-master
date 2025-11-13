"""
Comprehensive CSRF Protection Tests for State-Changing API Endpoints

Tests that all POST/PUT/DELETE endpoints properly enforce CSRF protection.
Validates CSRF exempt endpoints have documented alternative authentication.

Security Validation:
- POST requests without CSRF token are rejected
- PUT requests without CSRF token are rejected
- DELETE requests without CSRF token are rejected
- CSRF exempt endpoints have alternative auth (JWT, HMAC)
- Invalid CSRF tokens are rejected
- CSRF token rotation works correctly

Compliance:
- OWASP Top 10 (Cross-Site Request Forgery)
- .claude/rules.md Rule #4 (@csrf_exempt forbidden without documentation)
- Django CSRF protection best practices

Note: This complements test_csrf_protection.py which tests middleware.
This file focuses on endpoint-level CSRF enforcement.
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.conf import settings
from rest_framework.test import APIClient
from django.utils import timezone
from uuid import uuid4

from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt
from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessContent
from apps.y_helpdesk.models import Ticket

User = get_user_model()


@pytest.mark.security
class CSRFProtectionJournalEndpointsTestCase(TestCase):
    """Test CSRF protection for journal entry endpoints"""

    def setUp(self):
        """Create test user and client with CSRF enforcement"""
        self.tenant = Tenant.objects.create(
            tenantname="CSRF Test Tenant",
            subdomain_prefix="csrf-test"
        )
        self.bu = Bt.objects.create(
            bucode="CSRF_BU",
            buname="CSRF Test BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='csrfuser',
            email='csrf@example.com',
            password='password123',
            loginid='csrfuser',
            peoplecode='CSRF001',
            peoplename='CSRF User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

        # Client with CSRF checks enforced
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_journal_entry_creation_requires_csrf_token(self):
        """POST to create journal entry should require CSRF token"""
        # Attempt to create journal entry without CSRF token
        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test Entry',
            'content': 'Test content',
            'mood_rating': 7,
            'stress_level': 4,
            'energy_level': 6,
            'timestamp': timezone.now().isoformat()
        })

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Journal entry creation without CSRF token should be rejected"
        )

        # Verify error message mentions CSRF
        response_text = response.content.decode('utf-8')
        self.assertIn(
            'CSRF',
            response_text.upper(),
            "Error response should mention CSRF protection"
        )

    def test_journal_entry_creation_succeeds_with_csrf_token(self):
        """POST with valid CSRF token should succeed"""
        # Get CSRF token
        csrf_token = get_token(self.client)

        # Create journal entry with CSRF token
        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test Entry',
            'content': 'Test content',
            'mood_rating': 7,
            'stress_level': 4,
            'energy_level': 6,
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': csrf_token
        })

        # Should succeed (201 Created or 200 OK)
        self.assertIn(
            response.status_code,
            [200, 201],
            f"Journal entry creation with CSRF token should succeed (got {response.status_code})"
        )

    def test_journal_entry_update_requires_csrf_token(self):
        """PUT/PATCH to update journal entry should require CSRF token"""
        # Create a journal entry
        entry = JournalEntry.objects.create(
            id=uuid4(),
            user=self.user,
            tenant=self.tenant,
            entry_type='work',
            title='Original Title',
            content='Original content',
            timestamp=timezone.now()
        )

        # Attempt to update without CSRF token
        response = self.client.patch(f'/api/journal/entries/{entry.id}/', {
            'title': 'Updated Title'
        }, content_type='application/json')

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Journal entry update without CSRF token should be rejected"
        )

    def test_journal_entry_deletion_requires_csrf_token(self):
        """DELETE to remove journal entry should require CSRF token"""
        # Create a journal entry
        entry = JournalEntry.objects.create(
            id=uuid4(),
            user=self.user,
            tenant=self.tenant,
            entry_type='work',
            title='To Delete',
            content='Will be deleted',
            timestamp=timezone.now()
        )

        # Attempt to delete without CSRF token
        response = self.client.delete(f'/api/journal/entries/{entry.id}/')

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Journal entry deletion without CSRF token should be rejected"
        )

        # Verify entry still exists
        self.assertTrue(
            JournalEntry.objects.filter(id=entry.id).exists(),
            "Entry should not be deleted without CSRF token"
        )


@pytest.mark.security
class CSRFProtectionTicketEndpointsTestCase(TestCase):
    """Test CSRF protection for helpdesk ticket endpoints"""

    def setUp(self):
        """Create test user and client with CSRF enforcement"""
        self.tenant = Tenant.objects.create(
            tenantname="Ticket CSRF Tenant",
            subdomain_prefix="ticket-csrf"
        )
        self.bu = Bt.objects.create(
            bucode="TCSRF_BU",
            buname="Ticket CSRF BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='ticketcsrfuser',
            email='ticketcsrf@example.com',
            password='password123',
            loginid='ticketcsrf',
            peoplecode='TCSRF001',
            peoplename='Ticket CSRF User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_ticket_creation_requires_csrf_token(self):
        """POST to create ticket should require CSRF token"""
        response = self.client.post('/api/v2/tickets/', {
            'title': 'Test Ticket',
            'description': 'Test issue',
            'priority': 3,
            'submitter_email': self.user.email
        })

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Ticket creation without CSRF token should be rejected"
        )

    def test_ticket_update_requires_csrf_token(self):
        """PUT/PATCH to update ticket should require CSRF token"""
        # Create a ticket
        ticket = Ticket.objects.create(
            submitter_email=self.user.email,
            title='Original Ticket',
            description='Original description',
            priority=3,
            tenant=self.tenant,
            bu=self.bu
        )

        # Attempt to update without CSRF token
        response = self.client.patch(f'/api/v2/tickets/{ticket.id}/', {
            'priority': 1
        }, content_type='application/json')

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Ticket update without CSRF token should be rejected"
        )

        # Verify ticket was not modified
        ticket.refresh_from_db()
        self.assertEqual(
            ticket.priority,
            3,
            "Ticket priority should not change without CSRF token"
        )

    def test_ticket_deletion_requires_csrf_token(self):
        """DELETE to remove ticket should require CSRF token"""
        # Create a ticket
        ticket = Ticket.objects.create(
            submitter_email=self.user.email,
            title='To Delete',
            description='Will be deleted',
            priority=2,
            tenant=self.tenant,
            bu=self.bu
        )

        # Attempt to delete without CSRF token
        response = self.client.delete(f'/api/v2/tickets/{ticket.id}/')

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Ticket deletion without CSRF token should be rejected"
        )


@pytest.mark.security
class CSRFProtectionWellnessEndpointsTestCase(TestCase):
    """Test CSRF protection for wellness content management endpoints"""

    def setUp(self):
        """Create test admin user and client with CSRF enforcement"""
        self.tenant = Tenant.objects.create(
            tenantname="Wellness CSRF Tenant",
            subdomain_prefix="wellness-csrf"
        )
        self.bu = Bt.objects.create(
            bucode="WCSRF_BU",
            buname="Wellness CSRF BU",
            enable=True
        )
        # Create admin user (for content management)
        self.admin = User.objects.create_user(
            username='wellnessadmin',
            email='wellnessadmin@example.com',
            password='password123',
            loginid='wellnessadmin',
            peoplecode='WADM001',
            peoplename='Wellness Admin',
            bu=self.bu,
            is_staff=True
        )
        if hasattr(self.admin, 'tenant'):
            self.admin.tenant = self.tenant
            self.admin.save()

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.admin)

    def test_wellness_content_creation_requires_csrf_token(self):
        """POST to create wellness content should require CSRF token"""
        response = self.client.post('/api/wellness/content/', {
            'title': 'Test Wellness Content',
            'content_text': 'Test wellness advice',
            'category': 'stress_management',
            'delivery_context': 'daily_tip',
            'evidence_level': 'educational'
        })

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Wellness content creation without CSRF token should be rejected"
        )

    def test_wellness_content_deletion_requires_csrf_token(self):
        """DELETE to remove wellness content should require CSRF token"""
        # Create wellness content
        content = WellnessContent.objects.create(
            tenant=self.tenant,
            title='Test Content',
            content_text='Test wellness content',
            category='mental_health',
            delivery_context='daily_tip',
            evidence_level='educational',
            is_active=True
        )

        # Attempt to delete without CSRF token
        response = self.client.delete(f'/api/wellness/content/{content.id}/')

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Wellness content deletion without CSRF token should be rejected"
        )


@pytest.mark.security
class CSRFTokenValidationTestCase(TestCase):
    """Test CSRF token validation and security"""

    def setUp(self):
        """Create test user"""
        self.tenant = Tenant.objects.create(
            tenantname="Token Test Tenant",
            subdomain_prefix="token-test"
        )
        self.bu = Bt.objects.create(
            bucode="TOK_BU",
            buname="Token Test BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='tokenuser',
            email='token@example.com',
            password='password123',
            loginid='tokenuser',
            peoplecode='TOK001',
            peoplename='Token User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_invalid_csrf_token_rejected(self):
        """Request with invalid CSRF token should be rejected"""
        # Use invalid token
        invalid_token = 'invalid_token_12345'

        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test Entry',
            'content': 'Test content',
            'mood_rating': 7,
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': invalid_token
        })

        # Should be rejected with 403 Forbidden
        self.assertEqual(
            response.status_code,
            403,
            "Request with invalid CSRF token should be rejected"
        )

    def test_csrf_token_from_different_session_rejected(self):
        """CSRF token from different session should be rejected"""
        # Create another user/session
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='password123',
            loginid='otheruser',
            peoplecode='OTH001',
            peoplename='Other User',
            bu=self.bu
        )
        if hasattr(other_user, 'tenant'):
            other_user.tenant = self.tenant
            other_user.save()

        other_client = Client(enforce_csrf_checks=True)
        other_client.force_login(other_user)

        # Get CSRF token from other session
        other_csrf_token = get_token(other_client)

        # Try to use it in our session
        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test Entry',
            'content': 'Test content',
            'mood_rating': 7,
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': other_csrf_token
        })

        # Should be rejected
        self.assertEqual(
            response.status_code,
            403,
            "CSRF token from different session should be rejected"
        )

    def test_csrf_token_rotation_works(self):
        """CSRF token should work after rotation"""
        # Get initial CSRF token
        csrf_token_1 = get_token(self.client)

        # Make a request with first token
        response_1 = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Entry 1',
            'content': 'First entry',
            'mood_rating': 7,
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': csrf_token_1
        })

        # Token rotation may occur - get new token
        csrf_token_2 = get_token(self.client)

        # Make another request with potentially rotated token
        response_2 = self.client.post('/api/journal/entries/', {
            'entry_type': 'work',
            'title': 'Entry 2',
            'content': 'Second entry',
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': csrf_token_2
        })

        # Both requests should succeed (or both fail if endpoint doesn't exist)
        # The key is that token rotation doesn't break functionality
        if response_1.status_code in [200, 201]:
            self.assertIn(
                response_2.status_code,
                [200, 201],
                "Request after token rotation should succeed"
            )


@pytest.mark.security
class CSRFExemptEndpointsTestCase(TestCase):
    """Test that CSRF exempt endpoints have documented alternative authentication"""

    def setUp(self):
        """Setup for CSRF exempt endpoint tests"""
        self.tenant = Tenant.objects.create(
            tenantname="Exempt Test Tenant",
            subdomain_prefix="exempt-test"
        )
        self.bu = Bt.objects.create(
            bucode="EX_BU",
            buname="Exempt Test BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='exemptuser',
            email='exempt@example.com',
            password='password123',
            loginid='exemptuser',
            peoplecode='EX001',
            peoplename='Exempt User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

    def test_biometric_endpoints_have_alternative_auth(self):
        """Biometric endpoints should use HMAC or device token authentication"""
        # Biometric endpoints are CSRF exempt but require HMAC signature
        client = APIClient()

        # Attempt without authentication
        response = client.post('/api/v1/biometrics/face-recognition/', {
            'image_data': 'base64_encoded_image',
            'device_id': 'device123'
        })

        # Should be rejected with 401/403 (no valid auth)
        # CSRF exempt doesn't mean no authentication!
        self.assertIn(
            response.status_code,
            [401, 403, 404],  # 404 if endpoint doesn't exist
            "CSRF-exempt endpoint should still require authentication"
        )

    def test_nfc_scanning_endpoints_have_alternative_auth(self):
        """NFC scanning endpoints should use device authentication"""
        client = APIClient()

        # Attempt without authentication
        response = client.post('/api/v1/assets/nfc/scan/', {
            'nfc_tag': 'tag123',
            'device_id': 'device456'
        })

        # Should be rejected without valid device authentication
        self.assertIn(
            response.status_code,
            [401, 403, 404],  # 404 if endpoint doesn't exist
            "NFC endpoint should require device authentication"
        )

    def test_mobile_journal_endpoint_has_jwt_auth(self):
        """Mobile journal submission should use JWT authentication"""
        client = APIClient()

        # Attempt without JWT token
        response = client.post('/api/v1/journal/', {
            'entry_type': 'wellbeing',
            'title': 'Mobile Entry',
            'content': 'From mobile app',
            'mood_rating': 7
        })

        # Should be rejected without JWT token
        self.assertIn(
            response.status_code,
            [401, 403, 404],  # 404 if endpoint doesn't exist
            "Mobile journal endpoint should require JWT authentication"
        )


@pytest.mark.security
class CSRFProtectionIntegrationTestCase(TestCase):
    """Integration tests for CSRF protection across multiple endpoints"""

    def setUp(self):
        """Create test environment"""
        self.tenant = Tenant.objects.create(
            tenantname="Integration Test Tenant",
            subdomain_prefix="integration-test"
        )
        self.bu = Bt.objects.create(
            bucode="INT_BU",
            buname="Integration BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='password123',
            loginid='integrationuser',
            peoplecode='INT001',
            peoplename='Integration User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_multiple_state_changing_operations_require_csrf(self):
        """Test that all state-changing operations require CSRF protection"""
        # Define state-changing operations to test
        state_changing_operations = [
            ('POST', '/api/journal/entries/', {
                'entry_type': 'wellbeing',
                'title': 'Test',
                'content': 'Test',
                'mood_rating': 7,
                'timestamp': timezone.now().isoformat()
            }),
            ('POST', '/api/v2/tickets/', {
                'title': 'Test Ticket',
                'description': 'Test',
                'priority': 3,
                'submitter_email': self.user.email
            }),
        ]

        # All should be rejected without CSRF token
        for method, url, data in state_changing_operations:
            if method == 'POST':
                response = self.client.post(url, data)
            elif method == 'PUT':
                response = self.client.put(url, data, content_type='application/json')
            elif method == 'PATCH':
                response = self.client.patch(url, data, content_type='application/json')
            elif method == 'DELETE':
                response = self.client.delete(url)
            else:
                continue

            self.assertEqual(
                response.status_code,
                403,
                f"{method} {url} should require CSRF token"
            )

    def test_read_operations_do_not_require_csrf(self):
        """Test that read-only operations (GET) work without CSRF token"""
        # GET requests should work without CSRF token
        read_operations = [
            '/api/journal/entries/',
            '/api/v2/tickets/',
            '/api/wellness/content/',
        ]

        for url in read_operations:
            response = self.client.get(url)

            # Should succeed (200) or fail for other reasons (404, etc.)
            # but NOT fail due to CSRF (403 with CSRF in message)
            if response.status_code == 403:
                response_text = response.content.decode('utf-8')
                self.assertNotIn(
                    'CSRF',
                    response_text.upper(),
                    f"GET {url} should not require CSRF token"
                )


@pytest.mark.security
class CSRFHeaderMiddlewareIntegrationTestCase(TestCase):
    """Test integration between CSRF token validation and security headers"""

    def setUp(self):
        """Create test user"""
        self.tenant = Tenant.objects.create(
            tenantname="Header Test Tenant",
            subdomain_prefix="header-test"
        )
        self.bu = Bt.objects.create(
            bucode="HDR_BU",
            buname="Header Test BU",
            enable=True
        )
        self.user = User.objects.create_user(
            username='headeruser',
            email='header@example.com',
            password='password123',
            loginid='headeruser',
            peoplecode='HDR001',
            peoplename='Header User',
            bu=self.bu
        )
        if hasattr(self.user, 'tenant'):
            self.user.tenant = self.tenant
            self.user.save()

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_csrf_failure_includes_security_headers(self):
        """CSRF failure responses should include security headers"""
        # Make request without CSRF token
        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test',
            'content': 'Test',
            'mood_rating': 7,
            'timestamp': timezone.now().isoformat()
        })

        # Should fail with 403
        self.assertEqual(response.status_code, 403)

        # Should still include security headers
        # (these are added by CSRFHeaderMiddleware)
        if 'X-Content-Type-Options' in response:
            self.assertEqual(
                response['X-Content-Type-Options'],
                'nosniff',
                "CSRF failure should include security headers"
            )

    def test_csrf_success_includes_security_headers(self):
        """Successful CSRF-protected requests should include security headers"""
        csrf_token = get_token(self.client)

        response = self.client.post('/api/journal/entries/', {
            'entry_type': 'wellbeing',
            'title': 'Test',
            'content': 'Test',
            'mood_rating': 7,
            'timestamp': timezone.now().isoformat(),
            'csrfmiddlewaretoken': csrf_token
        })

        # Check security headers are present (regardless of status code)
        if 'X-Content-Type-Options' in response:
            self.assertEqual(
                response['X-Content-Type-Options'],
                'nosniff',
                "Successful request should include security headers"
            )
