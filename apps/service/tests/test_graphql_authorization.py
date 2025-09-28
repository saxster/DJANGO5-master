"""
GraphQL Authorization Testing Suite

Comprehensive tests for GraphQL authentication and authorization fixes
to prevent CVSS 9.1 authorization bypass vulnerability.

Test Coverage:
- Unauthenticated access rejection for all resolvers
- Authenticated access validation
- Multi-tenant authorization
- Cross-tenant data access prevention
- Permission-based access control
- Middleware authentication enforcement
- Mutation authorization
"""

import pytest
import json
from unittest.mock import Mock, patch
from django.test import RequestFactory, TestCase
from django.contrib.auth.models import AnonymousUser
from graphql import GraphQLError
from apps.peoples.models import People
from apps.onboarding.models import Bt, TypeAssist
from apps.activity.models.job_model import Jobneed
from apps.y_helpdesk.models import Ticket
from apps.service.queries.people_queries import PeopleQueries
from apps.service.queries.job_queries import JobQueries
from apps.service.queries.ticket_queries import TicketQueries
from apps.service.queries.asset_queries import AssetQueries
from apps.service.queries.bt_queries import BtQueries
from apps.service.queries.question_queries import QuestionQueries
from apps.service.queries.workpermit_queries import WorkPermitQueries
from apps.service.queries.typeassist_queries import TypeAssistQueries
from apps.service.mutations import (
    TaskTourUpdate,
    InsertRecord,
    ReportMutation,
    UploadAttMutaion,
    AdhocMutation,
    InsertJsonMutation,
    SyncMutation,
)
from apps.service.middleware.graphql_auth import GraphQLAuthenticationMiddleware
from apps.service.decorators import (
    require_authentication,
    require_tenant_access,
    require_permission,
)


@pytest.mark.django_db
class TestGraphQLAuthenticationDecorators(TestCase):
    """
    Test authentication decorators for GraphQL resolvers.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.bu = Bt.objects.create(
            id=2,
            bucode="BU001",
            buname="Test Business Unit",
            parent=self.client,
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.bu,
            isadmin=False,
            enable=True,
            isverified=True
        )

        self.other_client = Bt.objects.create(
            id=3,
            bucode="CLIENT002",
            buname="Other Client",
            enable=True
        )

        self.other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="otheruser@example.com",
            peoplename="Other User",
            client=self.other_client,
            bu=self.other_client,
            isadmin=False,
            enable=True,
            isverified=True
        )

    def test_require_authentication_blocks_unauthenticated(self):
        """Test that require_authentication decorator blocks unauthenticated requests."""
        @require_authentication
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = AnonymousUser()

        info = Mock()
        info.context = request

        with pytest.raises(GraphQLError, match="Authentication required"):
            test_resolver(None, info)

    def test_require_authentication_allows_authenticated(self):
        """Test that require_authentication decorator allows authenticated requests."""
        @require_authentication
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        result = test_resolver(None, info)
        assert result == "Success"

    def test_require_tenant_access_blocks_cross_tenant(self):
        """Test that require_tenant_access blocks cross-tenant data access."""
        @require_tenant_access
        def test_resolver(self, info, clientid, buid):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        with pytest.raises(GraphQLError, match="insufficient tenant permissions"):
            test_resolver(None, info, clientid=self.other_client.id, buid=self.bu.id)

    def test_require_tenant_access_allows_same_tenant(self):
        """Test that require_tenant_access allows same-tenant access."""
        @require_tenant_access
        def test_resolver(self, info, clientid, buid):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        result = test_resolver(None, info, clientid=self.user.client_id, buid=self.user.bu_id)
        assert result == "Success"

    def test_require_permission_blocks_without_permission(self):
        """Test that require_permission blocks users without permission."""
        @require_permission('can_approve_work_permits')
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        with pytest.raises(GraphQLError, match="Permission denied"):
            test_resolver(None, info)

    def test_require_permission_allows_admin(self):
        """Test that require_permission allows admin users."""
        @require_permission('can_approve_work_permits')
        def test_resolver(self, info):
            return "Success"

        admin_user = People.objects.create_user(
            loginid="adminuser",
            password="AdminPass123!",
            email="admin@example.com",
            peoplename="Admin User",
            client=self.client,
            bu=self.bu,
            isadmin=True,
            enable=True,
            isverified=True
        )

        request = self.factory.post('/graphql')
        request.user = admin_user

        info = Mock()
        info.context = request

        result = test_resolver(None, info)
        assert result == "Success"


@pytest.mark.django_db
class TestGraphQLQueryAuthentication(TestCase):
    """
    Test authentication enforcement for all GraphQL query resolvers.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.bu = Bt.objects.create(
            id=2,
            bucode="BU001",
            buname="Test Business Unit",
            parent=self.client,
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.bu,
            isadmin=False,
            enable=True,
            isverified=True
        )

    def _create_info_mock(self, user=None):
        """Helper to create GraphQL info mock."""
        request = self.factory.post('/graphql')
        request.user = user if user else AnonymousUser()

        info = Mock()
        info.context = request
        return info

    def test_people_queries_require_authentication(self):
        """Test PeopleQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            PeopleQueries.resolve_get_peoplemodifiedafter(
                None, info, mdtz="2024-01-01", ctzoffset=0, buid=self.bu.id
            )

    def test_job_queries_require_authentication(self):
        """Test JobQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            JobQueries.resolve_get_jobneedmodifiedafter(
                None, info, peopleid=1, buid=self.bu.id, clientid=self.client.id
            )

    def test_ticket_queries_require_authentication(self):
        """Test TicketQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            TicketQueries.resolve_get_tickets(
                None, info, peopleid=1, mdtz="2024-01-01", ctzoffset=0
            )

    def test_asset_queries_require_authentication(self):
        """Test AssetQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            AssetQueries.resolve_get_assetdetails(
                None, info, mdtz="2024-01-01", ctzoffset=0, buid=self.bu.id
            )

    def test_bt_queries_require_authentication(self):
        """Test BtQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            BtQueries.resolve_get_locations(
                None, info, mdtz="2024-01-01", ctzoffset=0, buid=self.bu.id
            )

    def test_question_queries_require_authentication(self):
        """Test QuestionQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            QuestionQueries.resolve_get_questionsmodifiedafter(
                None, info, mdtz="2024-01-01", ctzoffset=0, clientid=self.client.id
            )

    def test_workpermit_queries_require_authentication(self):
        """Test WorkPermitQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            WorkPermitQueries.resolve_get_vendors(
                None, info, clientid=self.client.id, mdtz="2024-01-01",
                buid=self.bu.id, ctzoffset=0
            )

    def test_typeassist_queries_require_authentication(self):
        """Test TypeAssistQueries resolvers require authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            TypeAssistQueries.resolve_get_typeassistmodifiedafter(
                None, info, mdtz="2024-01-01", ctzoffset=0, clientid=self.client.id
            )


@pytest.mark.django_db
class TestGraphQLMutationAuthentication(TestCase):
    """
    Test authentication enforcement for GraphQL mutations.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.bu = Bt.objects.create(
            id=2,
            bucode="BU001",
            buname="Test Business Unit",
            parent=self.client,
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.bu,
            isadmin=False,
            enable=True,
            isverified=True
        )

    def _create_info_mock(self, user=None):
        """Helper to create GraphQL info mock."""
        request = self.factory.post('/graphql')
        request.user = user if user else AnonymousUser()

        info = Mock()
        info.context = request
        return info

    def test_tasktour_update_requires_authentication(self):
        """Test TaskTourUpdate mutation requires authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            TaskTourUpdate.mutate(None, info, records=[])

    def test_insert_record_requires_authentication(self):
        """Test InsertRecord mutation requires authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            InsertRecord.mutate(None, info, records=[])

    def test_report_mutation_requires_authentication(self):
        """Test ReportMutation requires authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            ReportMutation.mutate(None, info, records=[])

    def test_adhoc_mutation_requires_authentication(self):
        """Test AdhocMutation requires authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            AdhocMutation.mutate(None, info, records=[])

    def test_insert_json_mutation_requires_authentication(self):
        """Test InsertJsonMutation requires authentication."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            InsertJsonMutation.mutate(None, info, jsondata=[], tablename="test")


@pytest.mark.django_db
class TestGraphQLMiddlewareAuthentication(TestCase):
    """
    Test GraphQL authentication middleware.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = GraphQLAuthenticationMiddleware()

        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.bu = Bt.objects.create(
            id=2,
            bucode="BU001",
            buname="Test Business Unit",
            parent=self.client,
            enable=True
        )

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.bu,
            isadmin=False,
            enable=True,
            isverified=True
        )

    def test_middleware_blocks_unauthenticated_queries(self):
        """Test middleware blocks unauthenticated queries."""
        request = self.factory.post('/graphql')
        request.user = AnonymousUser()

        info = Mock()
        info.context = request
        info.field_name = "getPeopleModifiedAfter"
        info.parent_type = Mock()
        info.parent_type.name = "Query"

        def next_resolver(root, info, **kwargs):
            return "Success"

        with pytest.raises(GraphQLError, match="Authentication required"):
            self.middleware.resolve(next_resolver, None, info)

    def test_middleware_allows_introspection(self):
        """Test middleware allows introspection queries without authentication."""
        request = self.factory.post('/graphql')
        request.user = AnonymousUser()

        info = Mock()
        info.context = request
        info.field_name = "__schema"
        info.parent_type = Mock()
        info.parent_type.name = "__Schema"

        def next_resolver(root, info, **kwargs):
            return "Success"

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == "Success"

    def test_middleware_allows_authenticated_queries(self):
        """Test middleware allows authenticated queries."""
        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request
        info.field_name = "getPeopleModifiedAfter"
        info.parent_type = Mock()
        info.parent_type.name = "Query"

        def next_resolver(root, info, **kwargs):
            return "Success"

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == "Success"


@pytest.mark.django_db
class TestCrossTenantDataAccessPrevention(TestCase):
    """
    Test cross-tenant data access prevention.
    """

    def setUp(self):
        """Set up test data with multiple tenants."""
        self.factory = RequestFactory()

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
            isverified=True
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
            isverified=True
        )

    def test_user_cannot_access_other_tenant_data(self):
        """Test user from tenant 1 cannot access tenant 2 data."""
        request = self.factory.post('/graphql')
        request.user = self.user1

        info = Mock()
        info.context = request

        with pytest.raises(GraphQLError, match="insufficient tenant permissions"):
            PeopleQueries.resolve_get_peoplemodifiedafter(
                None, info, mdtz="2024-01-01", ctzoffset=0, buid=self.client2.id
            )

    def test_user_can_access_own_tenant_data(self):
        """Test user can access their own tenant data."""
        request = self.factory.post('/graphql')
        request.user = self.user1

        info = Mock()
        info.context = request

        try:
            PeopleQueries.resolve_get_peoplemodifiedafter(
                None, info, mdtz="2024-01-01", ctzoffset=0, buid=self.client1.id
            )
        except Exception as e:
            if "insufficient tenant permissions" in str(e):
                pytest.fail("User should be able to access own tenant data")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])