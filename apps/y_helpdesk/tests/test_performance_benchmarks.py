"""
Performance Benchmark Tests

Measures actual performance improvements from ticket system refactoring:
- Database index effectiveness
- N+1 query elimination impact
- Caching performance gains
- Service layer efficiency
- API response time improvements

Usage: python manage.py test apps.y_helpdesk.tests.test_performance_benchmarks
"""

import time
import statistics
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from django.db import connection, reset_queries
from django.core.cache import cache

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.y_helpdesk.models.ticket_workflow import TicketWorkflow
from apps.y_helpdesk.utils.query_monitor import monitor_queries, compare_query_performance
from apps.y_helpdesk.serializers.unified_ticket_serializer import serialize_for_web_api

from apps.peoples.models import People, Pgroup
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist


class TicketPerformanceBenchmarkTestCase(TestCase):
    """Benchmark tests for ticket system performance improvements."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for performance benchmarking."""
        super().setUpClass()

        # Create test infrastructure
        cls.client_bt = Bt.objects.create(buname='Perf Client', bucode='PC001')
        cls.bu = Bt.objects.create(buname='Perf BU', bucode='PB001', client=cls.client_bt)

        # Create test users
        cls.users = []
        for i in range(10):
            user = People.objects.create(
                peoplename=f'User {i}',
                peoplecode=f'USR{i:03d}',
                loginid=f'user{i}',
                email=f'user{i}@test.com'
            )
            cls.users.append(user)

        # Create test groups
        cls.groups = []
        for i in range(3):
            group = Pgroup.objects.create(
                groupname=f'Group {i}',
                groupcode=f'GRP{i:03d}'
            )
            cls.groups.append(group)

        # Create ticket categories
        cls.categories = []
        for i in range(5):
            category = TypeAssist.objects.create(
                taname=f'Category {i}',
                tacode=f'CAT{i:03d}',
                bu=cls.bu,
                client=cls.client_bt
            )
            cls.categories.append(category)

        # Create test tickets (larger dataset for realistic benchmarks)
        cls.tickets = []
        for i in range(100):
            ticket = Ticket.objects.create(
                ticketno=f'PERF{i:05d}',
                ticketdesc=f'Performance test ticket {i}',
                status='NEW' if i % 4 == 0 else 'OPEN' if i % 4 == 1 else 'RESOLVED' if i % 4 == 2 else 'CLOSED',
                priority='HIGH' if i % 3 == 0 else 'MEDIUM' if i % 3 == 1 else 'LOW',
                bu=cls.bu,
                client=cls.client_bt,
                ticketcategory=cls.categories[i % len(cls.categories)],
                assignedtopeople=cls.users[i % len(cls.users)],
                assignedtogroup=cls.groups[i % len(cls.groups)],
                cuser=cls.users[0],
                muser=cls.users[0]
            )
            cls.tickets.append(ticket)

            # Create workflow for some tickets
            if i % 3 == 0:
                TicketWorkflow.objects.create(
                    ticket=ticket,
                    escalation_level=i % 4,
                    is_escalated=i % 4 > 0,
                    workflow_status='ACTIVE',
                    bu=cls.bu,
                    client=cls.client_bt,
                    cuser=cls.users[0]
                )

    def setUp(self):
        """Set up for each test."""
        # Clear cache before each test
        cache.clear()
        reset_queries()

    @override_settings(DEBUG=True)
    def test_ticket_list_query_performance(self):
        """Benchmark ticket list query performance."""
        def old_method():
            """Simulate old query method without optimizations."""
            tickets = Ticket.objects.filter(bu=self.bu)
            result = []
            for ticket in tickets:
                # This would cause N+1 queries in old implementation
                result.append({
                    'id': ticket.id,
                    'ticketno': ticket.ticketno,
                    'status': ticket.status,
                    'bu_name': ticket.bu.buname if ticket.bu else None,
                    'category_name': ticket.ticketcategory.taname if ticket.ticketcategory else None,
                    'assignee_name': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else None,
                })
            return result

        def new_method():
            """New optimized query method."""
            tickets = Ticket.objects.filter(bu=self.bu).select_related(
                'bu', 'ticketcategory', 'assignedtopeople'
            ).prefetch_related('workflow')

            return serialize_for_web_api(list(tickets), self.users[0])

        # Compare performance
        comparison = compare_query_performance(
            old_method, new_method, "ticket_list_optimization", iterations=3
        )

        # Verify significant improvements
        self.assertGreater(comparison['improvements']['query_reduction_percent'], 50)
        self.assertGreater(comparison['improvements']['time_improvement_percent'], 30)
        self.assertIn(comparison['improvements']['performance_rating'], ['EXCELLENT', 'GOOD'])

        print(f"\n📊 Ticket List Performance Improvement:")
        print(f"   Query reduction: {comparison['improvements']['query_reduction_percent']:.1f}%")
        print(f"   Time improvement: {comparison['improvements']['time_improvement_percent']:.1f}%")
        print(f"   Rating: {comparison['improvements']['performance_rating']}")

    @override_settings(DEBUG=True)
    def test_dashboard_stats_performance(self):
        """Benchmark dashboard statistics query performance."""
        iterations = 5
        times = []

        for i in range(iterations):
            reset_queries()
            start_time = time.time()

            # Execute dashboard stats query
            stats = Ticket.objects.filter(
                bu=self.bu,
                cdtz__date__gte=timezone.now().date()
            ).aggregate(
                new_count=models.Count(models.Case(
                    models.When(status='NEW', then=1)
                )),
                open_count=models.Count(models.Case(
                    models.When(status='OPEN', then=1)
                ))
            )

            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            times.append(execution_time)

            query_count = len(connection.queries)

        # Calculate statistics
        avg_time = statistics.mean(times)
        avg_queries = query_count  # Should be consistent

        # Performance assertions
        self.assertLessEqual(avg_time, 100)  # Should be under 100ms
        self.assertLessEqual(avg_queries, 3)  # Should be very few queries

        print(f"\n📊 Dashboard Stats Performance:")
        print(f"   Average time: {avg_time:.2f}ms")
        print(f"   Query count: {avg_queries}")

    def test_cache_performance_impact(self):
        """Measure cache performance impact."""
        from apps.y_helpdesk.services.ticket_cache_service import cache_ticket_list

        cache_key_params = {
            'bu_id': self.bu.id,
            'client_id': self.client_bt.id,
            'from': timezone.now().date().isoformat(),
            'to': timezone.now().date().isoformat()
        }

        def load_ticket_data():
            return list(Ticket.objects.filter(bu=self.bu).values(
                'id', 'ticketno', 'status'
            ))

        # Measure cache miss (first load)
        start_time = time.time()
        data1 = cache_ticket_list(cache_key_params, load_ticket_data)
        cache_miss_time = (time.time() - start_time) * 1000

        # Measure cache hit (second load)
        start_time = time.time()
        data2 = cache_ticket_list(cache_key_params, load_ticket_data)
        cache_hit_time = (time.time() - start_time) * 1000

        # Verify cache effectiveness
        self.assertEqual(data1, data2)  # Same data
        self.assertLess(cache_hit_time, cache_miss_time)  # Cache hit should be faster

        cache_improvement = ((cache_miss_time - cache_hit_time) / cache_miss_time) * 100

        print(f"\n📊 Cache Performance Impact:")
        print(f"   Cache miss time: {cache_miss_time:.2f}ms")
        print(f"   Cache hit time: {cache_hit_time:.2f}ms")
        print(f"   Performance improvement: {cache_improvement:.1f}%")

        # Cache hit should be at least 50% faster
        self.assertGreater(cache_improvement, 50)

    def test_unified_serializer_performance(self):
        """Benchmark unified serializer performance."""
        tickets = list(Ticket.objects.filter(bu=self.bu)[:20])

        # Measure serialization performance
        iterations = 10
        times = []

        for i in range(iterations):
            start_time = time.time()

            # Use unified serializer
            data = serialize_for_web_api(tickets, self.users[0])

            end_time = time.time()
            times.append((end_time - start_time) * 1000)

        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)

        # Performance assertions
        self.assertLessEqual(avg_time, 50)  # Should serialize quickly
        self.assertEqual(len(data), len(tickets))  # All tickets serialized

        print(f"\n📊 Unified Serializer Performance:")
        print(f"   Average time: {avg_time:.2f}ms for {len(tickets)} tickets")
        print(f"   Min/Max: {min_time:.2f}ms / {max_time:.2f}ms")

    def test_state_machine_validation_performance(self):
        """Benchmark state machine validation performance."""
        from apps.y_helpdesk.services.ticket_state_machine import (
            TicketStateMachine, TransitionContext, TransitionReason
        )

        # Test transition validation performance
        iterations = 1000
        start_time = time.time()

        for i in range(iterations):
            context = TransitionContext(
                user=self.users[0],
                reason=TransitionReason.USER_ACTION,
                comments="Test transition"
            )

            result = TicketStateMachine.validate_transition('NEW', 'OPEN', context)
            self.assertTrue(result.is_valid)

        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        avg_time_per_validation = total_time / iterations

        # Should be very fast
        self.assertLessEqual(avg_time_per_validation, 1.0)  # Under 1ms per validation

        print(f"\n📊 State Machine Performance:")
        print(f"   {iterations} validations in {total_time:.2f}ms")
        print(f"   Average per validation: {avg_time_per_validation:.3f}ms")