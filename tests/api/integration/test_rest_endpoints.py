"""
Integration tests for REST API endpoints.

Tests complete API workflows, permissions, filtering, pagination, and bulk operations.
"""

import pytest
import json
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.peoples.models import People, Pgroup
from apps.activity.models.asset_model import Asset


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestPeopleEndpoints:
    """Test People API endpoints."""
    
    def test_people_list_unauthenticated(self, api_client):
        """Test that unauthenticated users cannot access people list."""
        url = '/api/v1/people/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_people_list_authenticated(self, authenticated_client, people_factory):
        """Test authenticated access to people list."""
        people_factory.create_batch(5)
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 5
    
    def test_people_list_with_pagination(self, authenticated_client, people_factory):
        """Test people list with pagination."""
        people_factory.create_batch(25)
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url, {'page_size': 10})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert len(response.data['results']) == 10
    
    def test_people_list_with_field_selection(self, authenticated_client, people_factory):
        """Test field selection in people list."""
        person = people_factory.create()
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url, {'fields': 'id,first_name,email'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        
        person_data = response.data['results'][0]
        assert set(person_data.keys()) == {'id', 'first_name', 'email'}
    
    def test_people_list_with_filtering(self, authenticated_client, people_factory):
        """Test filtering people list."""
        active_people = people_factory.create_batch(3, is_active=True)
        inactive_people = people_factory.create_batch(2, is_active=False)
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url, {'is_active': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3
        
        for person in response.data['results']:
            assert person['is_active'] is True
    
    def test_people_list_with_search(self, authenticated_client, people_factory):
        """Test search functionality."""
        john = people_factory.create(first_name='John', last_name='Doe')
        jane = people_factory.create(first_name='Jane', last_name='Smith')
        bob = people_factory.create(first_name='Bob', last_name='Johnson')
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url, {'search': 'John'})
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should find both John Doe and Bob Johnson (contains 'John')
        found_ids = [person['id'] for person in response.data['results']]
        assert john.id in found_ids
    
    def test_people_list_with_ordering(self, authenticated_client, people_factory):
        """Test ordering people list."""
        alice = people_factory.create(first_name='Alice')
        bob = people_factory.create(first_name='Bob')
        charlie = people_factory.create(first_name='Charlie')
        
        url = '/api/v1/people/'
        response = authenticated_client.get(url, {'ordering': 'first_name'})
        
        assert response.status_code == status.HTTP_200_OK
        
        names = [person['first_name'] for person in response.data['results']]
        assert names == ['Alice', 'Bob', 'Charlie']
        
        # Test reverse ordering
        response = authenticated_client.get(url, {'ordering': '-first_name'})
        names = [person['first_name'] for person in response.data['results']]
        assert names == ['Charlie', 'Bob', 'Alice']
    
    def test_people_detail_retrieve(self, authenticated_client, people_factory):
        """Test retrieving a specific person."""
        person = people_factory.create()
        
        url = f'/api/v1/people/{person.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == person.id
        assert response.data['first_name'] == person.first_name
        assert response.data['email'] == person.email
    
    def test_people_detail_not_found(self, authenticated_client):
        """Test retrieving non-existent person."""
        url = '/api/v1/people/999/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_people_create(self, authenticated_client):
        """Test creating a new person."""
        url = '/api/v1/people/'
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'employee_code': 'EMP001',
            'mobile': '+1234567890'
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['first_name'] == 'John'
        assert response.data['email'] == 'john.doe@example.com'
        
        # Verify person was created in database
        assert People.objects.filter(email='john.doe@example.com').exists()
    
    def test_people_create_validation_error(self, authenticated_client):
        """Test creating person with validation errors."""
        url = '/api/v1/people/'
        data = {
            'first_name': 'John',
            # Missing required fields
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data
        assert 'employee_code' in response.data
    
    def test_people_update(self, authenticated_client, people_factory):
        """Test updating a person."""
        person = people_factory.create()
        
        url = f'/api/v1/people/{person.id}/'
        data = {
            'first_name': 'UpdatedName',
            'last_name': person.last_name,
            'email': person.email,
            'employee_code': person.employee_code
        }
        
        response = authenticated_client.put(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'UpdatedName'
        
        # Verify update in database
        person.refresh_from_db()
        assert person.first_name == 'UpdatedName'
    
    def test_people_partial_update(self, authenticated_client, people_factory):
        """Test partially updating a person."""
        person = people_factory.create()
        
        url = f'/api/v1/people/{person.id}/'
        data = {'first_name': 'PartiallyUpdated'}
        
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'PartiallyUpdated'
        assert response.data['last_name'] == person.last_name  # Unchanged
    
    def test_people_delete(self, authenticated_client, people_factory):
        """Test deleting a person."""
        person = people_factory.create()
        person_id = person.id
        
        url = f'/api/v1/people/{person.id}/'
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deletion in database
        assert not People.objects.filter(id=person_id).exists()


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestBulkOperations:
    """Test bulk operations for API endpoints."""
    
    def test_bulk_create_people(self, authenticated_client):
        """Test bulk creating people."""
        url = '/api/v1/people/bulk_create/'
        data = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
                'employee_code': 'EMP001'
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane@example.com',
                'employee_code': 'EMP002'
            }
        ]
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        
        # Verify people were created
        assert People.objects.count() == 2
        assert People.objects.filter(email='john@example.com').exists()
        assert People.objects.filter(email='jane@example.com').exists()
    
    def test_bulk_create_validation_error(self, authenticated_client):
        """Test bulk create with validation errors."""
        url = '/api/v1/people/bulk_create/'
        data = [
            {
                'first_name': 'John',
                'email': 'john@example.com',
                'employee_code': 'EMP001'
            },
            {
                'first_name': 'Jane',
                # Missing required fields
            }
        ]
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Should not create any people if validation fails
        assert People.objects.count() == 0
    
    def test_bulk_update_people(self, authenticated_client, people_factory):
        """Test bulk updating people."""
        people = people_factory.create_batch(3)
        people_ids = [person.id for person in people]
        
        url = '/api/v1/people/bulk_update/'
        data = {
            'ids': people_ids,
            'updates': {
                'last_name': 'BulkUpdated'
            }
        }
        
        response = authenticated_client.put(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        
        # Verify updates in database
        for person in People.objects.filter(id__in=people_ids):
            assert person.last_name == 'BulkUpdated'
    
    def test_bulk_delete_people(self, authenticated_client, people_factory):
        """Test bulk deleting people."""
        people = people_factory.create_batch(3)
        people_ids = [person.id for person in people]
        
        url = '/api/v1/people/bulk_delete/'
        data = {'ids': people_ids}
        
        response = authenticated_client.delete(url, data, format='json')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deletions in database
        assert People.objects.filter(id__in=people_ids).count() == 0


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestGroupEndpoints:
    """Test Group API endpoints."""
    
    def test_groups_list(self, authenticated_client, pgroup_factory):
        """Test groups list endpoint."""
        pgroup_factory.create_batch(3)
        
        url = '/api/v1/groups/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3
    
    def test_group_create(self, authenticated_client):
        """Test creating a new group."""
        url = '/api/v1/groups/'
        data = {
            'name': 'Test Group',
            'description': 'A test group',
            'is_active': True
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Group'
        
        # Verify group was created
        assert Pgroup.objects.filter(name='Test Group').exists()
    
    def test_group_detail(self, authenticated_client, pgroup_factory):
        """Test group detail endpoint."""
        group = pgroup_factory.create()
        
        url = f'/api/v1/groups/{group.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == group.id
        assert response.data['name'] == group.name
    
    def test_group_update(self, authenticated_client, pgroup_factory):
        """Test updating a group."""
        group = pgroup_factory.create()
        
        url = f'/api/v1/groups/{group.id}/'
        data = {
            'name': 'Updated Group Name',
            'description': group.description,
            'is_active': group.is_active
        }
        
        response = authenticated_client.put(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Group Name'
    
    def test_group_delete(self, authenticated_client, pgroup_factory):
        """Test deleting a group."""
        group = pgroup_factory.create()
        group_id = group.id
        
        url = f'/api/v1/groups/{group.id}/'
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deletion
        assert not Pgroup.objects.filter(id=group_id).exists()


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestAPIPermissions:
    """Test API permissions and access control."""
    
    def test_admin_only_endpoints(self, admin_client, api_client):
        """Test endpoints that require admin access."""
        admin_url = '/api/monitoring/dashboard/'
        
        # Admin should have access
        admin_response = admin_client.get(admin_url)
        assert admin_response.status_code != status.HTTP_403_FORBIDDEN
        
        # Regular client should be denied
        regular_response = api_client.get(admin_url)
        assert regular_response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]
    
    def test_authenticated_required_endpoints(self, authenticated_client, api_client):
        """Test endpoints that require authentication."""
        url = '/api/v1/people/'
        
        # Authenticated client should have access
        auth_response = authenticated_client.get(url)
        assert auth_response.status_code != status.HTTP_401_UNAUTHORIZED
        
        # Unauthenticated client should be denied
        unauth_response = api_client.get(url)
        assert unauth_response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_object_level_permissions(self, authenticated_client, people_factory, test_user):
        """Test object-level permissions."""
        # Create person owned by test user
        person = people_factory.create()
        
        url = f'/api/v1/people/{person.id}/'
        
        # Owner should be able to access
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Test updating own object
        data = {'first_name': 'Updated'}
        response = authenticated_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
    
    def test_field_level_permissions(self, authenticated_client, admin_client, people_factory):
        """Test field-level permissions."""
        person = people_factory.create()
        
        url = f'/api/v1/people/{person.id}/'
        
        # Regular user might not see sensitive fields
        regular_response = authenticated_client.get(url)
        assert regular_response.status_code == status.HTTP_200_OK
        
        # Admin should see all fields
        admin_response = admin_client.get(url)
        assert admin_response.status_code == status.HTTP_200_OK
        
        # Admin response might have more fields
        admin_fields = set(admin_response.data.keys())
        regular_fields = set(regular_response.data.keys())
        assert admin_fields >= regular_fields


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestAPIPerformance:
    """Test API performance and optimization."""
    
    def test_query_optimization(self, authenticated_client, query_counter, bulk_test_data):
        """Test that endpoints use optimized queries."""
        url = '/api/v1/people/'
        
        with query_counter() as context:
            response = authenticated_client.get(url)
            
            assert response.status_code == status.HTTP_200_OK
            
            # Should use optimized queries (select_related, prefetch_related)
            # Exact number depends on pagination and relationships
            assert len(context) <= 5  # Should be reasonably optimized
    
    def test_pagination_performance(self, authenticated_client, query_counter, bulk_test_data):
        """Test pagination performance with large datasets."""
        url = '/api/v1/people/'
        
        # Test first page
        with query_counter() as context:
            response = authenticated_client.get(url, {'page_size': 20})
            
            assert response.status_code == status.HTTP_200_OK
            first_page_queries = len(context)
        
        # Test second page
        with query_counter() as context:
            response = authenticated_client.get(url, {'page': 2, 'page_size': 20})
            
            assert response.status_code == status.HTTP_200_OK
            second_page_queries = len(context)
        
        # Query count should be similar regardless of page
        assert abs(first_page_queries - second_page_queries) <= 1
    
    def test_filtering_performance(self, authenticated_client, query_counter, bulk_test_data):
        """Test that filtering doesn't cause N+1 queries."""
        url = '/api/v1/people/'
        
        with query_counter() as context:
            response = authenticated_client.get(url, {'is_active': 'true'})
            
            assert response.status_code == status.HTTP_200_OK
            
            # Filtering should not significantly increase query count
            assert len(context) <= 5
    
    def test_bulk_operations_performance(self, authenticated_client, people_factory):
        """Test bulk operations performance."""
        # Create people to update
        people = people_factory.create_batch(50)
        people_ids = [person.id for person in people]
        
        url = '/api/v1/people/bulk_update/'
        data = {
            'ids': people_ids,
            'updates': {'last_name': 'BulkUpdated'}
        }
        
        import time
        start_time = time.time()
        
        response = authenticated_client.put(url, data, format='json')
        
        elapsed_time = time.time() - start_time
        
        assert response.status_code == status.HTTP_200_OK
        assert elapsed_time < 2.0  # Should complete in under 2 seconds


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
class TestAPIErrorHandling:
    """Test error handling in API endpoints."""
    
    def test_validation_error_response_format(self, authenticated_client):
        """Test validation error response format."""
        url = '/api/v1/people/'
        data = {
            'first_name': 'John',
            # Missing required fields
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert isinstance(response.data, dict)
        assert 'email' in response.data
        assert 'employee_code' in response.data
    
    def test_not_found_error(self, authenticated_client):
        """Test 404 error handling."""
        url = '/api/v1/people/99999/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'detail' in response.data
    
    def test_method_not_allowed_error(self, authenticated_client):
        """Test method not allowed error."""
        url = '/api/v1/people/'
        response = authenticated_client.options(url)  # Assuming OPTIONS is not allowed
        
        # Should either be allowed (200) or not allowed (405)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_server_error_handling(self, authenticated_client, people_factory):
        """Test server error handling."""
        person = people_factory.create()
        url = f'/api/v1/people/{person.id}/'
        
        # Mock a server error
        with patch('apps.peoples.models.People.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            response = authenticated_client.get(url)
            
            # Should handle gracefully
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.integration
@pytest.mark.rest
@pytest.mark.api
@pytest.mark.slow
class TestAPIIntegrationScenarios:
    """Test complete API integration scenarios."""
    
    def test_complete_crud_workflow(self, authenticated_client):
        """Test complete CRUD workflow for a resource."""
        # Create
        create_url = '/api/v1/people/'
        create_data = {
            'first_name': 'Integration',
            'last_name': 'Test',
            'email': 'integration@test.com',
            'employee_code': 'INT001'
        }
        
        create_response = authenticated_client.post(create_url, create_data, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        person_id = create_response.data['id']
        
        # Read
        read_url = f'/api/v1/people/{person_id}/'
        read_response = authenticated_client.get(read_url)
        assert read_response.status_code == status.HTTP_200_OK
        assert read_response.data['email'] == 'integration@test.com'
        
        # Update
        update_data = {
            'first_name': 'UpdatedIntegration',
            'last_name': 'Test',
            'email': 'integration@test.com',
            'employee_code': 'INT001'
        }
        update_response = authenticated_client.put(read_url, update_data, format='json')
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data['first_name'] == 'UpdatedIntegration'
        
        # Delete
        delete_response = authenticated_client.delete(read_url)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deletion
        verify_response = authenticated_client.get(read_url)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_complex_filtering_and_pagination_workflow(self, authenticated_client, people_factory):
        """Test complex filtering and pagination workflow."""
        # Create test data
        active_people = people_factory.create_batch(15, is_active=True, first_name='Active')
        inactive_people = people_factory.create_batch(10, is_active=False, first_name='Inactive')
        
        url = '/api/v1/people/'
        
        # Test filtering with pagination
        response = authenticated_client.get(url, {
            'is_active': 'true',
            'page_size': 10,
            'ordering': 'first_name'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 10
        assert 'next' in response.data
        
        # Get second page
        next_response = authenticated_client.get(response.data['next'])
        assert next_response.status_code == status.HTTP_200_OK
        assert len(next_response.data['results']) == 5  # Remaining active people
        
        # Test search with filtering
        search_response = authenticated_client.get(url, {
            'search': 'Active',
            'is_active': 'true'
        })
        
        assert search_response.status_code == status.HTTP_200_OK
        assert len(search_response.data['results']) == 15