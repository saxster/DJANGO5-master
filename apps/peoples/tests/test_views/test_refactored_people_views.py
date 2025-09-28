"""
Integration tests for refactored People views.

Tests HTTP request/response handling and service integration.
"""

import pytest
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from apps.peoples.models import People
from apps.peoples.views.people_views import PeopleView
from apps.onboarding.models import Bt, Typeassist
from apps.tenants.models import Tenant


@pytest.mark.integration
@pytest.mark.django_db
class TestPeopleViewIntegration(TestCase):
    """Integration tests for refactored PeopleView."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = Client()

        self.tenant = Tenant.objects.get_or_create(
            tenant_code="TEST",
            defaults={"tenant_name": "Test Tenant"}
        )[0]

        self.bu = Bt.objects.create(
            buname="Test BU",
            bucode="TESTBU",
            tenant=self.tenant
        )

        self.peopletype = Typeassist.objects.get_or_create(
            tacode="EMP",
            tafor="PEOPLE",
            defaults={"taname": "Employee"}
        )[0]

        self.user = People.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            peoplename="Test User",
            bu=self.bu,
            peopletype=self.peopletype,
            password="testpass123"
        )

        self.client.force_login(self.user)

        session = self.client.session
        session['bu_id'] = self.bu.id
        session['client_id'] = self.bu.id
        session['tenantid'] = self.tenant.id
        session.save()

    def test_people_list_view_loads(self):
        """Test people list template loads correctly."""
        response = self.client.get('/people/?template=true')

        assert response.status_code == 200

    def test_people_list_json_response(self):
        """Test people list returns JSON data."""
        response = self.client.get('/people/?action=list&draw=1&start=0&length=10')

        assert response.status_code == 200
        assert 'application/json' in response['Content-Type']
        data = response.json()
        assert 'data' in data
        assert 'recordsTotal' in data

    def test_people_form_create_renders(self):
        """Test create form renders correctly."""
        response = self.client.get('/people/?action=form')

        assert response.status_code == 200

    def test_people_unauthorized_access(self):
        """Test unauthorized access redirects."""
        self.client.logout()
        response = self.client.get('/people/?template=true')

        assert response.status_code == 302


@pytest.mark.integration
@pytest.mark.django_db
class TestAuthViewsIntegration(TestCase):
    """Integration tests for authentication views."""

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

    def test_login_page_loads(self):
        """Test login page loads successfully."""
        response = self.client.get('/login/')

        assert response.status_code in [200, 302]

    def test_logout_redirects(self):
        """Test logout redirects to login."""
        self.client.force_login(self.user)
        response = self.client.get('/logout/')

        assert response.status_code == 302