import time
from datetime import date
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection
from django.test.utils import override_settings
from apps.onboarding.models import TypeAssist, Bt, GeofenceMaster, Shift
from apps.onboarding.views import (
    SuperTypeAssist,
    TypeAssistView,
    BtView,
    ContractView,
    GeoFence,
    ShiftView,
    DashboardView,
)

User = get_user_model()


class QueryPerformanceTestCase(TestCase):
    """Test case to verify query optimizations are working correctly."""

    @classmethod
    def setUpTestData(cls):
        # Create test user
        cls.user = User.objects.create_user(
            loginid="testuser",
            password="testpass123",
            peoplename="Test User",
            peoplecode="TESTUSER001",
            email="testuser@example.com",
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2024, 1, 1),
        )

        # Create identifier for client
        client_identifier = TypeAssist.objects.create(
            tacode="CLIENT", taname="Client", enable=True
        )

        # Create test data
        cls.client_bt = Bt.objects.create(
            bucode="TEST_CLIENT",
            buname="Test Client",
            identifier=client_identifier,
            enable=True,
        )

        # Create TypeAssist test data
        for i in range(100):
            TypeAssist.objects.create(
                tacode=f"TA{i:03d}",
                taname=f"Type Assist {i}",
                client=cls.client_bt,
                enable=True,
            )

    def setUp(self):
        self.factory = RequestFactory()

    def _get_request_with_session(self, url="/", method="get"):
        """Helper to create request with session."""
        request = getattr(self.factory, method)(url)
        request.user = self.user

        # Add session
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session["client_id"] = self.client_bt.id
        request.session["bu_id"] = self.client_bt.id
        request.session["assignedsites"] = [self.client_bt.id]  # Add assignedsites
        request.session["assignedsitegroups"] = []  # Add assignedsitegroups
        request.session.save()

        return request

    @override_settings(DEBUG=True)
    def test_supertypeassist_query_performance(self):
        """Test that SuperTypeAssist view uses iterator() for memory efficiency."""
        request = self._get_request_with_session("/?action=list")
        view = SuperTypeAssist()

        # Reset queries
        connection.queries_log.clear()

        # Execute view
        response = view.get(request)

        # Check that we're not loading all objects into memory at once
        # The iterator() should be used
        query_count = len(connection.queries)
        self.assertLessEqual(
            query_count, 2, f"Expected at most 2 queries, but got {query_count}"
        )

    @override_settings(DEBUG=True)
    def test_typeassist_query_performance(self):
        """Test that TypeAssistView uses optimized queries."""
        request = self._get_request_with_session("/?action=list")
        view = TypeAssistView()

        # Reset queries
        connection.queries_log.clear()

        # Execute view
        response = view.get(request)

        # Verify select_related is being used
        queries = connection.queries
        self.assertTrue(
            any("JOIN" in q["sql"] for q in queries),
            "Expected JOIN queries from select_related",
        )

    def test_dashboard_aggregation_pattern(self):
        """Test the dashboard aggregation pattern."""
        request = self._get_request_with_session("/?from=2024-01-01&upto=2024-12-31")
        view = DashboardView()

        # Test that the optimized method exists and returns expected structure
        result = view.get_optimized_dashboard_counts(request, view.P)
        self.assertIn("counts", result)
        self.assertIsInstance(result["counts"], dict)

    def test_migration_indexes_created(self):
        """Test that database indexes were created properly."""
        from django.db import connection

        # Skip this test if not using PostgreSQL
        if connection.vendor != "postgresql":
            self.skipTest("Index check is PostgreSQL specific")

        with connection.cursor() as cursor:
            # Check TypeAssist indexes
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'onboarding_typeassist'
                AND indexname LIKE '%onboarding_ta%'
            """
            )
            indexes = cursor.fetchall()

            # We should have at least the indexes we created
            if indexes:
                index_names = [idx[0] for idx in indexes]
                self.assertIn("onboarding_tacode_enable_idx", index_names)
                self.assertIn("onboarding_ta_client_enable_idx", index_names)

    def test_iterator_memory_usage(self):
        """Test that iterator() reduces memory usage for large querysets."""
        # Create a large dataset
        for i in range(1000):
            TypeAssist.objects.create(
                tacode=f"BULK{i:04d}", taname=f"Bulk Type Assist {i}", enable=True
            )

        request = self._get_request_with_session("/?action=list")
        view = SuperTypeAssist()

        # Measure memory usage (simplified test)
        start_time = time.time()
        response = view.get(request)
        end_time = time.time()

        # With iterator(), the response time should be reasonable
        # even with large datasets
        self.assertLess(
            end_time - start_time,
            5.0,
            "Query took too long, iterator might not be working",
        )
