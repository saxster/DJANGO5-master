"""
Comprehensive DataLoader Performance Tests.

Tests N+1 query prevention and performance optimization for GraphQL resolvers
using DataLoader batching and caching.

Performance Target: 50%+ reduction in database queries
Expected Impact: 2-5x faster GraphQL query execution

Related: apps/api/graphql/dataloaders.py
"""

import pytest
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from graphene.test import Client as GrapheneClient
from apps.service.schema import schema
from apps.peoples.models import People, PeoplesGroups
from apps.activity.models import Job, Asset
from apps.onboarding.models import Bt, Client
from apps.api.graphql.dataloaders import get_loaders, DataLoaderRegistry
from unittest.mock import MagicMock
import time


@pytest.mark.performance
class TestDataLoaderPerformance(TestCase):
    """
    Performance tests for DataLoader query optimization.

    These tests verify that DataLoader significantly reduces database queries
    and improves GraphQL query performance.
    """

    databases = ['default']

    @classmethod
    def setUpTestData(cls):
        """Set up test data for performance tests."""
        # Create test client
        cls.test_client = Client.objects.create(
            bucode='TEST001',
            buname='Test Client Performance',
            enable=True
        )

        # Create test business unit
        cls.test_bu = Bt.objects.create(
            btcode='BU001',
            btname='Test BU',
            client=cls.test_client
        )

        # Create test users (10 users for realistic N+1 scenario)
        cls.test_users = []
        for i in range(10):
            user = People.objects.create_user(
                loginid=f'user{i}',
                password='test123',
                peoplename=f'Test User {i}',
                client=cls.test_client,
                bu=cls.test_bu,
                enable=True
            )
            cls.test_users.append(user)

        # Create test groups
        cls.test_groups = []
        for i in range(5):
            group = PeoplesGroups.objects.create(
                code=f'GROUP{i}',
                name=f'Test Group {i}',
                client=cls.test_client
            )
            cls.test_groups.append(group)

            # Assign users to groups (N+1 scenario)
            for user in cls.test_users[:5]:  # First 5 users in each group
                group.peoples.add(user)

        # Create test assets
        cls.test_assets = []
        for i in range(10):
            asset = Asset.objects.create(
                assetcode=f'ASSET{i}',
                assetname=f'Test Asset {i}',
                client=cls.test_client,
                bu=cls.test_bu
            )
            cls.test_assets.append(asset)

        # Create test jobs (classic N+1 scenario)
        cls.test_jobs = []
        for i in range(20):
            job = Job.objects.create(
                jobcode=f'JOB{i}',
                jobname=f'Test Job {i}',
                client=cls.test_client,
                bu=cls.test_bu,
                asset=cls.test_assets[i % 10],  # Assign to assets
                assigned_to=cls.test_users[i % 10]  # Assign to users
            )
            cls.test_jobs.append(job)

    def setUp(self):
        """Set up test client for each test."""
        self.graphene_client = GrapheneClient(schema)
        self.mock_info = MagicMock()
        self.mock_info.context = MagicMock()

    def test_dataloader_middleware_configured(self):
        """
        Verify that DataLoader middleware is properly configured.

        This is a prerequisite for all performance optimizations.
        """
        from django.conf import settings

        middleware_list = settings.GRAPHENE['MIDDLEWARE']
        assert any('DataLoaderMiddleware' in m for m in middleware_list), \
            "❌ DataLoaderMiddleware not configured in GRAPHENE['MIDDLEWARE']"

    def test_people_by_id_loader_reduces_queries(self):
        """
        Test that PeopleByIdLoader reduces N+1 queries.

        Without DataLoader: N+1 queries (1 + N individual queries)
        With DataLoader: 2 queries (1 + 1 batch query)
        Expected reduction: >80%
        """
        # Create DataLoader registry
        registry = DataLoaderRegistry()
        people_loader = registry.get_loader(
            __import__('apps.api.graphql.dataloaders', fromlist=['PeopleByIdLoader']).PeopleByIdLoader
        )

        # Test WITHOUT DataLoader (N+1 pattern)
        with CaptureQueriesContext(connection) as ctx_without:
            people_ids = [user.id for user in self.test_users]
            results_without = []
            for person_id in people_ids:
                person = People.objects.get(id=person_id)
                results_without.append(person)

        queries_without = len(ctx_without.captured_queries)

        # Test WITH DataLoader (batched)
        with CaptureQueriesContext(connection) as ctx_with:
            import asyncio
            from promise import Promise

            # Simulate DataLoader batching
            promises = [people_loader.load(user.id) for user in self.test_users]
            # In real GraphQL, these would be batched automatically
            # For testing, we manually trigger the batch
            results_with = [p.get() if isinstance(p, Promise) else p for p in promises]

        queries_with = len(ctx_with.captured_queries)

        # Verify significant reduction
        reduction_percentage = ((queries_without - queries_with) / queries_without) * 100

        print(f"\n📊 PeopleByIdLoader Performance:")
        print(f"   Queries WITHOUT DataLoader: {queries_without}")
        print(f"   Queries WITH DataLoader: {queries_with}")
        print(f"   Reduction: {reduction_percentage:.1f}%")

        # Assert at least 50% reduction (usually >80%)
        assert queries_with < queries_without, \
            f"❌ DataLoader should reduce queries ({queries_with} >= {queries_without})"
        assert reduction_percentage >= 50, \
            f"❌ Expected >50% reduction, got {reduction_percentage:.1f}%"

    def test_jobs_by_asset_loader_prevents_n_plus_1(self):
        """
        Test that JobsByAssetLoader prevents N+1 queries when loading jobs for assets.

        Scenario: Loading jobs for 10 assets
        Without DataLoader: 11 queries (1 for assets + 10 for jobs)
        With DataLoader: 2 queries (1 for assets + 1 batched for all jobs)
        Expected reduction: >80%
        """
        from apps.api.graphql.dataloaders import JobsByAssetLoader

        registry = DataLoaderRegistry()
        jobs_loader = registry.get_loader(JobsByAssetLoader)

        # Test WITHOUT DataLoader
        with CaptureQueriesContext(connection) as ctx_without:
            results_without = []
            for asset in self.test_assets:
                jobs = list(Job.objects.filter(asset=asset))
                results_without.append((asset, jobs))

        queries_without = len(ctx_without.captured_queries)

        # Test WITH DataLoader
        with CaptureQueriesContext(connection) as ctx_with:
            from promise import Promise

            promises = [jobs_loader.load(asset.id) for asset in self.test_assets]
            results_with = [p.get() if isinstance(p, Promise) else p for p in promises]

        queries_with = len(ctx_with.captured_queries)

        reduction_percentage = ((queries_without - queries_with) / queries_without) * 100

        print(f"\n📊 JobsByAssetLoader Performance:")
        print(f"   Queries WITHOUT DataLoader: {queries_without}")
        print(f"   Queries WITH DataLoader: {queries_with}")
        print(f"   Reduction: {reduction_percentage:.1f}%")

        assert queries_with <= 2, \
            f"❌ Expected ≤2 queries with DataLoader, got {queries_with}"
        assert reduction_percentage >= 80, \
            f"❌ Expected >80% reduction, got {reduction_percentage:.1f}%"

    def test_nested_query_performance(self):
        """
        Test DataLoader performance with nested GraphQL queries.

        Query: Get all jobs with their assigned users and assets
        This is a classic nested query scenario prone to N+1 issues.
        """
        query = """
        query {
            all_jobs {
                id
                jobname
                assigned_to {
                    id
                    peoplename
                }
                asset {
                    id
                    assetname
                }
            }
        }
        """

        # Measure query count with DataLoader middleware
        with CaptureQueriesContext(connection) as ctx:
            result = self.graphene_client.execute(query, context=self.mock_info.context)

        query_count = len(ctx.captured_queries)

        print(f"\n📊 Nested Query Performance:")
        print(f"   Total queries: {query_count}")
        print(f"   Jobs queried: {len(self.test_jobs)}")
        print(f"   Queries per job: {query_count / len(self.test_jobs):.2f}")

        # With DataLoader, we should have roughly:
        # 1 query for jobs + 1 for people + 1 for assets = ~3 queries
        # Without DataLoader: 1 + 20 (people) + 20 (assets) = 41 queries
        assert query_count <= 5, \
            f"❌ Expected ≤5 queries with DataLoader, got {query_count}"

        # Verify no errors in result
        assert 'errors' not in result or result['errors'] is None, \
            f"❌ GraphQL query returned errors: {result.get('errors')}"

    def test_dataloader_caching_behavior(self):
        """
        Test that DataLoader caches results within a single request.

        Loading the same entity multiple times should only query once.
        """
        from apps.api.graphql.dataloaders import PeopleByIdLoader

        registry = DataLoaderRegistry()
        people_loader = registry.get_loader(PeopleByIdLoader)

        test_person_id = self.test_users[0].id

        with CaptureQueriesContext(connection) as ctx:
            from promise import Promise

            # Load the same person 5 times
            promises = [people_loader.load(test_person_id) for _ in range(5)]
            results = [p.get() if isinstance(p, Promise) else p for p in promises]

        query_count = len(ctx.captured_queries)

        print(f"\n📊 DataLoader Caching:")
        print(f"   Loads requested: 5")
        print(f"   Database queries: {query_count}")

        # Should only query once due to caching
        assert query_count == 1, \
            f"❌ Expected 1 query due to caching, got {query_count}"

        # All results should be the same instance
        assert all(r.id == test_person_id for r in results), \
            "❌ Not all results match requested person"

    def test_dataloader_batching_efficiency(self):
        """
        Test that DataLoader batches multiple loads into a single query.

        Loading 10 different people should result in 1 batched query,
        not 10 individual queries.
        """
        from apps.api.graphql.dataloaders import PeopleByIdLoader

        registry = DataLoaderRegistry()
        people_loader = registry.get_loader(PeopleByIdLoader)

        people_ids = [user.id for user in self.test_users]

        with CaptureQueriesContext(connection) as ctx:
            from promise import Promise

            # Load 10 different people
            promises = [people_loader.load(person_id) for person_id in people_ids]
            results = [p.get() if isinstance(p, Promise) else p for p in promises]

        query_count = len(ctx.captured_queries)

        print(f"\n📊 DataLoader Batching:")
        print(f"   People loaded: {len(people_ids)}")
        print(f"   Database queries: {query_count}")

        # Should batch into 1 query using WHERE id IN (...)
        assert query_count == 1, \
            f"❌ Expected 1 batched query, got {query_count}"

        # Verify all people loaded correctly
        assert len(results) == len(people_ids), \
            f"❌ Expected {len(people_ids)} results, got {len(results)}"

    def test_performance_benchmark_realistic_query(self):
        """
        Benchmark a realistic GraphQL query with multiple relationships.

        This simulates a real-world dashboard query that would suffer from N+1.
        """
        query = """
        query DashboardQuery {
            all_jobs {
                id
                jobname
                jobcode
                assigned_to {
                    id
                    peoplename
                    loginid
                }
                asset {
                    id
                    assetname
                    assetcode
                }
            }
            all_people {
                id
                peoplename
                groups {
                    id
                    name
                }
            }
        }
        """

        # Measure performance
        start_time = time.time()

        with CaptureQueriesContext(connection) as ctx:
            result = self.graphene_client.execute(query, context=self.mock_info.context)

        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        query_count = len(ctx.captured_queries)

        print(f"\n📊 Realistic Query Benchmark:")
        print(f"   Execution time: {execution_time:.2f}ms")
        print(f"   Database queries: {query_count}")
        print(f"   Jobs returned: {len(self.test_jobs)}")
        print(f"   People returned: {len(self.test_users)}")

        # With DataLoader, should have <10 queries for this complex query
        assert query_count < 10, \
            f"❌ Expected <10 queries, got {query_count}"

        # Should complete in reasonable time
        assert execution_time < 1000, \
            f"❌ Query too slow: {execution_time:.2f}ms"

        # Verify query succeeded
        assert 'errors' not in result or result['errors'] is None, \
            f"❌ Query returned errors: {result.get('errors')}"


@pytest.mark.performance
class TestDataLoaderEdgeCases(TestCase):
    """
    Test edge cases and error handling for DataLoader.
    """

    def test_dataloader_with_empty_results(self):
        """
        Test DataLoader behavior with empty result sets.
        """
        from apps.api.graphql.dataloaders import JobsByAssetLoader

        registry = DataLoaderRegistry()
        jobs_loader = registry.get_loader(JobsByAssetLoader)

        # Load jobs for non-existent asset
        result = jobs_loader.load(999999).get()

        # Should return empty list, not error
        assert isinstance(result, list), "❌ Should return list for empty result"
        assert len(result) == 0, "❌ Should return empty list"

    def test_dataloader_with_none_key(self):
        """
        Test DataLoader behavior with None as key.
        """
        from apps.api.graphql.dataloaders import PeopleByIdLoader

        registry = DataLoaderRegistry()
        people_loader = registry.get_loader(PeopleByIdLoader)

        # Load with None key should handle gracefully
        try:
            result = people_loader.load(None).get()
            # Should either return None or raise specific error
            assert result is None, "❌ Should return None for None key"
        except (TypeError, ValueError):
            # Acceptable to raise error for invalid key
            pass

    def test_dataloader_registry_cleanup(self):
        """
        Test that DataLoader registry properly cleans up after request.
        """
        registry = DataLoaderRegistry()

        # Create some loaders
        from apps.api.graphql.dataloaders import PeopleByIdLoader, AssetByIdLoader

        people_loader = registry.get_loader(PeopleByIdLoader)
        asset_loader = registry.get_loader(AssetByIdLoader)

        # Verify loaders exist
        assert len(registry.loaders) > 0, "❌ Loaders should be registered"

        # Clear registry (simulates end of request)
        registry.clear()

        # Verify cleanup
        assert len(registry.loaders) == 0, "❌ Loaders should be cleared"


# Performance reporting
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-s'])
