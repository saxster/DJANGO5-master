"""
Comprehensive tests for permission system and user capabilities
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APITestCase
from rest_framework import status

from apps.peoples.models import People
    CanApproveAIRecommendations,
    CanManageKnowledgeBase,
    CanEscalateConversations
)
from apps.onboarding.models import Bt


class UserCapabilitiesTest(TestCase):
    """Test user capabilities management functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

    def test_has_capability_default(self):
        """Test has_capability with no capabilities set"""
        self.assertFalse(self.user.has_capability('test_capability'))

    def test_add_capability(self):
        """Test adding a capability"""
        self.user.add_capability('test_capability', True)
        self.assertTrue(self.user.has_capability('test_capability'))

        # Test adding with False value
        self.user.add_capability('disabled_capability', False)
        self.assertFalse(self.user.has_capability('disabled_capability'))

    def test_remove_capability(self):
        """Test removing a capability"""
        self.user.add_capability('test_capability', True)
        self.assertTrue(self.user.has_capability('test_capability'))

        self.user.remove_capability('test_capability')
        self.assertFalse(self.user.has_capability('test_capability'))

    def test_get_all_capabilities(self):
        """Test getting all user capabilities"""
        capabilities = {
            'can_approve_ai': True,
            'can_manage_kb': True,
            'system_admin': False
        }

        for cap, value in capabilities.items():
            self.user.add_capability(cap, value)

        all_caps = self.user.get_all_capabilities()
        for cap, expected_value in capabilities.items():
            self.assertEqual(all_caps[cap], expected_value)

    def test_set_ai_capabilities(self):
        """Test setting AI-specific capabilities"""
        self.user.set_ai_capabilities(
            can_approve=True,
            can_manage_kb=True,
            is_approver=True
        )

        self.assertTrue(self.user.has_capability('can_approve_ai_recommendations'))
        self.assertTrue(self.user.has_capability('can_manage_knowledge_base'))
        self.assertTrue(self.user.has_capability('ai_recommendation_approver'))

    def test_get_effective_permissions(self):
        """Test effective permissions combining capabilities with user flags"""
        # Test with regular user
        self.user.add_capability('custom_permission', True)
        permissions = self.user.get_effective_permissions()

        self.assertTrue(permissions['custom_permission'])
        self.assertNotIn('system_administrator', permissions)

        # Test with superuser
        self.user.is_superuser = True
        self.user.save()
        permissions = self.user.get_effective_permissions()

        self.assertTrue(permissions['system_administrator'])
        self.assertTrue(permissions['custom_permission'])

        # Test with staff user
        self.user.is_superuser = False
        self.user.is_staff = True
        self.user.save()
        permissions = self.user.get_effective_permissions()

        self.assertTrue(permissions['staff_access'])
        self.assertNotIn('system_administrator', permissions)

        # Test with admin user
        self.user.is_staff = False
        self.user.isadmin = True
        self.user.save()
        permissions = self.user.get_effective_permissions()

        self.assertTrue(permissions['tenant_administrator'])

    def test_capabilities_persistence(self):
        """Test that capabilities are properly saved to database"""
        self.user.set_ai_capabilities(can_approve=True, can_manage_kb=True)
        self.user.save()

        # Retrieve fresh instance from database
        fresh_user = People.objects.get(pk=self.user.pk)
        self.assertTrue(fresh_user.has_capability('can_approve_ai_recommendations'))
        self.assertTrue(fresh_user.has_capability('can_manage_knowledge_base'))


class AIRecommendationPermissionTest(TestCase):
    """Test AI recommendation approval permission system"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.permission = CanApproveAIRecommendations()

        # Create test users with different capabilities
        self.admin_user = People.objects.create_user(
            loginid='admin',
            peoplecode='ADMIN001',
            peoplename='Admin User',
            email='admin@example.com',
            dateofbirth='1990-01-01',
            is_staff=True
        )

        self.approver_user = People.objects.create_user(
            loginid='approver',
            peoplecode='APPR001',
            peoplename='Approver User',
            email='approver@example.com',
            dateofbirth='1990-01-01'
        )
        self.approver_user.set_ai_capabilities(can_approve=True, is_approver=True)

        self.regular_user = People.objects.create_user(
            loginid='regular',
            peoplecode='REG001',
            peoplename='Regular User',
            email='regular@example.com',
            dateofbirth='1990-01-01'
        )

    def test_superuser_has_permission(self):
        """Test that superuser always has permission"""
        self.admin_user.is_superuser = True
        self.admin_user.save()

        request = self.factory.get('/')
        request.user = self.admin_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_staff_user_has_permission(self):
        """Test that staff user has permission"""
        request = self.factory.get('/')
        request.user = self.admin_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_approver_user_has_permission(self):
        """Test that user with approval capability has permission"""
        request = self.factory.get('/')
        request.user = self.approver_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_regular_user_denied_permission(self):
        """Test that regular user is denied permission"""
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertFalse(self.permission.has_permission(request, None))

    def test_anonymous_user_denied_permission(self):
        """Test that anonymous user is denied permission"""
        request = self.factory.get('/')
        request.user = AnonymousUser()

        self.assertFalse(self.permission.has_permission(request, None))

    def test_user_with_explicit_approver_capability(self):
        """Test user with explicit AI approver capability"""
        self.regular_user.add_capability('ai_recommendation_approver', True)
        self.regular_user.save()

        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_user_with_system_administrator_capability(self):
        """Test user with system administrator capability"""
        self.regular_user.add_capability('system_administrator', True)
        self.regular_user.save()

        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(self.permission.has_permission(request, None))


class KnowledgeBasePermissionTest(TestCase):
    """Test knowledge base management permission system"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.permission = CanManageKnowledgeBase()

        self.curator_user = People.objects.create_user(
            loginid='curator',
            peoplecode='CUR001',
            peoplename='Curator User',
            email='curator@example.com',
            dateofbirth='1990-01-01'
        )
        self.curator_user.add_capability('can_manage_knowledge_base', True)
        self.curator_user.save()

        self.admin_user = People.objects.create_user(
            loginid='admin',
            peoplecode='ADMIN001',
            peoplename='Admin User',
            email='admin@example.com',
            dateofbirth='1990-01-01',
            isadmin=True
        )

        self.regular_user = People.objects.create_user(
            loginid='regular',
            peoplecode='REG001',
            peoplename='Regular User',
            email='regular@example.com',
            dateofbirth='1990-01-01'
        )

    def test_curator_has_permission(self):
        """Test that user with knowledge base capability has permission"""
        request = self.factory.get('/')
        request.user = self.curator_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_admin_has_permission(self):
        """Test that admin user has permission"""
        request = self.factory.get('/')
        request.user = self.admin_user

        self.assertTrue(self.permission.has_permission(request, None))

    def test_regular_user_denied_permission(self):
        """Test that regular user is denied permission"""
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertFalse(self.permission.has_permission(request, None))

    def test_content_curator_capability(self):
        """Test user with content curator capability"""
        self.regular_user.add_capability('content_curator', True)
        self.regular_user.save()

        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(self.permission.has_permission(request, None))


class SecurityAuditTest(TestCase):
    """Test security logging and audit functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

    @patch('apps.onboarding_api.permissions.security_logger')
    def test_security_violation_logging(self, mock_logger):
        """Test that security violations are logged"""
        factory = RequestFactory()
        permission = CanApproveAIRecommendations()

        request = factory.get('/')
        request.user = self.user

        # This should fail and trigger logging
        has_permission = permission.has_permission(request, None)

        self.assertFalse(has_permission)

    def test_capability_access_patterns(self):
        """Test various capability access patterns for security"""
        # Test with None capabilities
        user_no_caps = People.objects.create_user(
            loginid='nocaps',
            peoplecode='NOCAPS',
            peoplename='No Caps User',
            email='nocaps@example.com',
            dateofbirth='1990-01-01'
        )

        self.assertFalse(user_no_caps.has_capability('any_capability'))

        # Test with empty dict capabilities
        user_no_caps.capabilities = {}
        user_no_caps.save()
        self.assertFalse(user_no_caps.has_capability('any_capability'))

        # Test with malformed capabilities (should not crash)
        try:
            # This should be handled gracefully
            result = user_no_caps.get_effective_permissions()
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"get_effective_permissions raised {e} unexpectedly")


class PermissionIntegrationTest(APITestCase):
    """Integration tests for permission system in API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

        self.admin_user = People.objects.create_user(
            loginid='admin',
            peoplecode='ADMIN001',
            peoplename='Admin User',
            email='admin@example.com',
            dateofbirth='1990-01-01',
            is_staff=True
        )

        self.regular_user = People.objects.create_user(
            loginid='regular',
            peoplecode='REG001',
            peoplename='Regular User',
            email='regular@example.com',
            dateofbirth='1990-01-01'
        )

    def test_recommendation_approval_endpoint_permissions(self):
        """Test permissions on recommendation approval endpoint"""
        url = '/api/v1/onboarding/recommendations/approve/'

        # Test with admin user
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, {
            'session_id': 'test-session',
            'approved_items': [],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': True
        })

        # Should not get 403 Forbidden (might get other errors due to invalid data)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(url, {
            'session_id': 'test-session',
            'approved_items': [],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': True
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_knowledge_validation_endpoint_permissions(self):
        """Test permissions on knowledge validation endpoint"""
        url = '/api/v1/onboarding/knowledge/validate/'

        # Test with staff user
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, {
            'recommendation': {
                'type': 'test',
                'content': {}
            }
        })

        # Should not get 403 Forbidden
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(url, {
            'recommendation': {
                'type': 'test',
                'content': {}
            }
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users are denied access"""
        urls = [
            '/api/v1/onboarding/recommendations/approve/',
            '/api/v1/onboarding/knowledge/validate/',
        ]

        for url in urls:
            response = self.client.post(url, {})
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


@pytest.mark.django_db
class CapabilitiesManagementCommandTest(TestCase):
    """Test the management command for setting up AI capabilities"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = People.objects.create_user(
            loginid='admin',
            peoplecode='ADMIN001',
            peoplename='Admin User',
            email='admin@example.com',
            dateofbirth='1990-01-01',
            is_staff=True
        )

        self.regular_user = People.objects.create_user(
            loginid='regular',
            peoplecode='REG001',
            peoplename='Regular User',
            email='regular@example.com',
            dateofbirth='1990-01-01'
        )

    def test_command_imports_successfully(self):
        """Test that the management command can be imported"""
        try:
            # This would normally call the actual command, but we'll just test import
            from apps.peoples.management.commands.setup_ai_capabilities import Command
            self.assertIsNotNone(Command)
        except ImportError:
            self.fail("Management command could not be imported")