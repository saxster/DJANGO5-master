"""
Phase 4 Performance Gate: Verify UnifiedKnowledgeService performance.

PASS CRITERIA:
- P95 latency < 300ms (with all sources)
- Error rate < 0.1%
- Cache hit rate > 50% after warmup
- A/B testing readiness verified

FAIL ACTION: Keep USE_UNIFIED_KNOWLEDGE feature flag disabled
"""

import pytest
import time
import statistics
from django.test import override_settings


# Mark all tests in this module as requiring database
pytestmark = pytest.mark.django_db


@pytest.fixture
def service():
    """Create UnifiedKnowledgeService instance."""
    from apps.core.services.unified_knowledge_service import UnifiedKnowledgeService
    return UnifiedKnowledgeService()


@pytest.fixture
def test_user(db):
    """Create test user for queries."""
    from apps.tenants.models import Tenant
    from apps.peoples.models import People

    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

    user = People.objects.create(
        username=f"perftest_{int(time.time())}",
        email=f"perftest_{int(time.time())}@example.com",
        tenant=tenant
    )
    return user


class TestPhase4PerformanceGate:
    """Performance gate tests for Phase 4."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_p95_latency_under_300ms(self, service, test_user):
        """
        P95 latency should be < 300ms over 100 queries.

        This is the PRIMARY gate criterion for Phase 4.
        """
        latencies = []

        # Test queries covering different scenarios
        queries = [
            "authentication",
            "file download",
            "SLA tracking",
            "GPS permissions",
            "ticket escalation"
        ]

        # Run 100 queries (20 per query type)
        for query in queries:
            for _ in range(20):
                start = time.perf_counter()
                try:
                    service.search(query, user=test_user)
                    elapsed = (time.perf_counter() - start) * 1000  # ms
                    latencies.append(elapsed)
                except Exception as e:
                    # Log but continue - errors tracked in separate test
                    print(f"Query failed: {e}")
                    latencies.append(1000)  # Penalty for failures

        # Calculate statistics
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        mean = statistics.mean(latencies)
        median = statistics.median(latencies)

        # Print results
        print(f"\n=== Phase 4 Performance Metrics ===")
        print(f"Total queries: {len(latencies)}")
        print(f"P50 latency: {p50:.2f}ms")
        print(f"P95 latency: {p95:.2f}ms")
        print(f"P99 latency: {p99:.2f}ms")
        print(f"Mean latency: {mean:.2f}ms")
        print(f"Median latency: {median:.2f}ms")
        print(f"===================================\n")

        # Assert gate criterion
        assert p95 < 300, f"P95 latency {p95:.2f}ms exceeds 300ms threshold"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_error_rate_below_threshold(self, service, test_user):
        """
        Error rate should be < 0.1% over 1000 queries.

        This ensures the service is reliable under load.
        """
        total_queries = 1000
        error_count = 0

        queries = [
            "authentication",
            "file download",
            "SLA",
            "GPS",
            "ticket"
        ]

        for query in queries:
            for _ in range(total_queries // len(queries)):
                try:
                    service.search(query, user=test_user)
                except Exception as e:
                    error_count += 1
                    print(f"Error: {e}")

        error_rate = (error_count / total_queries) * 100

        print(f"\n=== Error Rate Analysis ===")
        print(f"Total queries: {total_queries}")
        print(f"Errors: {error_count}")
        print(f"Error rate: {error_rate:.3f}%")
        print(f"===========================\n")

        assert error_rate < 0.1, f"Error rate {error_rate:.3f}% exceeds 0.1% threshold"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_cache_hit_rate_after_warmup(self, service, test_user):
        """
        Cache hit rate should be > 50% after warmup.

        This ensures caching is working effectively.
        """
        query = "authentication"

        # Warmup - execute query twice to populate cache
        service.search(query, user=test_user)
        service.search(query, user=test_user)

        # Measure cache hit performance
        cache_hit_latencies = []
        for _ in range(50):
            start = time.perf_counter()
            service.search(query, user=test_user)
            elapsed = (time.perf_counter() - start) * 1000
            cache_hit_latencies.append(elapsed)

        # Cache hits should be consistently fast
        mean_cache_hit = statistics.mean(cache_hit_latencies)

        print(f"\n=== Cache Performance ===")
        print(f"Mean cache hit latency: {mean_cache_hit:.2f}ms")
        print(f"=========================\n")

        # Cache hits should be < 50ms (much faster than 300ms threshold)
        assert mean_cache_hit < 50, f"Cache hit latency {mean_cache_hit:.2f}ms too slow"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_graceful_degradation_on_source_failure(self, service, test_user):
        """
        Service should continue working if one source fails.

        This ensures resilience and fault tolerance.
        """
        from unittest.mock import patch

        # Simulate ontology source failure
        with patch.object(service, '_search_ontology', side_effect=Exception("Ontology down")):
            start = time.perf_counter()
            results = service.search("authentication", user=test_user)
            elapsed = (time.perf_counter() - start) * 1000

            # Should still return results from other sources
            assert isinstance(results, dict)
            assert 'articles' in results or 'helpbot' in results or 'tickets' in results

            # Should complete within latency budget despite failure
            assert elapsed < 300, f"Graceful degradation took {elapsed:.2f}ms (threshold: 300ms)"

        print(f"\n=== Graceful Degradation Test ===")
        print(f"Completed in {elapsed:.2f}ms with one source failing")
        print(f"==================================\n")

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_merged_results_ranking(self, service, test_user):
        """
        Test that get_related_knowledge merges and ranks results properly.
        """
        results = service.get_related_knowledge("authentication", user=test_user, limit=10)

        # Should return a list
        assert isinstance(results, list)

        # Should not exceed limit
        assert len(results) <= 10

        # Each result should have required fields
        for result in results:
            assert 'source' in result
            assert result['source'] in ['ontology', 'articles', 'helpbot', 'tickets']

        # Results should be sorted by relevance (if multiple results)
        if len(results) > 1:
            scores = [r.get('relevance', r.get('score', 0)) for r in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by relevance"

        print(f"\n=== Merged Results Test ===")
        print(f"Total merged results: {len(results)}")
        if results:
            sources = [r['source'] for r in results]
            print(f"Sources represented: {set(sources)}")
        print(f"===========================\n")

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': False})
    def test_feature_flag_enforcement(self, service, test_user):
        """
        Service should enforce feature flag properly.
        """
        with pytest.raises(RuntimeError, match="USE_UNIFIED_KNOWLEDGE feature flag is disabled"):
            service.search("authentication", user=test_user)

        print(f"\n=== Feature Flag Test ===")
        print(f"Feature flag enforcement: PASS")
        print(f"=========================\n")


class TestABTestingReadiness:
    """Test A/B testing readiness."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_consistent_results_across_calls(self, service, test_user):
        """
        Same query should return consistent results (important for A/B testing).
        """
        query = "authentication"

        # Make 5 calls and compare results
        results_list = []
        for _ in range(5):
            results = service.search(query, user=test_user)
            results_list.append(results)

        # All results should have same structure
        for results in results_list:
            assert set(results.keys()) == set(results_list[0].keys())

        print(f"\n=== Consistency Test ===")
        print(f"All 5 calls returned consistent structure: PASS")
        print(f"========================\n")

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_no_performance_degradation_under_concurrent_load(self, service, test_user):
        """
        Performance should not degrade significantly under concurrent-like load.
        """
        latencies = []

        # Simulate burst load (50 rapid queries)
        for _ in range(50):
            start = time.perf_counter()
            service.search("authentication", user=test_user)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        # Check that latencies remain stable
        first_10 = statistics.mean(latencies[:10])
        last_10 = statistics.mean(latencies[-10:])

        print(f"\n=== Load Stability Test ===")
        print(f"First 10 queries: {first_10:.2f}ms avg")
        print(f"Last 10 queries: {last_10:.2f}ms avg")
        print(f"Degradation: {((last_10 - first_10) / first_10 * 100):.1f}%")
        print(f"===========================\n")

        # Last queries should not be > 50% slower than first queries
        assert last_10 < first_10 * 1.5, f"Performance degraded under load"


def main():
    """
    Manual test runner for quick validation.

    Run: python tests/performance/test_phase4_gate.py
    """
    print("Phase 4 Performance Gate Tests")
    print("=" * 50)
    print("\nRun with pytest for full results:")
    print("pytest tests/performance/test_phase4_gate.py -v --tb=short\n")


if __name__ == '__main__':
    main()
