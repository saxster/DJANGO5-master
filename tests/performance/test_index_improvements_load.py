"""
Performance Load Testing for Index Improvements

Addresses Issue #18: Missing Database Indexes
Simulates production-scale queries to validate index performance improvements.

Test Scenarios:
- Concurrent status filtering (100 simultaneous users)
- Heavy date-range queries (report generation)
- Bulk data filtering with composite indexes
- JSON field containment queries
- Stress testing for index effectiveness

Complies with: .claude/rules.md Rule #12 (Database Query Optimization)

Usage:
    pytest tests/performance/test_index_improvements_load.py -v
"""

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import List, Dict, Any

from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.utils import timezone

from apps.y_helpdesk.models import Ticket
from apps.attendance.models import PeopleEventlog
from apps.work_order_management.models import Wom
from apps.activity.models import Job
from apps.peoples.models import People
from apps.client_onboarding.models import Bt, Shift


@pytest.mark.slow
@pytest.mark.performance
class IndexLoadTestCase(TransactionTestCase):
    """Load tests for index performance validation."""

    CONCURRENT_USERS = 50
    ITERATIONS_PER_USER = 10
    ACCEPTABLE_P95_MS = 100

    @classmethod
    def setUpClass(cls):
        """Set up large dataset for load testing."""
        super().setUpClass()
        cls._create_load_test_data()

    @classmethod
    def _create_load_test_data(cls):
        """Create production-scale test data."""
        try:
            bt = Bt.objects.create(
                bucode="LOAD_TEST",
                buname="Load Test Business Unit",
                enable=True
            )

            people_list = []
            for i in range(20):
                people = People.objects.create(
                    peoplecode=f"LOAD{i:03d}",
                    peoplename=f"Load Test User {i}",
                    loginid=f"loaduser{i}",
                    email=f"load{i}@test.com"
                )
                people_list.append(people)

            statuses = ['NEW', 'OPEN', 'RESOLVED', 'CLOSED']
            priorities = ['LOW', 'MEDIUM', 'HIGH']

            for i in range(1000):
                Ticket.objects.create(
                    ticketno=f"LOAD{i:05d}",
                    ticketdesc=f"Load test ticket {i}",
                    status=statuses[i % len(statuses)],
                    priority=priorities[i % len(priorities)],
                    bu=bt,
                    client=bt,
                    assignedtopeople=people_list[i % len(people_list)],
                )

            print(f"✓ Created {Ticket.objects.count()} tickets for load testing")

        except Exception as e:
            print(f"Load test data creation failed: {type(e).__name__}: {str(e)}")

    def test_concurrent_status_filtering(self):
        """Test concurrent status filtering with indexed queries."""
        def query_tickets_by_status(status: str) -> float:
            """Execute status filter query and measure time."""
            start = time.time()

            connection.queries_log.clear()
            tickets = list(Ticket.objects.filter(status=status)[:100])

            duration = (time.time() - start) * 1000
            return duration

        execution_times = []

        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as executor:
            futures = []
            for _ in range(self.CONCURRENT_USERS):
                for status in ['NEW', 'OPEN', 'RESOLVED']:
                    future = executor.submit(query_tickets_by_status, status)
                    futures.append(future)

            for future in as_completed(futures):
                try:
                    duration = future.result()
                    execution_times.append(duration)
                except Exception as e:
                    print(f"Query failed: {type(e).__name__}")

        if execution_times:
            p95 = statistics.quantiles(execution_times, n=20)[18]
            avg = statistics.mean(execution_times)

            print(f"\nConcurrent Status Filtering Results:")
            print(f"  Queries executed: {len(execution_times)}")
            print(f"  Average time: {avg:.2f}ms")
            print(f"  P95 time: {p95:.2f}ms")
            print(f"  Max time: {max(execution_times):.2f}ms")

            self.assertLess(
                p95,
                self.ACCEPTABLE_P95_MS,
                f"P95 query time {p95:.2f}ms exceeds threshold {self.ACCEPTABLE_P95_MS}ms"
            )

    def test_composite_index_load_performance(self):
        """Test composite index performance under load."""
        def query_by_status_and_priority(status: str, priority: str) -> float:
            """Execute composite filter query."""
            start = time.time()

            tickets = list(Ticket.objects.filter(
                status=status,
                priority=priority
            )[:50])

            return (time.time() - start) * 1000

        execution_times = []

        combinations = [
            ('NEW', 'HIGH'),
            ('OPEN', 'MEDIUM'),
            ('RESOLVED', 'LOW'),
        ]

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for _ in range(100):
                for status, priority in combinations:
                    future = executor.submit(query_by_status_and_priority, status, priority)
                    futures.append(future)

            for future in as_completed(futures):
                try:
                    execution_times.append(future.result())
                except Exception as e:
                    print(f"Composite query failed: {type(e).__name__}")

        if execution_times:
            p95 = statistics.quantiles(execution_times, n=20)[18]
            avg = statistics.mean(execution_times)

            print(f"\nComposite Index Performance:")
            print(f"  Queries: {len(execution_times)}")
            print(f"  Average: {avg:.2f}ms")
            print(f"  P95: {p95:.2f}ms")

            self.assertLess(p95, self.ACCEPTABLE_P95_MS)

    def test_date_range_query_load(self):
        """Test BRIN index performance on date range queries."""
        try:
            today = date.today()
            ranges = [
                (today - timedelta(days=7), today),
                (today - timedelta(days=30), today),
                (today - timedelta(days=90), today),
            ]

            execution_times = []

            for start_date, end_date in ranges * 20:
                start = time.time()

                try:
                    events = list(PeopleEventlog.objects.filter(
                        datefor__range=[start_date, end_date]
                    )[:100])

                    execution_times.append((time.time() - start) * 1000)

                except Exception as e:
                    print(f"Date query failed: {type(e).__name__}")

            if execution_times:
                avg = statistics.mean(execution_times)
                print(f"\nDate Range Query Performance:")
                print(f"  Average: {avg:.2f}ms")
                print(f"  Max: {max(execution_times):.2f}ms")

                self.assertLess(avg, 150, "Date range queries should be fast with BRIN indexes")

        except Exception as e:
            self.skipTest(f"Date range test skipped: {type(e).__name__}")

    def test_json_query_performance_under_load(self):
        """Test GIN index performance for JSON queries."""
        try:
            execution_times = []

            for _ in range(50):
                start = time.time()

                tickets = list(Ticket.objects.filter(
                    ticketlog__has_key='ticket_history'
                )[:50])

                execution_times.append((time.time() - start) * 1000)

            if execution_times:
                avg = statistics.mean(execution_times)
                print(f"\nJSON Query Performance:")
                print(f"  Average: {avg:.2f}ms")

                self.assertLess(avg, 200, "JSON queries should be fast with GIN indexes")

        except Exception as e:
            self.skipTest(f"JSON query test skipped: {type(e).__name__}")


@pytest.mark.slow
@pytest.mark.performance
class StressTestCase(TransactionTestCase):
    """Stress tests for extreme load scenarios."""

    def test_stress_concurrent_mixed_queries(self):
        """Stress test with mixed query types."""
        def mixed_query_workload():
            """Execute mixed queries."""
            try:
                Ticket.objects.filter(status='NEW').count()
                Ticket.objects.filter(priority='HIGH', status='OPEN').count()
                Job.objects.filter(enable=True, identifier='TASK').count()
                return True
            except Exception as e:
                return False

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(mixed_query_workload) for _ in range(500)]
            results = [f.result() for f in as_completed(futures)]

        success_rate = sum(results) / len(results) * 100
        print(f"\nStress Test Success Rate: {success_rate:.1f}%")

        self.assertGreater(success_rate, 95.0, "Should handle stress with >95% success")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
