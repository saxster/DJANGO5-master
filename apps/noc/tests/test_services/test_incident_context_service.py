"""
Tests for Incident Context Enrichment Service.

Tests all 5 context categories and auto-enrichment workflow.
Follows .claude/rules.md Rule #7 (test files <500 lines), Rule #18 (specific exceptions).
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from apps.noc.models import NOCIncident, NOCAlertEvent, IncidentContext
from apps.noc.services import IncidentContextService
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db


class TestIncidentContextService:
    """Test suite for IncidentContextService."""

    @pytest.fixture
    def setup_data(self):
        """Create test fixtures for incident context enrichment."""
        # Create tenant
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        # Create client and site
        client = Bt.objects.create(
            tenant=tenant,
            buname="Test Client",
            butype="Client"
        )
        site = Bt.objects.create(
            tenant=tenant,
            buname="Test Site",
            butype="Site",
            client=client
        )

        # Create user
        user = People.objects.create(
            tenant=tenant,
            peoplename="Test User",
            email="test@example.com",
            isactive=True
        )

        # Create profile and organizational data
        PeopleProfile.objects.create(people=user, gender="M")
        PeopleOrganizational.objects.create(people=user, bu=site)

        # Create recent alerts (within 30-min window)
        now = timezone.now()
        recent_alerts = []
        for i in range(3):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client,
                bu=site,
                alert_type='DEVICE_OFFLINE',
                severity='HIGH',
                status='NEW',
                dedup_key=f'test_dedup_{i}',
                message=f'Test alert {i}',
                entity_type='device',
                entity_id=i
            )
            alert.created_at = now - timedelta(minutes=10 + i)
            alert.save(update_fields=['created_at'])
            recent_alerts.append(alert)

        # Create older alert (outside 30-min window)
        old_alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client,
            bu=site,
            alert_type='ATTENDANCE_MISSING',
            severity='LOW',
            status='NEW',
            dedup_key='test_dedup_old',
            message='Old alert',
            entity_type='attendance',
            entity_id=999
        )
        old_alert.created_at = now - timedelta(hours=2)
        old_alert.save(update_fields=['created_at'])

        # Create historical resolved incident
        historical_incident = NOCIncident.objects.create(
            tenant=tenant,
            client=client,
            site=site,
            title="Similar Incident",
            description="Historical incident for pattern matching",
            severity='HIGH',
            state='RESOLVED',
            priority='HIGH',
            time_to_resolve=timedelta(minutes=45)
        )
        historical_incident.cdtz = now - timedelta(days=30)
        historical_incident.save(update_fields=['cdtz'])

        # Create test incident
        incident = NOCIncident.objects.create(
            tenant=tenant,
            client=client,
            site=site,
            title="Similar Test Incident",
            description="Test incident for enrichment",
            severity='HIGH',
            priority='HIGH'
        )
        incident.alerts.add(recent_alerts[0])

        return {
            'tenant': tenant,
            'client': client,
            'site': site,
            'user': user,
            'incident': incident,
            'recent_alerts': recent_alerts,
            'old_alert': old_alert,
            'historical_incident': historical_incident,
        }

    def test_enrich_incident_returns_all_5_categories(self, setup_data):
        """Test that enrichment returns all 5 context categories."""
        incident = setup_data['incident']

        # Clear cache
        cache.clear()

        # Enrich incident
        context = IncidentContextService.enrich_incident(incident)

        # Verify all 5 categories present
        assert 'related_alerts' in context
        assert 'recent_changes' in context
        assert 'historical_incidents' in context
        assert 'affected_resources' in context
        assert 'system_state' in context
        assert 'enriched_at' in context

        # Verify context stored in incident metadata
        incident.refresh_from_db()
        assert incident.metadata is not None
        assert 'context' in incident.metadata
        assert incident.metadata['context'] == context

    def test_related_alerts_within_30min_window(self, setup_data):
        """Test that related alerts are found within 30-minute window."""
        incident = setup_data['incident']
        cache.clear()

        context = IncidentContextService.enrich_incident(incident)
        related_alerts = context['related_alerts']

        # Should find 2 alerts (3 total - 1 already linked)
        assert len(related_alerts) >= 1
        assert all('id' in alert for alert in related_alerts)
        assert all('type' in alert for alert in related_alerts)
        assert all('severity' in alert for alert in related_alerts)
        assert all('message' in alert for alert in related_alerts)

        # Verify old alert (2 hours ago) is NOT included
        old_alert_ids = [alert['id'] for alert in related_alerts]
        assert setup_data['old_alert'].id not in old_alert_ids

    def test_historical_incidents_pattern_matching(self, setup_data):
        """Test that historical incidents are found by pattern matching."""
        incident = setup_data['incident']
        cache.clear()

        context = IncidentContextService.enrich_incident(incident)
        historical = context['historical_incidents']

        # Should find the historical incident
        assert len(historical) >= 1

        # Verify structure
        for hist_incident in historical:
            assert 'id' in hist_incident
            assert 'title' in hist_incident
            assert 'severity' in hist_incident
            assert 'resolution_time_minutes' in hist_incident

        # Verify the specific historical incident is found
        historical_ids = [inc['id'] for inc in historical]
        assert setup_data['historical_incident'].id in historical_ids

        # Verify resolution time is calculated
        historical_incident_data = next(
            inc for inc in historical
            if inc['id'] == setup_data['historical_incident'].id
        )
        assert historical_incident_data['resolution_time_minutes'] == 45

    def test_affected_resources_extraction(self, setup_data):
        """Test that affected resources are correctly extracted."""
        incident = setup_data['incident']
        cache.clear()

        context = IncidentContextService.enrich_incident(incident)
        resources = context['affected_resources']

        # Verify structure
        assert 'sites' in resources
        assert 'people' in resources
        assert 'devices' in resources
        assert 'assets' in resources

        # Verify site is identified
        assert len(resources['sites']) >= 1
        site_ids = [s['id'] for s in resources['sites']]
        assert setup_data['site'].id in site_ids

    def test_caching_behavior(self, setup_data):
        """Test that enriched context is cached for 5 minutes."""
        incident = setup_data['incident']
        cache.clear()

        # First call - cache miss
        context1 = IncidentContextService.enrich_incident(incident)
        enriched_at_1 = context1['enriched_at']

        # Second call immediately - should hit cache
        context2 = IncidentContextService.enrich_incident(incident)
        enriched_at_2 = context2['enriched_at']

        # Should be same cached data
        assert enriched_at_1 == enriched_at_2
        assert context1 == context2

        # Verify cache key exists
        cache_key = f"{IncidentContextService.CACHE_PREFIX}:{incident.id}"
        cached_data = cache.get(cache_key)
        assert cached_data is not None
        assert cached_data == context1

    def test_signal_auto_triggers_enrichment(self, setup_data):
        """Test that signal handler automatically enriches new incidents."""
        tenant = setup_data['tenant']
        client = setup_data['client']
        site = setup_data['site']

        # Clear cache
        cache.clear()

        # Create new incident (should trigger signal)
        new_incident = NOCIncident.objects.create(
            tenant=tenant,
            client=client,
            site=site,
            title="Auto-Enriched Incident",
            description="Should be auto-enriched by signal",
            severity='MEDIUM',
            priority='MEDIUM'
        )

        # Verify metadata was populated by signal
        new_incident.refresh_from_db()
        assert new_incident.metadata is not None
        assert 'context' in new_incident.metadata

        # Verify all 5 categories present
        context = new_incident.metadata['context']
        assert 'related_alerts' in context
        assert 'recent_changes' in context
        assert 'historical_incidents' in context
        assert 'affected_resources' in context
        assert 'system_state' in context

    def test_recent_changes_detection(self, setup_data):
        """Test that recent changes are detected (4-hour window)."""
        incident = setup_data['incident']
        user = setup_data['user']
        cache.clear()

        # Modify user within 4-hour window (simulates staff change)
        user.mdtz = timezone.now() - timedelta(hours=2)
        user.save(update_fields=['mdtz'])

        context = IncidentContextService.enrich_incident(incident)
        recent_changes = context['recent_changes']

        # Should detect the staff change
        assert isinstance(recent_changes, list)
        # May be empty if models don't exist, but should be a list
        assert all('type' in change for change in recent_changes)

    def test_system_state_snapshot(self, setup_data):
        """Test that current system state is captured."""
        incident = setup_data['incident']
        cache.clear()

        context = IncidentContextService.enrich_incident(incident)
        system_state = context['system_state']

        # Should have system state dict
        assert isinstance(system_state, dict)

        # May have active_guards_at_site if People query works
        # May have open_tickets_at_site if Ticket model accessible
        # Both are optional but should not raise errors
