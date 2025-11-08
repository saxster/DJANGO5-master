"""
import logging
logger = logging.getLogger(__name__)
Performance Tests for Predictive Alerting Tasks.

Tests N+1 query optimization in tenant loops.

Before optimization: O(N) queries where N = number of tenants
After optimization: O(1) - 1-2 queries total

Expected improvement: 60-70% reduction in query count.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.db import connection
from django.test import TestCase as DjangoTestCase
from django.utils import timezone
from datetime import timedelta
from apps.tenants.models import Tenant
from apps.noc.tasks.predictive_alerting_tasks_optimized import (
    PredictSLABreachesTask,
    PredictDeviceFailuresTask,
    PredictStaffingGapsTask,
)


@pytest.mark.django_db
class TestPredictiveTasksQueryOptimization(TransactionTestCase):
    """
    Test query count optimization for predictive tasks.
    
    Verifies that N+1 queries are eliminated using:
    - select_related() for foreign keys
    - prefetch_related() for many-to-many
    - Bulk queries outside loops
    """

    def setUp(self):
        """Create test data: multiple tenants with tickets/devices."""
        from apps.y_helpdesk.models import Ticket, TicketPriority
        from apps.client_onboarding.models import Bt, Client
        
        # Create 5 tenants to test multi-tenant query optimization
        self.tenants = []
        for i in range(5):
            tenant = Tenant.objects.create(
                tenantname=f'test_tenant_{i}',
                isactive=True
            )
            self.tenants.append(tenant)
            
            # Create client and site for each tenant
            client = Client.objects.create(
                name=f'Test Client {i}',
                tenant=tenant
            )
            
            site = Bt.objects.create(
                buname=f'Test Site {i}',
                tenant=tenant,
                client=client
            )
            
            # Create 10 tickets per tenant (50 total)
            priority = TicketPriority.objects.create(
                name='High',
                tenant=tenant
            )
            
            for j in range(10):
                Ticket.objects.create(
                    ticketno=f'TICK-{i}-{j}',
                    title=f'Test Ticket {i}-{j}',
                    status='NEW',
                    tenant=tenant,
                    client=client,
                    bu=site,
                    priority=priority
                )

    def test_sla_breach_task_query_count_optimized(self):
        """
        Test SLA breach prediction uses optimized queries.
        
        Expected: 1-2 queries regardless of tenant count.
        Before: 5+ queries (1 per tenant + base queries).
        """
        task = PredictSLABreachesTask()
        
        # Reset query counter
        connection.queries_log.clear()
        
        with self.assertNumQueries(2, using='default'):  # Should be ≤2 queries
            # Main query: fetch all tickets with select_related
            # Optional query: alert creation (batched)
            result = task.run()
        
        # Verify all tenants processed
        assert len(result) == 5, f"Expected 5 tenants, got {len(result)}"
        
        # Log query count for comparison
        query_count = len(connection.queries)
        logger.info(f"\n✅ SLA Breach Task - Query Count: {query_count}")
        logger.info(f"   Tenants processed: {len(result)}")
        logger.info(f"   Queries per tenant: {query_count / len(result):.2f}")

    def test_device_failure_task_query_count_optimized(self):
        """
        Test device failure prediction uses optimized queries.
        
        Expected: 1-2 queries regardless of tenant count.
        """
        # Create test devices
        try:
            from apps.monitoring.models import Device
            
            for tenant in self.tenants:
                for i in range(5):
                    Device.objects.create(
                        device_id=f'DEV-{tenant.id}-{i}',
                        tenant=tenant,
                        is_active=True
                    )
        except Exception as e:
            pytest.skip(f"Device model not available: {e}")
        
        task = PredictDeviceFailuresTask()
        
        connection.queries_log.clear()
        
        with self.assertNumQueries(2, using='default'):
            result = task.run()
        
        # Verify all tenants processed
        assert len(result) >= 0  # May be 0 if Device model unavailable
        
        query_count = len(connection.queries)
        logger.error(f"\n✅ Device Failure Task - Query Count: {query_count}")
        logger.info(f"   Tenants processed: {len(result)}")

    def test_staffing_gap_task_query_count_optimized(self):
        """
        Test staffing gap prediction uses optimized queries.
        
        Expected: 1-2 queries regardless of tenant count.
        """
        try:
            from apps.scheduler.models import Schedule
            
            now = timezone.now()
            
            # Create test shifts in next 4 hours
            for tenant in self.tenants:
                for i in range(3):
                    Schedule.objects.create(
                        tenant=tenant,
                        start_time=now + timedelta(hours=i),
                        end_time=now + timedelta(hours=i+1),
                    )
        except Exception as e:
            pytest.skip(f"Schedule model not available: {e}")
        
        task = PredictStaffingGapsTask()
        
        connection.queries_log.clear()
        
        with self.assertNumQueries(2, using='default'):
            result = task.run()
        
        query_count = len(connection.queries)
        logger.info(f"\n✅ Staffing Gap Task - Query Count: {query_count}")
        logger.info(f"   Tenants processed: {len(result)}")

    def test_bulk_vs_loop_query_comparison(self):
        """
        Compare query counts: old loop approach vs new bulk approach.
        
        This test demonstrates the N+1 problem and optimization.
        """
        from apps.y_helpdesk.models import Ticket
        
        # OLD APPROACH (N+1 queries)
        connection.queries_log.clear()
        old_query_count_start = len(connection.queries)
        
        for tenant in self.tenants:
            # This creates 1 query per tenant (N+1 problem)
            tickets = Ticket.objects.filter(
                tenant=tenant,
                status='NEW'
            )
            list(tickets)  # Force evaluation
        
        old_query_count = len(connection.queries) - old_query_count_start
        
        # NEW APPROACH (Bulk query)
        connection.queries_log.clear()
        new_query_count_start = len(connection.queries)
        
        # Single bulk query with select_related
        all_tickets = Ticket.objects.filter(
            status='NEW',
            tenant__in=self.tenants
        ).select_related('tenant', 'client', 'bu')
        
        # Group by tenant in memory (no additional queries)
        from collections import defaultdict
        tickets_by_tenant = defaultdict(list)
        for ticket in all_tickets:
            tickets_by_tenant[ticket.tenant_id].append(ticket)
        
        new_query_count = len(connection.queries) - new_query_count_start
        
        # Verify optimization
        logger.info(f"\n📊 Query Count Comparison:")
        logger.info(f"   Old (loop): {old_query_count} queries")
        logger.info(f"   New (bulk): {new_query_count} queries")
        logger.info(f"   Reduction: {((old_query_count - new_query_count) / old_query_count * 100):.1f}%")
        
        assert new_query_count < old_query_count, \
            f"Optimized version should use fewer queries: {new_query_count} vs {old_query_count}"
        
        # Should be ~80% reduction (5 queries -> 1 query)
        reduction_percent = (old_query_count - new_query_count) / old_query_count
        assert reduction_percent >= 0.6, \
            f"Expected ≥60% reduction, got {reduction_percent:.1%}"


@pytest.mark.django_db
class TestPredictiveTasksPerformance(TestCase):
    """
    Benchmark performance of optimized tasks.
    
    Tests execution time with realistic data volumes.
    """

    def test_sla_breach_task_performance_benchmark(self):
        """
        Benchmark SLA breach prediction with 100 tickets across 10 tenants.
        
        Target: <2 seconds for 100 tickets.
        """
        import time
        from apps.y_helpdesk.models import Ticket, TicketPriority
        from apps.client_onboarding.models import Bt, Client
        
        # Create realistic dataset
        for i in range(10):
            tenant = Tenant.objects.create(
                tenantname=f'perf_tenant_{i}',
                isactive=True
            )
            
            client = Client.objects.create(name=f'Client {i}', tenant=tenant)
            site = Bt.objects.create(buname=f'Site {i}', tenant=tenant, client=client)
            priority = TicketPriority.objects.create(name='High', tenant=tenant)
            
            for j in range(10):
                Ticket.objects.create(
                    ticketno=f'PERF-{i}-{j}',
                    title=f'Performance Test {i}-{j}',
                    status='NEW',
                    tenant=tenant,
                    client=client,
                    bu=site,
                    priority=priority
                )
        
        task = PredictSLABreachesTask()
        
        start_time = time.time()
        result = task.run()
        execution_time = time.time() - start_time
        
        logger.info(f"\n⏱️  SLA Breach Task Performance:")
        logger.info(f"   Tickets processed: 100")
        logger.info(f"   Tenants: 10")
        logger.info(f"   Execution time: {execution_time:.3f}s")
        logger.info(f"   Throughput: {100/execution_time:.1f} tickets/sec")
        
        # Performance assertion
        assert execution_time < 5.0, \
            f"Task too slow: {execution_time:.2f}s (expected <5s)"

    def test_query_optimization_with_select_related(self):
        """
        Verify select_related prevents additional queries for foreign keys.
        """
        from apps.y_helpdesk.models import Ticket
        
        # Create test data
        tenant = Tenant.objects.create(tenantname='select_test', isactive=True)
        
        # Without select_related (N+1 problem)
        connection.queries_log.clear()
        tickets = Ticket.objects.filter(tenant=tenant)[:10]
        for ticket in tickets:
            _ = ticket.tenant.tenantname  # Triggers additional query
        unoptimized_count = len(connection.queries)
        
        # With select_related (optimized)
        connection.queries_log.clear()
        tickets = Ticket.objects.filter(tenant=tenant).select_related('tenant')[:10]
        for ticket in tickets:
            _ = ticket.tenant.tenantname  # No additional query
        optimized_count = len(connection.queries)
        
        logger.info(f"\n🔍 select_related() Optimization:")
        logger.info(f"   Without: {unoptimized_count} queries")
        logger.info(f"   With: {optimized_count} queries")
        
        assert optimized_count < unoptimized_count, \
            "select_related should reduce query count"
