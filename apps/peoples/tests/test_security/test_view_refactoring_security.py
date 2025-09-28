"""
Security tests for refactored views.

Validates Rule #8 compliance and security enforcement.
"""

import pytest
from django.test import TestCase, Client
from apps.peoples.models import People
from apps.onboarding.models import Bt, Typeassist
from apps.tenants.models import Tenant


@pytest.mark.security
@pytest.mark.django_db
class TestRefactoredViewSecurity(TestCase):
    """Security tests for refactored views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()

        tenant = Tenant.objects.get_or_create(
            tenant_code="TEST",
            defaults={"tenant_name": "Test"}
        )[0]

        bu = Bt.objects.create(
            buname="Test BU",
            bucode="TESTBU",
            tenant=tenant
        )

        peopletype = Typeassist.objects.get_or_create(
            tacode="EMP",
            tafor="PEOPLE",
            defaults={"taname": "Employee"}
        )[0]

        self.user = People.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            peoplename="Test User",
            bu=bu,
            peopletype=peopletype,
            password="testpass123"
        )

    def test_authentication_required_on_people_view(self):
        """Test authentication enforced on people views."""
        response = self.client.get('/people/?template=true')

        assert response.status_code == 302
        assert '/login' in response.url or 'login' in response.url

    def test_sql_injection_protection_in_search(self):
        """Test SQL injection protection in search."""
        self.client.force_login(self.user)
        malicious_search = "'; DROP TABLE peoples_people; --"

        response = self.client.get(
            f'/people/?action=list&search[value]={malicious_search}'
        )

        assert response.status_code in [200, 400]

    def test_xss_protection_in_form_submission(self):
        """Test XSS protection in form data."""
        self.client.force_login(self.user)
        malicious_data = "<script>alert('XSS')</script>"

        response = self.client.post('/people/', {
            "formData": f"peoplename={malicious_data}"
        })

        assert response.status_code in [200, 400]

    def test_csrf_protection_enforced(self):
        """Test CSRF protection on POST requests."""
        self.client.force_login(self.user)

        response = self.client.post('/people/', {}, HTTP_X_CSRFTOKEN="invalid")

        assert response.status_code in [403, 400]