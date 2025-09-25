"""
Load testing for API endpoints using Locust.

Tests API performance under various load conditions.
"""

import pytest
from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging
import time
import json
import random
from unittest.mock import patch


# Locust User Classes for Load Testing

class APIUser(HttpUser):
    """Base API user for load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when user starts - perform authentication."""
        self.authenticate()
    
    def authenticate(self):
        """Authenticate user and get token."""
        login_data = {
            'username': 'testuser',
            'password': 'TestPassword123!'
        }
        
        response = self.client.post('/api/v1/auth/token/', json=login_data)
        if response.status_code == 200:
            token = response.json()['access']
            self.client.headers.update({'Authorization': f'Bearer {token}'})
        
        # Also test API key authentication
        if random.choice([True, False]):
            self.client.headers.update({'X-API-Key': 'test-api-key-123456789'})


class PeopleEndpointUser(APIUser):
    """User focused on People endpoints."""
    
    @task(3)
    def list_people(self):
        """Test people list endpoint."""
        params = {
            'page_size': random.randint(10, 50),
            'ordering': random.choice(['first_name', '-created_at', 'last_name'])
        }
        self.client.get('/api/v1/people/', params=params, name='GET /api/v1/people/')
    
    @task(2)
    def get_person_detail(self):
        """Test person detail endpoint."""
        person_id = random.randint(1, 100)  # Assume we have 100 people
        self.client.get(f'/api/v1/people/{person_id}/', name='GET /api/v1/people/{id}/')
    
    @task(1)
    def create_person(self):
        """Test person creation."""
        data = {
            'first_name': f'LoadTest{random.randint(1000, 9999)}',
            'last_name': f'User{random.randint(1000, 9999)}',
            'email': f'loadtest{random.randint(1000, 9999)}@example.com',
            'employee_code': f'LOAD{random.randint(1000, 9999)}'
        }
        self.client.post('/api/v1/people/', json=data, name='POST /api/v1/people/')
    
    @task(1)
    def update_person(self):
        """Test person update."""
        person_id = random.randint(1, 100)
        data = {
            'first_name': f'Updated{random.randint(1000, 9999)}'
        }
        self.client.patch(f'/api/v1/people/{person_id}/', json=data, name='PATCH /api/v1/people/{id}/')
    
    @task(1)
    def search_people(self):
        """Test people search."""
        search_terms = ['John', 'Jane', 'Test', 'User', 'Load']
        params = {
            'search': random.choice(search_terms),
            'page_size': 20
        }
        self.client.get('/api/v1/people/', params=params, name='GET /api/v1/people/ (search)')
    
    @task(1)
    def filter_people(self):
        """Test people filtering."""
        params = {
            'is_active': random.choice(['true', 'false']),
            'page_size': 25
        }
        self.client.get('/api/v1/people/', params=params, name='GET /api/v1/people/ (filter)')


class BulkOperationsUser(APIUser):
    """User focused on bulk operations."""
    
    @task(2)
    def bulk_create_people(self):
        """Test bulk create operations."""
        data = []
        for i in range(random.randint(5, 20)):
            data.append({
                'first_name': f'Bulk{i}',
                'last_name': f'User{random.randint(1000, 9999)}',
                'email': f'bulk{i}_{random.randint(1000, 9999)}@example.com',
                'employee_code': f'BULK{i}_{random.randint(1000, 9999)}'
            })
        
        self.client.post('/api/v1/people/bulk_create/', json=data, name='POST /api/v1/people/bulk_create/')
    
    @task(1)
    def bulk_update_people(self):
        """Test bulk update operations."""
        ids = [random.randint(1, 100) for _ in range(random.randint(3, 10))]
        data = {
            'ids': ids,
            'updates': {
                'last_name': f'BulkUpdated{random.randint(1000, 9999)}'
            }
        }
        self.client.put('/api/v1/people/bulk_update/', json=data, name='PUT /api/v1/people/bulk_update/')


class GraphQLUser(APIUser):
    """User focused on GraphQL endpoints."""
    
    @task(3)
    def simple_graphql_query(self):
        """Test simple GraphQL query."""
        query = """
        query {
            allPeople(first: 20) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                    }
                }
            }
        }
        """
        self.client.post('/api/graphql/', json={'query': query}, name='POST /api/graphql/ (simple)')
    
    @task(2)
    def complex_graphql_query(self):
        """Test complex GraphQL query with relationships."""
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
                        }
                        jobs {
                            id
                            title
                            assetDetails {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """
        self.client.post('/api/graphql/', json={'query': query}, name='POST /api/graphql/ (complex)')
    
    @task(1)
    def graphql_mutation(self):
        """Test GraphQL mutation."""
        mutation = f"""
        mutation {{
            createPerson(
                firstName: "GraphQL{random.randint(1000, 9999)}"
                lastName: "LoadTest"
                email: "graphql{random.randint(1000, 9999)}@example.com"
                employeeCode: "GQL{random.randint(1000, 9999)}"
            ) {{
                person {{
                    id
                    firstName
                }}
                success
            }}
        }}
        """
        self.client.post('/api/graphql/', json={'query': mutation}, name='POST /api/graphql/ (mutation)')


class MobileAPIUser(APIUser):
    """User focused on mobile API endpoints."""
    
    def on_start(self):
        """Setup mobile client."""
        super().on_start()
        # Add mobile-specific headers
        self.client.headers.update({
            'User-Agent': 'MobileApp/1.0 (iOS 16.0)',
            'X-Device-ID': f'device-{random.randint(1000, 9999)}',
            'X-App-Version': '1.0.0'
        })
    
    @task(3)
    def sync_data(self):
        """Test mobile sync endpoint."""
        data = {
            'last_sync': None,
            'client_id': f'load-test-{random.randint(1000, 9999)}',
            'changes': {
                'create': [],
                'update': [],
                'delete': []
            }
        }
        self.client.post('/api/v1/mobile/sync/', json=data, name='POST /api/v1/mobile/sync/')
    
    @task(1)
    def register_device(self):
        """Test device registration."""
        data = {
            'device_id': f'load-device-{random.randint(1000, 9999)}',
            'device_type': random.choice(['ios', 'android']),
            'app_version': '1.0.0',
            'push_token': f'push-token-{random.randint(1000, 9999)}'
        }
        self.client.post('/api/v1/mobile/devices/', json=data, name='POST /api/v1/mobile/devices/')
    
    @task(1)
    def get_mobile_config(self):
        """Test mobile configuration endpoint."""
        self.client.get('/api/v1/mobile/config/', name='GET /api/v1/mobile/config/')


# PyTest Integration for Load Testing

@pytest.mark.performance
@pytest.mark.load
@pytest.mark.slow
class TestLoadTesting:
    """Integration tests for load testing."""
    
    def test_people_endpoint_load(self, people_factory):
        """Test People endpoint under load."""
        # Create test data
        people_factory.create_batch(100)
        
        # Setup Locust environment
        env = Environment(user_classes=[PeopleEndpointUser])
        env.create_local_runner()
        
        # Start load test
        env.runner.start(user_count=10, spawn_rate=2)
        
        # Run for 30 seconds
        time.sleep(30)
        
        # Stop load test
        env.runner.stop()
        
        # Check results
        stats = env.runner.stats
        
        # Assert no failures
        assert stats.total.num_failures == 0, f"Load test had {stats.total.num_failures} failures"
        
        # Assert reasonable response times (< 2 seconds for 95th percentile)
        assert stats.total.get_response_time_percentile(0.95) < 2000
        
        # Assert good throughput (> 5 RPS)
        assert stats.total.total_rps > 5
    
    def test_bulk_operations_load(self, people_factory):
        """Test bulk operations under load."""
        people_factory.create_batch(200)
        
        env = Environment(user_classes=[BulkOperationsUser])
        env.create_local_runner()
        
        # Lower user count for bulk operations
        env.runner.start(user_count=5, spawn_rate=1)
        time.sleep(30)
        env.runner.stop()
        
        stats = env.runner.stats
        
        # Bulk operations should complete successfully
        assert stats.total.num_failures == 0
        
        # Response times might be higher for bulk operations
        assert stats.total.get_response_time_percentile(0.95) < 5000
    
    def test_graphql_load(self, bulk_test_data):
        """Test GraphQL endpoint under load."""
        env = Environment(user_classes=[GraphQLUser])
        env.create_local_runner()
        
        env.runner.start(user_count=8, spawn_rate=2)
        time.sleep(30)
        env.runner.stop()
        
        stats = env.runner.stats
        
        # GraphQL should handle load well with DataLoaders
        assert stats.total.num_failures == 0
        assert stats.total.get_response_time_percentile(0.95) < 3000
    
    def test_mixed_load_scenario(self, bulk_test_data):
        """Test mixed load scenario with multiple user types."""
        env = Environment(user_classes=[
            PeopleEndpointUser,
            GraphQLUser,
            MobileAPIUser
        ])
        env.create_local_runner()
        
        # Simulate realistic mixed load
        env.runner.start(user_count=20, spawn_rate=2)
        time.sleep(60)  # Run longer for mixed scenario
        env.runner.stop()
        
        stats = env.runner.stats
        
        # Mixed load should still perform well
        assert stats.total.num_failures < stats.total.num_requests * 0.01  # < 1% failure rate
        assert stats.total.get_response_time_percentile(0.95) < 3000


@pytest.mark.performance
@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def test_endpoint_response_times(self, benchmark, authenticated_client, people_factory):
        """Benchmark endpoint response times."""
        people_factory.create_batch(10)
        
        def make_request():
            return authenticated_client.get('/api/v1/people/')
        
        # Benchmark the request
        result = benchmark(make_request)
        
        # Should respond quickly
        assert result.status_code == 200
        
        # Benchmark should be under 200ms
        assert benchmark.stats.mean < 0.2
    
    def test_query_optimization_benchmark(self, benchmark, authenticated_client, query_counter, bulk_test_data):
        """Benchmark query optimization."""
        def make_optimized_request():
            with query_counter() as context:
                response = authenticated_client.get('/api/v1/people/')
                return response, len(context)
        
        response, query_count = benchmark(make_optimized_request)
        
        assert response.status_code == 200
        # Should use optimized queries
        assert query_count <= 5
    
    def test_bulk_operation_benchmark(self, benchmark, authenticated_client):
        """Benchmark bulk operations."""
        def bulk_create():
            data = [
                {
                    'first_name': f'Benchmark{i}',
                    'last_name': 'User',
                    'email': f'bench{i}@example.com',
                    'employee_code': f'BENCH{i}'
                }
                for i in range(50)
            ]
            return authenticated_client.post('/api/v1/people/bulk_create/', data, format='json')
        
        result = benchmark(bulk_create)
        
        assert result.status_code == 201
        # Bulk creation should be reasonably fast
        assert benchmark.stats.mean < 2.0
    
    def test_graphql_dataloader_benchmark(self, benchmark, graphql_client, bulk_test_data):
        """Benchmark GraphQL DataLoader performance."""
        query = """
        query {
            allPeople(first: 50) {
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
        
        def graphql_request():
            return graphql_client.execute(query)
        
        result = benchmark(graphql_request)
        
        assert 'errors' not in result
        # DataLoader should make this fast
        assert benchmark.stats.mean < 0.5


@pytest.mark.performance
@pytest.mark.memory
class TestMemoryUsage:
    """Test memory usage patterns."""
    
    def test_memory_usage_during_bulk_operations(self, authenticated_client):
        """Test memory usage during bulk operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Perform bulk operation
        data = [
            {
                'first_name': f'Memory{i}',
                'last_name': 'Test',
                'email': f'memory{i}@example.com',
                'employee_code': f'MEM{i:05d}'
            }
            for i in range(1000)  # Large batch
        ]
        
        response = authenticated_client.post('/api/v1/people/bulk_create/', data, format='json')
        assert response.status_code == 201
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
    
    def test_memory_leak_detection(self, authenticated_client, people_factory):
        """Test for memory leaks during repeated requests."""
        import psutil
        import os
        import gc
        
        people_factory.create_batch(100)
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make many requests
        for _ in range(100):
            response = authenticated_client.get('/api/v1/people/')
            assert response.status_code == 200
            
            # Force garbage collection
            gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Should not have significant memory increase
        assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase


@pytest.mark.performance 
@pytest.mark.concurrent
class TestConcurrency:
    """Test API behavior under concurrent access."""
    
    def test_concurrent_requests(self, authenticated_client, people_factory):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        people_factory.create_batch(50)
        
        results = []
        errors = []
        
        def make_request():
            try:
                response = authenticated_client.get('/api/v1/people/')
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create 20 concurrent threads
        threads = [threading.Thread(target=make_request) for _ in range(20)]
        
        start_time = time.time()
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # All requests should succeed
        assert len(errors) == 0
        assert all(status == 200 for status in results)
        
        # Should complete within reasonable time
        assert end_time - start_time < 10.0
    
    def test_concurrent_mutations(self, authenticated_client):
        """Test concurrent data mutations."""
        import threading
        
        results = []
        errors = []
        
        def create_person(index):
            try:
                data = {
                    'first_name': f'Concurrent{index}',
                    'last_name': 'User',
                    'email': f'concurrent{index}@example.com',
                    'employee_code': f'CONC{index:05d}'
                }
                response = authenticated_client.post('/api/v1/people/', data, format='json')
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create 10 concurrent creation requests
        threads = [threading.Thread(target=create_person, args=(i,)) for i in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(errors) == 0
        assert all(status == 201 for status in results)
        
        # Verify all people were created
        from apps.peoples.models import People
        concurrent_people = People.objects.filter(first_name__startswith='Concurrent')
        assert concurrent_people.count() == 10