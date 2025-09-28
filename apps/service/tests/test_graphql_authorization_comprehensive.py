"""
Comprehensive GraphQL Authorization Testing Suite

Tests all aspects of the GraphQL authorization remediation for CVSS 7.2
vulnerability fix, including:

1. Resolver-level authorization enforcement
2. Field-level permission controls
3. Object-level access validation
4. Mutation chaining protection
5. Introspection control in production
6. Django permissions integration
7. Cross-tenant data access prevention

Test Coverage:
- All schema.py resolvers have proper authorization
- All query resolvers enforce authentication/authorization
- All mutations require proper permissions
- Field access is restricted based on user roles
- Object access follows ownership/permission rules
- Mutation chaining limits are enforced
- Introspection is disabled in production
"""

import pytest
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from graphql import GraphQLError
from apps.peoples.models import People
from apps.onboarding.models import Bt
from apps.attendance.models import PeopleEventlog, Tracking
from apps.y_helpdesk.models import Ticket
from apps.activity.models.job_model import Jobneed
from apps.work_order_management.models import Wom
from apps.journal.models import JournalEntry
from apps.service.schema import Query, Mutation
from apps.service.middleware.graphql_auth import (
    GraphQLAuthenticationMiddleware,
    GraphQLMutationChainingProtectionMiddleware,
    GraphQLIntrospectionControlMiddleware,
)
from apps.core.security.graphql_field_permissions import FieldPermissionChecker
from apps.core.security.graphql_object_permissions import ObjectPermissionValidator


@pytest.mark.django_db
class TestSchemaResolverAuthorization(TestCase):
    """
    Test that all schema.py resolvers have proper authorization.

    Validates fix for unprotected resolvers (resolve_PELog_by_id, resolve_trackings, resolve_testcases).
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

        self.admin_user = People.objects.create_user(
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

    def _create_info_mock(self, user=None):
        """Helper to create GraphQL info mock."""
        request = self.factory.post('/graphql')
        request.user = user if user else AnonymousUser()

        info = Mock()
        info.context = request
        return info

    def test_resolve_pelog_by_id_requires_authentication(self):
        """Test resolve_PELog_by_id requires authentication (was unprotected)."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            Query.resolve_PELog_by_id(info, eventlog.id)

    def test_resolve_pelog_by_id_enforces_ownership(self):
        """Test resolve_PELog_by_id enforces ownership for non-admin users."""
        other_user = People.objects.create_user(
            loginid="otheruser",
            password="TestPassword123!",
            email="other@example.com",
            peoplename="Other User",
            client=self.client,
            bu=self.bu,
            enable=True
        )

        eventlog = PeopleEventlog.objects.create(
            peopleid=other_user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        info = self._create_info_mock(self.user)

        with pytest.raises(GraphQLError, match="Access denied"):
            Query.resolve_PELog_by_id(info, eventlog.id)

    def test_resolve_pelog_by_id_allows_admin(self):
        """Test resolve_PELog_by_id allows admin access to any event log."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        info = self._create_info_mock(self.admin_user)

        result = Query.resolve_PELog_by_id(info, eventlog.id)
        assert result == eventlog

    def test_resolve_trackings_requires_authentication(self):
        """Test resolve_trackings requires authentication (was unprotected)."""
        info = self._create_info_mock()

        with pytest.raises(GraphQLError, match="Authentication required"):
            Query.resolve_trackings(info)

    def test_resolve_trackings_filters_by_user_for_non_admin(self):
        """Test resolve_trackings filters data for non-admin users."""
        from apps.attendance.models import Tracking

        Tracking.objects.create(
            peopleid=self.user.id,
            client_id=self.client.id
        )
        Tracking.objects.create(
            peopleid=999,
            client_id=self.client.id
        )

        info = self._create_info_mock(self.user)

        results = Query.resolve_trackings(info)
        assert results.count() == 1
        assert results.first().peopleid == self.user.id

    def test_resolve_testcases_requires_admin(self):
        """Test resolve_testcases requires admin (was unprotected + typo)."""
        info = self._create_info_mock(self.user)

        with pytest.raises(GraphQLError, match="Admin privileges required"):
            Query.resolve_testcases(info)

    def test_resolve_testcases_allows_admin(self):
        """Test resolve_testcases allows admin users."""
        info = self._create_info_mock(self.admin_user)

        results = Query.resolve_testcases(info)
        assert isinstance(results, list)


@pytest.mark.django_db
class TestFieldLevelPermissions(TestCase):
    """
    Test field-level permission enforcement using FieldPermissionChecker.
    """

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
            isverified=True,
            capabilities={}
        )

        self.admin_user = People.objects.create_user(
            loginid="adminuser",
            password="AdminPass123!",
            email="admin@example.com",
            peoplename="Admin User",
            client=self.client,
            bu=self.bu,
            isadmin=True,
            enable=True
        )

    def test_admin_can_access_all_fields(self):
        """Test admin users can access all fields."""
        checker = FieldPermissionChecker(self.admin_user)

        assert checker.can_access_field('People', 'mobno') is True
        assert checker.can_access_field('People', 'email') is True
        assert checker.can_access_field('People', 'isadmin') is True
        assert checker.can_access_field('Ticket', 'internal_notes') is True

    def test_non_admin_cannot_access_admin_only_fields(self):
        """Test non-admin users cannot access admin-only fields."""
        checker = FieldPermissionChecker(self.user)

        assert checker.can_access_field('People', 'isadmin') is False
        assert checker.can_access_field('People', 'is_staff') is False
        assert checker.can_access_field('People', 'user_permissions') is False

    def test_non_admin_cannot_access_sensitive_fields_without_capability(self):
        """Test non-admin users need capabilities for sensitive fields."""
        checker = FieldPermissionChecker(self.user)

        assert checker.can_access_field('People', 'mobno') is False
        assert checker.can_access_field('People', 'capabilities') is False

    def test_user_with_capability_can_access_sensitive_fields(self):
        """Test users with appropriate capabilities can access sensitive fields."""
        self.user.capabilities = {'can_view_people_details': True}
        self.user.save()

        checker = FieldPermissionChecker(self.user)

        assert checker.can_access_field('People', 'mobno') is True
        assert checker.can_access_field('People', 'email') is True

    def test_filter_dict_by_permissions(self):
        """Test dictionary filtering based on field permissions."""
        checker = FieldPermissionChecker(self.user)

        data = {
            'peoplename': 'John Doe',
            'email': 'john@example.com',
            'mobno': '1234567890',
            'isadmin': True,
            'peoplecode': 'EMP001'
        }

        filtered = checker.filter_dict_by_permissions('People', data)

        assert filtered['peoplename'] == 'John Doe'
        assert filtered['peoplecode'] == 'EMP001'
        assert filtered['email'] is None
        assert filtered['mobno'] is None
        assert filtered['isadmin'] is None


@pytest.mark.django_db
class TestObjectLevelPermissions(TestCase):
    """
    Test object-level permission validation using ObjectPermissionValidator.
    """

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
            capabilities={}
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

    def test_user_can_view_own_event_log(self):
        """Test users can view their own event logs."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        validator = ObjectPermissionValidator(self.user)
        assert validator.can_access_object(eventlog, 'view') is True

    def test_user_cannot_view_other_user_event_log(self):
        """Test users cannot view other users' event logs without permission."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.other_user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        validator = ObjectPermissionValidator(self.user)
        assert validator.can_access_object(eventlog, 'view') is False

    def test_user_with_capability_can_view_all_event_logs(self):
        """Test users with capability can view all event logs."""
        eventlog = PeopleEventlog.objects.create(
            peopleid=self.other_user.id,
            client_id=self.client.id,
            bu_id=self.bu.id
        )

        self.user.capabilities = {'can_view_all_event_logs': True}
        self.user.save()

        validator = ObjectPermissionValidator(self.user)
        assert validator.can_access_object(eventlog, 'view') is True

    def test_tenant_isolation_prevents_cross_tenant_access(self):
        """Test tenant isolation prevents access to other tenant's objects."""
        other_client = Bt.objects.create(
            id=3,
            bucode="CLIENT002",
            buname="Other Client",
            enable=True
        )

        eventlog = PeopleEventlog.objects.create(
            peopleid=self.other_user.id,
            client_id=other_client.id,
            bu_id=other_client.id
        )

        validator = ObjectPermissionValidator(self.user)
        assert validator.can_access_object(eventlog, 'view') is False


@pytest.mark.django_db
class TestMutationChainingProtection(TestCase):
    """
    Test mutation chaining protection middleware.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = GraphQLMutationChainingProtectionMiddleware()

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

    def test_mutation_chaining_limit_enforced(self):
        """Test mutation chaining limit is enforced."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "insertRecord"
        info.parent_type = Mock()
        info.parent_type.name = "Mutation"

        def next_resolver(root, info, **kwargs):
            return "Success"

        for i in range(5):
            result = self.middleware.resolve(next_resolver, None, info)
            assert result == "Success"

        with pytest.raises(GraphQLError, match="Mutation chaining limit exceeded"):
            self.middleware.resolve(next_resolver, None, info)

    def test_queries_not_affected_by_mutation_chaining(self):
        """Test queries are not affected by mutation chaining protection."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "getPeople"
        info.parent_type = Mock()
        info.parent_type.name = "Query"

        def next_resolver(root, info, **kwargs):
            return "Success"

        for i in range(10):
            result = self.middleware.resolve(next_resolver, None, info)
            assert result == "Success"


@pytest.mark.django_db
@override_settings(DEBUG=False, GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION=True)
class TestIntrospectionControl(TestCase):
    """
    Test introspection control in production environment.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = GraphQLIntrospectionControlMiddleware()

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

    def test_introspection_disabled_in_production(self):
        """Test introspection queries are blocked in production."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "__schema"
        info.parent_type = Mock()
        info.parent_type.name = "__Schema"

        def next_resolver(root, info, **kwargs):
            return "Schema Data"

        with pytest.raises(GraphQLError, match="Introspection queries are disabled in production"):
            self.middleware.resolve(next_resolver, None, info)

    def test_normal_queries_allowed_in_production(self):
        """Test normal queries work in production even with introspection disabled."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "getPeople"
        info.parent_type = Mock()
        info.parent_type.name = "Query"

        def next_resolver(root, info, **kwargs):
            return "Success"

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == "Success"


@pytest.mark.django_db
@override_settings(DEBUG=True)
class TestIntrospectionAllowedInDevelopment(TestCase):
    """
    Test introspection is allowed in development environment.
    """

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = GraphQLIntrospectionControlMiddleware()

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

    def test_introspection_allowed_in_development(self):
        """Test introspection queries are allowed in development."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "__schema"
        info.parent_type = Mock()
        info.parent_type.name = "__Schema"

        def next_resolver(root, info, **kwargs):
            return "Schema Data"

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == "Schema Data"


@pytest.mark.django_db
class TestDjangoPermissionsIntegration(TestCase):
    """
    Test Django permissions integration with GraphQL decorators.
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

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.client,
            isadmin=False,
            enable=True
        )

        self.admin_user = People.objects.create_user(
            loginid="adminuser",
            password="AdminPass123!",
            email="admin@example.com",
            peoplename="Admin User",
            client=self.client,
            bu=self.client,
            isadmin=True,
            enable=True
        )

        content_type = ContentType.objects.get_for_model(People)
        self.view_permission = Permission.objects.get_or_create(
            codename='view_people',
            name='Can view people',
            content_type=content_type,
        )[0]

    def test_require_model_permission_blocks_without_permission(self):
        """Test require_model_permission blocks users without Django permission."""
        from apps.service.decorators import require_model_permission

        @require_model_permission('peoples.view_people')
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        with pytest.raises(GraphQLError, match="Permission denied"):
            test_resolver(None, info)

    def test_require_model_permission_allows_with_permission(self):
        """Test require_model_permission allows users with Django permission."""
        from apps.service.decorators import require_model_permission

        self.user.user_permissions.add(self.view_permission)

        @require_model_permission('peoples.view_people')
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request

        result = test_resolver(None, info)
        assert result == "Success"

    def test_require_model_permission_allows_admin(self):
        """Test require_model_permission allows admin users."""
        from apps.service.decorators import require_model_permission

        @require_model_permission('peoples.view_people')
        def test_resolver(self, info):
            return "Success"

        request = self.factory.post('/graphql')
        request.user = self.admin_user

        info = Mock()
        info.context = request

        result = test_resolver(None, info)
        assert result == "Success"


@pytest.mark.django_db
class TestComprehensiveAuthorizationCoverage(TestCase):
    """
    Comprehensive test to validate all critical resolvers have authorization.
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

        self.user = People.objects.create_user(
            loginid="testuser",
            password="TestPassword123!",
            email="testuser@example.com",
            peoplename="Test User",
            client=self.client,
            bu=self.client,
            enable=True
        )

    def test_all_schema_resolvers_require_authentication(self):
        """Test all resolvers in schema.py require authentication."""
        info_unauthenticated = Mock()
        request_unauth = self.factory.post('/graphql')
        request_unauth.user = AnonymousUser()
        info_unauthenticated.context = request_unauth

        with pytest.raises(GraphQLError, match="Authentication required"):
            Query.resolve_PELog_by_id(info_unauthenticated, 1)

        with pytest.raises(GraphQLError, match="Authentication required"):
            Query.resolve_trackings(info_unauthenticated)

        with pytest.raises(GraphQLError, match="Authentication required"):
            Query.resolve_testcases(info_unauthenticated)

    def test_django_debug_field_removed(self):
        """Test DjangoDebug field has been removed from schema."""
        from apps.service.schema import RootQuery

        assert not hasattr(RootQuery, 'debug')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])