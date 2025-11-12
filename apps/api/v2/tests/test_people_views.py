"""
Test V2 People API Endpoints

Tests for user management with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- Search and filtering
- Pagination

Following TDD: Tests written BEFORE implementation.
"""

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

People = get_user_model()


@pytest.mark.django_db
class TestPeopleListView:
    """Test GET /api/v2/people/users/ endpoint."""

    def test_authenticated_user_can_list_users(self):
        """
        Test that authenticated user can list users in their tenant.

        V2 Response format:
        {
            "success": true,
            "data": {
                "results": [
                    {
                        "id": 1,
                        "username": "user1@example.com",
                        "email": "user1@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": true
                    }
                ],
                "count": 10,
                "next": "cursor-string",
                "previous": null
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create test users in same tenant
        user1 = People.objects.create_user(
            username='user1@example.com',
            email='user1@example.com',
            password='password123',
            first_name='John',
            last_name='Doe'
        )
        user2 = People.objects.create_user(
            username='user2@example.com',
            email='user2@example.com',
            password='password123',
            first_name='Jane',
            last_name='Smith'
        )

        # Login as user1
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'user1@example.com',
            'password': 'password123'
        }, format='json')

        access_token = login_response.data['data']['access']

        # Act: List users
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-list')
        response = client.get(url, format='json')

        # Assert: Verify response structure
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
        assert 'meta' in response.data

        # Data contains pagination
        data = response.data['data']
        assert 'results' in data
        assert 'count' in data
        assert isinstance(data['results'], list)
        assert data['count'] >= 2  # At least our 2 test users

        # Each user has required fields
        user_result = data['results'][0]
        assert 'id' in user_result
        assert 'username' in user_result
        assert 'email' in user_result
        assert 'first_name' in user_result
        assert 'last_name' in user_result
        assert 'is_active' in user_result

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']
        assert 'timestamp' in response.data['meta']

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated request returns 401."""
        client = APIClient()
        url = reverse('api_v2:people-users-list')

        # Act: Request without authentication
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_filters_users_by_name(self):
        """Test that search query filters users by name."""
        # Arrange: Create users
        user1 = People.objects.create_user(
            username='admin@example.com',
            password='password123',
            first_name='Alice',
            last_name='Anderson'
        )
        user2 = People.objects.create_user(
            username='user@example.com',
            password='password123',
            first_name='Bob',
            last_name='Brown'
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'admin@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Search for "Alice"
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-list')
        response = client.get(url, {'search': 'Alice'}, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        results = response.data['data']['results']

        # Should find Alice
        usernames = [u['username'] for u in results]
        assert 'admin@example.com' in usernames

    def test_pagination_returns_correct_structure(self):
        """Test that pagination metadata is included."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Get first page
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-list')
        response = client.get(url, {'limit': 10}, format='json')

        # Assert: Pagination fields present
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'count' in data
        assert 'next' in data
        assert 'previous' in data
        assert 'results' in data


@pytest.mark.django_db
class TestPeopleUserDetailView:
    """Test GET /api/v2/people/users/{id}/ endpoint."""

    def test_authenticated_user_can_view_user_detail(self):
        """
        Test that authenticated user can view user details.

        V2 Response format:
        {
            "success": true,
            "data": {
                "id": 1,
                "username": "user@example.com",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": true,
                "date_joined": "2025-11-07T...",
                "last_login": "2025-11-07T..."
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create users
        user1 = People.objects.create_user(
            username='admin@example.com',
            password='password123',
            first_name='Admin',
            last_name='User'
        )
        user2 = People.objects.create_user(
            username='target@example.com',
            password='password123',
            first_name='Target',
            last_name='User'
        )

        # Login as user1
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'admin@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Get user2 details
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-detail', kwargs={'user_id': user2.id})
        response = client.get(url, format='json')

        # Assert: Verify response structure
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
        assert 'meta' in response.data

        # User data contains all fields
        data = response.data['data']
        assert data['id'] == user2.id
        assert data['username'] == 'target@example.com'
        assert data['email'] == 'target@example.com'
        assert data['first_name'] == 'Target'
        assert data['last_name'] == 'User'
        assert data['is_active'] is True
        assert 'date_joined' in data
        assert 'last_login' in data

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']

    def test_user_not_found_returns_404(self):
        """Test that non-existent user returns 404."""
        # Arrange: Create and login
        user = People.objects.create_user(
            username='admin@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'admin@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Request non-existent user
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-detail', kwargs={'user_id': 99999})
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'USER_NOT_FOUND'

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated request returns 401."""
        # Arrange: Create user
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        # Act: Request without authentication
        client = APIClient()
        url = reverse('api_v2:people-users-detail', kwargs={'user_id': user.id})
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPeopleUserUpdateView:
    """Test PATCH /api/v2/people/users/{id}/ endpoint."""

    def test_authenticated_user_can_update_profile(self):
        """
        Test that user can update their own profile.

        V2 Response format:
        {
            "success": true,
            "data": {
                "id": 1,
                "username": "user@example.com",
                "first_name": "Updated",
                "last_name": "Name",
                ...
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user
        user = People.objects.create_user(
            username='test@example.com',
            password='password123',
            first_name='Original',
            last_name='Name'
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Update own profile
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-update', kwargs={'user_id': user.id})
        response = client.patch(url, {
            'first_name': 'Updated',
            'last_name': 'Name'
        }, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data

        # Updated fields reflected
        data = response.data['data']
        assert data['first_name'] == 'Updated'
        assert data['last_name'] == 'Name'
        assert data['id'] == user.id

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']

        # Verify database was updated
        user.refresh_from_db()
        assert user.first_name == 'Updated'
        assert user.last_name == 'Name'

    def test_user_cannot_update_another_user_profile(self):
        """Test that regular user cannot update another user's profile."""
        # Arrange: Create two users
        user1 = People.objects.create_user(
            username='user1@example.com',
            password='password123'
        )
        user2 = People.objects.create_user(
            username='user2@example.com',
            password='password123',
            first_name='Original'
        )

        # Login as user1
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'user1@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Attempt to update user2
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-update', kwargs={'user_id': user2.id})
        response = client.patch(url, {
            'first_name': 'Hacked'
        }, format='json')

        # Assert: Should be forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'PERMISSION_DENIED'

        # Verify database was NOT updated
        user2.refresh_from_db()
        assert user2.first_name == 'Original'

    def test_update_with_invalid_data_returns_400(self):
        """Test that invalid data returns 400."""
        # Arrange: Create user
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Update with invalid email
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-users-update', kwargs={'user_id': user.id})
        response = client.patch(url, {
            'email': 'invalid-email-format'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'


@pytest.mark.django_db
class TestPeopleSearchView:
    """Test GET /api/v2/people/search/ endpoint."""

    def test_search_returns_matching_users(self):
        """
        Test that search query returns matching users.

        V2 Response format: Same as list endpoint with search filtering
        """
        # Arrange: Create users with different names
        People.objects.create_user(
            username='alice@example.com',
            password='password123',
            first_name='Alice',
            last_name='Anderson'
        )
        People.objects.create_user(
            username='bob@example.com',
            password='password123',
            first_name='Bob',
            last_name='Brown'
        )
        People.objects.create_user(
            username='charlie@example.com',
            password='password123',
            first_name='Charlie',
            last_name='Chen'
        )

        # Login as Alice
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'alice@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Search for "Bob"
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-search')
        response = client.get(url, {'q': 'Bob'}, format='json')

        # Assert: Verify Bob is found
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        results = response.data['data']['results']
        assert len(results) >= 1

        # Bob should be in results
        usernames = [u['username'] for u in results]
        assert 'bob@example.com' in usernames

        # Alice and Charlie should NOT be in results
        assert 'alice@example.com' not in usernames
        assert 'charlie@example.com' not in usernames

    def test_search_with_empty_query_returns_all_users(self):
        """Test that empty search query returns all users."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Search with empty query
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:people-search')
        response = client.get(url, format='json')

        # Assert: Returns all users (at least test user)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert len(response.data['data']['results']) >= 1

    def test_search_unauthenticated_returns_401(self):
        """Test that unauthenticated search returns 401."""
        client = APIClient()
        url = reverse('api_v2:people-search')

        # Act: Search without authentication
        response = client.get(url, {'q': 'test'}, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
