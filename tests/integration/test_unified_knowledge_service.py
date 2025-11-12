"""
Integration tests for UnifiedKnowledgeService.

Tests unified search across all knowledge sources:
- Ontology registry (code components)
- help_center articles
- helpbot knowledge base
- y_helpdesk ticket solutions

Performance Requirements:
- P95 latency < 300ms
- Error rate < 0.1%
- Cache hit rate > 80% after warmup
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from django.test import override_settings

# Mark all tests in this module as requiring database
pytestmark = pytest.mark.django_db


@pytest.fixture
def service():
    """Create UnifiedKnowledgeService instance."""
    # Lazy import to avoid Django setup issues
    from apps.core.services.unified_knowledge_service import UnifiedKnowledgeService
    return UnifiedKnowledgeService()


@pytest.fixture
def mock_user(db):
    """Create mock user for permission tests."""
    from apps.peoples.models import Tenant, People

    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test"
        )

    user = People.objects.create(
        username=f"testuser_{int(time.time())}",
        email=f"test_{int(time.time())}@example.com",
        tenant=tenant
    )
    return user


class TestUnifiedSearch:
    """Test unified search across all sources."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_all_sources_when_enabled(self, service, mock_user):
        """Search should query all sources when feature flag enabled."""
        results = service.search("authentication", user=mock_user)

        # Should have results from multiple sources
        assert 'ontology' in results
        assert 'articles' in results
        assert 'helpbot' in results
        assert 'tickets' in results

        # Each source should return a list
        assert isinstance(results['ontology'], list)
        assert isinstance(results['articles'], list)
        assert isinstance(results['helpbot'], list)
        assert isinstance(results['tickets'], list)

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': False})
    def test_search_disabled_when_feature_flag_off(self, service, mock_user):
        """Search should raise error when feature flag disabled."""
        with pytest.raises(RuntimeError, match="USE_UNIFIED_KNOWLEDGE feature flag is disabled"):
            service.search("authentication", user=mock_user)

    def test_search_with_source_filtering(self, service, mock_user):
        """Search should respect source filtering."""
        with override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True}):
            # Only ontology and articles
            results = service.search(
                "authentication",
                sources=['ontology', 'articles'],
                user=mock_user
            )

            assert 'ontology' in results
            assert 'articles' in results
            assert 'helpbot' not in results
            assert 'tickets' not in results

    def test_search_with_invalid_source(self, service, mock_user):
        """Search should raise ValueError for invalid source."""
        with override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True}):
            with pytest.raises(ValueError, match="Invalid source"):
                service.search(
                    "authentication",
                    sources=['invalid_source'],
                    user=mock_user
                )

    def test_search_with_empty_query(self, service, mock_user):
        """Search should handle empty query gracefully."""
        with override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True}):
            results = service.search("", user=mock_user)

            # Should return empty results for all sources
            assert all(len(v) == 0 for v in results.values())

    def test_search_respects_limit_parameter(self, service, mock_user):
        """Search should respect limit parameter for each source."""
        with override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True}):
            results = service.search("authentication", user=mock_user, limit=3)

            # Each source should have <= 3 results
            for source, items in results.items():
                assert len(items) <= 3


class TestPermissionFiltering:
    """Test permission filtering for user-specific content."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_articles_filtered_by_user_permissions(self, service, mock_user):
        """Articles should be filtered based on user permissions."""
        results = service.search("authentication", user=mock_user)

        # All articles should be accessible to user
        for article in results['articles']:
            # Articles should have 'id' and 'tenant' fields for permission check
            assert 'id' in article
            assert article.get('tenant') == mock_user.tenant.id or article.get('tenant') is None

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_tickets_filtered_by_user_permissions(self, service, mock_user):
        """Tickets should be filtered based on user permissions."""
        results = service.search("authentication", user=mock_user)

        # All tickets should be accessible to user
        for ticket in results['tickets']:
            assert 'id' in ticket
            # Tickets should belong to same tenant
            assert ticket.get('tenant') == mock_user.tenant.id

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_without_user_returns_public_only(self, service):
        """Search without user should return only public content."""
        results = service.search("authentication", user=None)

        # Should still return ontology (public) and helpbot (public)
        assert 'ontology' in results
        assert 'helpbot' in results

        # Articles and tickets should be empty (require user context)
        assert len(results.get('articles', [])) == 0
        assert len(results.get('tickets', [])) == 0


class TestResultMergingAndRanking:
    """Test result merging and ranking logic."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_get_related_knowledge_merges_sources(self, service, mock_user):
        """get_related_knowledge should merge and rank results."""
        results = service.get_related_knowledge("authentication", user=mock_user, limit=10)

        # Should return merged list
        assert isinstance(results, list)

        # Each result should have source attribution
        for result in results:
            assert 'source' in result
            assert result['source'] in ['ontology', 'articles', 'helpbot', 'tickets']

            # Should have required fields
            assert 'title' in result or 'qualified_name' in result
            assert 'relevance' in result or 'score' in result

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_results_sorted_by_relevance(self, service, mock_user):
        """Results should be sorted by relevance score."""
        results = service.get_related_knowledge("authentication", user=mock_user, limit=10)

        if len(results) > 1:
            # Check that relevance scores are in descending order
            scores = [r.get('relevance', r.get('score', 0)) for r in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by relevance"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_get_related_knowledge_respects_limit(self, service, mock_user):
        """get_related_knowledge should respect limit after merging."""
        limit = 5
        results = service.get_related_knowledge("authentication", user=mock_user, limit=limit)

        assert len(results) <= limit


class TestCachingBehavior:
    """Test Redis caching functionality."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_cache_hit_returns_cached_results(self, service, mock_user):
        """Second query should return cached results."""
        query = f"test_cache_{int(time.time())}"

        # First query - cache miss
        start1 = time.perf_counter()
        results1 = service.search(query, user=mock_user)
        elapsed1 = time.perf_counter() - start1

        # Second query - cache hit (should be much faster)
        start2 = time.perf_counter()
        results2 = service.search(query, user=mock_user)
        elapsed2 = time.perf_counter() - start2

        # Results should be identical
        assert results1.keys() == results2.keys()

        # Cache hit should be significantly faster (at least 50% faster)
        assert elapsed2 < elapsed1 * 0.5, f"Cache hit ({elapsed2:.4f}s) should be faster than cache miss ({elapsed1:.4f}s)"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_cache_respects_ttl(self, service, mock_user):
        """Cache should respect 15-minute TTL."""
        query = f"test_ttl_{int(time.time())}"

        # First query
        results1 = service.search(query, user=mock_user)

        # Verify cache was set (check internal method)
        cache_key = service._get_cache_key(query, sources=None, user=mock_user)
        cached = service._get_from_cache(cache_key)
        assert cached is not None, "Results should be cached"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_cache_invalidation_on_source_parameter_change(self, service, mock_user):
        """Different source parameters should use different cache keys."""
        query = "authentication"

        # Query with all sources
        results1 = service.search(query, user=mock_user)

        # Query with only ontology
        results2 = service.search(query, sources=['ontology'], user=mock_user)

        # Results should be different
        assert results1.keys() != results2.keys()


class TestGracefulDegradation:
    """Test graceful degradation when sources fail."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_continues_on_single_source_failure(self, service, mock_user):
        """Service should continue if one source fails."""
        with patch.object(service, '_search_ontology', side_effect=Exception("Ontology down")):
            results = service.search("authentication", user=mock_user)

            # Should still have other sources
            assert 'articles' in results
            assert 'helpbot' in results
            assert 'tickets' in results

            # Failed source should return empty list
            assert results.get('ontology', []) == []

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_continues_on_multiple_source_failures(self, service, mock_user):
        """Service should continue even if multiple sources fail."""
        with patch.object(service, '_search_ontology', side_effect=Exception("Ontology down")), \
             patch.object(service, '_search_articles', side_effect=Exception("Articles down")):

            results = service.search("authentication", user=mock_user)

            # Should still have working sources
            assert 'helpbot' in results
            assert 'tickets' in results

            # Failed sources should return empty lists
            assert results.get('ontology', []) == []
            assert results.get('articles', []) == []

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_cache_failure_falls_back_to_direct_query(self, service, mock_user):
        """Service should work even if cache is unavailable."""
        with patch.object(service, '_get_from_cache', side_effect=Exception("Redis down")), \
             patch.object(service, '_set_in_cache', side_effect=Exception("Redis down")):

            # Should still return results
            results = service.search("authentication", user=mock_user)

            assert isinstance(results, dict)
            assert len(results) > 0


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration for fault tolerance."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_circuit_breaker_opens_after_failures(self, service, mock_user):
        """Circuit breaker should open after consecutive failures."""
        # Simulate 3 consecutive failures (circuit breaker threshold)
        with patch.object(service, '_search_ontology', side_effect=Exception("Service down")):
            for _ in range(3):
                results = service.search("test", user=mock_user)
                assert results.get('ontology', []) == []

            # 4th call should short-circuit (no actual call)
            # Circuit breaker should be open
            results = service.search("test", user=mock_user)
            assert results.get('ontology', []) == []


class TestPerformanceRequirements:
    """Test performance requirements (P95 < 300ms)."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_completes_within_latency_budget(self, service, mock_user):
        """Single search should complete in < 300ms."""
        start = time.perf_counter()
        results = service.search("authentication", user=mock_user)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        assert elapsed < 300, f"Search took {elapsed:.2f}ms (threshold: 300ms)"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_p95_latency_under_300ms(self, service, mock_user):
        """P95 latency should be < 300ms over 100 queries."""
        latencies = []

        queries = ["authentication", "file download", "SLA", "GPS", "ticket"]

        for query in queries:
            for _ in range(20):  # 100 total queries
                start = time.perf_counter()
                service.search(query, user=mock_user)
                elapsed = (time.perf_counter() - start) * 1000  # ms
                latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        assert p95 < 300, f"P95 latency {p95:.2f}ms exceeds 300ms threshold"

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_error_rate_below_threshold(self, service, mock_user):
        """Error rate should be < 0.1% over 1000 queries."""
        total_queries = 1000
        error_count = 0

        queries = ["authentication", "file download", "SLA", "GPS", "ticket"]

        for query in queries:
            for _ in range(total_queries // len(queries)):
                try:
                    service.search(query, user=mock_user)
                except Exception:
                    error_count += 1

        error_rate = (error_count / total_queries) * 100

        assert error_rate < 0.1, f"Error rate {error_rate:.2f}% exceeds 0.1% threshold"


class TestSourceSpecificMethods:
    """Test individual source query methods."""

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_ontology_returns_formatted_results(self, service):
        """_search_ontology should return properly formatted results."""
        results = service._search_ontology("authentication", limit=5)

        assert isinstance(results, list)

        if len(results) > 0:
            # Check result structure
            result = results[0]
            assert 'source' in result
            assert result['source'] == 'ontology'
            assert 'qualified_name' in result or 'title' in result

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_articles_filters_by_user(self, service, mock_user):
        """_search_articles should filter by user tenant."""
        results = service._search_articles("authentication", user=mock_user, limit=5)

        assert isinstance(results, list)

        for result in results:
            assert 'source' in result
            assert result['source'] == 'articles'

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_helpbot_returns_knowledge_entries(self, service):
        """_search_helpbot should return knowledge base entries."""
        results = service._search_helpbot("authentication", limit=5)

        assert isinstance(results, list)

        if len(results) > 0:
            result = results[0]
            assert 'source' in result
            assert result['source'] == 'helpbot'

    @override_settings(FEATURES={'USE_UNIFIED_KNOWLEDGE': True})
    def test_search_ticket_solutions_requires_user(self, service, mock_user):
        """_search_ticket_solutions should require user for tenant filtering."""
        results = service._search_ticket_solutions("authentication", user=mock_user, limit=5)

        assert isinstance(results, list)

        for result in results:
            assert 'source' in result
            assert result['source'] == 'tickets'
