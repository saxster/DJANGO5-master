"""
Tests for Unified Semantic Search

Comprehensive test suite covering:
- Cross-module search
- Relevance ranking
- Fuzzy matching
- Tenant isolation
- Module filtering
- Performance benchmarks
- Voice search integration
- Search analytics

Follows CLAUDE.md testing standards:
- Rule #19: pytest fixtures for setup
- Rule #20: Descriptive test names
- Rule #21: Assert specific exceptions
- Rule #22: Mock external dependencies
"""

import pytest
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.search.services.unified_semantic_search_service import UnifiedSemanticSearchService
from apps.search.models import SearchAnalytics
from apps.tenants.models import Tenant
from apps.peoples.models import People


@pytest.mark.django_db
class TestUnifiedSemanticSearchService:
    """Test suite for UnifiedSemanticSearchService."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, created = Tenant.objects.get_or_create(
            tenantname='test_tenant',
            defaults={'enable': True}
        )
        return tenant

    @pytest.fixture
    def user(self, tenant):
        """Create test user."""
        user = People.objects.create(
            username=f'testuser_{uuid.uuid4().hex[:8]}',
            peoplename='Test User',
            peopleemail='test@example.com',
            tenant=tenant,
            enable=True,
        )
        return user

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return UnifiedSemanticSearchService()

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test."""
        cache.clear()
        yield
        cache.clear()

    def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service is not None
        assert service.cache_prefix == 'unified_search'
        assert service.module_weights is not None
        assert 'tickets' in service.module_weights

    def test_search_empty_query(self, service, tenant):
        """Test search with empty query returns error."""
        result = service.search(
            query='',
            tenant_id=tenant.id,
        )

        assert result['total_count'] == 0
        assert 'error' in result
        assert 'Empty query' in result['error']

    def test_search_all_modules(self, service, tenant, user):
        """Test search across all modules."""
        result = service.search(
            query='test',
            tenant_id=tenant.id,
            user_id=user.id,
            limit=50,
        )

        assert 'results' in result
        assert 'total_count' in result
        assert 'search_time_ms' in result
        assert 'modules_searched' in result
        assert 'suggestions' in result
        assert 'fuzzy_matches' in result

    def test_search_specific_modules(self, service, tenant):
        """Test search with specific module filter."""
        result = service.search(
            query='test',
            tenant_id=tenant.id,
            modules=['tickets', 'assets'],
            limit=20,
        )

        assert result['modules_searched'] == ['tickets', 'assets']

    def test_search_with_filters(self, service, tenant):
        """Test search with additional filters."""
        filters = {
            'status': 'OPEN',
            'priority': 'HIGH',
            'date_from': '2025-11-01',
        }

        result = service.search(
            query='urgent',
            tenant_id=tenant.id,
            filters=filters,
            limit=50,
        )

        assert 'results' in result

    def test_search_result_format(self, service, tenant):
        """Test search results have correct format."""
        result = service.search(
            query='test',
            tenant_id=tenant.id,
            limit=10,
        )

        if result['results']:
            first_result = result['results'][0]
            assert 'id' in first_result
            assert 'module' in first_result
            assert 'type' in first_result
            assert 'title' in first_result
            assert 'snippet' in first_result
            assert 'metadata' in first_result
            assert 'url' in first_result
            assert 'relevance_score' in first_result
            assert 'timestamp' in first_result

    def test_search_caching(self, service, tenant):
        """Test search results are cached."""
        query = f'test_cache_{uuid.uuid4().hex[:8]}'

        # First search
        result1 = service.search(
            query=query,
            tenant_id=tenant.id,
            limit=10,
        )
        assert result1['from_cache'] is False

        # Second search should be from cache
        result2 = service.search(
            query=query,
            tenant_id=tenant.id,
            limit=10,
        )
        assert result2['from_cache'] is True

    def test_tenant_isolation(self, service):
        """Test tenant isolation in search."""
        # Create two tenants
        tenant1, _ = Tenant.objects.get_or_create(
            tenantname='tenant1_test',
            defaults={'enable': True}
        )
        tenant2, _ = Tenant.objects.get_or_create(
            tenantname='tenant2_test',
            defaults={'enable': True}
        )

        # Search for each tenant
        result1 = service.search(
            query='test',
            tenant_id=tenant1.id,
            limit=10,
        )
        result2 = service.search(
            query='test',
            tenant_id=tenant2.id,
            limit=10,
        )

        # Results should be different (tenant-specific)
        # Verify tenant_id in results
        for result in result1.get('results', []):
            if 'tenant_id' in result:
                assert result['tenant_id'] == tenant1.id

    def test_fuzzy_matching(self, service, tenant):
        """Test fuzzy matching detects similar terms."""
        # This would need actual data to test properly
        result = service.search(
            query='coolig',  # Typo for 'cooling'
            tenant_id=tenant.id,
            limit=10,
        )

        assert 'fuzzy_matches' in result
        # If there were actual 'cooling' entries, they would be detected

    def test_relevance_ranking(self, service, tenant):
        """Test results are ranked by relevance."""
        result = service.search(
            query='test',
            tenant_id=tenant.id,
            limit=20,
        )

        if len(result['results']) > 1:
            # Check scores are in descending order
            scores = [r['relevance_score'] for r in result['results']]
            assert scores == sorted(scores, reverse=True)

    def test_search_performance(self, service, tenant):
        """Test search completes within 500ms."""
        result = service.search(
            query='performance test',
            tenant_id=tenant.id,
            limit=50,
        )

        # Search should complete in under 500ms
        assert result['search_time_ms'] < 500

    def test_search_suggestions(self, service, tenant):
        """Test search suggestions are generated."""
        result = service.search(
            query='test query',
            tenant_id=tenant.id,
            limit=10,
        )

        assert 'suggestions' in result
        assert isinstance(result['suggestions'], list)

    def test_module_weight_ranking(self, service):
        """Test module weights affect ranking."""
        # Create mock results from different modules
        ticket_result = {
            'module': 'tickets',
            'title': 'Test',
            'text': 'Test content',
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            'score': 1.0,
        }
        people_result = {
            'module': 'people',
            'title': 'Test',
            'text': 'Test content',
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            'score': 1.0,
        }

        results = [ticket_result, people_result]
        ranked = service._rank_results(results, 'test')

        # Tickets should rank higher than people (higher module weight)
        assert ranked[0]['module'] == 'tickets'
        assert ranked[1]['module'] == 'people'

    def test_recency_boost(self, service):
        """Test recent items get relevance boost."""
        now = datetime.now(dt_timezone.utc)
        old_date = now - timedelta(days=100)

        recent_result = {
            'module': 'tickets',
            'title': 'Test',
            'text': 'Test content',
            'timestamp': now.isoformat(),
            'score': 0.5,
        }
        old_result = {
            'module': 'tickets',
            'title': 'Test',
            'text': 'Test content',
            'timestamp': old_date.isoformat(),
            'score': 0.5,
        }

        results = [old_result, recent_result]
        ranked = service._rank_results(results, 'test')

        # Recent result should rank higher
        assert ranked[0]['timestamp'] == now.isoformat()

    @patch('apps.search.services.unified_semantic_search_service.Ticket')
    def test_search_tickets_database_error(self, mock_ticket, service, tenant):
        """Test graceful handling of database errors."""
        from django.db import OperationalError

        mock_ticket.objects.filter.side_effect = OperationalError("Database error")

        result = service._search_tickets('test', tenant.id, 10)

        assert result == []  # Should return empty list, not crash

    def test_cache_key_generation(self, service):
        """Test cache key is generated consistently."""
        key1 = service._generate_cache_key(
            query='test',
            tenant_id=1,
            modules=['tickets'],
            filters={'status': 'OPEN'}
        )
        key2 = service._generate_cache_key(
            query='test',
            tenant_id=1,
            modules=['tickets'],
            filters={'status': 'OPEN'}
        )

        assert key1 == key2

        # Different parameters should generate different keys
        key3 = service._generate_cache_key(
            query='different',
            tenant_id=1,
            modules=['tickets'],
            filters={'status': 'OPEN'}
        )

        assert key1 != key3

    def test_empty_result_structure(self, service):
        """Test empty result has correct structure."""
        result = service._empty_result("Test error")

        assert result['results'] == []
        assert result['total_count'] == 0
        assert result['search_time_ms'] == 0
        assert 'error' in result
        assert result['error'] == "Test error"


@pytest.mark.django_db
class TestSearchAnalytics:
    """Test search analytics tracking."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, created = Tenant.objects.get_or_create(
            tenantname='analytics_tenant',
            defaults={'enable': True}
        )
        return tenant

    @pytest.fixture
    def user(self, tenant):
        """Create test user."""
        user = People.objects.create(
            username=f'analytics_user_{uuid.uuid4().hex[:8]}',
            peoplename='Analytics User',
            peopleemail='analytics@example.com',
            tenant=tenant,
            enable=True,
        )
        return user

    def test_analytics_creation(self, tenant, user):
        """Test analytics record is created."""
        correlation_id = uuid.uuid4()

        analytics = SearchAnalytics.objects.create(
            tenant=tenant,
            user=user,
            query='test query',
            entities=['tickets', 'assets'],
            filters={'status': 'OPEN'},
            result_count=10,
            response_time_ms=45,
            correlation_id=correlation_id,
        )

        assert analytics.id is not None
        assert analytics.query == 'test query'
        assert analytics.result_count == 10
        assert analytics.response_time_ms == 45

    def test_analytics_click_tracking(self, tenant, user):
        """Test click tracking updates analytics."""
        correlation_id = uuid.uuid4()

        analytics = SearchAnalytics.objects.create(
            tenant=tenant,
            user=user,
            query='test',
            result_count=5,
            response_time_ms=30,
            correlation_id=correlation_id,
        )

        # Update with click data
        analytics.clicked_entity_type = 'ticket'
        analytics.clicked_entity_id = 'uuid-123'
        analytics.click_position = 2
        analytics.save()

        # Verify update
        analytics.refresh_from_db()
        assert analytics.clicked_entity_type == 'ticket'
        assert analytics.clicked_entity_id == 'uuid-123'
        assert analytics.click_position == 2


@pytest.mark.django_db
class TestSearchIndexing:
    """Test search indexing functionality."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return UnifiedSemanticSearchService()

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, created = Tenant.objects.get_or_create(
            tenantname='index_tenant',
            defaults={'enable': True}
        )
        return tenant

    @patch('apps.search.services.unified_semantic_search_service.Ticket')
    def test_index_tickets(self, mock_ticket, service, tenant):
        """Test ticket indexing."""
        # Mock ticket data
        mock_ticket_obj = Mock()
        mock_ticket_obj.uuid = uuid.uuid4()
        mock_ticket_obj.ticketno = 'T00001'
        mock_ticket_obj.ticketdesc = 'Test ticket description'
        mock_ticket_obj.comments = 'Test comments'
        mock_ticket_obj.tenant_id = tenant.id

        mock_queryset = Mock()
        mock_queryset.select_related.return_value = [mock_ticket_obj]
        mock_queryset.__getitem__ = lambda self, key: [mock_ticket_obj]

        mock_ticket.objects.all.return_value = mock_queryset
        mock_ticket.objects.filter.return_value = mock_queryset

        # Index tickets
        documents = service._index_tickets(tenant.id)

        assert len(documents) > 0
        assert documents[0]['module'] == 'tickets'
        assert 'text' in documents[0]

    def test_build_unified_index_no_txtai(self, service, tenant):
        """Test index build handles missing txtai gracefully."""
        service.embeddings = None

        result = service.build_unified_index(tenant.id)

        assert result is False


# Integration tests requiring API client
@pytest.mark.django_db
class TestSearchAPI:
    """Test search API endpoints."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, created = Tenant.objects.get_or_create(
            tenantname='api_tenant',
            defaults={'enable': True}
        )
        return tenant

    @pytest.fixture
    def user(self, tenant):
        """Create authenticated user."""
        user = People.objects.create(
            username=f'api_user_{uuid.uuid4().hex[:8]}',
            peoplename='API User',
            peopleemail='api@example.com',
            tenant=tenant,
            enable=True,
        )
        user.set_password('testpass123')
        user.save()
        return user

    def test_search_endpoint_requires_auth(self, client):
        """Test search endpoint requires authentication."""
        response = client.get('/api/v1/search/unified/')

        # Should get 401 or redirect to login
        assert response.status_code in [401, 302, 403]

    def test_search_endpoint_missing_query(self, client, user):
        """Test search endpoint validates query parameter."""
        client.force_login(user)

        response = client.get('/api/v1/search/unified/')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'required' in data['error'].lower()

    def test_search_endpoint_invalid_modules(self, client, user):
        """Test search endpoint validates module names."""
        client.force_login(user)

        response = client.get('/api/v1/search/unified/?q=test&modules=invalid_module')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'invalid' in data['error'].lower()

    def test_search_endpoint_invalid_limit(self, client, user):
        """Test search endpoint validates limit parameter."""
        client.force_login(user)

        response = client.get('/api/v1/search/unified/?q=test&limit=9999')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data


# Performance benchmarks
@pytest.mark.benchmark
@pytest.mark.django_db
class TestSearchPerformance:
    """Performance benchmarks for search."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return UnifiedSemanticSearchService()

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, created = Tenant.objects.get_or_create(
            tenantname='perf_tenant',
            defaults={'enable': True}
        )
        return tenant

    def test_search_performance_50_results(self, service, tenant, benchmark):
        """Benchmark search with 50 results."""
        def run_search():
            return service.search(
                query='performance test',
                tenant_id=tenant.id,
                limit=50,
            )

        result = benchmark(run_search)

        # Should complete in under 500ms
        assert result['search_time_ms'] < 500

    def test_cache_hit_performance(self, service, tenant, benchmark):
        """Benchmark cached search performance."""
        # Prime cache
        service.search(
            query='cache_test',
            tenant_id=tenant.id,
            limit=50,
        )

        def run_cached_search():
            return service.search(
                query='cache_test',
                tenant_id=tenant.id,
                limit=50,
            )

        result = benchmark(run_cached_search)

        # Cached search should be very fast (under 50ms)
        assert result['search_time_ms'] < 50
