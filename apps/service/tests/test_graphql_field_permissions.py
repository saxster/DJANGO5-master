"""
GraphQL Field-Level Permissions Testing Suite

Comprehensive tests for field-level authorization to ensure sensitive fields
are properly protected from unauthorized access.

Test Coverage:
- Sensitive field access control
- Admin-only field restrictions
- Role-based field access
- Field filtering in queries
- Permission caching behavior
- Capability-based field access
- Cross-field permission validation
"""

import pytest
import json
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from apps.peoples.models import People
from apps.onboarding.models import Bt
from apps.core.security.graphql_field_permissions import (
    FieldPermissionChecker,
    require_field_permission,
    filter_fields_by_permission,
)


@pytest.mark.django_db
class TestFieldPermissionChecker(TestCase):
    """Test FieldPermissionChecker class functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.regular_user = People.objects.create_user(
            loginid="regularuser",
            password="TestPassword123!",
            email="regular@example.com",
            peoplename="Regular User",
            client=self.client,
            bu=self.client,
            isadmin=False,
            enable=True,
            capabilities={}
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

        self.manager_user = People.objects.create_user(
            loginid="manageruser",
            password="ManagerPass123!",
            email="manager@example.com",
            peoplename="Manager User",
            client=self.client,
            bu=self.client,
            isadmin=False,
            enable=True,
            capabilities={'is_manager': True}
        )

    def test_unauthenticated_user_cannot_access_any_field(self):
        """Test unauthenticated users cannot access any fields."""
        anonymous = AnonymousUser()
        checker = FieldPermissionChecker(anonymous)

        assert checker.can_access_field('People', 'peoplename') is False
        assert checker.can_access_field('People', 'email') is False

    def test_admin_can_access_all_fields(self):
        """Test admin users can access all fields including admin-only."""
        checker = FieldPermissionChecker(self.admin_user)

        assert checker.can_access_field('People', 'mobno') is True
        assert checker.can_access_field('People', 'email') is True
        assert checker.can_access_field('People', 'isadmin') is True
        assert checker.can_access_field('People', 'is_staff') is True
        assert checker.can_access_field('Ticket', 'internal_notes') is True

    def test_regular_user_cannot_access_admin_only_fields(self):
        """Test regular users cannot access admin-only fields."""
        checker = FieldPermissionChecker(self.regular_user)

        assert checker.can_access_field('People', 'isadmin') is False
        assert checker.can_access_field('People', 'is_staff') is False
        assert checker.can_access_field('People', 'user_permissions') is False

    def test_regular_user_can_access_public_fields(self):
        """Test regular users can access public fields."""
        checker = FieldPermissionChecker(self.regular_user)

        assert checker.can_access_field('People', 'peoplename') is True
        assert checker.can_access_field('People', 'peoplecode') is True

    def test_sensitive_fields_require_capability(self):
        """Test sensitive fields require specific capabilities."""
        checker = FieldPermissionChecker(self.regular_user)

        assert checker.can_access_field('People', 'mobno') is False
        assert checker.can_access_field('People', 'email') is False

        self.regular_user.capabilities = {'can_view_people_details': True}
        self.regular_user.save()

        checker_with_cap = FieldPermissionChecker(self.regular_user)

        assert checker_with_cap.can_access_field('People', 'mobno') is True
        assert checker_with_cap.can_access_field('People', 'email') is True

    def test_role_based_field_access(self):
        """Test role-based field access control."""
        checker = FieldPermissionChecker(self.manager_user)

        assert checker.can_access_field('People', 'performance_metrics') is True
        assert checker.can_access_field('People', 'attendance_summary') is True

    def test_filter_dict_by_permissions(self):
        """Test filtering dictionaries by field permissions."""
        checker = FieldPermissionChecker(self.regular_user)

        data = {
            'id': 1,
            'peoplename': 'John Doe',
            'peoplecode': 'EMP001',
            'email': 'john@example.com',
            'mobno': '1234567890',
            'isadmin': True,
            'is_staff': False
        }

        filtered = checker.filter_dict_by_permissions('People', data)

        assert filtered['id'] == 1
        assert filtered['peoplename'] == 'John Doe'
        assert filtered['peoplecode'] == 'EMP001'
        assert filtered['email'] is None
        assert filtered['mobno'] is None
        assert filtered['isadmin'] is None
        assert filtered['is_staff'] is None

    def test_permission_caching(self):
        """Test that permissions are cached for performance."""
        checker = FieldPermissionChecker(self.regular_user)

        assert 'can_view_people_details' not in checker._permission_cache

        first_check = checker.can_access_field('People', 'mobno')

        assert first_check is False

        self.regular_user.capabilities = {'can_view_people_details': True}
        self.regular_user.save()

        second_check = checker.can_access_field('People', 'mobno')

        assert second_check is False


@pytest.mark.django_db
class TestFieldPermissionDecorators(TestCase):
    """Test field permission decorators."""

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
            isadmin=False,
            enable=True,
            capabilities={}
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

    def test_require_field_permission_decorator_blocks_unauthorized(self):
        """Test require_field_permission decorator blocks unauthorized access."""
        from unittest.mock import Mock

        @require_field_permission('People', 'mobno')
        def resolve_mobno(parent, info):
            return parent.mobno

        request = Mock()
        request.user = self.user

        info = Mock()
        info.context = request

        parent = Mock()
        parent.mobno = '1234567890'

        result = resolve_mobno(parent, info)
        assert result is None

    def test_require_field_permission_decorator_allows_with_capability(self):
        """Test require_field_permission allows access with capability."""
        from unittest.mock import Mock

        self.user.capabilities = {'can_view_people_details': True}
        self.user.save()

        @require_field_permission('People', 'mobno')
        def resolve_mobno(parent, info):
            return parent.mobno

        request = Mock()
        request.user = self.user

        info = Mock()
        info.context = request

        parent = Mock()
        parent.mobno = '1234567890'

        result = resolve_mobno(parent, info)
        assert result == '1234567890'

    def test_filter_fields_by_permission_decorator(self):
        """Test filter_fields_by_permission decorator filters response."""
        from unittest.mock import Mock

        @filter_fields_by_permission('People')
        def resolve_people(parent, info):
            return {
                'peoplename': 'John Doe',
                'email': 'john@example.com',
                'mobno': '1234567890',
                'isadmin': True
            }

        request = Mock()
        request.user = self.user

        info = Mock()
        info.context = request

        result = resolve_people(None, info)

        assert result['peoplename'] == 'John Doe'
        assert result['email'] is None
        assert result['mobno'] is None
        assert result['isadmin'] is None


@pytest.mark.django_db
class TestJournalEntryFieldPermissions(TestCase):
    """Test field permissions for sensitive wellness data in JournalEntry."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            id=1,
            bucode="CLIENT001",
            buname="Test Client",
            enable=True
        )

        self.regular_user = People.objects.create_user(
            loginid="regularuser",
            password="TestPassword123!",
            email="regular@example.com",
            peoplename="Regular User",
            client=self.client,
            bu=self.client,
            isadmin=False,
            enable=True,
            capabilities={}
        )

        self.wellness_admin = People.objects.create_user(
            loginid="wellnessadmin",
            password="AdminPass123!",
            email="wellness@example.com",
            peoplename="Wellness Admin",
            client=self.client,
            bu=self.client,
            isadmin=False,
            enable=True,
            capabilities={'can_view_wellbeing_data': True}
        )

    def test_wellbeing_fields_require_capability(self):
        """Test wellbeing fields require specific capability."""
        checker_regular = FieldPermissionChecker(self.regular_user)
        checker_wellness = FieldPermissionChecker(self.wellness_admin)

        wellbeing_fields = ['mood_rating', 'stress_level', 'energy_level', 'stress_triggers']

        for field in wellbeing_fields:
            assert checker_regular.can_access_field('JournalEntry', field) is False
            assert checker_wellness.can_access_field('JournalEntry', field) is True


@pytest.mark.django_db
class TestFieldPermissionLogging(TestCase):
    """Test field permission access logging and monitoring."""

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
            isadmin=False,
            enable=True
        )

    def test_field_access_denial_is_logged(self):
        """Test that field access denials are logged."""
        checker = FieldPermissionChecker(self.user)

        with self.assertLogs('security', level='WARNING') as cm:
            result = checker.can_access_field('People', 'isadmin')

            assert result is False
            assert any('Field access denied' in log for log in cm.output)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])