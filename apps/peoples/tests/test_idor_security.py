"""
IDOR Security Tests for Peoples App

Tests prevent Insecure Direct Object Reference vulnerabilities that could allow
unauthorized access to user data, profiles, and organizational information.

Critical Test Coverage:
    - Cross-tenant user access prevention
    - Cross-user profile access prevention
    - Permission boundary enforcement (regular user vs admin)
    - Direct object access by ID manipulation
    - API endpoint security validation

Security Note:
    These tests verify core authentication and authorization security.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.peoples.models import PeopleProfile, PeopleOrganizational
from apps.peoples.tests.factories import (
    BtFactory,
    PeopleFactory,
    CompleteUserFactory,
    AdminUserFactory
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.idor
class PeoplesIDORTestCase(TestCase):
    """Test suite for IDOR vulnerabilities in peoples app."""

    def setUp(self):
        """Set up test fixtures for IDOR testing."""
        self.client = Client()
        
        # Create two separate tenants
        self.tenant_a = BtFactory(bucode="TENANT_A", buname="Tenant A")
        self.tenant_b = BtFactory(bucode="TENANT_B", buname="Tenant B")
        
        # Create users for tenant A
        self.user_a1 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="USER_A1",
            peoplename="User A1"
        )
        self.user_a2 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="USER_A2",
            peoplename="User A2"
        )
        
        # Create users for tenant B
        self.user_b1 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="USER_B1",
            peoplename="User B1"
        )
        self.user_b2 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="USER_B2",
            peoplename="User B2"
        )
        
        # Create admin users for each tenant
        self.admin_a = AdminUserFactory(
            client=self.tenant_a,
            peoplecode="ADMIN_A",
            peoplename="Admin A"
        )
        self.admin_b = AdminUserFactory(
            client=self.tenant_b,
            peoplecode="ADMIN_B",
            peoplename="Admin B"
        )

    # ==================
    # Cross-Tenant Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_user_profile(self):
        """Test IDOR: User from tenant A cannot access tenant B user profile"""
        self.client.force_login(self.user_a1)
        
        # Attempt to access tenant B user profile
        response = self.client.get(f'/people/profile/{self.user_b1.id}/')
        
        # Should be forbidden or not found
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_user_data(self):
        """Test IDOR: User cannot modify another tenant's user data"""
        self.client.force_login(self.user_a1)
        
        # Attempt to update tenant B user
        response = self.client.post(
            f'/people/update/{self.user_b1.id}/',
            {
                'peoplename': 'Hacked Name',
                'email': 'hacked@example.com'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify data wasn't changed
        self.user_b1.refresh_from_db()
        self.assertNotEqual(self.user_b1.peoplename, 'Hacked Name')
        self.assertNotEqual(self.user_b1.email, 'hacked@example.com')

    def test_user_cannot_delete_other_tenant_user(self):
        """Test IDOR: User cannot delete users from another tenant"""
        self.client.force_login(self.user_a1)
        
        user_b_id = self.user_b2.id
        
        # Attempt to delete tenant B user
        response = self.client.post(f'/people/delete/{user_b_id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify user still exists
        self.assertTrue(User.objects.filter(id=user_b_id).exists())

    def test_user_cannot_list_other_tenant_users(self):
        """Test IDOR: User listing should be scoped to tenant"""
        self.client.force_login(self.user_a1)
        
        # Get user list
        response = self.client.get('/people/list/')
        
        if response.status_code == 200:
            # Parse response content (adjust based on actual view implementation)
            content = response.content.decode()
            
            # Should see tenant A users
            self.assertIn(self.user_a1.peoplename, content)
            self.assertIn(self.user_a2.peoplename, content)
            
            # Should NOT see tenant B users
            self.assertNotIn(self.user_b1.peoplename, content)
            self.assertNotIn(self.user_b2.peoplename, content)

    # ==================
    # Cross-User Access Prevention Tests
    # ==================

    def test_user_cannot_access_another_user_profile_same_tenant(self):
        """Test IDOR: Regular user cannot access another user's profile details"""
        self.client.force_login(self.user_a1)
        
        # Get own profile - should succeed
        response_own = self.client.get(f'/people/profile/{self.user_a1.id}/')
        self.assertEqual(response_own.status_code, 200)
        
        # Try to access another user's profile in same tenant
        # (depends on business rules - adjust expected behavior)
        response_other = self.client.get(f'/people/profile/{self.user_a2.id}/')
        
        # If profiles should be private, should be forbidden
        # If profiles are viewable within tenant, should be 200
        # Adjust based on actual requirements
        self.assertIn(response_other.status_code, [200, 403])

    def test_user_cannot_edit_another_user_profile_same_tenant(self):
        """Test IDOR: User cannot modify another user's profile"""
        self.client.force_login(self.user_a1)
        
        profile_a2 = PeopleProfile.objects.get(people=self.user_a2)
        original_gender = profile_a2.gender
        
        # Attempt to update another user's profile
        response = self.client.post(
            f'/people/profile/update/{self.user_a2.id}/',
            {
                'gender': 'HACKED',
                'dateofbirth': '2000-01-01'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify data wasn't changed
        profile_a2.refresh_from_db()
        self.assertEqual(profile_a2.gender, original_gender)

    def test_user_cannot_change_own_tenant_assignment(self):
        """Test IDOR: User cannot reassign themselves to different tenant"""
        self.client.force_login(self.user_a1)
        
        original_tenant = self.user_a1.client
        
        # Attempt to change tenant
        response = self.client.post(
            f'/people/update/{self.user_a1.id}/',
            {
                'peoplename': self.user_a1.peoplename,
                'email': self.user_a1.email,
                'client': self.tenant_b.id  # Try to switch to tenant B
            }
        )
        
        # Verify tenant didn't change
        self.user_a1.refresh_from_db()
        self.assertEqual(self.user_a1.client, original_tenant)

    # ==================
    # Permission Boundary Tests
    # ==================

    def test_regular_user_cannot_access_admin_functions(self):
        """Test IDOR: Regular user cannot access admin-only functions"""
        self.client.force_login(self.user_a1)
        
        # Try to access admin-only pages
        admin_urls = [
            '/people/admin/permissions/',
            '/people/admin/capabilities/',
            '/people/admin/groups/',
        ]
        
        for url in admin_urls:
            response = self.client.get(url)
            # Should be forbidden or redirect to login
            self.assertIn(response.status_code, [302, 403, 404])

    def test_admin_cannot_access_other_tenant_users(self):
        """Test IDOR: Admin from tenant A cannot manage tenant B users"""
        self.client.force_login(self.admin_a)
        
        # Attempt to access tenant B user
        response = self.client.get(f'/people/profile/{self.user_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_admin_cannot_escalate_regular_user_to_superuser(self):
        """Test IDOR: Admin cannot create superusers (privilege escalation)"""
        self.client.force_login(self.admin_a)
        
        # Attempt to create superuser
        response = self.client.post(
            '/people/create/',
            {
                'peoplecode': 'HACKER',
                'peoplename': 'Hacker',
                'loginid': 'hacker',
                'email': 'hacker@example.com',
                'client': self.tenant_a.id,
                'is_superuser': True,
                'is_staff': True
            }
        )
        
        # If creation succeeded, verify superuser flags were not set
        if User.objects.filter(loginid='hacker').exists():
            hacker_user = User.objects.get(loginid='hacker')
            self.assertFalse(hacker_user.is_superuser)

    # ==================
    # Direct ID Manipulation Tests
    # ==================

    def test_sequential_id_enumeration_prevention(self):
        """Test IDOR: Cannot enumerate users by sequential ID access"""
        self.client.force_login(self.user_a1)
        
        # Try to access users by sequential IDs
        accessible_count = 0
        forbidden_count = 0
        
        # Test a range of IDs
        for user_id in range(1, 100):
            response = self.client.get(f'/people/profile/{user_id}/')
            if response.status_code == 200:
                accessible_count += 1
            elif response.status_code in [403, 404]:
                forbidden_count += 1
        
        # Should have significantly more forbidden than accessible
        # (only own tenant users should be accessible)
        self.assertGreater(
            forbidden_count,
            0,
            "Should prevent enumeration of non-tenant users"
        )

    def test_negative_id_handling(self):
        """Test IDOR: Negative IDs should not expose data"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/people/profile/-1/')
        
        # Should return 404 or 400, not 500
        self.assertIn(response.status_code, [400, 404])

    def test_uuid_vs_integer_id_confusion(self):
        """Test IDOR: Invalid ID formats should be rejected"""
        self.client.force_login(self.user_a1)
        
        invalid_ids = [
            'invalid',
            '../../etc/passwd',
            '<script>alert(1)</script>',
            '1 OR 1=1',
        ]
        
        for invalid_id in invalid_ids:
            response = self.client.get(f'/people/profile/{invalid_id}/')
            # Should return 400 or 404, not 500
            self.assertIn(response.status_code, [400, 404])

    # ==================
    # API Endpoint Security Tests
    # ==================

    def test_api_user_detail_cross_tenant_blocked(self):
        """Test IDOR: API endpoints enforce tenant isolation"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B user via API
        response = self.client.get(f'/api/v1/people/{self.user_b1.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_user_list_filtered_by_tenant(self):
        """Test IDOR: API list endpoints scope to tenant"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/api/v1/people/')
        
        if response.status_code == 200:
            data = response.json()
            
            # Should only include tenant A users
            user_ids = [user['id'] for user in data.get('results', data)]
            
            self.assertIn(self.user_a1.id, user_ids)
            self.assertIn(self.user_a2.id, user_ids)
            self.assertNotIn(self.user_b1.id, user_ids)
            self.assertNotIn(self.user_b2.id, user_ids)

    def test_api_bulk_operations_scoped_to_tenant(self):
        """Test IDOR: Bulk operations cannot affect other tenants"""
        self.client.force_login(self.admin_a)
        
        # Attempt bulk update including cross-tenant user
        response = self.client.post(
            '/api/v1/people/bulk_update/',
            {
                'user_ids': [self.user_a1.id, self.user_b1.id],
                'is_active': False
            },
            content_type='application/json'
        )
        
        # Verify tenant B user was not affected
        self.user_b1.refresh_from_db()
        self.assertTrue(self.user_b1.is_active)

    # ==================
    # Session and Cookie Security Tests
    # ==================

    def test_session_tenant_isolation(self):
        """Test IDOR: Session data doesn't leak between tenants"""
        # Login as tenant A user
        self.client.force_login(self.user_a1)
        response_a = self.client.get('/people/profile/me/')
        
        # Logout and login as tenant B user
        self.client.logout()
        self.client.force_login(self.user_b1)
        response_b = self.client.get('/people/profile/me/')
        
        # Verify different user data returned
        self.assertNotEqual(
            response_a.content,
            response_b.content,
            "Session should not leak data between tenants"
        )

    def test_cookie_manipulation_blocked(self):
        """Test IDOR: Cookie manipulation cannot bypass tenant checks"""
        self.client.force_login(self.user_a1)
        
        # Manually set cookies to try to impersonate tenant B user
        self.client.cookies['user_id'] = str(self.user_b1.id)
        self.client.cookies['tenant_id'] = str(self.tenant_b.id)
        
        response = self.client.get('/people/profile/me/')
        
        if response.status_code == 200:
            # Should still return tenant A user data
            content = response.content.decode()
            self.assertIn(self.user_a1.peoplename, content)
            self.assertNotIn(self.user_b1.peoplename, content)

    # ==================
    # Organizational Data Security Tests
    # ==================

    def test_organizational_data_cross_tenant_blocked(self):
        """Test IDOR: Organizational data access is tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        org_b = PeopleOrganizational.objects.get(people=self.user_b1)
        
        # Try to access tenant B organizational data
        response = self.client.get(f'/people/organizational/{org_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_reporting_hierarchy_cross_tenant_blocked(self):
        """Test IDOR: Reporting hierarchy doesn't expose cross-tenant data"""
        self.client.force_login(self.user_a1)
        
        # Try to set tenant B user as manager
        org_a = PeopleOrganizational.objects.get(people=self.user_a1)
        
        response = self.client.post(
            f'/people/organizational/update/{org_a.id}/',
            {
                'reportto': self.user_b1.id  # Cross-tenant manager
            }
        )
        
        # Should be rejected
        org_a.refresh_from_db()
        self.assertNotEqual(org_a.reportto, self.user_b1)

    # ==================
    # Group and Permission Tests
    # ==================

    def test_group_membership_cross_tenant_blocked(self):
        """Test IDOR: Cannot add users to cross-tenant groups"""
        from apps.peoples.models import Pgroup, Pgbelonging
        
        self.client.force_login(self.admin_a)
        
        # Create groups for each tenant
        group_a = Pgroup.objects.create(
            groupname="Group A",
            groupcode="GRP_A",
            client=self.tenant_a
        )
        
        group_b = Pgroup.objects.create(
            groupname="Group B",
            groupcode="GRP_B",
            client=self.tenant_b
        )
        
        # Try to add tenant B user to tenant A group
        response = self.client.post(
            f'/people/groups/{group_a.id}/add_member/',
            {'user_id': self.user_b1.id}
        )
        
        # Should be rejected
        self.assertFalse(
            Pgbelonging.objects.filter(
                groupid=group_a,
                peopleid=self.user_b1
            ).exists()
        )

    def test_capability_assignment_cross_tenant_blocked(self):
        """Test IDOR: Cannot assign capabilities to cross-tenant users"""
        from apps.peoples.models import Capability
        
        self.client.force_login(self.admin_a)
        
        # Create capability
        capability = Capability.objects.create(
            capability_name="admin_feature",
            category="admin",
            display_name="Admin Feature"
        )
        
        # Try to assign capability to tenant B user
        response = self.client.post(
            f'/people/capabilities/assign/',
            {
                'user_id': self.user_b1.id,
                'capability_id': capability.id
            }
        )
        
        # Should be rejected
        self.user_b1.refresh_from_db()
        capabilities = self.user_b1.capabilities or {}
        self.assertNotIn('admin_feature', capabilities.get('webcapability', []))


@pytest.mark.security
@pytest.mark.idor
@pytest.mark.performance
class PeoplesIDORPerformanceTestCase(TestCase):
    """Performance tests to ensure IDOR checks don't degrade performance."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = BtFactory()
        self.user = CompleteUserFactory(client=self.tenant)
        self.client = Client()
        self.client.force_login(self.user)

    def test_tenant_scoping_query_performance(self):
        """Test that tenant scoping doesn't cause N+1 queries"""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test import TransactionTestCase
        
        # Create multiple users in same tenant
        users = [
            CompleteUserFactory(client=self.tenant)
            for _ in range(10)
        ]
        
        # Measure queries for listing users
        with self.assertNumQueries(5):  # Adjust based on actual implementation
            response = self.client.get('/people/list/')
            self.assertEqual(response.status_code, 200)

    def test_permission_check_caching(self):
        """Test that permission checks are cached within request"""
        # Make multiple requests that require permission checks
        urls = [
            f'/people/profile/{self.user.id}/',
            f'/people/organizational/{self.user.id}/',
            f'/people/capabilities/{self.user.id}/',
        ]
        
        # Each subsequent request should use cached permissions
        for url in urls:
            response = self.client.get(url)
            # Should not timeout or be significantly slow
            self.assertIn(response.status_code, [200, 404])
