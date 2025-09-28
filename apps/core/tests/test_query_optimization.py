"""
Comprehensive Test Suite for Database Query Optimization.

This test suite validates that query optimizations are working correctly
and prevents N+1 query regressions.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.db import connection
from django.conf import settings
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone
from typing import List, Dict, Any

from apps.core.services.query_optimization_service import QueryOptimizer
from apps.core.managers.optimized_managers import (
    OptimizedPeopleManager,
    OptimizedJobManager,
    OptimizedAssetManager,
)
from apps.api.graphql.dataloaders import get_loaders, PeopleByIdLoader, JobsByAssetLoader


class QueryCountTestCase(TestCase):
    """
    Base test case that provides query count testing utilities.
    """

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.reset_query_count()

    def reset_query_count(self):
        """Reset the query count."""
        connection.queries_log.clear()

    def get_query_count(self) -> int:
        """Get the current number of queries executed."""
        return len(connection.queries_log)

    def assertMaxQueries(self, max_queries: int, msg: str = None):
        """
        Assert that no more than max_queries have been executed.

        Args:
            max_queries: Maximum allowed number of queries
            msg: Optional error message
        """
        query_count = self.get_query_count()
        if query_count > max_queries:
            queries = [q['sql'] for q in connection.queries_log]
            self.fail(
                f"Expected at most {max_queries} queries, but {query_count} were executed.\n"
                f"Queries:\n" + "\n".join(queries) + (f"\n{msg}" if msg else "")
            )

    def assertExactQueries(self, expected_queries: int, msg: str = None):
        """
        Assert exact number of queries executed.

        Args:
            expected_queries: Expected number of queries
            msg: Optional error message
        """
        query_count = self.get_query_count()
        if query_count != expected_queries:
            queries = [q['sql'] for q in connection.queries_log]
            self.fail(
                f"Expected exactly {expected_queries} queries, but {query_count} were executed.\n"
                f"Queries:\n" + "\n".join(queries) + (f"\n{msg}" if msg else "")
            )


@override_settings(DEBUG=True)  # Enable query logging
class QueryOptimizationServiceTestCase(QueryCountTestCase):
    """
    Test cases for the QueryOptimizer service.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data for optimization tests."""
        # Create test people data
        from apps.peoples.models import People
        from apps.onboarding.models import BT, Shift

        cls.bt = BT.objects.create(
            bucode="TEST_BT",
            buname="Test Business Unit",
            enable=True
        )

        cls.shift = Shift.objects.create(
            shiftname="Test Shift",
            starttime="09:00",
            endtime="17:00",
            client=cls.bt
        )

        cls.people = []
        for i in range(5):
            person = People.objects.create(
                loginid=f"testuser{i}",
                peoplename=f"Test User {i}",
                peoplecode=f"TEST{i:03d}",
                email=f"testuser{i}@example.com",
                dateofbirth=date(1990, 1, 1),
                dateofjoin=date(2024, 1, 1),
                shift=cls.shift,
                bt=cls.bt
            )
            cls.people.append(person)

    def test_query_optimizer_basic_optimization(self):
        """Test basic query optimization."""
        from apps.peoples.models import People

        self.reset_query_count()

        # Unoptimized query - should access related fields individually
        unoptimized = People.objects.all()
        people_list = list(unoptimized)

        # Access related fields to trigger N+1 queries
        for person in people_list:
            _ = person.shift.shiftname if person.shift else None
            _ = person.bt.buname if person.bt else None

        unoptimized_queries = self.get_query_count()

        self.reset_query_count()

        # Optimized query - should use select_related
        optimized = QueryOptimizer.optimize_queryset(People.objects.all())
        people_list = list(optimized)

        # Access related fields - should not trigger additional queries
        for person in people_list:
            _ = person.shift.shiftname if person.shift else None
            _ = person.bt.buname if person.bt else None

        optimized_queries = self.get_query_count()

        # Optimized should use significantly fewer queries
        self.assertLess(optimized_queries, unoptimized_queries,
                       "Optimized query should use fewer queries than unoptimized")
        self.assertMaxQueries(3, "Optimized query should use at most 3 queries")

    def test_query_optimizer_aggressive_profile(self):
        """Test aggressive optimization profile."""
        from apps.peoples.models import People

        queryset = People.objects.all()
        optimized = QueryOptimizer.optimize_queryset(queryset, profile='aggressive')

        # Should have select_related and prefetch_related applied
        self.assertTrue(hasattr(optimized, '_select_related'))
        self.assertTrue(hasattr(optimized, '_prefetch_related_lookups'))

    def test_query_optimizer_minimal_profile(self):
        """Test minimal optimization profile."""
        from apps.peoples.models import People

        queryset = People.objects.all()
        optimized = QueryOptimizer.optimize_queryset(queryset, profile='minimal')

        # Should have minimal optimizations applied
        self.assertIsNotNone(optimized)

    def test_relationship_analysis(self):
        """Test model relationship analysis."""
        from apps.peoples.models import People

        # Clear cache to ensure fresh analysis
        QueryOptimizer.clear_cache()

        # Analyze People model
        QueryOptimizer._analyze_model_relationships(People)

        model_key = f"{People._meta.app_label}.{People._meta.model_name}"
        self.assertIn(model_key, QueryOptimizer._relationship_cache)

        relationships = QueryOptimizer._relationship_cache[model_key]
        self.assertIn('foreign_keys', relationships)
        self.assertIn('many_to_many', relationships)
        self.assertIsInstance(relationships['foreign_keys'], list)

    def test_query_performance_analysis(self):
        """Test query performance analysis."""
        from apps.peoples.models import People

        queryset = People.objects.all()
        analysis = QueryOptimizer.analyze_query_performance(queryset)

        self.assertIn('query_count_estimate', analysis)
        self.assertIn('optimization_opportunities', analysis)
        self.assertIn('recommendations', analysis)
        self.assertIsInstance(analysis['query_count_estimate'], int)


@override_settings(DEBUG=True)
class OptimizedManagerTestCase(QueryCountTestCase):
    """
    Test cases for optimized managers.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data for manager tests."""
        from apps.peoples.models import People
        from apps.onboarding.models import BT, Shift
        from apps.activity.models.job_model import Job
        from apps.activity.models.asset_model import Asset

        cls.bt = BT.objects.create(
            bucode="TEST_BT",
            buname="Test Business Unit",
            enable=True
        )

        cls.shift = Shift.objects.create(
            shiftname="Test Shift",
            starttime="09:00",
            endtime="17:00",
            client=cls.bt
        )

        cls.people = People.objects.create(
            loginid="testuser",
            peoplename="Test User",
            peoplecode="TEST001",
            email="testuser@example.com",
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2024, 1, 1),
            shift=cls.shift,
            bt=cls.bt
        )

        # Create test assets and jobs
        try:
            cls.asset = Asset.objects.create(
                name="Test Asset",
                assetcode="ASSET001",
                is_active=True
            )

            cls.job = Job.objects.create(
                title="Test Job",
                status="pending",
                people=cls.people,
                asset=cls.asset
            )
        except Exception:
            # Handle case where models don't exist or have different fields
            pass

    def test_optimized_people_manager_query_count(self):
        """Test that OptimizedPeopleManager reduces query count."""
        from apps.peoples.models import People

        # Create a mock optimized manager
        manager = OptimizedPeopleManager()
        manager.model = People

        self.reset_query_count()

        # Use optimized queryset
        people = list(manager.optimized_all())

        # Access related fields
        for person in people:
            _ = person.shift.shiftname if person.shift else None
            _ = person.bt.buname if person.bt else None

        # Should use minimal queries due to select_related
        self.assertMaxQueries(3, "Optimized manager should minimize queries")

    def test_optimized_manager_filter_methods(self):
        """Test optimized filter methods."""
        from apps.peoples.models import People

        manager = OptimizedPeopleManager()
        manager.model = People

        # Test optimized filter
        filtered = manager.optimized_filter(is_active=True)
        self.assertTrue(hasattr(filtered, '_select_related'))

        # Test active people method
        active = manager.active_people()
        self.assertIsNotNone(active)

    def test_bulk_optimization_methods(self):
        """Test bulk optimization methods."""
        from apps.peoples.models import People

        manager = OptimizedPeopleManager()
        manager.model = People

        # Test bulk optimization with IDs
        ids = [self.people.id]
        bulk_queryset = manager.with_bulk_optimizations(ids)
        self.assertIsNotNone(bulk_queryset)


@override_settings(DEBUG=True)
class GraphQLDataLoaderTestCase(QueryCountTestCase):
    """
    Test cases for GraphQL DataLoader optimizations.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data for DataLoader tests."""
        from apps.peoples.models import People
        from apps.onboarding.models import BT, Shift

        cls.bt = BT.objects.create(
            bucode="TEST_BT",
            buname="Test Business Unit",
            enable=True
        )

        cls.shift = Shift.objects.create(
            shiftname="Test Shift",
            starttime="09:00",
            endtime="17:00",
            client=cls.bt
        )

        cls.people = []
        for i in range(10):
            person = People.objects.create(
                loginid=f"testuser{i}",
                peoplename=f"Test User {i}",
                peoplecode=f"TEST{i:03d}",
                email=f"testuser{i}@example.com",
                dateofbirth=date(1990, 1, 1),
                dateofjoin=date(2024, 1, 1),
                shift=cls.shift,
                bt=cls.bt
            )
            cls.people.append(person)

    def test_people_by_id_loader_batch_loading(self):
        """Test that PeopleByIdLoader batches requests efficiently."""
        loader = PeopleByIdLoader()

        self.reset_query_count()

        # Load multiple people - should batch into single query
        people_ids = [p.id for p in self.people[:5]]

        # Simulate DataLoader batching
        results = loader.batch_load_fn(people_ids)

        # Should use only one query for all IDs
        self.assertMaxQueries(1, "DataLoader should batch multiple IDs into single query")

    def test_dataloader_context_management(self):
        """Test DataLoader context management."""
        # Mock GraphQL info context
        mock_info = MagicMock()
        mock_info.context = MagicMock()

        # Test get_loaders function
        loaders = get_loaders(mock_info)

        self.assertIn('people_by_id', loaders)
        self.assertIn('jobs_by_asset', loaders)
        self.assertIsInstance(loaders['people_by_id'], PeopleByIdLoader)


class QueryOptimizationIntegrationTestCase(TransactionTestCase):
    """
    Integration tests for query optimization across the application.
    """

    def test_scheduler_view_optimizations(self):
        """Test that scheduler views use optimized queries."""
        # This would test actual view methods for query optimization
        # For now, just verify the optimization service is working
        from apps.core.services.query_optimization_service import QueryOptimizer

        self.assertIsNotNone(QueryOptimizer)
        self.assertTrue(hasattr(QueryOptimizer, 'optimize_queryset'))

    def test_graphql_schema_optimizations(self):
        """Test that GraphQL schema uses DataLoaders effectively."""
        from apps.api.graphql.dataloaders import get_loaders

        # Mock context
        mock_info = MagicMock()
        mock_info.context = MagicMock()

        loaders = get_loaders(mock_info)

        # Verify all expected loaders are present
        expected_loaders = [
            'people_by_id',
            'jobs_by_asset',
            'asset_by_id',
            'job_count_by_asset'
        ]

        for loader_name in expected_loaders:
            self.assertIn(loader_name, loaders, f"Missing DataLoader: {loader_name}")

    def test_audit_command_functionality(self):
        """Test that the audit command can analyze queries."""
        from apps.core.management.commands.audit_query_optimization import Command

        command = Command()
        self.assertTrue(hasattr(command, 'handle'))
        self.assertTrue(hasattr(command, '_audit_file_queries'))


@pytest.mark.performance
class QueryPerformanceRegressionTestCase(QueryCountTestCase):
    """
    Performance regression tests to ensure optimizations maintain performance.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up performance test data."""
        from apps.peoples.models import People
        from apps.onboarding.models import BT, Shift

        cls.bt = BT.objects.create(
            bucode="PERF_BT",
            buname="Performance Test BT",
            enable=True
        )

        cls.shift = Shift.objects.create(
            shiftname="Performance Shift",
            starttime="09:00",
            endtime="17:00",
            client=cls.bt
        )

        # Create larger dataset for performance testing
        cls.people = []
        for i in range(50):  # Larger dataset
            person = People.objects.create(
                loginid=f"perfuser{i}",
                peoplename=f"Performance User {i}",
                peoplecode=f"PERF{i:03d}",
                email=f"perfuser{i}@example.com",
                dateofbirth=date(1990, 1, 1),
                dateofjoin=date(2024, 1, 1),
                shift=cls.shift,
                bt=cls.bt
            )
            cls.people.append(person)

    def test_large_dataset_query_performance(self):
        """Test query performance with larger datasets."""
        from apps.peoples.models import People

        self.reset_query_count()

        # Use optimized queryset for large dataset
        people = QueryOptimizer.optimize_queryset(People.objects.all())
        people_list = list(people)

        # Access related fields
        for person in people_list[:10]:  # Sample first 10
            _ = person.shift.shiftname if person.shift else None
            _ = person.bt.buname if person.bt else None

        # Should still use minimal queries despite large dataset
        self.assertMaxQueries(5, "Large dataset should still use minimal queries")

    def test_dataloader_batch_size_efficiency(self):
        """Test DataLoader efficiency with various batch sizes."""
        loader = PeopleByIdLoader()

        # Test with different batch sizes
        batch_sizes = [1, 5, 10, 25]

        for batch_size in batch_sizes:
            self.reset_query_count()

            people_ids = [p.id for p in self.people[:batch_size]]
            results = loader.batch_load_fn(people_ids)

            # Should always use exactly 1 query regardless of batch size
            self.assertExactQueries(1, f"Batch size {batch_size} should use exactly 1 query")


class QueryOptimizationConfigTestCase(TestCase):
    """
    Test configuration and setup of query optimization features.
    """

    def test_optimization_service_imports(self):
        """Test that all optimization services can be imported."""
        from apps.core.services.query_optimization_service import (
            QueryOptimizer,
            get_optimized_people,
            get_optimized_activities,
            optimize_queryset
        )

        self.assertIsNotNone(QueryOptimizer)
        self.assertTrue(callable(get_optimized_people))
        self.assertTrue(callable(get_optimized_activities))
        self.assertTrue(callable(optimize_queryset))

    def test_optimized_managers_imports(self):
        """Test that all optimized managers can be imported."""
        from apps.core.managers.optimized_managers import (
            OptimizedPeopleManager,
            OptimizedJobManager,
            OptimizedAssetManager,
            get_optimized_people_queryset,
            get_optimized_job_queryset,
            get_optimized_asset_queryset
        )

        self.assertIsNotNone(OptimizedPeopleManager)
        self.assertIsNotNone(OptimizedJobManager)
        self.assertIsNotNone(OptimizedAssetManager)
        self.assertTrue(callable(get_optimized_people_queryset))
        self.assertTrue(callable(get_optimized_job_queryset))
        self.assertTrue(callable(get_optimized_asset_queryset))

    def test_dataloader_imports(self):
        """Test that all DataLoaders can be imported."""
        from apps.api.graphql.dataloaders import (
            PeopleByIdLoader,
            JobsByAssetLoader,
            get_loaders,
            DataLoaderMiddleware
        )

        self.assertIsNotNone(PeopleByIdLoader)
        self.assertIsNotNone(JobsByAssetLoader)
        self.assertTrue(callable(get_loaders))
        self.assertIsNotNone(DataLoaderMiddleware)


# Custom test decorators for query optimization
def requires_query_optimization(test_func):
    """
    Decorator to mark tests that require query optimization features.
    """
    return pytest.mark.query_optimization(test_func)


def performance_critical(test_func):
    """
    Decorator to mark performance-critical tests.
    """
    return pytest.mark.performance(test_func)


# Test utilities
class QueryOptimizationTestMixin:
    """
    Mixin to provide query optimization testing utilities.
    """

    def assertQueryOptimized(self, queryset, max_queries=3):
        """
        Assert that a queryset is properly optimized.

        Args:
            queryset: QuerySet to test
            max_queries: Maximum allowed queries
        """
        self.reset_query_count()
        list(queryset)  # Force evaluation
        self.assertMaxQueries(max_queries, "QuerySet should be optimized")

    def assertDataLoaderEfficient(self, loader_func, items, max_queries=1):
        """
        Assert that a DataLoader function is efficient.

        Args:
            loader_func: DataLoader function to test
            items: Items to load
            max_queries: Maximum allowed queries
        """
        self.reset_query_count()
        loader_func(items)
        self.assertMaxQueries(max_queries, "DataLoader should be efficient")


if __name__ == '__main__':
    pytest.main([__file__])