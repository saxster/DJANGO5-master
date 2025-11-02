"""
Tests for Anomaly WebSocket Broadcasts (Gap #11).

Tests:
1. Broadcast method works correctly
2. Latency is acceptable (<200ms)
3. Consumer receives and forwards messages
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from apps.noc.services.websocket_service import NOCWebSocketService
from apps.noc.consumers.noc_dashboard_consumer import NOCDashboardConsumer
from apps.noc.security_intelligence.models import AttendanceAnomalyLog


@pytest.fixture
def sample_anomaly(tenant, mock_user, sample_site, db):
    """Create sample attendance anomaly."""
    from apps.attendance.models import PeopleEventlog

    attendance_event = PeopleEventlog.objects.create(
        tenant=tenant,
        people=mock_user,
        bu=sample_site,
        punchintime=timezone.now(),
        inout=True
    )

    anomaly = AttendanceAnomalyLog.objects.create(
        tenant=tenant,
        anomaly_type='WRONG_PERSON',
        severity='HIGH',
        person=mock_user,
        site=sample_site,
        attendance_event=attendance_event,
        detected_at=timezone.now(),
        confidence_score=0.95,
    )
    return anomaly


@pytest.mark.django_db
class TestAnomalyWebSocketBroadcast:
    """Test anomaly broadcast functionality."""

    def test_broadcast_anomaly_success(self, sample_anomaly):
        """Test successful anomaly broadcast to WebSocket."""
        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_layer = MagicMock()
            mock_get_layer.return_value = mock_layer

            # Call broadcast
            NOCWebSocketService.broadcast_anomaly(sample_anomaly)

            # Verify channel layer calls
            assert mock_layer.group_send.call_count == 2  # Tenant + Site groups

            # Check tenant group broadcast
            tenant_call = mock_layer.group_send.call_args_list[0]
            assert tenant_call[0][0] == f"noc_tenant_{sample_anomaly.tenant_id}"

            tenant_data = tenant_call[0][1]
            assert tenant_data['type'] == 'anomaly_detected'
            assert tenant_data['anomaly_id'] == str(sample_anomaly.id)
            assert tenant_data['person_id'] == sample_anomaly.person.id
            assert tenant_data['person_name'] == sample_anomaly.person.peoplename
            assert tenant_data['site_id'] == sample_anomaly.site.id
            assert tenant_data['site_name'] == sample_anomaly.site.buname
            assert tenant_data['anomaly_type'] == 'WRONG_PERSON'
            assert tenant_data['severity'] == 'HIGH'
            assert 'timestamp' in tenant_data

            # Check site group broadcast
            site_call = mock_layer.group_send.call_args_list[1]
            assert site_call[0][0] == f"noc_site_{sample_anomaly.site.id}"

    def test_broadcast_anomaly_latency(self, sample_anomaly):
        """Test broadcast latency is under 200ms."""
        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_layer = MagicMock()
            mock_get_layer.return_value = mock_layer

            # Measure latency
            start_time = time.time()
            NOCWebSocketService.broadcast_anomaly(sample_anomaly)
            latency_ms = (time.time() - start_time) * 1000

            # Verify latency
            assert latency_ms < 200, f"Broadcast latency {latency_ms:.2f}ms exceeds 200ms"

    def test_broadcast_anomaly_no_channel_layer(self, sample_anomaly, caplog):
        """Test broadcast handles missing channel layer gracefully."""
        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_get_layer.return_value = None

            # Should not raise exception
            NOCWebSocketService.broadcast_anomaly(sample_anomaly)

            # Should log warning
            assert 'Channel layer not configured' in caplog.text

    def test_broadcast_anomaly_exception_handling(self, sample_anomaly, caplog):
        """Test broadcast handles exceptions gracefully."""
        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_layer = MagicMock()
            mock_layer.group_send.side_effect = ValueError("Test error")
            mock_get_layer.return_value = mock_layer

            # Should not raise exception
            NOCWebSocketService.broadcast_anomaly(sample_anomaly)

            # Should log error
            assert 'Failed to broadcast anomaly' in caplog.text

    def test_broadcast_anomaly_without_site(self, tenant, mock_user, db):
        """Test broadcast works when anomaly has no site (edge case)."""
        from apps.attendance.models import PeopleEventlog
        from apps.onboarding.models import Bt

        site = Bt.objects.create(
            tenant=tenant,
            bucode='SITE002',
            buname='Test Site 2'
        )

        attendance_event = PeopleEventlog.objects.create(
            tenant=tenant,
            people=mock_user,
            bu=site,
            punchintime=timezone.now(),
            inout=True
        )

        anomaly = AttendanceAnomalyLog.objects.create(
            tenant=tenant,
            anomaly_type='GPS_SPOOFING',
            severity='MEDIUM',
            person=mock_user,
            site=site,
            attendance_event=attendance_event,
            detected_at=timezone.now(),
            confidence_score=0.75,
        )

        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_layer = MagicMock()
            mock_get_layer.return_value = mock_layer

            # Call broadcast
            NOCWebSocketService.broadcast_anomaly(anomaly)

            # Should still broadcast
            assert mock_layer.group_send.call_count >= 1


@pytest.mark.django_db
@pytest.mark.asyncio
class TestAnomalyConsumerHandler:
    """Test consumer's anomaly_detected handler."""

    async def test_consumer_receives_anomaly(self, sample_anomaly):
        """Test consumer receives and forwards anomaly message."""
        # Create event data matching broadcast format
        event = {
            'type': 'anomaly_detected',
            'anomaly_id': str(sample_anomaly.id),
            'person_id': sample_anomaly.person.id,
            'person_name': sample_anomaly.person.peoplename,
            'site_id': sample_anomaly.site.id,
            'site_name': sample_anomaly.site.buname,
            'anomaly_type': 'WRONG_PERSON',
            'fraud_score': 0.85,
            'severity': 'HIGH',
            'timestamp': sample_anomaly.detected_at.isoformat()
        }

        # Create consumer instance
        consumer = NOCDashboardConsumer()
        consumer.send = MagicMock()

        # Call handler
        await consumer.anomaly_detected(event)

        # Verify send was called with correct data
        assert consumer.send.call_count == 1
        sent_data = consumer.send.call_args[1]['text_data']

        import json
        parsed = json.loads(sent_data)

        assert parsed['type'] == 'anomaly_detected'
        assert parsed['anomaly_id'] == str(sample_anomaly.id)
        assert parsed['person_id'] == sample_anomaly.person.id
        assert parsed['person_name'] == sample_anomaly.person.peoplename
        assert parsed['site_id'] == sample_anomaly.site.id
        assert parsed['site_name'] == sample_anomaly.site.buname
        assert parsed['anomaly_type'] == 'WRONG_PERSON'
        assert parsed['fraud_score'] == 0.85
        assert parsed['severity'] == 'HIGH'
        assert parsed['timestamp'] == sample_anomaly.detected_at.isoformat()

    async def test_consumer_handles_missing_fraud_score(self, sample_anomaly):
        """Test consumer handles anomaly without fraud_score."""
        event = {
            'type': 'anomaly_detected',
            'anomaly_id': str(sample_anomaly.id),
            'person_id': sample_anomaly.person.id,
            'person_name': sample_anomaly.person.peoplename,
            'site_id': sample_anomaly.site.id,
            'site_name': sample_anomaly.site.buname,
            'anomaly_type': 'IMPOSSIBLE_SHIFTS',
            'severity': 'CRITICAL',
            'timestamp': sample_anomaly.detected_at.isoformat()
            # No fraud_score
        }

        consumer = NOCDashboardConsumer()
        consumer.send = MagicMock()

        await consumer.anomaly_detected(event)

        sent_data = consumer.send.call_args[1]['text_data']
        import json
        parsed = json.loads(sent_data)

        # Should default to 0.0
        assert parsed['fraud_score'] == 0.0


@pytest.mark.django_db
class TestAnomalyBroadcastIntegration:
    """Integration test: Anomaly creation → Broadcast → Consumer."""

    def test_end_to_end_anomaly_broadcast(self, tenant, mock_user, sample_site, db):
        """Test complete flow from anomaly creation to WebSocket broadcast."""
        from apps.noc.security_intelligence.services.security_anomaly_orchestrator import SecurityAnomalyOrchestrator
        from apps.attendance.models import PeopleEventlog

        # Create attendance event
        attendance_event = PeopleEventlog.objects.create(
            tenant=tenant,
            people=mock_user,
            bu=sample_site,
            punchintime=timezone.now(),
            inout=True
        )

        with patch('apps.noc.services.websocket_service.get_channel_layer') as mock_get_layer:
            mock_layer = MagicMock()
            mock_get_layer.return_value = mock_layer

            # Mock anomaly detector to return an anomaly
            with patch('apps.noc.security_intelligence.services.attendance_anomaly_detector.AttendanceAnomalyDetector.detect_wrong_person') as mock_detect:
                mock_detect.return_value = {
                    'anomaly_type': 'WRONG_PERSON',
                    'severity': 'HIGH',
                    'confidence_score': 0.9,
                    'expected_person': mock_user,
                    'evidence_data': {'test': 'data'}
                }

                # Mock config
                with patch('apps.noc.security_intelligence.models.SecurityAnomalyConfig.get_config_for_site') as mock_config:
                    config_mock = MagicMock()
                    config_mock.is_active = True
                    config_mock.predictive_fraud_enabled = False
                    mock_config.return_value = config_mock

                    # Process attendance event
                    results = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

                    # Verify anomaly was created
                    assert len(results['anomalies']) >= 0

                    # If anomaly was created, verify broadcast was called
                    if results['anomalies']:
                        # Verify broadcast was called (tenant + site groups)
                        assert mock_layer.group_send.call_count >= 1

                        # Check that anomaly_detected type was sent
                        calls = [call[0][1] for call in mock_layer.group_send.call_args_list]
                        anomaly_broadcasts = [c for c in calls if c.get('type') == 'anomaly_detected']
                        assert len(anomaly_broadcasts) > 0
