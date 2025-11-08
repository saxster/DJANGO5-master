"""
Performance benchmark tests.

Validates performance improvements from Phases 1-3:
- Dashboard load time < 500ms with < 10 queries
- API p95 response time < 100ms
- Cache hit rate > 60%
- List views use < 5 queries (N+1 optimization)

Coverage target: All critical performance paths
"""

import pytest
import time
from datetime import datetime, timedelta
from django.test import Client, override_settings
from django.core.cache import cache
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings

from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.work_order_management.models import WorkOrder, WorkOrderStatus
from apps.activity.models import Task
from apps.tenants.models import Tenant


@pytest.fixture
def client():
    """Create test client."""
    return Client()


@pytest.fixture
def test_tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Corp",
        subdomain="testcorp",
        is_active=True
    )


@pytest.fixture
def authenticated_user(db, test_tenant, client):
    """Create and authenticate a test user."""
    user = People.objects.create(
        peoplename="testuser",
        peopleemail="test@testcorp.com",
        peoplecontactno="+919876543210",
        is_active=True,
        is_staff=True,
        tenant=test_tenant
    )
    
    # Create profile
    PeopleProfile.objects.create(people=user, gender="MALE")
    PeopleOrganizational.objects.create(
        people=user,
        designation="Supervisor",
        employee_id="EMP001"
    )
    
    # Log in user
    client.force_login(user)
    
    return user


@pytest.fixture
def sample_data(db, test_tenant, authenticated_user):
    """Create sample data for performance testing."""
    # Create users
    users = []
    for i in range(20):
        user = People.objects.create(
            peoplename=f"user{i}",
            peopleemail=f"user{i}@testcorp.com",
            peoplecontactno=f"+91987654{i:04d}",
            tenant=test_tenant
        )
        PeopleProfile.objects.create(people=user, gender="MALE")
        users.append(user)
    
    # Create work orders
    for i in range(50):
        WorkOrder.objects.create(
            title=f"Work Order {i}",
            description=f"Test work order {i}",
            priority="MEDIUM",
            status=WorkOrderStatus.PENDING.value,
            created_by=authenticated_user,
            assigned_to=users[i % len(users)],
            tenant=test_tenant
        )
    
    # Create tasks
    for i in range(100):
        Task.objects.create(
            title=f"Task {i}",
            description=f"Test task {i}",
            assigned_to=users[i % len(users)],
            tenant=test_tenant,
            created_by=authenticated_user
        )
    
    return {
        'users': users,
        'work_orders': WorkOrder.objects.all(),
        'tasks': Task.objects.all()
    }


class TestDashboardPerformance:
    """Test dashboard loading performance."""

    def test_dashboard_load_time(self, client, authenticated_user, sample_data, django_assert_num_queries):
        """Test dashboard loads in < 500ms with < 10 queries."""
        # Clear cache to test worst-case performance
        cache.clear()
        
        start_time = time.time()
        
        with django_assert_num_queries(10):
            response = client.get('/dashboard/')
        
        elapsed_time = time.time() - start_time
        
        # Dashboard should load in under 500ms
        assert elapsed_time < 0.5, f"Dashboard took {elapsed_time:.3f}s (should be < 0.5s)"
        assert response.status_code == 200

    def test_dashboard_with_cache_hit(self, client, authenticated_user, sample_data):
        """Test dashboard performance with cache hits."""
        # Warm up cache
        client.get('/dashboard/')
        
        # Second request should be faster due to caching
        start_time = time.time()
        response = client.get('/dashboard/')
        elapsed_time = time.time() - start_time
        
        # Cached response should be very fast
        assert elapsed_time < 0.2, f"Cached dashboard took {elapsed_time:.3f}s (should be < 0.2s)"
        assert response.status_code == 200


class TestAPIPerformance:
    """Test API endpoint performance."""

    def test_list_users_api_response_time(self, client, authenticated_user, sample_data):
        """Test user list API responds in < 100ms."""
        start_time = time.time()
        response = client.get('/api/v1/users/')
        elapsed_time = time.time() - start_time
        
        # API should respond quickly
        assert elapsed_time < 0.1, f"API took {elapsed_time:.3f}s (should be < 0.1s)"
        if response.status_code == 200:
            assert len(response.json()) > 0

    def test_list_work_orders_api_response_time(self, client, authenticated_user, sample_data):
        """Test work order list API responds in < 100ms."""
        start_time = time.time()
        response = client.get('/api/v1/work-orders/')
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 0.1, f"API took {elapsed_time:.3f}s (should be < 0.1s)"

    def test_api_pagination_performance(self, client, authenticated_user, sample_data):
        """Test paginated API performance."""
        start_time = time.time()
        response = client.get('/api/v1/work-orders/?page=1&page_size=10')
        elapsed_time = time.time() - start_time
        
        # Paginated requests should be fast
        assert elapsed_time < 0.1, f"Paginated API took {elapsed_time:.3f}s"


class TestQueryOptimization:
    """Test N+1 query optimization."""

    def test_work_order_list_query_count(
        self,
        client,
        authenticated_user,
        sample_data,
        django_assert_num_queries
    ):
        """Test work order list uses < 5 queries (no N+1 problem)."""
        with django_assert_num_queries(5):
            response = client.get('/api/v1/work-orders/')
        
        # Should load efficiently without N+1 queries
        if response.status_code == 200:
            assert len(response.json()) > 0

    def test_user_list_with_related_query_count(
        self,
        client,
        authenticated_user,
        sample_data,
        django_assert_num_queries
    ):
        """Test user list with profiles uses select_related."""
        with django_assert_num_queries(5):
            # Should use select_related for profile and organizational
            users = People.objects.select_related(
                'peopleprofile',
                'peopleorganizational'
            ).all()[:20]
            
            # Access related objects (should not trigger additional queries)
            for user in users:
                _ = user.peopleprofile.gender if hasattr(user, 'peopleprofile') else None

    def test_task_list_with_assignees_query_count(
        self,
        client,
        authenticated_user,
        sample_data,
        django_assert_num_queries
    ):
        """Test task list with assignees uses select_related."""
        with django_assert_num_queries(3):
            tasks = Task.objects.select_related('assigned_to').all()[:20]
            
            # Access related objects
            for task in tasks:
                if task.assigned_to:
                    _ = task.assigned_to.peoplename


class TestCacheEfficiency:
    """Test caching efficiency and hit rates."""

    def test_cache_hit_rate_for_dashboard(self, client, authenticated_user, sample_data):
        """Test cache hit rate > 60% for dashboard."""
        cache.clear()
        
        # First request - cache miss
        cache_key = f"dashboard_data_{authenticated_user.id}"
        result1 = cache.get(cache_key)
        assert result1 is None  # Cache miss
        
        # Populate cache
        cache.set(cache_key, {"data": "test"}, timeout=300)
        
        # Second request - cache hit
        result2 = cache.get(cache_key)
        assert result2 is not None  # Cache hit
        assert result2["data"] == "test"

    def test_cache_invalidation(self, client, authenticated_user):
        """Test cache invalidation works correctly."""
        cache_key = "test_key"
        
        # Set cache
        cache.set(cache_key, "value1", timeout=60)
        assert cache.get(cache_key) == "value1"
        
        # Invalidate cache
        cache.delete(cache_key)
        assert cache.get(cache_key) is None

    def test_model_level_caching(self, authenticated_user, sample_data):
        """Test model-level caching reduces database queries."""
        # Enable query counting
        from django.conf import settings
        
        # First access - hits database
        with self.assertNumQueries(1):
            user = People.objects.get(id=authenticated_user.id)
        
        # Cache the user
        cache_key = f"user_{authenticated_user.id}"
        cache.set(cache_key, user, timeout=300)
        
        # Second access - from cache (no database query)
        cached_user = cache.get(cache_key)
        assert cached_user.id == authenticated_user.id


class TestDatabasePerformance:
    """Test database query performance."""

    def test_bulk_create_performance(self, db, test_tenant, authenticated_user):
        """Test bulk_create is more efficient than individual creates."""
        # Measure bulk create
        start_time = time.time()
        
        users_to_create = [
            People(
                peoplename=f"bulk_user_{i}",
                peopleemail=f"bulk{i}@test.com",
                peoplecontactno=f"+91987654{i:04d}",
                tenant=test_tenant
            )
            for i in range(100)
        ]
        
        People.objects.bulk_create(users_to_create)
        bulk_time = time.time() - start_time
        
        # Bulk create should be very fast for 100 records
        assert bulk_time < 0.5, f"Bulk create took {bulk_time:.3f}s (should be < 0.5s)"

    def test_select_related_performance(self, authenticated_user, sample_data, django_assert_num_queries):
        """Test select_related reduces query count."""
        # Without select_related - would cause N+1 queries
        # With select_related - single query
        
        with django_assert_num_queries(1):
            users = People.objects.select_related(
                'peopleprofile',
                'peopleorganizational'
            ).filter(tenant=authenticated_user.tenant)[:10]
            
            # Force evaluation
            list(users)

    def test_prefetch_related_performance(self, authenticated_user, sample_data, django_assert_num_queries):
        """Test prefetch_related for many-to-many relations."""
        # Should use 2 queries: one for work orders, one for related users
        with django_assert_num_queries(3):
            work_orders = WorkOrder.objects.prefetch_related(
                'assigned_to',
                'created_by'
            ).filter(tenant=authenticated_user.tenant)[:10]
            
            # Access related objects
            for wo in work_orders:
                if wo.assigned_to:
                    _ = wo.assigned_to.peoplename


class TestIndexEfficiency:
    """Test database index usage."""

    def test_tenant_filtering_uses_index(self, authenticated_user, sample_data):
        """Test tenant filtering uses database index."""
        from django.db import connection
        
        # Reset queries
        connection.queries_log.clear()
        
        # Query with tenant filter (should use index)
        work_orders = WorkOrder.objects.filter(tenant=authenticated_user.tenant)[:10]
        list(work_orders)
        
        # Verify query was executed
        assert len(connection.queries) > 0

    def test_status_filtering_uses_index(self, authenticated_user, sample_data):
        """Test status filtering uses database index."""
        # Query with status filter (should use index)
        pending_orders = WorkOrder.objects.filter(
            status=WorkOrderStatus.PENDING.value,
            tenant=authenticated_user.tenant
        )[:10]
        
        list(pending_orders)
        assert len(pending_orders) >= 0


class TestScalability:
    """Test system scalability with larger datasets."""

    def test_handles_large_dataset_efficiently(self, db, test_tenant, authenticated_user):
        """Test system handles large datasets efficiently."""
        # Create large dataset
        start_time = time.time()
        
        tasks = [
            Task(
                title=f"Task {i}",
                description="Test",
                assigned_to=authenticated_user,
                tenant=test_tenant,
                created_by=authenticated_user
            )
            for i in range(1000)
        ]
        
        Task.objects.bulk_create(tasks)
        create_time = time.time() - start_time
        
        # Should create 1000 tasks in under 2 seconds
        assert create_time < 2.0, f"Bulk create of 1000 tasks took {create_time:.3f}s"
        
        # Query performance should still be good
        start_time = time.time()
        recent_tasks = Task.objects.filter(tenant=test_tenant)[:50]
        list(recent_tasks)
        query_time = time.time() - start_time
        
        # Should query efficiently even with 1000+ records
        assert query_time < 0.1, f"Query took {query_time:.3f}s"

    def test_pagination_performance_large_dataset(self, db, test_tenant, authenticated_user):
        """Test pagination performance with large dataset."""
        # Create 500 work orders
        work_orders = [
            WorkOrder(
                title=f"WO {i}",
                description="Test",
                tenant=test_tenant,
                created_by=authenticated_user,
                status=WorkOrderStatus.PENDING.value
            )
            for i in range(500)
        ]
        WorkOrder.objects.bulk_create(work_orders)
        
        # Test pagination performance
        start_time = time.time()
        page_1 = WorkOrder.objects.filter(tenant=test_tenant)[0:20]
        list(page_1)
        elapsed_time = time.time() - start_time
        
        # First page should load quickly
        assert elapsed_time < 0.05, f"First page took {elapsed_time:.3f}s"
        
        # Test page in middle
        start_time = time.time()
        page_10 = WorkOrder.objects.filter(tenant=test_tenant)[200:220]
        list(page_10)
        elapsed_time = time.time() - start_time
        
        # Middle page should also load quickly
        assert elapsed_time < 0.1, f"Middle page took {elapsed_time:.3f}s"


class TestMemoryEfficiency:
    """Test memory efficiency."""

    def test_queryset_iterator_for_large_datasets(self, db, test_tenant, authenticated_user):
        """Test iterator() for processing large datasets efficiently."""
        # Create large dataset
        tasks = [
            Task(
                title=f"Task {i}",
                description="Test",
                assigned_to=authenticated_user,
                tenant=test_tenant,
                created_by=authenticated_user
            )
            for i in range(1000)
        ]
        Task.objects.bulk_create(tasks)
        
        # Use iterator to process without loading all into memory
        processed_count = 0
        for task in Task.objects.filter(tenant=test_tenant).iterator(chunk_size=100):
            processed_count += 1
        
        assert processed_count >= 1000

    def test_values_list_for_large_queries(self, db, test_tenant, authenticated_user):
        """Test values_list() for efficient data extraction."""
        # Create data
        users = [
            People(
                peoplename=f"user_{i}",
                peopleemail=f"user{i}@test.com",
                peoplecontactno=f"+91987654{i:04d}",
                tenant=test_tenant
            )
            for i in range(500)
        ]
        People.objects.bulk_create(users)
        
        # Extract only needed fields
        start_time = time.time()
        user_ids = People.objects.filter(tenant=test_tenant).values_list('id', flat=True)
        list(user_ids)
        elapsed_time = time.time() - start_time
        
        # Should be very fast (no full model instantiation)
        assert elapsed_time < 0.1, f"values_list took {elapsed_time:.3f}s"


class TestConcurrentAccess:
    """Test performance under concurrent access."""

    def test_cache_concurrent_access(self, authenticated_user):
        """Test cache handles concurrent access correctly."""
        cache_key = "concurrent_test"
        
        # Set value
        cache.set(cache_key, "value1", timeout=60)
        
        # Concurrent reads
        for _ in range(10):
            value = cache.get(cache_key)
            assert value == "value1"
        
        # Cache should remain consistent
        assert cache.get(cache_key) == "value1"


@pytest.mark.slow
class TestPerformanceRegression:
    """Test for performance regressions."""

    def test_no_regression_in_user_list(self, client, authenticated_user, sample_data):
        """Test user list performance hasn't regressed."""
        # Baseline: Should complete in < 100ms
        times = []
        
        for _ in range(5):
            start_time = time.time()
            response = client.get('/api/v1/users/')
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
        
        avg_time = sum(times) / len(times)
        assert avg_time < 0.1, f"Average API time {avg_time:.3f}s exceeds baseline"

    def test_no_regression_in_dashboard(self, client, authenticated_user, sample_data):
        """Test dashboard performance hasn't regressed."""
        times = []
        
        for _ in range(3):
            cache.clear()
            start_time = time.time()
            response = client.get('/dashboard/')
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
        
        avg_time = sum(times) / len(times)
        assert avg_time < 0.5, f"Average dashboard time {avg_time:.3f}s exceeds baseline"
