"""
Unit tests for AlertCorrelationService.

Tests de-duplication, correlation logic, and maintenance window suppression.
Follows .claude/rules.md testing guidelines with specific exceptions.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.noc.services import AlertCorrelationService
from apps.noc.models import NOCAlertEvent, MaintenanceWindow
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestAlertCorrelationService:
    """Test suite for AlertCorrelationService."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")

    @pytest.fixture
    def client_bt(self, tenant):
        """Create test client business unit."""
        from apps.core_onboarding.models import TypeAssist
        client_type = TypeAssist.objects.create(
            taname="CLIENT",
            tacode="CLIENT",
            tenant=tenant
        )
        return Bt.objects.create(
            tenant=tenant,
            bucode="CLIENT001",
            buname="Test Client",
            identifier=client_type
        )

    @pytest.fixture
    def alert_data(self, tenant, client_bt):
        """Create sample alert data."""
        return {
            'tenant': tenant,
            'client': client_bt,
            'bu': None,
            'alert_type': 'DEVICE_OFFLINE',
            'severity': 'HIGH',
            'message': 'Test device is offline',
            'entity_type': 'device',
            'entity_id': 123,
            'metadata': {'device_name': 'TestDevice'},
        }

    def test_alert_creation(self, alert_data):
        """Test basic alert creation through service."""
        alert = AlertCorrelationService.process_alert(alert_data)

        assert alert is not None
        assert alert.id is not None
        assert alert.status == 'NEW'
        assert alert.alert_type == 'DEVICE_OFFLINE'
        assert alert.dedup_key is not None

    def test_alert_deduplication(self, alert_data):
        """Test that duplicate alerts are deduplicated."""
        alert1 = AlertCorrelationService.process_alert(alert_data)
        alert2 = AlertCorrelationService.process_alert(alert_data)

        assert alert1.id == alert2.id
        assert alert2.suppressed_count == 1

        alert3 = AlertCorrelationService.process_alert(alert_data)
        assert alert3.id == alert1.id
        alert3.refresh_from_db()
        assert alert3.suppressed_count == 2

    def test_dedup_key_generation(self, alert_data):
        """Test deterministic dedup key generation."""
        key1 = AlertCorrelationService._generate_dedup_key(alert_data)
        key2 = AlertCorrelationService._generate_dedup_key(alert_data)

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    def test_maintenance_window_suppression(self, tenant, client_bt, alert_data):
        """Test alert suppression during maintenance window."""
        MaintenanceWindow.objects.create(
            tenant=tenant,
            client=client_bt,
            title="Test Maintenance",
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            suppress_all=True,
            reason="Planned maintenance",
            is_active=True
        )

        alert = AlertCorrelationService.process_alert(alert_data)
        assert alert is None

    def test_specific_alert_type_suppression(self, tenant, client_bt, alert_data):
        """Test suppression of specific alert types during maintenance."""
        MaintenanceWindow.objects.create(
            tenant=tenant,
            client=client_bt,
            title="Partial Suppression",
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            suppress_all=False,
            suppress_alerts=['DEVICE_OFFLINE', 'SYNC_DEGRADED'],
            reason="Network maintenance",
            is_active=True
        )

        alert = AlertCorrelationService.process_alert(alert_data)
        assert alert is None

        alert_data['alert_type'] = 'TICKET_ESCALATED'
        alert2 = AlertCorrelationService.process_alert(alert_data)
        assert alert2 is not None

    def test_correlation_id_assignment(self, alert_data):
        """Test correlation ID assignment for related alerts."""
        alert1 = AlertCorrelationService.process_alert(alert_data)
        assert alert1.correlation_id is not None

        alert_data['entity_id'] = 456
        alert2 = AlertCorrelationService.process_alert(alert_data)

        assert alert2.correlation_id is not None

    def test_invalid_alert_data(self):
        """Test handling of invalid alert data."""
        with pytest.raises(ValueError):
            AlertCorrelationService.process_alert({})

        with pytest.raises(ValueError):
            AlertCorrelationService.process_alert({'alert_type': 'TEST'})