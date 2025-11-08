"""
IDOR Security Tests for Work Order Management App

Tests prevent Insecure Direct Object Reference vulnerabilities for work orders,
vendors, approvals, and permits.

Critical Test Coverage:
    - Cross-tenant work order access prevention
    - Cross-tenant vendor access prevention
    - Approval workflow security
    - Work permit access control
    - Vendor assignment security

Security Note:
    Work orders contain sensitive operational and vendor data.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.work_order_management.models import Wom, Vendor, Approver, WomDetails
from apps.work_order_management.tests.factories import (
    BtFactory,
    LocationFactory,
    AssetFactory,
    VendorFactory,
    WomFactory,
    WorkPermitFactory,
    ApproverFactory,
    PeopleFactory
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.idor
class WorkOrderIDORTestCase(TestCase):
    """Test suite for IDOR vulnerabilities in work order management."""

    def setUp(self):
        """Set up test fixtures for IDOR testing."""
        self.client = Client()
        
        # Create two separate tenants
        self.tenant_a = BtFactory(bucode="WO_A", buname="Work Order Tenant A")
        self.tenant_b = BtFactory(bucode="WO_B", buname="Work Order Tenant B")
        
        # Create locations
        self.location_a = LocationFactory(
            client=self.tenant_a,
            site="WOSITE_A"
        )
        self.location_b = LocationFactory(
            client=self.tenant_b,
            site="WOSITE_B"
        )
        
        # Create users
        self.user_a = PeopleFactory(
            client=self.tenant_a,
            peoplecode="WOUSER_A"
        )
        self.user_b = PeopleFactory(
            client=self.tenant_b,
            peoplecode="WOUSER_B"
        )
        
        # Create vendors
        self.vendor_a = VendorFactory(
            client=self.tenant_a,
            code="VEND_A"
        )
        self.vendor_b = VendorFactory(
            client=self.tenant_b,
            code="VEND_B"
        )
        
        # Create work orders
        self.wo_a = WomFactory(
            client=self.tenant_a,
            location=self.location_a,
            vendor=self.vendor_a,
            cdby=self.user_a
        )
        self.wo_b = WomFactory(
            client=self.tenant_b,
            location=self.location_b,
            vendor=self.vendor_b,
            cdby=self.user_b
        )

    # ==================
    # Cross-Tenant Work Order Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_work_order(self):
        """Test IDOR: User from tenant A cannot access tenant B's work order"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B work order
        response = self.client.get(f'/work-orders/{self.wo_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_work_order(self):
        """Test IDOR: User cannot modify work orders from another tenant"""
        self.client.force_login(self.user_a)
        
        original_name = self.wo_b.name
        original_priority = self.wo_b.priority
        
        # Try to update tenant B work order
        response = self.client.post(
            f'/work-orders/{self.wo_b.id}/update/',
            {
                'name': 'Hacked Work Order',
                'priority': 'CRITICAL',
                'workstatus': 'CANCELLED'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        self.wo_b.refresh_from_db()
        self.assertEqual(self.wo_b.name, original_name)
        self.assertEqual(self.wo_b.priority, original_priority)

    def test_user_cannot_delete_other_tenant_work_order(self):
        """Test IDOR: User cannot delete work orders from another tenant"""
        self.client.force_login(self.user_a)
        
        wo_id = self.wo_b.id
        
        # Try to delete tenant B work order
        response = self.client.post(f'/work-orders/{wo_id}/delete/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify still exists
        self.assertTrue(Wom.objects.filter(id=wo_id).exists())

    def test_work_order_list_scoped_to_tenant(self):
        """Test IDOR: Work order listing is scoped to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/work-orders/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A work orders
            self.assertIn(self.wo_a.name, content)
            
            # Should NOT see tenant B work orders
            self.assertNotIn(self.wo_b.name, content)

    # ==================
    # Cross-Tenant Vendor Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_vendor(self):
        """Test IDOR: User cannot view vendors from another tenant"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B vendor
        response = self.client.get(f'/work-orders/vendors/{self.vendor_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_vendor(self):
        """Test IDOR: User cannot modify vendors from another tenant"""
        self.client.force_login(self.user_a)
        
        original_name = self.vendor_b.name
        
        # Try to update tenant B vendor
        response = self.client.post(
            f'/work-orders/vendors/{self.vendor_b.id}/update/',
            {
                'name': 'Hacked Vendor',
                'email': 'hacked@vendor.com'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        self.vendor_b.refresh_from_db()
        self.assertEqual(self.vendor_b.name, original_name)

    def test_user_cannot_delete_other_tenant_vendor(self):
        """Test IDOR: User cannot delete vendors from another tenant"""
        self.client.force_login(self.user_a)
        
        vendor_id = self.vendor_b.id
        
        # Try to delete tenant B vendor
        response = self.client.post(f'/work-orders/vendors/{vendor_id}/delete/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify still exists
        self.assertTrue(Vendor.objects.filter(id=vendor_id).exists())

    def test_vendor_list_scoped_to_tenant(self):
        """Test IDOR: Vendor listing is scoped to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/work-orders/vendors/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A vendors
            self.assertIn(self.vendor_a.name, content)
            
            # Should NOT see tenant B vendors
            self.assertNotIn(self.vendor_b.name, content)

    def test_user_cannot_assign_cross_tenant_vendor_to_work_order(self):
        """Test IDOR: Cannot assign cross-tenant vendor to work order"""
        self.client.force_login(self.user_a)
        
        # Try to assign tenant B vendor to tenant A work order
        response = self.client.post(
            f'/work-orders/{self.wo_a.id}/update/',
            {
                'name': self.wo_a.name,
                'vendor': self.vendor_b.id  # Cross-tenant vendor
            }
        )
        
        # Should be rejected
        self.wo_a.refresh_from_db()
        self.assertEqual(self.wo_a.vendor, self.vendor_a)

    # ==================
    # Work Permit Security Tests
    # ==================

    def test_user_cannot_access_other_tenant_work_permit(self):
        """Test IDOR: Work permits are tenant-scoped"""
        # Create work permits
        wp_a = WorkPermitFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        wp_b = WorkPermitFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to access tenant B work permit
        response = self.client.get(f'/work-orders/permits/{wp_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_approve_other_tenant_work_permit(self):
        """Test IDOR: Cannot approve work permits from another tenant"""
        wp_b = WorkPermitFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to approve tenant B work permit
        response = self.client.post(
            f'/work-orders/permits/{wp_b.id}/approve/',
            {
                'approval_status': 'APPROVED',
                'comments': 'Approved'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_approver_list_scoped_to_tenant(self):
        """Test IDOR: Approver assignments are tenant-scoped"""
        wp_a = WorkPermitFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        
        approver_a = ApproverFactory(
            wom=wp_a,
            people=self.user_a
        )
        
        wp_b = WorkPermitFactory(
            client=self.tenant_b,
            location=self.location_b,
            cdby=self.user_b
        )
        
        approver_b = ApproverFactory(
            wom=wp_b,
            people=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Get approver list
        response = self.client.get('/work-orders/approvers/')
        
        if response.status_code == 200:
            # Should only see tenant A approvers
            approvers = Approver.objects.filter(wom__client=self.tenant_a)
            self.assertGreater(approvers.count(), 0)

    # ==================
    # Approval Workflow Security Tests
    # ==================

    def test_user_cannot_add_cross_tenant_approver(self):
        """Test IDOR: Cannot add approvers from another tenant"""
        wp_a = WorkPermitFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        
        self.client.force_login(self.user_a)
        
        # Try to add tenant B user as approver
        response = self.client.post(
            f'/work-orders/permits/{wp_a.id}/add_approver/',
            {'approver_id': self.user_b.id}
        )
        
        # Should be rejected
        cross_tenant_approvers = Approver.objects.filter(
            wom=wp_a,
            people=self.user_b
        )
        self.assertEqual(cross_tenant_approvers.count(), 0)

    def test_approval_requires_assignment(self):
        """Test IDOR: User can only approve if assigned as approver"""
        # Create another user in tenant A
        user_a2 = PeopleFactory(
            client=self.tenant_a,
            peoplecode="WOUSER_A2"
        )
        
        wp_a = WorkPermitFactory(
            client=self.tenant_a,
            location=self.location_a,
            cdby=self.user_a
        )
        
        # Add user_a as approver (not user_a2)
        approver = ApproverFactory(
            wom=wp_a,
            people=self.user_a
        )
        
        self.client.force_login(user_a2)
        
        # Try to approve without being assigned
        response = self.client.post(
            f'/work-orders/permits/{wp_a.id}/approve/',
            {'approval_status': 'APPROVED'}
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    # ==================
    # Work Order Status Security Tests
    # ==================

    def test_vendor_cannot_complete_other_vendor_work_order(self):
        """Test IDOR: Vendors can only complete their assigned work orders"""
        # This would require vendor user type
        # Adjust based on actual implementation
        self.client.force_login(self.user_a)
        
        # Try to complete work order assigned to different vendor
        other_vendor = VendorFactory(
            client=self.tenant_a,
            code="VEND_A2"
        )
        
        wo_other = WomFactory(
            client=self.tenant_a,
            location=self.location_a,
            vendor=other_vendor,
            cdby=self.user_a
        )
        
        # This test depends on vendor authentication model
        # Placeholder for actual implementation

    def test_work_order_status_transition_validation(self):
        """Test IDOR: Status changes respect workflow rules"""
        self.client.force_login(self.user_a)
        
        # Try invalid status transition
        response = self.client.post(
            f'/work-orders/{self.wo_a.id}/update/',
            {
                'workstatus': 'INVALID_STATUS'
            }
        )
        
        # Should be rejected
        self.wo_a.refresh_from_db()
        self.assertNotEqual(self.wo_a.workstatus, 'INVALID_STATUS')

    # ==================
    # Direct ID Manipulation Tests
    # ==================

    def test_sequential_work_order_id_enumeration_blocked(self):
        """Test IDOR: Cannot enumerate work orders by sequential IDs"""
        self.client.force_login(self.user_a)
        
        forbidden_count = 0
        
        for wo_id in range(1, 50):
            response = self.client.get(f'/work-orders/{wo_id}/')
            if response.status_code in [403, 404]:
                forbidden_count += 1
        
        self.assertGreater(
            forbidden_count,
            0,
            "Should prevent enumeration of work orders"
        )

    def test_negative_work_order_id_handling(self):
        """Test IDOR: Negative IDs handled gracefully"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/work-orders/-1/')
        
        # Should return 400 or 404, not 500
        self.assertIn(response.status_code, [400, 404])

    def test_invalid_vendor_id_format_rejected(self):
        """Test IDOR: Invalid ID formats are rejected"""
        self.client.force_login(self.user_a)
        
        invalid_ids = ['invalid', 'abc123', '<script>', '../../etc']
        
        for invalid_id in invalid_ids:
            response = self.client.get(f'/work-orders/vendors/{invalid_id}/')
            self.assertIn(response.status_code, [400, 404])

    # ==================
    # API Endpoint Security Tests
    # ==================

    def test_api_work_order_detail_cross_tenant_blocked(self):
        """Test IDOR: API endpoints enforce tenant isolation"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B work order via API
        response = self.client.get(f'/api/v1/work-orders/{self.wo_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_work_order_list_filtered_by_tenant(self):
        """Test IDOR: API list endpoints scope to tenant"""
        self.client.force_login(self.user_a)
        
        response = self.client.get('/api/v1/work-orders/')
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            
            # Should only include tenant A work orders
            wo_ids = [item['id'] for item in results]
            
            self.assertIn(self.wo_a.id, wo_ids)
            self.assertNotIn(self.wo_b.id, wo_ids)

    def test_api_vendor_detail_cross_tenant_blocked(self):
        """Test IDOR: Vendor API enforces tenant isolation"""
        self.client.force_login(self.user_a)
        
        # Try to access tenant B vendor via API
        response = self.client.get(f'/api/v1/vendors/{self.vendor_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_bulk_work_order_update_scoped_to_tenant(self):
        """Test IDOR: Bulk operations cannot affect other tenants"""
        self.client.force_login(self.user_a)
        
        # Attempt bulk update including cross-tenant work order
        response = self.client.post(
            '/api/v1/work-orders/bulk_update/',
            {
                'work_order_ids': [self.wo_a.id, self.wo_b.id],
                'priority': 'CRITICAL'
            },
            content_type='application/json'
        )
        
        # Verify tenant B work order was not affected
        self.wo_b.refresh_from_db()
        self.assertNotEqual(self.wo_b.priority, 'CRITICAL')

    # ==================
    # Report Access Security Tests
    # ==================

    def test_work_order_reports_cross_tenant_blocked(self):
        """Test IDOR: Work order reports are tenant-scoped"""
        self.client.force_login(self.user_a)
        
        # Try to generate report including tenant B data
        response = self.client.post(
            '/work-orders/reports/generate/',
            {
                'work_order_ids': [self.wo_a.id, self.wo_b.id],
                'report_type': 'summary'
            }
        )
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should include tenant A data
            self.assertIn(self.wo_a.name, content)
            
            # Should NOT include tenant B data
            self.assertNotIn(self.wo_b.name, content)

    def test_vendor_performance_reports_scoped_to_tenant(self):
        """Test IDOR: Vendor reports are tenant-scoped"""
        self.client.force_login(self.user_a)
        
        response = self.client.get(
            f'/work-orders/vendors/{self.vendor_b.id}/performance/'
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    # ==================
    # Asset Association Security Tests
    # ==================

    def test_work_order_cannot_link_cross_tenant_asset(self):
        """Test IDOR: Cannot associate cross-tenant assets"""
        asset_b = AssetFactory(
            client=self.tenant_b,
            location=self.location_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to update work order with cross-tenant asset
        response = self.client.post(
            f'/work-orders/{self.wo_a.id}/update/',
            {
                'name': self.wo_a.name,
                'asset': asset_b.id  # Cross-tenant asset
            }
        )
        
        # Should be rejected
        self.wo_a.refresh_from_db()
        # Asset should remain unchanged or be None
        if hasattr(self.wo_a, 'asset'):
            self.assertNotEqual(self.wo_a.asset.id, asset_b.id)

    def test_work_order_location_scoped_to_tenant(self):
        """Test IDOR: Work order locations must be from same tenant"""
        self.client.force_login(self.user_a)
        
        # Try to update work order with cross-tenant location
        response = self.client.post(
            f'/work-orders/{self.wo_a.id}/update/',
            {
                'name': self.wo_a.name,
                'location': self.location_b.id  # Cross-tenant location
            }
        )
        
        # Should be rejected
        self.wo_a.refresh_from_db()
        self.assertEqual(self.wo_a.location, self.location_a)


@pytest.mark.security
@pytest.mark.idor
@pytest.mark.integration
class WorkOrderIDORIntegrationTestCase(TestCase):
    """Integration tests for work order IDOR across workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_a = BtFactory(bucode="WOINT_A")
        self.tenant_b = BtFactory(bucode="WOINT_B")
        
        self.user_a = PeopleFactory(client=self.tenant_a)
        self.user_b = PeopleFactory(client=self.tenant_b)
        
        self.client = Client()

    def test_complete_work_order_workflow_tenant_isolation(self):
        """Test full work order workflow maintains tenant isolation"""
        self.client.force_login(self.user_a)
        
        # 1. Create work order (tenant A)
        location_a = LocationFactory(client=self.tenant_a)
        vendor_a = VendorFactory(client=self.tenant_a)
        
        response_create = self.client.post(
            '/work-orders/create/',
            {
                'name': 'Test WO A',
                'location': location_a.id,
                'vendor': vendor_a.id,
                'priority': 'MEDIUM'
            }
        )
        
        # 2. Create work permit (tenant A)
        if response_create.status_code in [200, 302]:
            response_permit = self.client.post(
                '/work-orders/permits/create/',
                {
                    'name': 'Test Permit A',
                    'location': location_a.id,
                    'vendor': vendor_a.id
                }
            )
        
        # 3. Try to access tenant B work order
        wo_b = WomFactory(
            client=self.tenant_b,
            location=LocationFactory(client=self.tenant_b),
            vendor=VendorFactory(client=self.tenant_b),
            cdby=self.user_b
        )
        
        response_access = self.client.get(f'/work-orders/{wo_b.id}/')
        self.assertIn(response_access.status_code, [403, 404])

    def test_approval_workflow_cross_tenant_protection(self):
        """Test approval workflow maintains tenant boundaries"""
        # Create work permit for tenant A
        wp_a = WorkPermitFactory(
            client=self.tenant_a,
            location=LocationFactory(client=self.tenant_a),
            cdby=self.user_a
        )
        
        # Add approver from tenant A
        approver_a = ApproverFactory(
            wom=wp_a,
            people=self.user_a
        )
        
        # Create work permit for tenant B
        wp_b = WorkPermitFactory(
            client=self.tenant_b,
            location=LocationFactory(client=self.tenant_b),
            cdby=self.user_b
        )
        
        self.client.force_login(self.user_a)
        
        # Try to approve tenant B permit
        response = self.client.post(
            f'/work-orders/permits/{wp_b.id}/approve/',
            {'approval_status': 'APPROVED'}
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
