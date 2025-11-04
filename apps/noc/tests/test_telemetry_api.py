"""
Tests for NOC Telemetry API Endpoints.

Tests the three telemetry REST API endpoints:
- GET /api/v2/noc/telemetry/signals/<person_id>/
- GET /api/v2/noc/telemetry/signals/site/<site_id>/
- GET /api/v2/noc/telemetry/correlations/
"""

import pytest
import json
from django.test import Client
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.noc.models import CorrelatedIncident, NOCAlertEvent


@pytest.mark.django_db
class TestPersonSignalsEndpoint:
    """Test GET /api/v2/noc/telemetry/signals/<person_id>/"""

    def test_person_signals_success(self, client, authenticated_user, tenant, site_bt):
        """Test successful person signals retrieval."""
        # Create person with organizational data
        person = People.objects.create(
            tenant=tenant,
            peoplename='Test Guard',
            isactive=True
        )

        # Mock peopleorganizational
        from apps.peoples.models import PeopleOrganizational
        PeopleOrganizational.objects.create(
            tenant=tenant,
            people=person,
            bu=site_bt
        )

        # Make request
        url = f'/api/v2/noc/telemetry/signals/{person.id}/'
        response = client.get(url)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'data' in data
        assert data['data']['person_id'] == person.id
        assert 'signals' in data['data']

    def test_person_signals_authentication_required(self, client):
        """Test endpoint requires authentication."""
        url = '/api/v2/noc/telemetry/signals/1/'
        response = client.get(url)
        assert response.status_code in [302, 401, 403]  # Redirect to login or forbidden

    def test_person_signals_rbac_capability_required(self, client, user_without_noc_capability):
        """Test endpoint requires 'noc:view' capability."""
        client.force_login(user_without_noc_capability)
        url = '/api/v2/noc/telemetry/signals/1/'
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_person_signals_caching(self, client, authenticated_user, tenant):
        """Test Redis caching with 60-second TTL."""
        person = People.objects.create(
            tenant=tenant,
            peoplename='Cached Test',
            isactive=True
        )

        # First request (cache miss)
        url = f'/api/v2/noc/telemetry/signals/{person.id}/'
        response1 = client.get(url)
        data1 = response1.json()
        assert data1.get('cached') is False

        # Second request (cache hit)
        response2 = client.get(url)
        data2 = response2.json()
        assert data2.get('cached') is True

        # Verify cache key
        cache_key = f'telemetry:person:{person.id}'
        assert cache.get(cache_key) is not None

    def test_person_signals_window_parameter(self, client, authenticated_user, tenant):
        """Test window_minutes query parameter."""
        person = People.objects.create(
            tenant=tenant,
            peoplename='Window Test',
            isactive=True
        )

        url = f'/api/v2/noc/telemetry/signals/{person.id}/?window_minutes=60'
        response = client.get(url)
        data = response.json()

        assert data['status'] == 'success'
        assert data['data']['window_minutes'] == 60

    def test_person_signals_not_found(self, client, authenticated_user):
        """Test 404 for non-existent person."""
        url = '/api/v2/noc/telemetry/signals/999999/'
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestSiteSignalsEndpoint:
    """Test GET /api/v2/noc/telemetry/signals/site/<site_id>/"""

    def test_site_signals_aggregation(self, client, authenticated_user, tenant, site_bt):
        """Test site-level signal aggregation."""
        # Create multiple people at site
        for i in range(3):
            person = People.objects.create(
                tenant=tenant,
                peoplename=f'Guard {i}',
                isactive=True
            )
            from apps.peoples.models import PeopleOrganizational
            PeopleOrganizational.objects.create(
                tenant=tenant,
                people=person,
                bu=site_bt
            )

        url = f'/api/v2/noc/telemetry/signals/site/{site_bt.id}/'
        response = client.get(url)

        data = response.json()
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert data['data']['active_people_count'] == 3
        assert 'aggregated_signals' in data['data']

    def test_site_signals_caching(self, client, authenticated_user, tenant, site_bt):
        """Test site signals caching."""
        url = f'/api/v2/noc/telemetry/signals/site/{site_bt.id}/'

        # First request
        response1 = client.get(url)
        assert response1.json()['cached'] is False

        # Second request (cached)
        response2 = client.get(url)
        assert response2.json()['cached'] is True

    def test_site_signals_no_active_people(self, client, authenticated_user, tenant, site_bt):
        """Test site with no active people."""
        url = f'/api/v2/noc/telemetry/signals/site/{site_bt.id}/'
        response = client.get(url)

        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['active_people_count'] == 0


@pytest.mark.django_db
class TestCorrelationsEndpoint:
    """Test GET /api/v2/noc/telemetry/correlations/"""

    def test_correlations_filtering(self, client, authenticated_user, tenant, site_bt):
        """Test correlation endpoint with filters."""
        # Create correlated incident
        person = People.objects.create(
            tenant=tenant,
            peoplename='Correlation Test'
        )

        CorrelatedIncident.objects.create(
            tenant=tenant,
            person=person,
            site=site_bt,
            signals={'phone_events_count': 0},
            combined_severity='HIGH'
        )

        url = '/api/v2/noc/telemetry/correlations/?min_severity=MEDIUM'
        response = client.get(url)

        data = response.json()
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert data['data']['total_count'] >= 1

    def test_correlations_site_filter(self, client, authenticated_user, tenant, site_bt):
        """Test filtering by site_id."""
        person = People.objects.create(tenant=tenant, peoplename='Site Filter Test')

        CorrelatedIncident.objects.create(
            tenant=tenant,
            person=person,
            site=site_bt,
            signals={},
            combined_severity='MEDIUM'
        )

        url = f'/api/v2/noc/telemetry/correlations/?site_id={site_bt.id}'
        response = client.get(url)

        data = response.json()
        assert data['status'] == 'success'
        assert all(inc['site_id'] == site_bt.id for inc in data['data']['incidents'])

    def test_correlations_time_window(self, client, authenticated_user, tenant):
        """Test hours parameter for time window."""
        url = '/api/v2/noc/telemetry/correlations/?hours=12'
        response = client.get(url)

        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['filters']['hours'] == 12


@pytest.mark.django_db
class TestTelemetryAPIPerformance:
    """Test telemetry API performance characteristics."""

    def test_response_time_under_500ms(self, client, authenticated_user, tenant, benchmark):
        """Test API response time meets <500ms target."""
        person = People.objects.create(tenant=tenant, peoplename='Perf Test')
        url = f'/api/v2/noc/telemetry/signals/{person.id}/'

        # Benchmark the request
        result = benchmark(lambda: client.get(url))

        # Verify <500ms (0.5 seconds)
        assert result.stats.mean < 0.5  # seconds
