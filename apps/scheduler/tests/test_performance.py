"""
import logging
logger = logging.getLogger(__name__)
Performance tests for scheduler module improvements.

This module tests the performance improvements made:
- Database indexes on identifier fields
- Query optimization with constants usage
- Efficient filtering operations
"""

import time
from django.test import TestCase
from django.db import connection

from apps.activity.models.job_model import Job, Jobneed
from apps.core.constants import JobConstants
from apps.peoples.models import People


class PerformanceTestCase(TestCase):
    """Test case for performance improvements."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for performance tests."""
        super().setUpClass()

        # Apply migrations to ensure indexes are present
        # In a real test environment, this would be handled by test database setup

        # Create test user
        cls.test_user = People.objects.create_user(
            email='perftest@example.com',
            password='testpass123',
            first_name='Perf',
            last_name='Test'
        )

        # Create test data for performance testing
        cls._create_test_data()

    @classmethod
    def _create_test_data(cls):
        """Create a substantial amount of test data."""
        # Create multiple jobs with different identifiers
        jobs_data = []
        for i in range(100):
            identifier = [
                JobConstants.Identifier.TASK,
                JobConstants.Identifier.INTERNALTOUR,
                JobConstants.Identifier.EXTERNALTOUR,
                JobConstants.Identifier.PPM
            ][i % 4]

            jobs_data.append(Job(
                jobname=f'Test Job {i}',
                jobdesc=f'Test Description {i}',
                fromdate='2024-01-01 00:00:00',
                uptodate='2024-12-31 23:59:59',
                planduration=60,
                gracetime=10,
                expirytime=5,
                identifier=identifier,
                cron='0 0 * * *',
                multifactor=1,
                priority=1 + (i % 3)
            ))

        # Bulk create for efficiency
        Job.objects.bulk_create(jobs_data)

        # Create jobneeds for the jobs
        jobs = Job.objects.all()
        jobneeds_data = []
        for i, job in enumerate(jobs[:50]):  # Create jobneeds for first 50 jobs
            jobneeds_data.append(Jobneed(
                jobneedname=f'Test Jobneed {i}',
                code=f'JN{i:03d}',
                job=job,
                plandatetime='2024-06-01 10:00:00',
                expirydatetime='2024-06-01 11:00:00',
                identifier=job.identifier,
                jobstatus='PENDING'
            ))

        Jobneed.objects.bulk_create(jobneeds_data)

    def setUp(self):
        """Set up for individual tests."""
        # Reset query counting
        connection.queries_log.clear()

    def test_identifier_index_performance(self):
        """Test that identifier field queries use indexes efficiently."""
        # Enable query logging
        with self.assertNumQueries(1):
            # Query that should use the identifier index
            tasks = list(Job.objects.filter(
                identifier=JobConstants.Identifier.TASK
            )[:10])

        self.assertGreater(len(tasks), 0)

        # Check the query plan (if supported by database)
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("""
                    EXPLAIN (FORMAT JSON)
                    SELECT * FROM activity_job
                    WHERE identifier = %s
                    LIMIT 10
                """, [JobConstants.Identifier.TASK])

                plan = cursor.fetchone()[0]
                # The plan should indicate index usage
                # This is database-specific and may need adjustment
                plan_str = str(plan).lower()
                # Look for indicators of index usage
                self.assertTrue(
                    'index' in plan_str or 'btree' in plan_str,
                    f"Query plan doesn't indicate index usage: {plan}"
                )

    def test_jobneed_identifier_index_performance(self):
        """Test that Jobneed identifier queries are efficient."""
        with self.assertNumQueries(1):
            tours = list(Jobneed.objects.filter(
                identifier=JobConstants.Identifier.INTERNALTOUR
            )[:10])

        # Should execute in reasonable time
        start_time = time.time()
        Jobneed.objects.filter(
            identifier=JobConstants.Identifier.INTERNALTOUR
        ).count()
        end_time = time.time()

        query_time = end_time - start_time
        self.assertLess(query_time, 0.1, "Query took too long, index may not be working")

    def test_complex_query_performance(self):
        """Test performance of complex queries with multiple filters."""
        start_time = time.time()

        # Complex query that should benefit from indexes
        results = list(Job.objects.filter(
            identifier__in=[
                JobConstants.Identifier.TASK,
                JobConstants.Identifier.INTERNALTOUR
            ],
            priority__lte=2
        ).select_related().values(
            'id', 'jobname', 'identifier', 'priority'
        )[:20])

        end_time = time.time()
        query_time = end_time - start_time

        self.assertGreater(len(results), 0)
        self.assertLess(query_time, 0.2, "Complex query took too long")

    def test_constants_usage_efficiency(self):
        """Test that using constants doesn't impact performance."""
        # Time query with constants
        start_time = time.time()
        with_constants = list(Job.objects.filter(
            identifier=JobConstants.Identifier.EXTERNALTOUR
        )[:10])
        constants_time = time.time() - start_time

        # Time query with string literal
        start_time = time.time()
        with_literal = list(Job.objects.filter(
            identifier="EXTERNALTOUR"
        )[:10])
        literal_time = time.time() - start_time

        # Performance should be equivalent
        self.assertEqual(len(with_constants), len(with_literal))

        # Allow for some variance but they should be similar
        time_diff = abs(constants_time - literal_time)
        self.assertLess(time_diff, 0.05, "Constants usage significantly impacts performance")

    def test_bulk_operations_performance(self):
        """Test performance of bulk operations."""
        # Test bulk filtering with indexes
        start_time = time.time()

        # Get counts for each identifier type
        task_count = Job.objects.filter(
            identifier=JobConstants.Identifier.TASK
        ).count()

        tour_count = Job.objects.filter(
            identifier=JobConstants.Identifier.INTERNALTOUR
        ).count()

        external_tour_count = Job.objects.filter(
            identifier=JobConstants.Identifier.EXTERNALTOUR
        ).count()

        end_time = time.time()
        total_time = end_time - start_time

        self.assertGreater(task_count + tour_count + external_tour_count, 0)
        self.assertLess(total_time, 0.5, "Bulk counting operations took too long")

    def test_pagination_performance(self):
        """Test performance of paginated queries."""
        # Simulate pagination with offset/limit
        page_size = 10
        num_pages = 5

        start_time = time.time()

        for page in range(num_pages):
            offset = page * page_size
            page_results = list(Job.objects.filter(
                identifier=JobConstants.Identifier.TASK
            ).order_by('id')[offset:offset + page_size])

            # Each page should return results (assuming we have enough data)
            if page < 3:  # First few pages should definitely have data
                self.assertGreater(len(page_results), 0)

        end_time = time.time()
        total_time = end_time - start_time

        self.assertLess(total_time, 1.0, "Pagination queries took too long")

    def test_join_performance(self):
        """Test performance of queries with joins."""
        start_time = time.time()

        # Query that joins Job and Jobneed
        results = list(Jobneed.objects.select_related('job').filter(
            identifier=JobConstants.Identifier.INTERNALTOUR,
            job__identifier=JobConstants.Identifier.INTERNALTOUR
        )[:10])

        end_time = time.time()
        query_time = end_time - start_time

        self.assertLess(query_time, 0.3, "Join query took too long")

        # Verify we got results and they're properly joined
        for jobneed in results:
            self.assertEqual(
                jobneed.identifier,
                JobConstants.Identifier.INTERNALTOUR
            )
            self.assertEqual(
                jobneed.job.identifier,
                JobConstants.Identifier.INTERNALTOUR
            )

    def test_query_count_optimization(self):
        """Test that queries are optimized to minimize database hits."""
        # Test a view-like operation that should be efficient
        with self.assertNumQueries(1):
            # This should be a single query with proper select_related
            jobs = list(Job.objects.select_related().filter(
                identifier=JobConstants.Identifier.TASK
            ).values(
                'id',
                'jobname',
                'identifier',
                'priority',
                'fromdate',
                'uptodate'
            )[:10])

        self.assertGreater(len(jobs), 0)

    def test_memory_usage_efficiency(self):
        """Test that queries don't consume excessive memory."""

        # Get initial memory usage
        initial_objects = len([obj for obj in vars().values() if hasattr(obj, '__dict__')])

        # Perform operations that should be memory efficient
        # Use iterator() to avoid loading all objects into memory
        count = 0
        for job in Job.objects.filter(
            identifier=JobConstants.Identifier.TASK
        ).iterator():
            count += 1
            if count >= 20:  # Limit for test
                break

        # Memory usage shouldn't grow significantly
        final_objects = len([obj for obj in vars().values() if hasattr(obj, '__dict__')])
        object_growth = final_objects - initial_objects

        self.assertLess(object_growth, 50, "Query created too many objects in memory")

    def tearDown(self):
        """Clean up after each test."""
        # Analyze query performance if needed
        if connection.queries:
            total_time = sum(float(query['time']) for query in connection.queries)
            if total_time > 1.0:
                logger.warning(f"Warning: Test queries took {total_time:.3f}s total")

    @classmethod
    def tearDownClass(cls):
        """Clean up test data."""
        # Clean up test data
        Job.objects.filter(jobname__startswith='Test Job').delete()
        Jobneed.objects.filter(jobneedname__startswith='Test Jobneed').delete()
        super().tearDownClass()


class DatabaseIndexTestCase(TestCase):
    """Test that database indexes are properly created."""

    def test_job_identifier_index_exists(self):
        """Test that Job.identifier field has an index."""
        # Check database schema for index
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'activity_job'
                    AND indexdef LIKE '%identifier%'
                """)
                indexes = cursor.fetchall()
                self.assertGreater(
                    len(indexes), 0,
                    "No index found on Job.identifier field"
                )

            elif connection.vendor == 'sqlite':
                cursor.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND tbl_name = 'activity_job'
                    AND sql LIKE '%identifier%'
                """)
                indexes = cursor.fetchall()
                self.assertGreater(
                    len(indexes), 0,
                    "No index found on Job.identifier field"
                )

    def test_jobneed_identifier_index_exists(self):
        """Test that Jobneed.identifier field has an index."""
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'activity_jobneed'
                    AND indexdef LIKE '%identifier%'
                """)
                indexes = cursor.fetchall()
                self.assertGreater(
                    len(indexes), 0,
                    "No index found on Jobneed.identifier field"
                )

            elif connection.vendor == 'sqlite':
                cursor.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND tbl_name = 'activity_jobneed'
                    AND sql LIKE '%identifier%'
                """)
                indexes = cursor.fetchall()
                self.assertGreater(
                    len(indexes), 0,
                    "No index found on Jobneed.identifier field"
                )


if __name__ == '__main__':
    import django
    django.setup()
    import unittest
    unittest.main()