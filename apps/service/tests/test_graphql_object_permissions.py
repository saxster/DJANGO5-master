"""
GraphQL Object-Level Permissions Testing Suite

Tests object-level authorization to ensure users can only access resources
they own or have explicit permissions for.

Test Coverage:
- Object ownership validation
- Tenant isolation enforcement
- Cross-tenant access prevention
- Role-based object access
- Capability-based object permissions
- Object filtering based on permissions
- Access denial logging
"""

import pytest
from django.test import TestCase
from graphql import GraphQLError
from apps.peoples.models import People
from apps.onboarding.models import Bt
from apps.attendance.models import PeopleEventlog
from apps.y_helpdesk.models import Ticket
from apps.activity.models.job_model import Jobneed
from apps.core.security.graphql_object_permissions import (
    ObjectPermissionValidator,
    can_view_object,
    can_modify_object,
    can_delete_object,
)


@pytest.mark.django_db
class TestObjectPermissionValidator(TestCase):
    """Test ObjectPermissionValidator class functionality."""

    def setUp(self):
        """Set up test data."""
        self.client1 = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Client 1",
            enable=True
        )

        self.client2 = Bt.objects.create(
            id=2,
            bucode="CLIENT002",
            buname="Client 2",
            enable=True
        )

        self.user1 = People.objects.create_user(
            loginid="user1",
            password="TestPassword123!",
            email="user1@example.com",
            peoplename="User 1",
            client=self.client1,
            bu=self.client1,
            isadmin=False,
            enable=True,
            capabilities={}
        )

        self.user2 = People.objects.create_user(
            loginid="user2",
            password="TestPassword123!",
            email="user2@example.com",
            peoplename="User 2",
            client=self.client2,
            bu=self.client2,
            isadmin=False,
            enable=True,
            capabilities={}
        )

        self.admin_user = People.objects.create_user(
            loginid="adminuser",
            password="AdminPass123!",
            email="admin@example.com",
            peoplename="Admin User",
            client=self.client1,
            bu=self.client1,
            isadmin=True,
            enable=True
        )

    def test_admin_can_access_any_object(self):
        """Test admin users can access any object."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user1.id,
            client_id=self.client1.id,
            bu_id=self.client1.id
        )

        validator = ObjectPermissionValidator(self.admin_user)
        assert validator.can_access_object(eventlog, 'view') is True
        assert validator.can_access_object(eventlog, 'change') is True
        assert validator.can_access_object(eventlog, 'delete') is True

    def test_user_can_access_own_object(self):
        """Test users can access their own objects."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user1.id,
            client_id=self.client1.id,
            bu_id=self.client1.id
        )

        validator = ObjectPermissionValidator(self.user1)
        assert validator.can_access_object(eventlog, 'view') is True

    def test_user_cannot_access_other_user_object(self):
        """Test users cannot access other users' objects."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user2.id,
            client_id=self.client2.id,
            bu_id=self.client2.id
        )

        validator = ObjectPermissionValidator(self.user1)
        assert validator.can_access_object(eventlog, 'view') is False

    def test_tenant_isolation_enforced(self):
        """Test tenant isolation prevents cross-tenant object access."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user1.id,
            client_id=self.client2.id,
            bu_id=self.client2.id
        )

        validator = ObjectPermissionValidator(self.user1)
        assert validator.can_access_object(eventlog, 'view') is False

    def test_capability_grants_object_access(self):
        """Test capability grants access to objects."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user2.id,
            client_id=self.client1.id,
            bu_id=self.client1.id
        )

        validator_without = ObjectPermissionValidator(self.user1)
        assert validator_without.can_access_object(eventlog, 'view') is False

        self.user1.capabilities = {'can_view_all_event_logs': True}
        self.user1.save()

        validator_with = ObjectPermissionValidator(self.user1)
        assert validator_with.can_access_object(eventlog, 'view') is True


@pytest.mark.django_db
class TestTicketObjectPermissions(TestCase):
    """Test object permissions for Ticket model."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.creator = People.objects.create_user(
            loginid="creator",
            password="TestPassword123!",
            email="creator@example.com",
            peoplename="Ticket Creator",
            client=self.client,
            bu=self.client,
            enable=True
        )

        self.assignee = People.objects.create_user(
            loginid="assignee",
            password="TestPassword123!",
            email="assignee@example.com",
            peoplename="Assignee",
            client=self.client,
            bu=self.client,
            enable=True
        )

        self.other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="other@example.com",
            peoplename="Other User",
            client=self.client,
            bu=self.client,
            enable=True
        )

    def test_creator_can_view_own_ticket(self):
        """Test ticket creator can view their ticket."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.creator,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.creator)
        assert validator.can_access_object(ticket, 'view') is True

    def test_assignee_can_view_assigned_ticket(self):
        """Test ticket assignee can view assigned ticket."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.creator,
            assigned_to=self.assignee,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.assignee)
        assert validator.can_access_object(ticket, 'view') is True

    def test_other_user_cannot_view_ticket(self):
        """Test other users cannot view ticket without permission."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.creator,
            assigned_to=self.assignee,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.other_user)
        assert validator.can_access_object(ticket, 'view') is False

    def test_assignee_can_modify_assigned_ticket(self):
        """Test ticket assignee can modify assigned ticket."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.creator,
            assigned_to=self.assignee,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.assignee)
        assert validator.can_access_object(ticket, 'change') is True

    def test_other_user_cannot_modify_ticket(self):
        """Test other users cannot modify ticket."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.creator,
            assigned_to=self.assignee,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.other_user)
        assert validator.can_access_object(ticket, 'change') is False


@pytest.mark.django_db
class TestJobObjectPermissions(TestCase):
    """Test object permissions for Jobneed model."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.bu = Bt.objects.create(
            id=2,
            bucode="BU001",
            buname="Business Unit",
            parent=self.client,
            enable=True
        )

        self.performer = People.objects.create_user(
            loginid="performer",
            password="TestPassword123!",
            email="performer@example.com",
            peoplename="Job Performer",
            client=self.client,
            bu=self.bu,
            enable=True
        )

        self.other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="other@example.com",
            peoplename="Other User",
            client=self.client,
            bu=self.bu,
            enable=True
        )

    def test_performer_can_view_assigned_job(self):
        """Test job performer can view assigned job."""
        from apps.activity.models.location_model import Location

        location = Location.objects.create(
            locname="Test Location",
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        job = Jobneed.objects.create(
            performedby=self.performer,
            client_id=self.client.id,
            bu_id=self.bu.id,
            location=location
        )

        validator = ObjectPermissionValidator(self.performer)
        assert validator.can_access_object(job, 'view') is True

    def test_bu_member_can_view_bu_job(self):
        """Test business unit members can view BU jobs."""
        from apps.activity.models.location_model import Location

        location = Location.objects.create(
            locname="Test Location",
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        job = Jobneed.objects.create(
            performedby=self.performer,
            client_id=self.client.id,
            bu_id=self.bu.id,
            location=location
        )

        validator = ObjectPermissionValidator(self.other_user)
        assert validator.can_access_object(job, 'view') is True


@pytest.mark.django_db
class TestHelperFunctions(TestCase):
    """Test object permission helper functions."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.client,
            enable=True,
            capabilities={}
        )

        self.other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="other@example.com",
            peoplename="Other User",
            client=self.client,
            bu=self.client,
            enable=True
        )

    def test_can_view_object_helper(self):
        """Test can_view_object helper function."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user.id,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        assert can_view_object(self.user, eventlog) is True
        assert can_view_object(self.other_user, eventlog) is False

    def test_can_modify_object_helper(self):
        """Test can_modify_object helper function."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.user,
            assigned_to=self.user,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        assert can_modify_object(self.user, ticket) is True
        assert can_modify_object(self.other_user, ticket) is False

    def test_can_delete_object_helper(self):
        """Test can_delete_object helper function."""
        ticket = Ticket.objects.create(
            description="Test ticket",
            created_by=self.user,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        assert can_delete_object(self.user, ticket) is True
        assert can_delete_object(self.other_user, ticket) is False


@pytest.mark.django_db
class TestObjectPermissionLogging(TestCase):
    """Test object permission access logging."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.client,
            enable=True
        )

        self.other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="other@example.com",
            peoplename="Other User",
            client=self.client,
            bu=self.client,
            enable=True
        )

    def test_object_access_denial_is_logged(self):
        """Test that object access denials are logged for security monitoring."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.other_user.id,
            client_id=self.client.id,
            bu_id=self.client.id
        )

        validator = ObjectPermissionValidator(self.user)

        with self.assertLogs('graphql_object_permissions', level='WARNING') as cm:
            result = validator.can_access_object(eventlog, 'view')

            assert result is False
            assert any('Object access denied' in log for log in cm.output)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])