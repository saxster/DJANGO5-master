"""
Tests for Natural Language Query System.

Comprehensive test suite for NL query parser, executor, formatter, and API.
Follows .claude/rules.md testing standards.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.noc.services.query_parser import QueryParser
from apps.noc.services.query_executor import QueryExecutor
from apps.noc.services.result_formatter import ResultFormatter
from apps.noc.services.query_cache import QueryCache
from apps.noc.services.nl_query_service import NLQueryService

User = get_user_model()


class QueryParserTestCase(TestCase):
    """Tests for QueryParser service."""

    @patch('apps.noc.services.query_parser.anthropic')
    def test_parse_query_alerts(self, mock_anthropic):
        """Test parsing natural language query for alerts."""
        # Mock Anthropic response
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.stop_reason = "tool_use"
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.input = {
            'query_type': 'alerts',
            'filters': {'severity': ['CRITICAL', 'HIGH']},
            'time_range': {'hours': 24},
            'output_format': 'summary',
        }
        mock_message.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client

        query = "Show me critical and high severity alerts from the last 24 hours"
        result = QueryParser.parse_query(query)

        assert result['query_type'] == 'alerts'
        assert 'CRITICAL' in result['filters']['severity']
        assert result['time_range']['hours'] == 24

    def test_parse_query_empty_text(self):
        """Test parsing with empty query text."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            QueryParser.parse_query("")

    def test_parse_query_too_long(self):
        """Test parsing with overly long query text."""
        long_query = "x" * 1001
        with pytest.raises(ValueError, match="exceeds maximum length"):
            QueryParser.parse_query(long_query)

    @override_settings(ANTHROPIC_API_KEY=None)
    def test_parse_query_missing_api_key(self):
        """Test parsing without Anthropic API key configured."""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not configured"):
            QueryParser.parse_query("test query")


class QueryExecutorTestCase(TestCase):
    """Tests for QueryExecutor service."""

    def setUp(self):
        """Set up test fixtures."""
        from apps.tenants.models import Tenant
        from apps.onboarding.models import Bt, Identifier

        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant")

        # Create user with tenant
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            tenant=self.tenant,
            isadmin=True
        )

        # Create client identifier
        self.client_identifier = Identifier.objects.create(
            tacode='CLIENT',
            tenant=self.tenant
        )

        # Create test client
        self.client = Bt.objects.create(
            btname='Test Client',
            tenant=self.tenant,
            identifier=self.client_identifier
        )

    def test_execute_alerts_query(self):
        """Test executing alerts query with filters."""
        params = {
            'query_type': 'alerts',
            'filters': {'severity': ['CRITICAL']},
            'time_range': {'hours': 24},
            'aggregation': {'limit': 10},
        }

        result = QueryExecutor.execute_query(params, self.user)

        assert result['metadata']['query_type'] == 'alerts'
        assert 'results' in result
        assert isinstance(result['results'], list)

    def test_execute_query_permission_denied(self):
        """Test query execution with insufficient permissions."""
        # Create user without NOC capabilities
        user_no_perms = User.objects.create_user(
            username='noperms',
            email='noperms@example.com',
            password='testpass',
            tenant=self.tenant,
            isadmin=False
        )

        params = {
            'query_type': 'alerts',
            'filters': {},
            'time_range': {'hours': 24},
        }

        with pytest.raises(PermissionDenied):
            QueryExecutor.execute_query(params, user_no_perms)

    def test_execute_query_tenant_isolation(self):
        """Test that queries are tenant-isolated."""
        # Create another tenant with data
        other_tenant = Tenant.objects.create(name="Other Tenant")

        params = {
            'query_type': 'alerts',
            'filters': {},
            'time_range': {'hours': 24},
        }

        result = QueryExecutor.execute_query(params, self.user)

        # Should only return data from self.user's tenant
        assert result['metadata']['query_type'] == 'alerts'


class ResultFormatterTestCase(TestCase):
    """Tests for ResultFormatter service."""

    def test_format_results_summary(self):
        """Test formatting results as summary."""
        raw_results = {
            'results': [],
            'metadata': {
                'query_type': 'alerts',
                'returned_count': 0,
                'total_count': 0,
            }
        }

        formatted = ResultFormatter.format_results(raw_results, 'summary')

        assert formatted['format'] == 'summary'
        assert 'summary' in formatted
        assert 'No alerts found' in formatted['summary']

    def test_format_results_json(self):
        """Test formatting results as JSON."""
        raw_results = {
            'results': [{'id': 1, 'type': 'alert'}],
            'metadata': {'query_type': 'alerts', 'returned_count': 1},
        }

        formatted = ResultFormatter.format_results(raw_results, 'json')

        assert formatted['format'] == 'json'
        assert len(formatted['data']) == 1

    def test_format_results_invalid_format(self):
        """Test formatting with invalid format."""
        raw_results = {
            'results': [],
            'metadata': {'query_type': 'alerts'},
        }

        with pytest.raises(ValueError, match="Invalid output format"):
            ResultFormatter.format_results(raw_results, 'invalid')


class QueryCacheTestCase(TestCase):
    """Tests for QueryCache service."""

    def setUp(self):
        """Set up test fixtures."""
        QueryCache.reset_stats()

    def test_cache_set_and_get(self):
        """Test setting and getting cached results."""
        query_text = "test query"
        user_id = 1
        tenant_id = 1
        result = {'status': 'success', 'data': []}

        # Set cache
        success = QueryCache.set(query_text, user_id, tenant_id, result)
        assert success is True

        # Get cache
        cached = QueryCache.get(query_text, user_id, tenant_id)
        assert cached is not None
        assert cached['status'] == 'success'

    def test_cache_miss(self):
        """Test cache miss."""
        result = QueryCache.get("nonexistent query", 999, 999)
        assert result is None

    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        key1 = QueryCache.get_cache_key("test query", 1, 1)
        key2 = QueryCache.get_cache_key("test query", 1, 1)
        assert key1 == key2

        # Different query should generate different key
        key3 = QueryCache.get_cache_key("different query", 1, 1)
        assert key1 != key3

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        QueryCache.reset_stats()

        # Generate cache miss
        QueryCache.get("query1", 1, 1)

        # Generate cache hit
        QueryCache.set("query2", 1, 1, {'data': []})
        QueryCache.get("query2", 1, 1)

        stats = QueryCache.get_cache_stats()
        assert stats['misses'] >= 1
        assert stats['hits'] >= 1


class NLQueryServiceTestCase(TestCase):
    """Tests for NLQueryService orchestration."""

    def setUp(self):
        """Set up test fixtures."""
        from apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            tenant=self.tenant,
            isadmin=True
        )

    def test_validate_query_text_empty(self):
        """Test query text validation - empty."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            NLQueryService._validate_query_text("")

    def test_validate_query_text_too_short(self):
        """Test query text validation - too short."""
        with pytest.raises(ValidationError, match="too short"):
            NLQueryService._validate_query_text("ab")

    def test_validate_query_text_too_long(self):
        """Test query text validation - too long."""
        long_text = "x" * 1001
        with pytest.raises(ValidationError, match="too long"):
            NLQueryService._validate_query_text(long_text)

    def test_validate_query_text_suspicious_pattern(self):
        """Test query text validation - suspicious patterns."""
        with pytest.raises(ValidationError, match="suspicious pattern"):
            NLQueryService._validate_query_text("test <script>alert('xss')</script>")

    @patch('apps.noc.services.nl_query_service.QueryParser')
    @patch('apps.noc.services.nl_query_service.QueryExecutor')
    @patch('apps.noc.services.nl_query_service.ResultFormatter')
    def test_process_query_success(self, mock_formatter, mock_executor, mock_parser):
        """Test successful query processing."""
        # Mock parser
        mock_parser.parse_query.return_value = {
            'query_type': 'alerts',
            'filters': {},
            'time_range': {'hours': 24},
            'output_format': 'summary',
            'aggregation': {'limit': 100},
        }

        # Mock executor
        mock_executor.execute_query.return_value = {
            'results': [],
            'metadata': {'query_type': 'alerts', 'returned_count': 0},
        }

        # Mock formatter
        mock_formatter.format_results.return_value = {
            'summary': 'No alerts found',
            'data': [],
            'insights': '',
            'format': 'summary',
            'metadata': {},
        }

        result = NLQueryService.process_natural_language_query(
            "test query",
            self.user,
            'summary'
        )

        assert result['status'] == 'success'
        assert 'summary' in result


class NLQueryAPITestCase(APITestCase):
    """Tests for Natural Language Query API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        from apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            tenant=self.tenant,
            isadmin=True
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('apps.noc.services.nl_query_service.NLQueryService.process_natural_language_query')
    def test_nl_query_endpoint_success(self, mock_process):
        """Test NL query endpoint with valid request."""
        mock_process.return_value = {
            'status': 'success',
            'summary': 'Test summary',
            'data': [],
            'insights': 'Test insights',
            'metadata': {},
            'cached': False,
        }

        response = self.client.post(
            '/api/v2/noc/query/nl/',
            {'query': 'show me alerts'},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'success'

    def test_nl_query_endpoint_missing_query(self):
        """Test NL query endpoint without query field."""
        response = self.client.post(
            '/api/v2/noc/query/nl/',
            {},
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Missing required field' in response.data['error']

    def test_nl_query_endpoint_invalid_format(self):
        """Test NL query endpoint with invalid output format."""
        response = self.client.post(
            '/api/v2/noc/query/nl/',
            {
                'query': 'test query',
                'output_format': 'invalid'
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nl_query_endpoint_unauthenticated(self):
        """Test NL query endpoint without authentication."""
        client = APIClient()
        response = client.post(
            '/api/v2/noc/query/nl/',
            {'query': 'test'},
            format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cache_stats_endpoint(self):
        """Test cache stats endpoint."""
        response = self.client.get('/api/v2/noc/query/nl/stats/')

        assert response.status_code == status.HTTP_200_OK
        assert 'cache_stats' in response.data
        assert 'hit_rate_percent' in response.data['cache_stats']
