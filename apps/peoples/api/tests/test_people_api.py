"""
People Management API Tests

Tests for CRUD operations, permissions, and filtering.

Compliance with .claude/rules.md:
- Comprehensive test coverage
- Specific assertions
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.peoples.models import People


@pytest.mark.django_db
class TestPeopleViewSet:
    """Test cases for PeopleViewSet."""

    def setup_method(self):
        """Set up test client and users."""
        self.client = APIClient()

        # Create admin user
        self.admin_user = People.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='Admin123!',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            client_id=1,
            bu_id=1
        )

        # Create regular user
        self.regular_user = People.objects.create_user(
            username='user@example.com',
            email='user@example.com',
            password='User123!',
            first_name='Regular',
            last_name='User',
            is_active=True,
            client_id=1,
            bu_id=1
        )

        self.list_url = reverse('api_v1:people:people-list')

    def test_list_people_authenticated(self):
        """Test listing people requires authentication."""
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_people_success(self):
        """Test listing people with authentication."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.list_url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_create_user_success(self):
        """Test creating new user."""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            'username': 'newuser@example.com',
            'email': 'newuser@example.com',
            'password': 'NewUser123!',
            'password_confirm': 'NewUser123!',
            'first_name': 'New',
            'last_name': 'User',
            'bu_id': 1,
            'client_id': 1
        }

        response = self.client.post(self.list_url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert People.objects.filter(username='newuser@example.com').exists()

    def test_create_user_mismatched_passwords(self):
        """Test creating user with mismatched passwords fails."""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            'username': 'newuser@example.com',
            'email': 'newuser@example.com',
            'password': 'NewUser123!',
            'password_confirm': 'DifferentPassword!',
            'first_name': 'New',
            'last_name': 'User'
        }

        response = self.client.post(self.list_url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_user_detail(self):
        """Test retrieving specific user."""
        self.client.force_authenticate(user=self.regular_user)

        url = reverse('api_v1:people:people-detail', kwargs={'pk': self.regular_user.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'user@example.com'

    def test_update_user_partial(self):
        """Test partial update of user."""
        self.client.force_authenticate(user=self.regular_user)

        url = reverse('api_v1:people:people-detail', kwargs={'pk': self.regular_user.pk})
        data = {'first_name': 'Updated'}

        response = self.client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK

        self.regular_user.refresh_from_db()
        assert self.regular_user.first_name == 'Updated'

    def test_soft_delete_user(self):
        """Test soft deletion sets is_active=False."""
        self.client.force_authenticate(user=self.admin_user)

        # Create user to delete
        user_to_delete = People.objects.create_user(
            username='delete@example.com',
            email='delete@example.com',
            password='Delete123!',
            is_active=True,
            client_id=1
        )

        url = reverse('api_v1:people:people-detail', kwargs={'pk': user_to_delete.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        user_to_delete.refresh_from_db()
        assert user_to_delete.is_active is False


@pytest.mark.django_db
class TestPeoplePermissions:
    """Test permission and access control."""

    def setup_method(self):
        """Set up test users with different tenants."""
        self.client = APIClient()

        # User from tenant 1
        self.user_tenant1 = People.objects.create_user(
            username='tenant1@example.com',
            password='Tenant123!',
            client_id=1,
            bu_id=1
        )

        # User from tenant 2
        self.user_tenant2 = People.objects.create_user(
            username='tenant2@example.com',
            password='Tenant123!',
            client_id=2,
            bu_id=2
        )

    def test_tenant_isolation_list(self):
        """Test users only see their tenant's data."""
        self.client.force_authenticate(user=self.user_tenant1)

        url = reverse('api_v1:people:people-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Should only see users from client_id=1
        for user in response.data['results']:
            assert user['client_id'] == 1


__all__ = [
    'TestPeopleViewSet',
    'TestPeoplePermissions',
]
