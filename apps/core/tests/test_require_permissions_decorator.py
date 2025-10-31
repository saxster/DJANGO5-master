"""
Tests for require_permissions decorator

This module provides comprehensive tests for the @require_permissions decorator
including authentication checks, permission validation, and response handling.

Test Categories:
- Authentication validation
- Permission checking (single and multiple)
- Special permissions (is_staff, is_superuser)
- Response types (JSON, HTMX, standard)
- Security logging
- Edge cases

Compliance: CLAUDE.md Rule #8 (Test Coverage)
"""

import pytest
import json
from django.test import RequestFactory, TestCase
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from apps.peoples.models import People
from apps.core.decorators import require_permissions


class TestRequirePermissionsDecorator(TestCase):
    """Test suite for @require_permissions decorator"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()

        # Create test user with no special permissions
        self.regular_user = People.objects.create(
            loginid='testuser',
            peoplename='Test User',
            email='test@example.com',
            is_staff=False,
            is_superuser=False
        )
        self.regular_user.set_password('testpass123')
        self.regular_user.save()

        # Create staff user
        self.staff_user = People.objects.create(
            loginid='staffuser',
            peoplename='Staff User',
            email='staff@example.com',
            is_staff=True,
            is_superuser=False
        )
        self.staff_user.set_password('staffpass123')
        self.staff_user.save()

        # Create superuser
        self.super_user = People.objects.create(
            loginid='superuser',
            peoplename='Super User',
            email='super@example.com',
            is_staff=True,
            is_superuser=True
        )
        self.super_user.set_password('superpass123')
        self.super_user.save()

    def test_unauthenticated_json_request(self):
        """Test that unauthenticated JSON requests get 401 response"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = AnonymousUser()

        response = protected_view(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data['code'], 'AUTHENTICATION_REQUIRED')

    def test_unauthenticated_htmx_request(self):
        """Test that unauthenticated HTMX requests get appropriate response"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return HttpResponse('Success')

        request = self.factory.post('/test/')
        request.user = AnonymousUser()
        request.META['HTTP_HX_REQUEST'] = 'true'

        response = protected_view(request)

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', response.content.decode())

    def test_unauthenticated_standard_request(self):
        """Test that unauthenticated standard requests raise PermissionDenied"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return HttpResponse('Success')

        request = self.factory.post('/test/')
        request.user = AnonymousUser()

        with self.assertRaises(PermissionDenied):
            protected_view(request)

    def test_authenticated_with_permission(self):
        """Test that users with required permissions can access view"""
        # Add specific permission to user
        content_type = ContentType.objects.get_for_model(People)
        permission = Permission.objects.create(
            codename='test_permission',
            name='Can Test',
            content_type=content_type
        )
        self.regular_user.user_permissions.add(permission)

        @require_permissions('peoples.test_permission')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_authenticated_without_permission_json(self):
        """Test that users without permission get 403 JSON response"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['code'], 'PERMISSION_DENIED')
        self.assertIn('activity.add_job', data['required_permissions'])

    def test_authenticated_without_permission_htmx(self):
        """Test that HTMX requests without permission get appropriate response"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return HttpResponse('Success')

        request = self.factory.post('/test/')
        request.user = self.regular_user
        request.META['HTTP_HX_REQUEST'] = 'true'

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('Permission denied', response.content.decode())

    def test_authenticated_without_permission_standard(self):
        """Test that standard requests without permission raise PermissionDenied"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return HttpResponse('Success')

        request = self.factory.post('/test/')
        request.user = self.regular_user

        with self.assertRaises(PermissionDenied) as cm:
            protected_view(request)

        self.assertIn('activity.add_job', str(cm.exception))

    def test_multiple_permissions_all_granted(self):
        """Test that users with ALL required permissions can access view"""
        # Add multiple permissions
        content_type = ContentType.objects.get_for_model(People)
        perm1 = Permission.objects.create(
            codename='test_perm1',
            name='Can Test 1',
            content_type=content_type
        )
        perm2 = Permission.objects.create(
            codename='test_perm2',
            name='Can Test 2',
            content_type=content_type
        )
        self.regular_user.user_permissions.add(perm1, perm2)

        @require_permissions('peoples.test_perm1', 'peoples.test_perm2')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_multiple_permissions_partial(self):
        """Test that users with only SOME permissions get denied"""
        # Add only one of two required permissions
        content_type = ContentType.objects.get_for_model(People)
        perm1 = Permission.objects.create(
            codename='test_perm_a',
            name='Can Test A',
            content_type=content_type
        )
        self.regular_user.user_permissions.add(perm1)

        @require_permissions('peoples.test_perm_a', 'peoples.test_perm_b')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn('peoples.test_perm_b', data['required_permissions'])

    def test_is_staff_permission_granted(self):
        """Test that staff users pass is_staff permission check"""
        @require_permissions('is_staff')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.staff_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_is_staff_permission_denied(self):
        """Test that non-staff users fail is_staff permission check"""
        @require_permissions('is_staff')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)

    def test_is_superuser_permission_granted(self):
        """Test that superusers pass is_superuser permission check"""
        @require_permissions('is_superuser')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.super_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_is_superuser_permission_denied(self):
        """Test that non-superusers fail is_superuser permission check"""
        @require_permissions('is_superuser')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.staff_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)

    def test_mixed_permissions(self):
        """Test combination of Django permissions and special permissions"""
        content_type = ContentType.objects.get_for_model(People)
        permission = Permission.objects.create(
            codename='mixed_test',
            name='Can Mixed Test',
            content_type=content_type
        )
        self.staff_user.user_permissions.add(permission)

        @require_permissions('is_staff', 'peoples.mixed_test')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.staff_user

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_preserves_function_metadata(self):
        """Test that decorator preserves wrapped function's metadata"""
        @require_permissions('activity.add_job')
        def my_special_view(request):
            """My special docstring"""
            return JsonResponse({'status': 'success'})

        self.assertEqual(my_special_view.__name__, 'my_special_view')
        self.assertEqual(my_special_view.__doc__, 'My special docstring')

    def test_ajax_request_detection(self):
        """Test that AJAX requests are properly detected"""
        @require_permissions('activity.add_job')
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post('/test/')
        request.user = self.regular_user
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')


    def test_no_permissions_required(self):
        """Test decorator with no permissions specified (should allow all authenticated)"""
        @require_permissions()
        def protected_view(request):
            return JsonResponse({'status': 'success'})

        request = self.factory.post(
            '/test/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        request.user = self.regular_user

        response = protected_view(request)

        # Should allow access since user is authenticated and no permissions required
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        """Clean up test data"""
        People.objects.all().delete()
        Permission.objects.filter(codename__startswith='test_').delete()
