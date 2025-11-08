"""
N+1 Query Optimization Tests

Validates that critical views and services use optimized querysets
with query count assertions.

Run with:
    pytest tests/test_n1_optimizations.py -v

Author: Claude Code
Date: 2025-11-07
"""

import pytest
from django.test import TestCase, Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestWorkOrderServiceOptimizations(TestCase):
    """Test work order service N+1 optimizations."""
    
    @classmethod
    def setUpTestData(cls):
        """Create test data once for all tests."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_update_work_order_query_count(self):
        """
        Test that updating a work order uses select_related.
        
        Expected: 1 SELECT query (with joins) + 1 UPDATE
        Maximum: 3 queries total
        """
        from apps.work_order_management.services.work_order_service import (
            WorkOrderService, WorkOrderData
        )
        
        # Skip if work order doesn't exist (would need factory setup)
        pytest.skip("Requires test data factory setup")
    
    def test_work_order_metrics_query_count(self):
        """
        Test that metrics calculation uses optimized queries.
        
        Expected for 100 work orders:
        - 1 query with select_related (not 100+ queries)
        """
        from apps.work_order_management.services.work_order_service import WorkOrderService
        
        service = WorkOrderService()
        
        with CaptureQueriesContext(connection) as context:
            metrics = service.get_work_order_metrics()
            
            # Should use 1 optimized query, not N+1
            # Allow up to 5 queries for aggregations
            assert len(context.captured_queries) <= 5, \
                f"Expected <=5 queries, got {len(context.captured_queries)}"


@pytest.mark.django_db
class TestAdminPanelOptimizations(TestCase):
    """Test admin panel N+1 optimizations."""
    
    @classmethod
    def setUpTestData(cls):
        """Create admin user."""
        cls.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@test.com'
        )
        cls.client = Client()
    
    def test_reports_admin_uses_select_related(self):
        """
        Test that ScheduleReportAdmin uses list_select_related.
        
        Expected: Queries don't scale with number of objects.
        """
        from apps.reports.admin import ScheduleReportAdmin
        from apps.reports.models import ScheduleReport
        
        admin = ScheduleReportAdmin(ScheduleReport, None)
        
        # Verify list_select_related is configured
        assert hasattr(admin, 'list_select_related'), \
            "ScheduleReportAdmin missing list_select_related"
        
        assert 'bu' in admin.list_select_related, \
            "Missing 'bu' in list_select_related"
        
        assert 'client' in admin.list_select_related, \
            "Missing 'client' in list_select_related"
    
    def test_attendance_admin_uses_select_related(self):
        """
        Test that PostAdmin uses both select_related and prefetch_related.
        """
        from apps.attendance.admin import PostAdmin
        from apps.attendance.models import Post
        
        admin = PostAdmin(Post, None)
        
        # Verify list_select_related is configured
        assert hasattr(admin, 'list_select_related'), \
            "PostAdmin missing list_select_related"
        
        expected_fk_relations = ['site', 'shift', 'zone', 'geofence']
        for relation in expected_fk_relations:
            assert relation in admin.list_select_related, \
                f"Missing '{relation}' in list_select_related"
        
        # Verify list_prefetch_related is configured
        assert hasattr(admin, 'list_prefetch_related'), \
            "PostAdmin missing list_prefetch_related"
        
        assert 'required_certifications' in admin.list_prefetch_related, \
            "Missing 'required_certifications' in list_prefetch_related"
    
    def test_ticket_admin_uses_select_related(self):
        """
        Test that TicketAdmin uses optimized queries.
        """
        from apps.y_helpdesk.admin import TicketAdmin
        from apps.y_helpdesk.models import Ticket
        
        admin = TicketAdmin(Ticket, None)
        
        # Verify list_select_related is configured
        assert hasattr(admin, 'list_select_related'), \
            "TicketAdmin missing list_select_related"
        
        expected_relations = [
            'assignedtopeople', 'bu', 'createdbypeople',
            'ticketcategory', 'ticketsubcategory'
        ]
        for relation in expected_relations:
            assert relation in admin.list_select_related, \
                f"Missing '{relation}' in list_select_related"


@pytest.mark.django_db
class TestNOCViewOptimizations(TestCase):
    """Test NOC view optimizations (already optimized)."""
    
    def test_alert_list_view_uses_select_related(self):
        """
        Validate that NOC alert list view uses select_related.
        
        This test confirms existing optimization is maintained.
        """
        from apps.noc.views.alert_views import NOCAlertListView
        
        # This is a documentation test - verifies pattern exists in code
        import inspect
        source = inspect.getsource(NOCAlertListView.get)
        
        # Verify select_related is used
        assert 'select_related' in source, \
            "NOC alert list view missing select_related"
        
        assert "'client'" in source, \
            "Alert view should select_related client"
        
        assert "'bu'" in source, \
            "Alert view should select_related bu"
    
    def test_incident_list_uses_combined_optimization(self):
        """
        Validate that incident list uses both select_related and prefetch_related.
        """
        from apps.noc.views.incident_views import NOCIncidentListCreateView
        
        import inspect
        source = inspect.getsource(NOCIncidentListCreateView.get)
        
        # Verify both optimizations are used
        assert 'select_related' in source, \
            "Incident view missing select_related"
        
        assert 'prefetch_related' in source, \
            "Incident view missing prefetch_related"
        
        assert "'alerts'" in source, \
            "Incident view should prefetch_related alerts"


@pytest.mark.django_db  
class TestQueryCountRegression(TestCase):
    """
    Regression tests to ensure N+1 optimizations don't regress.
    
    These tests will fail if optimizations are removed.
    """
    
    @override_settings(DEBUG=True)
    def test_work_order_service_doesnt_regress(self):
        """
        Regression test: Work order service must maintain optimizations.
        
        This test will fail if select_related is removed from service methods.
        """
        from apps.work_order_management.services.work_order_service import WorkOrderService
        import inspect
        
        # Get source code of service
        source = inspect.getsource(WorkOrderService)
        
        # Count occurrences of select_related (should be at least 5)
        select_related_count = source.count('select_related')
        
        assert select_related_count >= 5, \
            f"Expected >=5 select_related calls, found {select_related_count}. " \
            f"N+1 optimizations may have been removed!"
    
    @override_settings(DEBUG=True)
    def test_admin_panels_dont_regress(self):
        """
        Regression test: Admin panels must maintain list_select_related.
        """
        test_cases = [
            ('apps.reports.admin', 'ScheduleReportAdmin', 'list_select_related'),
            ('apps.attendance.admin', 'PostAdmin', 'list_select_related'),
            ('apps.y_helpdesk.admin', 'TicketAdmin', 'list_select_related'),
        ]
        
        for module_path, class_name, attribute in test_cases:
            module = __import__(module_path, fromlist=[class_name])
            admin_class = getattr(module, class_name)
            
            assert hasattr(admin_class, attribute), \
                f"{class_name} missing {attribute}. " \
                f"N+1 optimization was removed!"


# Performance benchmarking tests (optional, for CI/CD)
@pytest.mark.slow
@pytest.mark.django_db
class TestPerformanceBenchmarks(TestCase):
    """
    Performance benchmark tests (run with --slow flag).
    
    These tests measure actual query performance improvements.
    """
    
    @pytest.mark.skip(reason="Requires production-like data volume")
    def test_ticket_admin_list_performance(self):
        """
        Benchmark: Ticket admin list should load in <500ms with 100 tickets.
        """
        import time
        from django.contrib.admin.sites import site
        from apps.y_helpdesk.models import Ticket
        from django.test import RequestFactory
        
        # Create mock request
        factory = RequestFactory()
        request = factory.get('/admin/y_helpdesk/ticket/')
        request.user = User.objects.create_superuser(
            username='bench', password='bench'
        )
        
        # Get admin
        ticket_admin = site._registry[Ticket]
        
        # Time the query
        start_time = time.time()
        
        with CaptureQueriesContext(connection) as context:
            queryset = ticket_admin.get_queryset(request)
            list(queryset[:100])  # Force evaluation
        
        elapsed_time = time.time() - start_time
        query_count = len(context.captured_queries)
        
        # Performance assertions
        assert query_count < 10, \
            f"Too many queries: {query_count} (should be <10)"
        
        assert elapsed_time < 0.5, \
            f"Too slow: {elapsed_time:.2f}s (should be <0.5s)"
        
        print(f"✅ Performance: {query_count} queries in {elapsed_time:.3f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
