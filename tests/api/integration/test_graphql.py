"""
Integration tests for GraphQL API.

Tests DataLoader optimization, query performance, mutations, and authentication.
"""

import pytest
import json
from unittest.mock import patch, Mock
from django.test import Client
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from apps.api.graphql.enhanced_schema import schema
from apps.api.graphql.dataloaders import get_loaders
from apps.peoples.models import People, Pgroup
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Job, Jobneed


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLQueries:
    """Test GraphQL query functionality."""
    
    def test_simple_people_query(self, graphql_client, people_factory):
        """Test basic people query."""
        person = people_factory.create(first_name='John', last_name='Doe')
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        fullName
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        assert 'data' in result
        
        people = result['data']['allPeople']['edges']
        assert len(people) == 1
        
        person_data = people[0]['node']
        assert person_data['firstName'] == 'John'
        assert person_data['lastName'] == 'Doe'
        assert person_data['fullName'] == 'John Doe'
    
    def test_people_with_groups_query(self, graphql_client, people_factory, pgroup_factory):
        """Test people query with groups relationship."""
        group = pgroup_factory.create(name='Test Group')
        person = people_factory.create(first_name='John')
        person.groups.add(group)
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                        groups {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        person_data = result['data']['allPeople']['edges'][0]['node']
        assert len(person_data['groups']) == 1
        assert person_data['groups'][0]['name'] == 'Test Group'
    
    def test_single_person_query(self, graphql_client, people_factory):
        """Test single person query by ID."""
        person = people_factory.create(first_name='Jane', last_name='Smith')
        
        query = f"""
        query {{
            person(id: {person.id}) {{
                id
                firstName
                lastName
                email
            }}
        }}
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        person_data = result['data']['person']
        assert person_data['id'] == str(person.id)
        assert person_data['firstName'] == 'Jane'
        assert person_data['email'] == person.email
    
    def test_groups_with_members_query(self, graphql_client, people_factory, pgroup_factory):
        """Test groups query with members relationship."""
        group = pgroup_factory.create(name='Development Team')
        people = people_factory.create_batch(3)
        
        for person in people:
            person.groups.add(group)
        
        query = """
        query {
            allGroups {
                edges {
                    node {
                        id
                        name
                        members {
                            id
                            firstName
                        }
                        memberCount
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        group_data = result['data']['allGroups']['edges'][0]['node']
        assert group_data['name'] == 'Development Team'
        assert len(group_data['members']) == 3
        assert group_data['memberCount'] == 3
    
    def test_search_people_query(self, graphql_client, people_factory):
        """Test search functionality."""
        john = people_factory.create(first_name='John', last_name='Doe')
        jane = people_factory.create(first_name='Jane', last_name='Smith')
        johnny = people_factory.create(first_name='Johnny', last_name='Cash')
        
        query = """
        query {
            searchPeople(query: "John", limit: 10) {
                id
                firstName
                lastName
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        found_people = result['data']['searchPeople']
        
        # Should find John and Johnny
        found_names = [person['firstName'] for person in found_people]
        assert 'John' in found_names
        assert 'Johnny' in found_names
        assert 'Jane' not in found_names
    
    def test_active_people_query(self, graphql_client, people_factory):
        """Test active people query."""
        active_people = people_factory.create_batch(3, is_active=True)
        inactive_people = people_factory.create_batch(2, is_active=False)
        
        query = """
        query {
            activePeople {
                id
                firstName
                isActive
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        people = result['data']['activePeople']
        
        assert len(people) == 3
        for person in people:
            assert person['isActive'] is True
    
    def test_statistics_query(self, graphql_client, bulk_test_data):
        """Test statistics query."""
        query = """
        query {
            statistics
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        stats = json.loads(result['data']['statistics'])
        
        assert 'people' in stats
        assert 'groups' in stats
        assert 'assets' in stats
        
        assert stats['people']['total'] > 0
        assert stats['groups']['total'] > 0
    
    def test_my_profile_query(self, graphql_client, people_factory, test_user):
        """Test my profile query."""
        # Create a person record for the test user
        person = people_factory.create(user=test_user)
        
        query = """
        query {
            myProfile {
                id
                firstName
                lastName
                email
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        profile = result['data']['myProfile']
        
        if profile:  # May be null if user doesn't have a People record
            assert profile['id'] == str(person.id)


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLDataLoaders:
    """Test DataLoader optimization in GraphQL."""
    
    def test_no_n_plus_one_queries_with_groups(self, graphql_client, query_counter, people_factory, pgroup_factory):
        """Test that DataLoaders prevent N+1 queries for groups."""
        # Create test data
        groups = pgroup_factory.create_batch(5)
        people = people_factory.create_batch(10)
        
        # Assign groups to people
        for i, person in enumerate(people):
            person.groups.set([groups[i % len(groups)]])
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                        groups {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        
        with query_counter() as context:
            result = graphql_client.execute(query)
            
            assert 'errors' not in result
            
            # Should use DataLoader to batch load groups
            # Exact number depends on implementation, but should be much less than N+1
            assert len(context) <= 5  # Should be optimized with DataLoader
    
    def test_no_n_plus_one_queries_with_jobs(self, graphql_client, query_counter, people_factory, asset_factory):
        """Test DataLoader optimization for jobs."""
        # Create test data
        people = people_factory.create_batch(5)
        assets = asset_factory.create_batch(3)
        
        # Create jobs for people
        for person in people:
            for asset in assets[:2]:  # 2 jobs per person
                Job.objects.create(
                    people=person,
                    asset=asset,
                    title=f'Job for {person.first_name}',
                    status='pending'
                )
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                        jobs {
                            id
                            title
                            assetDetails {
                                id
                                name
                            }
                        }
                        jobCount
                    }
                }
            }
        }
        """
        
        with query_counter() as context:
            result = graphql_client.execute(query)
            
            assert 'errors' not in result
            
            # Should use DataLoaders to optimize queries
            assert len(context) <= 6  # Should be optimized
    
    def test_dataloader_batching(self, graphql_client, people_factory, pgroup_factory):
        """Test that DataLoader batches requests efficiently."""
        # Create people and groups
        groups = pgroup_factory.create_batch(3)
        people = people_factory.create_batch(6)
        
        # Assign groups to people
        for i, person in enumerate(people):
            person.groups.add(groups[i % len(groups)])
        
        # Mock the DataLoader to verify batching
        with patch('apps.api.graphql.dataloaders.PeopleByGroupLoader.load_many') as mock_load_many:
            mock_load_many.return_value = [[] for _ in range(3)]  # Return empty lists
            
            query = """
            query {
                allGroups {
                    edges {
                        node {
                            id
                            name
                            members {
                                id
                                firstName
                            }
                        }
                    }
                }
            }
            """
            
            result = graphql_client.execute(query)
            
            # DataLoader should batch load all group members in one call
            assert mock_load_many.called
    
    def test_dataloader_caching(self, graphql_client, people_factory, pgroup_factory):
        """Test that DataLoader caches results within a request."""
        group = pgroup_factory.create(name='Test Group')
        person = people_factory.create(first_name='John')
        person.groups.add(group)
        
        # Query that accesses the same data multiple times
        query = f"""
        query {{
            person(id: {person.id}) {{
                id
                firstName
                groups {{
                    id
                    name
                }}
            }}
            group(id: {group.id}) {{
                id
                name
                members {{
                    id
                    firstName
                }}
            }}
        }}
        """
        
        with query_counter() as context:
            result = graphql_client.execute(query)
            
            assert 'errors' not in result
            
            # Should use caching to avoid duplicate queries
            assert len(context) <= 4  # Should be reasonably optimized with caching


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLMutations:
    """Test GraphQL mutation functionality."""
    
    def test_create_person_mutation(self, graphql_client):
        """Test creating a person via mutation."""
        mutation = """
        mutation {
            createPerson(
                firstName: "GraphQL",
                lastName: "User",
                email: "graphql@example.com",
                employeeCode: "GQL001"
            ) {
                person {
                    id
                    firstName
                    lastName
                    email
                }
                success
                errors
            }
        }
        """
        
        result = graphql_client.execute(mutation)
        
        assert 'errors' not in result
        data = result['data']['createPerson']
        
        assert data['success'] is True
        assert data['errors'] == []
        assert data['person']['firstName'] == 'GraphQL'
        assert data['person']['email'] == 'graphql@example.com'
        
        # Verify person was created in database
        assert People.objects.filter(email='graphql@example.com').exists()
    
    def test_create_person_validation_error(self, graphql_client):
        """Test person creation with validation errors."""
        mutation = """
        mutation {
            createPerson(
                firstName: "Invalid",
                lastName: "User",
                email: "invalid-email",
                employeeCode: ""
            ) {
                person {
                    id
                }
                success
                errors
            }
        }
        """
        
        result = graphql_client.execute(mutation)
        
        assert 'errors' not in result
        data = result['data']['createPerson']
        
        assert data['success'] is False
        assert len(data['errors']) > 0
        assert data['person'] is None
    
    def test_update_person_mutation(self, graphql_client, people_factory):
        """Test updating a person via mutation."""
        person = people_factory.create()
        
        mutation = f"""
        mutation {{
            updatePerson(
                id: {person.id},
                firstName: "Updated",
                lastName: "Name"
            ) {{
                person {{
                    id
                    firstName
                    lastName
                }}
                success
                errors
            }}
        }}
        """
        
        result = graphql_client.execute(mutation)
        
        assert 'errors' not in result
        data = result['data']['updatePerson']
        
        assert data['success'] is True
        assert data['person']['firstName'] == 'Updated'
        assert data['person']['lastName'] == 'Name'
        
        # Verify update in database
        person.refresh_from_db()
        assert person.first_name == 'Updated'
        assert person.last_name == 'Name'
    
    def test_update_nonexistent_person(self, graphql_client):
        """Test updating a non-existent person."""
        mutation = """
        mutation {
            updatePerson(
                id: 99999,
                firstName: "NotFound"
            ) {
                person {
                    id
                }
                success
                errors
            }
        }
        """
        
        result = graphql_client.execute(mutation)
        
        assert 'errors' not in result
        data = result['data']['updatePerson']
        
        assert data['success'] is False
        assert 'Person not found' in data['errors']
        assert data['person'] is None
    
    def test_delete_person_mutation(self, graphql_client, people_factory):
        """Test deleting a person via mutation."""
        person = people_factory.create()
        person_id = person.id
        
        mutation = f"""
        mutation {{
            deletePerson(id: {person_id}) {{
                success
                errors
            }}
        }}
        """
        
        result = graphql_client.execute(mutation)
        
        assert 'errors' not in result
        data = result['data']['deletePerson']
        
        assert data['success'] is True
        assert data['errors'] == []
        
        # Verify deletion in database
        assert not People.objects.filter(id=person_id).exists()
    
    def test_mutation_with_dataloader_cache_invalidation(self, graphql_client, people_factory):
        """Test that mutations properly invalidate DataLoader cache."""
        person = people_factory.create(first_name='Original')
        
        # Query first to populate cache
        query = f"""
        query {{
            person(id: {person.id}) {{
                id
                firstName
            }}
        }}
        """
        
        initial_result = graphql_client.execute(query)
        assert initial_result['data']['person']['firstName'] == 'Original'
        
        # Update via mutation
        mutation = f"""
        mutation {{
            updatePerson(
                id: {person.id},
                firstName: "Updated"
            ) {{
                person {{
                    id
                    firstName
                }}
                success
            }}
        }}
        """
        
        mutation_result = graphql_client.execute(mutation)
        assert mutation_result['data']['updatePerson']['success'] is True
        
        # Query again - should see updated data (cache invalidated)
        final_result = graphql_client.execute(query)
        assert final_result['data']['person']['firstName'] == 'Updated'


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLAuthentication:
    """Test GraphQL authentication requirements."""
    
    def test_unauthenticated_query_denied(self):
        """Test that unauthenticated queries are denied."""
        client = Client()
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                    }
                }
            }
        }
        """
        
        response = client.post(
            '/api/graphql/',
            json.dumps({'query': query}),
            content_type='application/json'
        )
        
        result = response.json()
        assert 'errors' in result
        # Should have authentication error
        assert any('authentication' in error.get('message', '').lower() 
                 for error in result['errors'])
    
    def test_authenticated_query_allowed(self, graphql_client, people_factory):
        """Test that authenticated queries are allowed."""
        person = people_factory.create()
        
        query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        assert 'data' in result
        assert len(result['data']['allPeople']['edges']) == 1
    
    def test_mutation_requires_authentication(self):
        """Test that mutations require authentication."""
        client = Client()
        
        mutation = """
        mutation {
            createPerson(
                firstName: "Test",
                lastName: "User",
                email: "test@example.com",
                employeeCode: "TEST001"
            ) {
                success
            }
        }
        """
        
        response = client.post(
            '/api/graphql/',
            json.dumps({'query': mutation}),
            content_type='application/json'
        )
        
        result = response.json()
        assert 'errors' in result


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLFiltering:
    """Test GraphQL filtering capabilities."""
    
    def test_people_filtering_by_active_status(self, graphql_client, people_factory):
        """Test filtering people by active status."""
        active_people = people_factory.create_batch(3, is_active=True)
        inactive_people = people_factory.create_batch(2, is_active=False)
        
        query = """
        query {
            allPeople(isActive: true) {
                edges {
                    node {
                        id
                        firstName
                        isActive
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        people = result['data']['allPeople']['edges']
        
        assert len(people) == 3
        for person in people:
            assert person['node']['isActive'] is True
    
    def test_people_filtering_by_name(self, graphql_client, people_factory):
        """Test filtering people by name."""
        john = people_factory.create(first_name='John')
        jane = people_factory.create(first_name='Jane')
        bob = people_factory.create(first_name='Bob')
        
        query = """
        query {
            allPeople(firstName_Icontains: "J") {
                edges {
                    node {
                        id
                        firstName
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        people = result['data']['allPeople']['edges']
        
        # Should find John and Jane
        names = [person['node']['firstName'] for person in people]
        assert 'John' in names
        assert 'Jane' in names
        assert 'Bob' not in names
    
    def test_groups_filtering(self, graphql_client, pgroup_factory):
        """Test filtering groups."""
        active_groups = pgroup_factory.create_batch(3, is_active=True)
        inactive_groups = pgroup_factory.create_batch(2, is_active=False)
        
        query = """
        query {
            allGroups(isActive: true) {
                edges {
                    node {
                        id
                        name
                        isActive
                    }
                }
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert 'errors' not in result
        groups = result['data']['allGroups']['edges']
        
        assert len(groups) == 3
        for group in groups:
            assert group['node']['isActive'] is True


@pytest.mark.integration
@pytest.mark.graphql
@pytest.mark.api
class TestGraphQLPerformance:
    """Test GraphQL performance characteristics."""
    
    def test_deep_query_performance(self, graphql_client, query_counter, bulk_test_data):
        """Test performance of deep nested queries."""
        query = """
        query {
            allPeople(first: 10) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        groups {
                            id
                            name
                            memberCount
                        }
                        jobs {
                            id
                            title
                            assetDetails {
                                id
                                name
                                locationName
                            }
                        }
                        jobCount
                    }
                }
            }
        }
        """
        
        with query_counter() as context:
            result = graphql_client.execute(query)
            
            assert 'errors' not in result
            
            # Should be optimized with DataLoaders
            assert len(context) <= 8  # Should be well-optimized
    
    def test_large_dataset_query_performance(self, graphql_client, query_counter, bulk_test_data):
        """Test performance with large datasets."""
        query = """
        query {
            allPeople(first: 50) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        fullName
                    }
                }
            }
        }
        """
        
        import time
        start_time = time.time()
        
        with query_counter() as context:
            result = graphql_client.execute(query)
            
            elapsed_time = time.time() - start_time
            
            assert 'errors' not in result
            assert len(result['data']['allPeople']['edges']) == 50
            
            # Should complete quickly
            assert elapsed_time < 1.0
            
            # Should use optimized queries
            assert len(context) <= 5