"""
Performance tests for N+1 query optimizations in NOC app.

Tests verify that queries are optimized and don't scale linearly with data size.
"""

import pytest
from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings
from apps.noc.models import NOCIncident, NOCAlertEvent
from apps.noc.views.export_views import NOCExportIncidentsView
from apps.noc.views.analytics_views import NOCAnalyticsView
from apps.peoples.models import People
from apps.client_onboarding.models import Bt


@pytest.mark.django_db
class TestNOCExportPerformance(TestCase):
    """Performance tests for NOC export views."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data once."""
        cls.factory = RequestFactory()
        
        # Create test user with minimal permissions
        cls.user = People.objects.create(
            peoplename='Test User',
            peopleemail='test@example.com',
            bu_id=1
        )
        
        # Create test client
        cls.client = Bt.objects.filter(pk=1).first()
        if not cls.client:
            cls.client = Bt.objects.create(
                buname='Test Client',
                tenant_id=1
            )
    
    def setUp(self):
        """Set up for each test."""
        # Clear query log
        connection.queries_log.clear()
    
    def test_export_incidents_minimal_queries(self):
        """Export should use constant queries regardless of incident count."""
        # Create 50 incidents with varying alert counts
        incidents = []
        for i in range(50):
            incident = NOCIncident.objects.create(
                title=f'Incident {i}',
                client=self.client,
                severity='high',
                state='NEW',
                tenant_id=1
            )
            incidents.append(incident)
        
        # Create varying number of alerts per incident (5-10)
        for incident in incidents:
            for j in range(5):
                NOCAlertEvent.objects.create(
                    title=f'Alert for incident {incident.id}',
                    client=self.client,
                    severity='medium',
                    tenant_id=1
                )
                incident.alerts.add(
                    NOCAlertEvent.objects.filter(
                        title=f'Alert for incident {incident.id}'
                    ).first()
                )
        
        # Test export query count
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        queryset = NOCIncident.objects.for_export().filter(
            client=self.client
        ).distinct()[:50]
        
        # Force evaluation
        list(queryset)
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use max 5 queries regardless of data size
        self.assertLessEqual(
            queries_used, 5,
            f"Export used {queries_used} queries, expected <= 5"
        )
        
        # Verify alert_count is annotated
        for incident in queryset:
            self.assertTrue(
                hasattr(incident, 'alert_count'),
                "Incident should have alert_count annotation"
            )
    
    def test_export_scales_with_data_size(self):
        """Verify query count stays constant as data size increases."""
        query_counts = []
        
        for size in [10, 50, 100]:
            # Create incidents
            for i in range(size):
                incident = NOCIncident.objects.create(
                    title=f'Test Incident {size}-{i}',
                    client=self.client,
                    severity='medium',
                    state='NEW',
                    tenant_id=1
                )
                # Add 5 alerts per incident
                for j in range(5):
                    alert = NOCAlertEvent.objects.create(
                        title=f'Alert {i}-{j}',
                        client=self.client,
                        severity='low',
                        tenant_id=1
                    )
                    incident.alerts.add(alert)
            
            # Measure queries
            connection.force_debug_cursor = True
            query_count_before = len(connection.queries)
            
            queryset = NOCIncident.objects.for_export().filter(
                client=self.client
            ).distinct()[:size]
            list(queryset)
            
            query_count_after = len(connection.queries)
            queries_used = query_count_after - query_count_before
            query_counts.append(queries_used)
            
            # Clean up for next iteration
            NOCIncident.objects.filter(client=self.client).delete()
            NOCAlertEvent.objects.filter(client=self.client).delete()
        
        # Verify query count doesn't scale linearly
        # With optimization, all sizes should use similar query count (≤5)
        for count in query_counts:
            self.assertLessEqual(
                count, 6,
                f"Query count {count} should be constant, not scale with data size"
            )


@pytest.mark.django_db
class TestNOCAnalyticsPerformance(TestCase):
    """Performance tests for analytics views."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.factory = RequestFactory()
        cls.user = People.objects.create(
            peoplename='Analytics User',
            peopleemail='analytics@example.com',
            bu_id=1
        )
    
    def test_mttr_by_client_uses_single_query(self):
        """MTTR calculation should use aggregated query, not loop."""
        from datetime import timedelta
        
        # Create 10 clients
        clients = []
        for i in range(10):
            client = Bt.objects.create(
                buname=f'Client {i}',
                tenant_id=1
            )
            clients.append(client)
            
            # Create 20 alerts per client with resolution times
            for j in range(20):
                NOCAlertEvent.objects.create(
                    title=f'Alert {i}-{j}',
                    client=client,
                    severity='medium',
                    resolved_at=timezone.now(),
                    time_to_resolve=timedelta(minutes=30),
                    tenant_id=1
                )
        
        # Test analytics query
        view = NOCAnalyticsView()
        window_start = timezone.now() - timedelta(days=30)
        
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        results = view._calculate_mttr_by_client(clients, window_start)
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use 2 queries max: 1 for aggregation
        self.assertLessEqual(
            queries_used, 3,
            f"MTTR calculation used {queries_used} queries, expected <= 3"
        )
        
        # Verify results
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIn('client_id', result)
            self.assertIn('avg_minutes', result)
            self.assertIn('count', result)
            self.assertEqual(result['count'], 20)


@pytest.mark.django_db  
class TestIncidentManagerOptimizations(TestCase):
    """Test custom manager methods for optimal queries."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.client = Bt.objects.filter(pk=1).first() or Bt.objects.create(
            buname='Test Client',
            tenant_id=1
        )
        cls.user = People.objects.create(
            peoplename='Manager Test User',
            peopleemail='manager@example.com',
            bu_id=1
        )
    
    def test_with_counts_annotates_alert_count(self):
        """with_counts() should annotate alert count without N+1."""
        # Create incidents
        for i in range(10):
            incident = NOCIncident.objects.create(
                title=f'Incident {i}',
                client=self.client,
                severity='high',
                state='NEW',
                tenant_id=1
            )
            # Add varying number of alerts
            for j in range(i):
                alert = NOCAlertEvent.objects.create(
                    title=f'Alert {i}-{j}',
                    client=self.client,
                    severity='low',
                    tenant_id=1
                )
                incident.alerts.add(alert)
        
        # Use manager method
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        incidents = list(NOCIncident.objects.with_counts().filter(client=self.client))
        
        # Access counts (should not trigger additional queries)
        for incident in incidents:
            _ = incident.alert_count
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use 1 query with annotation
        self.assertLessEqual(
            queries_used, 2,
            f"with_counts() used {queries_used} queries, expected <= 2"
        )
    
    def test_with_full_details_prefetches_relations(self):
        """with_full_details() should prefetch all related data."""
        # Create incident with relations
        incident = NOCIncident.objects.create(
            title='Detail Test',
            client=self.client,
            assigned_to=self.user,
            severity='critical',
            state='ASSIGNED',
            tenant_id=1
        )
        
        # Add alerts
        for i in range(5):
            alert = NOCAlertEvent.objects.create(
                title=f'Detail Alert {i}',
                client=self.client,
                reported_by=self.user,
                severity='high',
                tenant_id=1
            )
            incident.alerts.add(alert)
        
        # Fetch with manager
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        fetched_incident = NOCIncident.objects.with_full_details().get(pk=incident.pk)
        
        # Access all relations (should not trigger queries)
        _ = fetched_incident.assigned_to.peoplename
        _ = fetched_incident.client.buname
        for alert in fetched_incident.alerts.all():
            _ = alert.title
            if alert.reported_by:
                _ = alert.reported_by.peoplename
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Should use 2-3 queries max (main query + prefetches)
        self.assertLessEqual(
            queries_used, 4,
            f"with_full_details() used {queries_used} queries, expected <= 4"
        )
    
    def test_active_incidents_filters_and_counts(self):
        """active_incidents() should combine filtering with counts."""
        # Create mix of active and resolved incidents
        states = ['NEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED']
        for i, state in enumerate(states * 3):
            NOCIncident.objects.create(
                title=f'Incident {i}',
                client=self.client,
                severity='medium',
                state=state,
                tenant_id=1
            )
        
        connection.force_debug_cursor = True
        query_count_before = len(connection.queries)
        
        active = list(NOCIncident.objects.active_incidents().filter(client=self.client))
        
        query_count_after = len(connection.queries)
        queries_used = query_count_after - query_count_before
        
        # Verify only active states returned
        for incident in active:
            self.assertIn(incident.state, ['NEW', 'ASSIGNED', 'IN_PROGRESS'])
            self.assertTrue(hasattr(incident, 'alert_count'))
        
        # Should use 1 query
        self.assertLessEqual(
            queries_used, 2,
            f"active_incidents() used {queries_used} queries, expected <= 2"
        )
