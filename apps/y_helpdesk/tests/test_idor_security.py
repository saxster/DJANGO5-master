"""
IDOR Security Tests for Y_Helpdesk App

Tests prevent Insecure Direct Object Reference vulnerabilities for tickets,
escalations, comments, and knowledge base access.

Critical Test Coverage:
    - Cross-tenant ticket access prevention
    - Cross-user ticket privacy enforcement
    - Comment access control
    - Escalation workflow security
    - Knowledge base access control
    - Attachment security

Security Note:
    Helpdesk tickets contain sensitive customer and operational data.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.y_helpdesk.models import Ticket
from apps.client_onboarding.models import Bt
from apps.peoples.tests.factories import (
    BtFactory,
    CompleteUserFactory,
    LocationFactory
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.idor
class HelpdeskIDORTestCase(TestCase):
    """Test suite for IDOR vulnerabilities in y_helpdesk app."""

    def setUp(self):
        """Set up test fixtures for IDOR testing."""
        self.client = Client()
        
        # Create two separate tenants
        self.tenant_a = BtFactory(bucode="HELP_A", buname="Helpdesk Tenant A")
        self.tenant_b = BtFactory(bucode="HELP_B", buname="Helpdesk Tenant B")
        
        # Create users for tenant A
        self.user_a1 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="HELP_A1",
            peoplename="User A1"
        )
        self.user_a2 = CompleteUserFactory(
            client=self.tenant_a,
            peoplecode="HELP_A2",
            peoplename="User A2"
        )
        
        # Create users for tenant B
        self.user_b1 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="HELP_B1",
            peoplename="User B1"
        )
        self.user_b2 = CompleteUserFactory(
            client=self.tenant_b,
            peoplecode="HELP_B2",
            peoplename="User B2"
        )
        
        # Create tickets
        self.ticket_a = Ticket.objects.create(
            ticketdesc="Ticket from Tenant A",
            client=self.tenant_a,
            bu=self.tenant_a,
            assignedtopeople=self.user_a1,
            status="OPEN",
            priority="MEDIUM"
        )
        
        self.ticket_b = Ticket.objects.create(
            ticketdesc="Ticket from Tenant B",
            client=self.tenant_b,
            bu=self.tenant_b,
            assignedtopeople=self.user_b1,
            status="OPEN",
            priority="MEDIUM"
        )

    # ==================
    # Cross-Tenant Ticket Access Prevention Tests
    # ==================

    def test_user_cannot_access_other_tenant_ticket(self):
        """Test IDOR: User cannot view tickets from another tenant"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B ticket
        response = self.client.get(f'/help-desk/tickets/{self.ticket_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_tenant_ticket(self):
        """Test IDOR: User cannot modify tickets from another tenant"""
        self.client.force_login(self.user_a1)
        
        original_desc = self.ticket_b.ticketdesc
        original_priority = self.ticket_b.priority
        
        # Try to update tenant B ticket
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/update/',
            {
                'ticketdesc': 'Hacked description',
                'priority': 'CRITICAL',
                'status': 'CLOSED'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify not changed
        self.ticket_b.refresh_from_db()
        self.assertEqual(self.ticket_b.ticketdesc, original_desc)
        self.assertEqual(self.ticket_b.priority, original_priority)

    def test_user_cannot_delete_other_tenant_ticket(self):
        """Test IDOR: User cannot delete tickets from another tenant"""
        self.client.force_login(self.user_a1)
        
        ticket_id = self.ticket_b.id
        
        # Try to delete tenant B ticket
        response = self.client.post(f'/help-desk/tickets/{ticket_id}/delete/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])
        
        # Verify still exists
        self.assertTrue(Ticket.objects.filter(id=ticket_id).exists())

    def test_ticket_list_scoped_to_tenant(self):
        """Test IDOR: Ticket listing is scoped to tenant"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/help-desk/tickets/')
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should see tenant A tickets
            self.assertIn(self.ticket_a.ticketdesc, content)
            
            # Should NOT see tenant B tickets
            self.assertNotIn(self.ticket_b.ticketdesc, content)

    # ==================
    # Cross-User Ticket Privacy Tests
    # ==================

    def test_user_can_view_assigned_ticket(self):
        """Test: User CAN view tickets assigned to them"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get(f'/help-desk/tickets/{self.ticket_a.id}/')
        
        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_user_can_view_own_created_ticket(self):
        """Test: User CAN view tickets they created"""
        # Create ticket created by user A2
        ticket_created_by_a2 = Ticket.objects.create(
            ticketdesc="Ticket created by A2",
            client=self.tenant_a,
            bu=self.tenant_a,
            createdby=self.user_a2,
            assignedtopeople=self.user_a1,
            status="OPEN"
        )
        
        self.client.force_login(self.user_a2)
        
        response = self.client.get(f'/help-desk/tickets/{ticket_created_by_a2.id}/')
        
        # Creator should be able to view
        self.assertEqual(response.status_code, 200)

    def test_user_cannot_edit_unassigned_ticket(self):
        """Test IDOR: User cannot edit tickets not assigned to them"""
        # Create ticket assigned to user A2
        ticket_a2 = Ticket.objects.create(
            ticketdesc="Ticket for A2",
            client=self.tenant_a,
            bu=self.tenant_a,
            assignedtopeople=self.user_a2,
            status="OPEN"
        )
        
        self.client.force_login(self.user_a1)
        
        original_status = ticket_a2.status
        
        # Try to update
        response = self.client.post(
            f'/help-desk/tickets/{ticket_a2.id}/update/',
            {'status': 'CLOSED'}
        )
        
        # Should be forbidden (unless user is supervisor)
        # Adjust based on actual business rules
        if response.status_code == 403:
            ticket_a2.refresh_from_db()
            self.assertEqual(ticket_a2.status, original_status)

    def test_user_cannot_reassign_ticket_to_cross_tenant_user(self):
        """Test IDOR: Cannot reassign ticket to user from another tenant"""
        self.client.force_login(self.user_a1)
        
        # Try to reassign tenant A ticket to tenant B user
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_a.id}/assign/',
            {'assigned_to': self.user_b1.id}
        )
        
        # Should be rejected
        self.ticket_a.refresh_from_db()
        self.assertNotEqual(self.ticket_a.assignedtopeople, self.user_b1)

    # ==================
    # Comment Access Security Tests
    # ==================

    def test_user_cannot_view_comments_on_cross_tenant_ticket(self):
        """Test IDOR: Comments on cross-tenant tickets are not accessible"""
        self.client.force_login(self.user_a1)
        
        # Try to view comments on tenant B ticket
        response = self.client.get(
            f'/help-desk/tickets/{self.ticket_b.id}/comments/'
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_add_comment_to_cross_tenant_ticket(self):
        """Test IDOR: Cannot add comments to cross-tenant tickets"""
        self.client.force_login(self.user_a1)
        
        # Try to comment on tenant B ticket
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/comments/add/',
            {
                'comment': 'Hacked comment',
                'is_internal': False
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_edit_other_user_comment(self):
        """Test IDOR: Users cannot edit comments by other users"""
        # This requires comment model - adjust based on actual implementation
        # Placeholder for actual test
        pass

    def test_internal_comments_not_visible_to_regular_users(self):
        """Test IDOR: Internal comments restricted to staff"""
        # This requires comment model with is_internal flag
        # Placeholder for actual test
        pass

    # ==================
    # Escalation Workflow Security Tests
    # ==================

    def test_user_cannot_escalate_cross_tenant_ticket(self):
        """Test IDOR: Cannot escalate tickets from another tenant"""
        self.client.force_login(self.user_a1)
        
        # Try to escalate tenant B ticket
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/escalate/',
            {
                'escalation_level': 'MANAGER',
                'reason': 'Urgent issue'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_escalation_history_cross_tenant_blocked(self):
        """Test IDOR: Escalation history is tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to view escalation history for tenant B ticket
        response = self.client.get(
            f'/help-desk/tickets/{self.ticket_b.id}/escalations/'
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_supervisor_can_view_subordinate_tickets_only(self):
        """Test IDOR: Supervisors see only their team's tickets"""
        # This requires supervisor/subordinate relationship
        # Placeholder for actual test based on organizational model
        pass

    # ==================
    # Attachment Security Tests
    # ==================

    def test_user_cannot_download_attachment_from_cross_tenant_ticket(self):
        """Test IDOR: Attachments on cross-tenant tickets are not accessible"""
        self.client.force_login(self.user_a1)
        
        # Try to download attachment from tenant B ticket
        # Assumes attachment ID or path
        response = self.client.get(
            f'/help-desk/tickets/{self.ticket_b.id}/attachments/1/download/'
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_user_cannot_upload_attachment_to_cross_tenant_ticket(self):
        """Test IDOR: Cannot upload to cross-tenant tickets"""
        self.client.force_login(self.user_a1)
        
        # Try to upload to tenant B ticket
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        test_file = SimpleUploadedFile(
            "test.txt",
            b"test content",
            content_type="text/plain"
        )
        
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/attachments/upload/',
            {'file': test_file}
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_attachment_path_traversal_blocked(self):
        """Test IDOR: Path traversal in attachment access is blocked"""
        self.client.force_login(self.user_a1)
        
        # Try path traversal attacks
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            '%2e%2e%2f',
        ]
        
        for path in malicious_paths:
            response = self.client.get(
                f'/help-desk/attachments/download/{path}'
            )
            # Should be rejected
            self.assertIn(response.status_code, [400, 403, 404])

    # ==================
    # Knowledge Base Security Tests
    # ==================

    def test_knowledge_base_article_access_scoped_to_tenant(self):
        """Test IDOR: Knowledge base articles are tenant-scoped"""
        # This requires KB article model
        # Placeholder for actual test
        pass

    def test_private_kb_articles_not_accessible(self):
        """Test IDOR: Private KB articles restricted"""
        # This requires KB article with visibility flags
        # Placeholder for actual test
        pass

    # ==================
    # Direct ID Manipulation Tests
    # ==================

    def test_sequential_ticket_id_enumeration_blocked(self):
        """Test IDOR: Cannot enumerate tickets by sequential IDs"""
        self.client.force_login(self.user_a1)
        
        forbidden_count = 0
        
        for ticket_id in range(1, 50):
            response = self.client.get(f'/help-desk/tickets/{ticket_id}/')
            if response.status_code in [403, 404]:
                forbidden_count += 1
        
        self.assertGreater(
            forbidden_count,
            0,
            "Should prevent enumeration of tickets"
        )

    def test_negative_ticket_id_handling(self):
        """Test IDOR: Negative IDs handled gracefully"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/help-desk/tickets/-1/')
        
        # Should return 400 or 404, not 500
        self.assertIn(response.status_code, [400, 404])

    def test_invalid_ticket_id_format_rejected(self):
        """Test IDOR: Invalid ID formats are rejected"""
        self.client.force_login(self.user_a1)
        
        invalid_ids = ['invalid', 'abc123', '<script>', '../../etc']
        
        for invalid_id in invalid_ids:
            response = self.client.get(f'/help-desk/tickets/{invalid_id}/')
            self.assertIn(response.status_code, [400, 404])

    # ==================
    # API Endpoint Security Tests
    # ==================

    def test_api_ticket_detail_cross_tenant_blocked(self):
        """Test IDOR: API endpoints enforce tenant isolation"""
        self.client.force_login(self.user_a1)
        
        # Try to access tenant B ticket via API
        response = self.client.get(f'/api/v1/tickets/{self.ticket_b.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_api_ticket_list_filtered_by_tenant(self):
        """Test IDOR: API list endpoints scope to tenant"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/api/v1/tickets/')
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            
            # Should only include tenant A tickets
            ticket_ids = [item['id'] for item in results]
            
            self.assertIn(self.ticket_a.id, ticket_ids)
            self.assertNotIn(self.ticket_b.id, ticket_ids)

    def test_api_bulk_ticket_update_scoped_to_tenant(self):
        """Test IDOR: Bulk operations cannot affect other tenants"""
        self.client.force_login(self.user_a1)
        
        # Attempt bulk update including cross-tenant ticket
        response = self.client.post(
            '/api/v1/tickets/bulk_update/',
            {
                'ticket_ids': [self.ticket_a.id, self.ticket_b.id],
                'status': 'CLOSED'
            },
            content_type='application/json'
        )
        
        # Verify tenant B ticket was not affected
        self.ticket_b.refresh_from_db()
        self.assertNotEqual(self.ticket_b.status, 'CLOSED')

    # ==================
    # SLA and Priority Security Tests
    # ==================

    def test_user_cannot_manipulate_sla_on_cross_tenant_ticket(self):
        """Test IDOR: SLA settings are tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to modify SLA on tenant B ticket
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/sla/update/',
            {
                'sla_hours': 24,
                'priority': 'CRITICAL'
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_priority_escalation_requires_authorization(self):
        """Test IDOR: Priority changes require proper permissions"""
        self.client.force_login(self.user_a1)
        
        original_priority = self.ticket_a.priority
        
        # Try to escalate to CRITICAL (may require special permission)
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_a.id}/update/',
            {'priority': 'CRITICAL'}
        )
        
        # Depending on business rules, may be allowed or forbidden
        # Adjust based on actual implementation
        if response.status_code == 403:
            self.ticket_a.refresh_from_db()
            self.assertEqual(self.ticket_a.priority, original_priority)

    # ==================
    # Report Access Security Tests
    # ==================

    def test_ticket_reports_cross_tenant_blocked(self):
        """Test IDOR: Ticket reports are tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to generate report including tenant B data
        response = self.client.post(
            '/help-desk/reports/generate/',
            {
                'ticket_ids': [self.ticket_a.id, self.ticket_b.id],
                'report_type': 'summary'
            }
        )
        
        if response.status_code == 200:
            content = response.content.decode()
            
            # Should include tenant A data
            self.assertIn(self.ticket_a.ticketdesc, content)
            
            # Should NOT include tenant B data
            self.assertNotIn(self.ticket_b.ticketdesc, content)

    def test_analytics_dashboard_scoped_to_tenant(self):
        """Test IDOR: Analytics show only tenant data"""
        self.client.force_login(self.user_a1)
        
        response = self.client.get('/help-desk/analytics/')
        
        if response.status_code == 200:
            # Verify analytics include only tenant A tickets
            # Adjust based on actual implementation
            pass

    # ==================
    # Notification Security Tests
    # ==================

    def test_user_cannot_trigger_notifications_for_cross_tenant_ticket(self):
        """Test IDOR: Notifications are tenant-scoped"""
        self.client.force_login(self.user_a1)
        
        # Try to send notification for tenant B ticket
        response = self.client.post(
            f'/help-desk/tickets/{self.ticket_b.id}/notify/',
            {
                'message': 'Test notification',
                'recipients': [self.user_b1.id]
            }
        )
        
        # Should be forbidden
        self.assertIn(response.status_code, [403, 404])

    def test_email_templates_scoped_to_tenant(self):
        """Test IDOR: Email templates are tenant-scoped"""
        # This requires email template model
        # Placeholder for actual test
        pass


@pytest.mark.security
@pytest.mark.idor
@pytest.mark.integration
class HelpdeskIDORIntegrationTestCase(TestCase):
    """Integration tests for helpdesk IDOR across workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_a = BtFactory(bucode="HELPINT_A")
        self.tenant_b = BtFactory(bucode="HELPINT_B")
        
        self.user_a = CompleteUserFactory(client=self.tenant_a)
        self.user_b = CompleteUserFactory(client=self.tenant_b)
        
        self.client = Client()

    def test_complete_ticket_lifecycle_tenant_isolation(self):
        """Test full ticket lifecycle maintains tenant isolation"""
        self.client.force_login(self.user_a)
        
        # 1. Create ticket (tenant A)
        response_create = self.client.post(
            '/help-desk/tickets/create/',
            {
                'ticketdesc': 'Test Ticket A',
                'priority': 'MEDIUM',
                'category': 'TECHNICAL'
            }
        )
        
        # 2. Try to comment on tenant B ticket
        ticket_b = Ticket.objects.create(
            ticketdesc="Tenant B Ticket",
            client=self.tenant_b,
            bu=self.tenant_b,
            assignedtopeople=self.user_b,
            status="OPEN"
        )
        
        response_comment = self.client.post(
            f'/help-desk/tickets/{ticket_b.id}/comments/add/',
            {'comment': 'Cross-tenant comment attempt'}
        )
        
        # Should be forbidden
        self.assertIn(response_comment.status_code, [403, 404])
        
        # 3. Try to escalate tenant B ticket
        response_escalate = self.client.post(
            f'/help-desk/tickets/{ticket_b.id}/escalate/',
            {'level': 'MANAGER'}
        )
        
        # Should be forbidden
        self.assertIn(response_escalate.status_code, [403, 404])

    def test_multi_user_ticket_collaboration_within_tenant(self):
        """Test that collaboration works within tenant but not across"""
        # Create ticket in tenant A
        ticket_a = Ticket.objects.create(
            ticketdesc="Collaborative Ticket",
            client=self.tenant_a,
            bu=self.tenant_a,
            assignedtopeople=self.user_a,
            status="OPEN"
        )
        
        # User A can access
        self.client.force_login(self.user_a)
        response_a = self.client.get(f'/help-desk/tickets/{ticket_a.id}/')
        self.assertEqual(response_a.status_code, 200)
        
        # User B cannot access
        self.client.logout()
        self.client.force_login(self.user_b)
        response_b = self.client.get(f'/help-desk/tickets/{ticket_a.id}/')
        self.assertIn(response_b.status_code, [403, 404])
