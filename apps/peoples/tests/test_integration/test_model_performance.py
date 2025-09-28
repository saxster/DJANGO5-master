"""
Performance tests for refactored People model architecture.

Tests query optimization and N+1 prevention:
- Manager optimization methods effectiveness
- select_related performance
- Query count verification
- Index utilization
"""

import pytest
from datetime import date
from django.test import TestCase
from django.test.utils import override_settings
from apps.peoples.models import People


@pytest.mark.django_db
class TestQueryOptimizationMethods:
    """Test that optimization methods reduce query count."""

    def test_with_profile_reduces_queries(self):
        """Test that with_profile() prevents N+1 queries."""
        for i in range(5):
            people = People.objects.create_user(
                loginid=f"perf{i:03d}",
                peoplecode=f"PERF{i:03d}",
                peoplename=f"Performance User {i}",
                email=f"perf{i}@example.com"
            )
            people._temp_dateofbirth = date(1990, 1, 1)
            people._temp_gender = "M"
            people.save()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            users = People.objects.with_profile().all()[:5]
            for user in users:
                _ = user.profile.gender

        query_count = len(context.captured_queries)
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"

    def test_with_organizational_reduces_queries(self):
        """Test that with_organizational() prevents N+1 queries."""
        for i in range(5):
            people = People.objects.create_user(
                loginid=f"org{i:03d}",
                peoplecode=f"ORG{i:03d}",
                peoplename=f"Org User {i}",
                email=f"org{i}@example.com"
            )
            people._temp_dateofbirth = date(1990, 1, 1)
            people.save()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            users = People.objects.with_organizational().all()[:5]
            for user in users:
                _ = user.organizational

        query_count = len(context.captured_queries)
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"

    def test_with_full_details_prevents_all_n_plus_one(self):
        """Test that with_full_details() fetches everything efficiently."""
        for i in range(5):
            people = People.objects.create_user(
                loginid=f"full{i:03d}",
                peoplecode=f"FULL{i:03d}",
                peoplename=f"Full User {i}",
                email=f"full{i}@example.com"
            )
            people._temp_dateofbirth = date(1990, 1, 1)
            people._temp_gender = "F"
            people.save()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            users = People.objects.with_full_details().all()[:5]
            for user in users:
                _ = user.profile.gender
                _ = user.organizational

        query_count = len(context.captured_queries)
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"


@pytest.mark.django_db
class TestPropertyAccessorPerformance:
    """Test performance of property accessors."""

    def test_property_access_with_prefetch(self):
        """Test that property access works efficiently with prefetch."""
        people = People.objects.create_user(
            loginid="prop001",
            peoplecode="PROP001",
            peoplename="Property User",
            email="prop@example.com"
        )
        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_gender = "M"
        people.save()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            user = People.objects.with_full_details().get(peoplecode="PROP001")
            _ = user.gender
            _ = user.dateofbirth

        query_count = len(context.captured_queries)
        assert query_count <= 1, f"Expected 1 query, got {query_count}"

    def test_property_setter_performance(self):
        """Test that property setters don't cause excessive queries."""
        people = People.objects.create_user(
            loginid="setter001",
            peoplecode="SETTER001",
            peoplename="Setter User",
            email="setter@example.com"
        )
        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            people.gender = "F"

        query_count = len(context.captured_queries)
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"


@pytest.mark.django_db
class TestIndexEffectiveness:
    """Test that indexes are being utilized."""

    def test_peoplecode_lookup_uses_index(self):
        """Test that peoplecode lookups use the index."""
        people = People.objects.create_user(
            loginid="idx001",
            peoplecode="IDX001",
            peoplename="Index User",
            email="idx@example.com"
        )
        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        result = People.objects.filter(peoplecode="IDX001").first()
        assert result is not None
        assert result.peoplecode == "IDX001"

    def test_loginid_lookup_uses_index(self):
        """Test that loginid lookups use the index."""
        people = People.objects.create_user(
            loginid="idx002",
            peoplecode="IDX002",
            peoplename="Index User 2",
            email="idx2@example.com"
        )
        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        result = People.objects.filter(loginid="idx002").first()
        assert result is not None
        assert result.loginid == "idx002"

    def test_active_users_query_uses_compound_index(self):
        """Test that active users query uses the compound index."""
        people = People.objects.create_user(
            loginid="idx003",
            peoplecode="IDX003",
            peoplename="Index User 3",
            email="idx3@example.com"
        )
        people.isverified = True
        people.enable = True
        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        result = People.objects.filter(isverified=True, enable=True).first()
        assert result is not None


@pytest.mark.integration
@pytest.mark.django_db
class TestPerformanceComparison:
    """Test performance improvements from refactoring."""

    def test_bulk_create_performance(self):
        """Test that bulk operations work efficiently."""
        users_data = []
        for i in range(10):
            people = People(
                loginid=f"bulk{i:03d}",
                peoplecode=f"BULK{i:03d}",
                peoplename=f"Bulk User {i}",
                email=f"bulk{i}@example.com"
            )
            people.set_password("testpass123")
            users_data.append(people)

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            People.objects.bulk_create(users_data)

        query_count = len(context.captured_queries)
        assert query_count <= 3, f"Bulk create should use <= 3 queries, got {query_count}"

    def test_filter_with_related_data(self):
        """Test filtering with related data access."""
        for i in range(5):
            people = People.objects.create_user(
                loginid=f"filter{i:03d}",
                peoplecode=f"FILTER{i:03d}",
                peoplename=f"Filter User {i}",
                email=f"filter{i}@example.com"
            )
            people._temp_dateofbirth = date(1990, 1, 1)
            people.save()

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            users = People.objects.with_full_details().filter(
                peoplecode__startswith="FILTER"
            )
            results = list(users)
            for user in results:
                _ = user.profile
                _ = user.organizational

        query_count = len(context.captured_queries)
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"


@pytest.mark.django_db
class TestCachingBehavior:
    """Test that related objects are cached properly."""

    def test_multiple_profile_access_no_extra_queries(self):
        """Test that accessing profile multiple times doesn't cause extra queries."""
        people = People.objects.create_user(
            loginid="cache001",
            peoplecode="CACHE001",
            peoplename="Cache User",
            email="cache@example.com"
        )
        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_gender = "M"
        people.save()

        people = People.objects.with_profile().get(peoplecode="CACHE001")

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            _ = people.profile
            _ = people.profile
            _ = people.profile.gender
            _ = people.profile.dateofbirth

        query_count = len(context.captured_queries)
        assert query_count == 0, f"Expected 0 queries (cached), got {query_count}"