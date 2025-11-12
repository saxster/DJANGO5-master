"""
Tests for dashboard views - cache isolation and tenant security.

Tests Sprint 1, Task 2: Fix Dashboard Cache Poisoning via BU ID Fallback
"""

import pytest
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from apps.peoples.models import People
from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt  # Business Unit model
from apps.peoples.models import PeopleOrganizational
from apps.dashboard.views import get_user_tenant_id, command_center_api
from unittest.mock import patch, MagicMock


class TestGetUserTenantIdSecurity(TestCase):
    """Test security of get_user_tenant_id() function."""

    def setUp(self):
        """Set up test data: Two tenants with same BU ID."""
        # Create two different tenants
        self.tenant_a = Tenant.objects.create(
            tenantname="Tenant A",
            subdomain_prefix="tenant-a"
        )
        self.tenant_b = Tenant.objects.create(
            tenantname="Tenant B",
            subdomain_prefix="tenant-b"
        )

        # Create a shared business unit (simulating cross-tenant BU)
        self.shared_bu = Bt.objects.create(
            bucode="SHARED_BU_001",
            buname="Shared Business Unit",
            tenant=self.tenant_a  # BU belongs to Tenant A
        )

        # User A from Tenant A with bu pointing to shared_bu
        self.user_a = People.objects.create_user(
            peoplecode="USER_A",
            peoplename="User A",
            loginid="user_a",
            email="user_a@example.com",
            mobno="1234567890",
            password="password123",
            tenant=self.tenant_a  # Set tenant during creation
        )

        # Create organizational info with shared BU
        # Note: Signal may auto-create this, but we'll create/update explicitly for test control
        try:
            self.org_a = PeopleOrganizational.objects.get(people=self.user_a)
            self.org_a.bu = self.shared_bu
            self.org_a.save()
        except PeopleOrganizational.DoesNotExist:
            self.org_a = PeopleOrganizational.objects.create(
                people=self.user_a,
                bu=self.shared_bu  # bu_id will be shared_bu.id
            )

        # User B from Tenant B with bu pointing to SAME shared_bu
        self.user_b = People.objects.create_user(
            peoplecode="USER_B",
            peoplename="User B",
            loginid="user_b",
            email="user_b@example.com",
            mobno="0987654321",
            password="password123",
            tenant=self.tenant_b  # Set tenant during creation
        )

        # Create organizational info with SAME shared BU
        try:
            self.org_b = PeopleOrganizational.objects.get(people=self.user_b)
            self.org_b.bu = self.shared_bu
            self.org_b.save()
        except PeopleOrganizational.DoesNotExist:
            self.org_b = PeopleOrganizational.objects.create(
                people=self.user_b,
                bu=self.shared_bu  # SAME bu_id as user_a
            )

        # Verify both users share the same bu_id (setup validation)
        assert self.org_a.bu_id == self.org_b.bu_id, "Test setup failed: users should share bu_id"

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_cache_isolation_different_tenants_same_buid(self):
        """
        TEST: Users from different tenants with same BU ID should NOT share cache.

        This test demonstrates the cache poisoning vulnerability when bu_id
        is used as a fallback for tenant_id in cache keys.

        Expected behavior:
        - User A requests data → cached with tenant_id=tenant_a.id
        - User B requests data → gets DIFFERENT data (tenant_id=tenant_b.id)
        - Cache keys should be isolated by tenant_id, not bu_id
        """
        # Mock the CommandCenterService to return tenant-specific data
        with patch('apps.dashboard.views.CommandCenterService.get_live_summary') as mock_service:
            # Configure mock to return different data based on tenant_id
            def side_effect(tenant_id):
                if tenant_id == self.tenant_a.id:
                    return {
                        'critical_alerts': [{'id': 1, 'message': 'Tenant A Alert'}],
                        'summary_stats': {'alerts_today': 10}
                    }
                elif tenant_id == self.tenant_b.id:
                    return {
                        'critical_alerts': [{'id': 2, 'message': 'Tenant B Alert'}],
                        'summary_stats': {'alerts_today': 20}
                    }
                else:
                    raise ValueError(f"Unexpected tenant_id: {tenant_id}")

            mock_service.side_effect = side_effect

            # Create request factory
            factory = RequestFactory()

            # User A requests command center data
            request_a = factory.get('/api/dashboard/command-center/')
            request_a.user = self.user_a
            response_a = command_center_api(request_a)

            # Verify User A got correct response
            self.assertEqual(response_a.status_code, 200)
            import json
            data_a = json.loads(response_a.content)
            self.assertTrue(data_a['success'])
            self.assertEqual(data_a['data']['summary_stats']['alerts_today'], 10)
            self.assertEqual(data_a['data']['critical_alerts'][0]['message'], 'Tenant A Alert')

            # User B requests command center data (with potentially same cache key if bu_id used)
            request_b = factory.get('/api/dashboard/command-center/')
            request_b.user = self.user_b
            response_b = command_center_api(request_b)

            # Verify User B got correct response (NOT User A's cached data)
            self.assertEqual(response_b.status_code, 200)
            data_b = json.loads(response_b.content)
            self.assertTrue(data_b['success'])

            # CRITICAL ASSERTION: User B should NOT see User A's data
            self.assertEqual(data_b['data']['summary_stats']['alerts_today'], 20,
                           "User B is seeing User A's cached data - cache poisoning vulnerability!")
            self.assertEqual(data_b['data']['critical_alerts'][0]['message'], 'Tenant B Alert',
                           "User B is seeing User A's alerts - tenant isolation violated!")

    def test_user_with_tenant_id_returns_correct_value(self):
        """TEST: Users with tenant_id should have it returned."""
        tenant_id = get_user_tenant_id(self.user_a)
        self.assertEqual(tenant_id, self.tenant_a.id)
        self.assertIsNotNone(tenant_id)

    def test_user_without_tenant_id_returns_none(self):
        """TEST: Users without tenant_id should return None (not bu_id)."""
        # Create user with tenant first, then remove it (simulating misconfigured user)
        user_no_tenant = People.objects.create_user(
            peoplecode="USER_NO_TENANT",
            peoplename="User No Tenant",
            loginid="user_no_tenant",
            email="no_tenant@example.com",
            mobno="5555555555",
            password="password123",
            tenant=self.tenant_a  # Create with tenant first
        )
        # Explicitly set tenant to None (simulating edge case/misconfiguration)
        user_no_tenant.tenant = None
        user_no_tenant.save(skip_tenant_validation=True)

        # Create organizational info with BU
        try:
            org = PeopleOrganizational.objects.get(people=user_no_tenant)
            org.bu = self.shared_bu
            org.save()
        except PeopleOrganizational.DoesNotExist:
            org = PeopleOrganizational.objects.create(
                people=user_no_tenant,
                bu=self.shared_bu
            )

        tenant_id = get_user_tenant_id(user_no_tenant)

        # Should return None, NOT bu_id
        self.assertIsNone(tenant_id, "Should return None when tenant_id is missing, not bu_id")

        # Verify user has bu_id but it wasn't returned
        user_no_tenant.refresh_from_db()
        if hasattr(user_no_tenant, 'peopleorganizational') and user_no_tenant.peopleorganizational:
            self.assertIsNotNone(user_no_tenant.peopleorganizational.bu_id)

    def test_command_center_api_handles_none_tenant_id(self):
        """TEST: command_center_api() should handle None tenant_id gracefully."""
        # Create user with tenant first, then remove it
        user_no_tenant = People.objects.create_user(
            peoplecode="USER_NO_TENANT_API",
            peoplename="User No Tenant API",
            loginid="user_no_tenant_api",
            email="no_tenant_api@example.com",
            mobno="6666666666",
            password="password123",
            tenant=self.tenant_a
        )
        user_no_tenant.tenant = None
        user_no_tenant.save(skip_tenant_validation=True)

        factory = RequestFactory()
        request = factory.get('/api/dashboard/command-center/')
        request.user = user_no_tenant

        response = command_center_api(request)

        # Should return 400 error with appropriate message
        self.assertEqual(response.status_code, 400)
        import json
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('tenant', data['error'].lower())


class TestCacheKeyIsolation(TestCase):
    """Test that cache keys are properly isolated by tenant_id."""

    def setUp(self):
        """Set up test data."""
        self.tenant_x = Tenant.objects.create(
            tenantname="Tenant X",
            subdomain_prefix="tenant-x"
        )
        self.tenant_y = Tenant.objects.create(
            tenantname="Tenant Y",
            subdomain_prefix="tenant-y"
        )

        self.user_x = People.objects.create_user(
            peoplecode="USER_X",
            peoplename="User X",
            loginid="user_x",
            email="user_x@example.com",
            mobno="1111111111",
            password="password123",
            tenant=self.tenant_x
        )

        self.user_y = People.objects.create_user(
            peoplecode="USER_Y",
            peoplename="User Y",
            loginid="user_y",
            email="user_y@example.com",
            mobno="2222222222",
            password="password123",
            tenant=self.tenant_y
        )

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_different_tenants_have_different_cache_keys(self):
        """TEST: Different tenants should use different cache keys."""
        from apps.dashboard.services.command_center_service import CommandCenterService

        with patch('apps.dashboard.services.command_center_service.CommandCenterService._get_critical_alerts') as mock_alerts, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_devices_at_risk') as mock_devices, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_sla_at_risk') as mock_sla, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_attendance_anomalies') as mock_attendance, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_active_sos') as mock_sos, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_incomplete_tours') as mock_tours, \
             patch('apps.dashboard.services.command_center_service.CommandCenterService._get_summary_stats') as mock_stats:

            # Configure mocks to return tenant-specific data
            mock_alerts.return_value = []
            mock_devices.return_value = []
            mock_sla.return_value = []
            mock_attendance.return_value = []
            mock_sos.return_value = []
            mock_tours.return_value = []

            mock_stats.side_effect = lambda tenant_id: {
                'alerts_today': tenant_id * 100  # Unique per tenant
            }

            # Get summary for Tenant X
            summary_x = CommandCenterService.get_live_summary(self.tenant_x.id)
            self.assertEqual(summary_x['summary_stats']['alerts_today'], self.tenant_x.id * 100)

            # Get summary for Tenant Y (should NOT get Tenant X's cached data)
            summary_y = CommandCenterService.get_live_summary(self.tenant_y.id)
            self.assertEqual(summary_y['summary_stats']['alerts_today'], self.tenant_y.id * 100)

            # Verify they're different
            self.assertNotEqual(summary_x['summary_stats']['alerts_today'],
                              summary_y['summary_stats']['alerts_today'])
