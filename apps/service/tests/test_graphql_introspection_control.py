"""
GraphQL Introspection Control Testing Suite

Tests introspection control middleware to ensure schema discovery is properly
restricted in production environments while remaining accessible in development.

Test Coverage:
- Introspection disabled in production
- Introspection allowed in development
- Introspection field detection
- Security logging for introspection attempts
- Proper error messages and codes
"""

import pytest
from django.test import TestCase, RequestFactory, override_settings
from unittest.mock import Mock
from graphql import GraphQLError
from apps.peoples.models import People
from apps.onboarding.models import Bt
from apps.service.middleware.graphql_auth import GraphQLIntrospectionControlMiddleware


@pytest.mark.django_db
@override_settings(DEBUG=False, GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION=True)
class TestIntrospectionBlockedInProduction(TestCase):
    """Test introspection queries are blocked in production."""

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

    def _create_introspection_info(self, field_name):
        """Helper to create introspection info mock."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = field_name
        info.parent_type = Mock()
        info.parent_type.name = '__Schema'

        return info

    def test_schema_introspection_blocked(self):
        """Test __schema introspection is blocked in production."""
        info = self._create_introspection_info('__schema')

        def next_resolver(root, info, **kwargs):
            return "Schema Data"

        with pytest.raises(GraphQLError, match="Introspection queries are disabled in production"):
            self.middleware.resolve(next_resolver, None, info)

    def test_type_introspection_blocked(self):
        """Test __type introspection is blocked in production."""
        info = self._create_introspection_info('__type')

        def next_resolver(root, info, **kwargs):
            return "Type Data"

        with pytest.raises(GraphQLError, match="Introspection queries are disabled in production"):
            self.middleware.resolve(next_resolver, None, info)

    def test_typename_introspection_blocked(self):
        """Test __typename introspection is blocked in production."""
        info = self._create_introspection_info('__typename')

        def next_resolver(root, info, **kwargs):
            return "TypeName Data"

        with pytest.raises(GraphQLError, match="Introspection queries are disabled in production"):
            self.middleware.resolve(next_resolver, None, info)

    def test_introspection_error_includes_documentation_url(self):
        """Test introspection error provides documentation URL."""
        info = self._create_introspection_info('__schema')

        def next_resolver(root, info, **kwargs):
            return "Schema Data"

        try:
            self.middleware.resolve(next_resolver, None, info)
            pytest.fail("Should have raised GraphQLError")
        except GraphQLError as e:
            assert hasattr(e, 'extensions')
            assert e.extensions.get('code') == 'INTROSPECTION_DISABLED'
            assert e.extensions.get('documentation_url') == '/api/docs/'

    def test_normal_queries_allowed_in_production(self):
        """Test normal queries work even with introspection disabled."""
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
@override_settings(DEBUG=True, GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION=True)
class TestIntrospectionAllowedInDevelopment(TestCase):
    """Test introspection queries are allowed in development."""

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

    def test_schema_introspection_allowed_in_development(self):
        """Test __schema introspection works in development."""
        request = self.factory.post('/graphql')
        request.user = self.user
        request.correlation_id = 'test_correlation_123'

        info = Mock()
        info.context = request
        info.field_name = "__schema"
        info.parent_type = Mock()
        info.parent_type.name = "__Schema"

        def next_resolver(root, info, **kwargs):
            return {"queryType": "Query", "mutationType": "Mutation"}

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == {"queryType": "Query", "mutationType": "Mutation"}

    def test_type_introspection_allowed_in_development(self):
        """Test __type introspection works in development."""
        request = self.factory.post('/graphql')
        request.user = self.user

        info = Mock()
        info.context = request
        info.field_name = "__type"
        info.parent_type = Mock()
        info.parent_type.name = "__Type"

        def next_resolver(root, info, **kwargs):
            return {"name": "People", "kind": "OBJECT"}

        result = self.middleware.resolve(next_resolver, None, info)
        assert result == {"name": "People", "kind": "OBJECT"}


@pytest.mark.django_db
@override_settings(DEBUG=False, GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION=False)
class TestIntrospectionConfigurationOverride(TestCase):
    """Test introspection can be explicitly enabled in production."""

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

    def test_introspection_allowed_when_explicitly_enabled(self):
        """Test introspection works when explicitly enabled in production."""
        request = self.factory.post('/graphql')
        request.user = self.user

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
class TestIntrospectionLogging(TestCase):
    """Test introspection control security logging."""

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

    @override_settings(DEBUG=False, GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION=True)
    def test_introspection_attempt_logged_in_production(self):
        """Test introspection attempts are logged in production."""
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

        with self.assertLogs('graphql_security', level='WARNING') as cm:
            with pytest.raises(GraphQLError):
                self.middleware.resolve(next_resolver, None, info)

            assert any('introspection attempt blocked in production' in log.lower() for log in cm.output)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])