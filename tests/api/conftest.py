"""
Pytest configuration and fixtures for API testing.

Provides common fixtures for API tests.
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import datetime, timedelta
from django.utils import timezone
import json

fake = Faker()


# ==================== Fixtures ====================

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    """Provide an API client for testing."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Provide an authenticated API client."""
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='TestPassword123!'
    )
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='AdminPassword123!'
    )
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    """Provide an authenticated admin API client."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def api_key_client(api_client, db):
    """Provide an API key authenticated client."""
    from apps.core.models import APIKey
    api_key = APIKey.objects.create(
        name='Test API Key',
        key='test-api-key-123456789'
    )
    api_client.credentials(HTTP_X_API_KEY='test-api-key-123456789')
    return api_client


@pytest.fixture
def mobile_client(api_client, test_user):
    """Provide a mobile client with device registration."""
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}',
        HTTP_USER_AGENT='MobileApp/1.0 (iOS 16.0)',
        HTTP_X_DEVICE_ID='device-123456',
        HTTP_X_APP_VERSION='1.0.0'
    )
    return api_client


@pytest.fixture
def query_counter():
    """Context manager to count database queries."""
    def _query_counter():
        with CaptureQueriesContext(connection) as context:
            yield context
    return _query_counter


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for testing."""
    mock_cache = mocker.MagicMock()
    mocker.patch('django.core.cache.cache', mock_cache)
    return mock_cache


@pytest.fixture
def graphql_client(client, test_user):
    """Provide a GraphQL client."""
    class GraphQLClient:
        def __init__(self, client, user=None):
            self.client = client
            self.user = user
            if user:
                refresh = RefreshToken.for_user(user)
                self.token = str(refresh.access_token)
            else:
                self.token = None
        
        def execute(self, query, variables=None):
            headers = {}
            if self.token:
                headers['HTTP_AUTHORIZATION'] = f'Bearer {self.token}'
            
            response = self.client.post(
                '/api/graphql/',
                json.dumps({
                    'query': query,
                    'variables': variables or {}
                }),
                content_type='application/json',
                **headers
            )
            return response.json()
    
    return GraphQLClient(client, test_user)


# ==================== Factory Classes ====================

class PeopleFactory(DjangoModelFactory):
    """Factory for creating People instances."""
    class Meta:
        model = 'peoples.People'
    
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')
    employee_code = factory.Sequence(lambda n: f'EMP{n:05d}')
    mobile = factory.Faker('phone_number')
    is_active = True
    created_at = factory.Faker('date_time_this_year', tzinfo=timezone.get_current_timezone())


class PgroupFactory(DjangoModelFactory):
    """Factory for creating Pgroup instances."""
    class Meta:
        model = 'peoples.Pgroup'
    
    name = factory.Faker('company')
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True


class AssetFactory(DjangoModelFactory):
    """Factory for creating Asset instances."""
    class Meta:
        model = 'activity.Asset'
    
    name = factory.Faker('company')
    asset_code = factory.Sequence(lambda n: f'ASSET{n:05d}')
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True


class JobFactory(DjangoModelFactory):
    """Factory for creating Job instances."""
    class Meta:
        model = 'activity.Job'
    
    title = factory.Faker('job')
    status = factory.Faker('random_element', elements=['pending', 'in_progress', 'completed', 'cancelled'])
    priority = factory.Faker('random_element', elements=['low', 'medium', 'high', 'critical'])
    created_at = factory.Faker('date_time_this_year', tzinfo=timezone.get_current_timezone())


@pytest.fixture
def people_factory():
    """Provide PeopleFactory."""
    return PeopleFactory


@pytest.fixture
def pgroup_factory():
    """Provide PgroupFactory."""
    return PgroupFactory


@pytest.fixture
def asset_factory():
    """Provide AssetFactory."""
    return AssetFactory


@pytest.fixture
def job_factory():
    """Provide JobFactory."""
    return JobFactory


@pytest.fixture
def bulk_test_data(people_factory, pgroup_factory, asset_factory, job_factory):
    """Create bulk test data for performance testing."""
    # Create 100 people
    people = people_factory.create_batch(100)
    
    # Create 20 groups
    groups = pgroup_factory.create_batch(20)
    
    # Create 50 assets
    assets = asset_factory.create_batch(50)
    
    # Create 200 jobs
    jobs = job_factory.create_batch(200)
    
    # Assign people to groups randomly
    for person in people:
        person.groups.set(fake.random_elements(groups, length=fake.random_int(1, 5)))
    
    return {
        'people': people,
        'groups': groups,
        'assets': assets,
        'jobs': jobs
    }


# ==================== Helper Functions ====================

@pytest.fixture
def assert_no_n_plus_one():
    """Helper to assert no N+1 queries."""
    def _assert_no_n_plus_one(func, iterations=5):
        with CaptureQueriesContext(connection) as context:
            func()
            baseline_queries = len(context)
        
        for _ in range(iterations - 1):
            with CaptureQueriesContext(connection) as context:
                func()
                assert len(context) == baseline_queries, \
                    f"N+1 query detected! Expected {baseline_queries} queries but got {len(context)}"
    
    return _assert_no_n_plus_one


@pytest.fixture
def measure_performance():
    """Helper to measure API performance."""
    import time
    
    def _measure_performance(func, max_time=0.2):
        start = time.time()
        result = func()
        elapsed = time.time() - start
        assert elapsed < max_time, f"Performance issue: took {elapsed:.3f}s, expected < {max_time}s"
        return result, elapsed
    
    return _measure_performance


@pytest.fixture
def mock_external_api(responses):
    """Mock external API calls."""
    def _mock_external_api(url, json_response, status=200):
        responses.add(
            responses.GET,
            url,
            json=json_response,
            status=status
        )
    return _mock_external_api


# ==================== Test Markers ====================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "graphql: marks tests as GraphQL tests"
    )
    config.addinivalue_line(
        "markers", "mobile: marks tests as mobile API tests"
    )


# ==================== Test Database Settings ====================

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Override database setup for tests."""
    with django_db_blocker.unblock():
        # Run any initial setup here
        pass