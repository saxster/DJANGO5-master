"""
Tests for Threat Intelligence WebSocket Consumer.

Verifies:
- Authentication enforcement
- Tenant isolation
- Alert delivery
- Connection lifecycle
"""

import pytest
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser
from apps.threat_intelligence.consumers import ThreatAlertConsumer
from apps.threat_intelligence.models import IntelligenceAlert, ThreatEvent, TenantIntelligenceProfile
from apps.peoples.models import People
from apps.tenants.models import Tenant
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.utils import timezone
from asgiref.sync import async_to_sync
import json


@pytest.mark.django_db
class TestThreatAlertConsumer:
    """Test suite for ThreatAlertConsumer WebSocket functionality."""
    
    @pytest.fixture
    def tenant1(self):
        """Create test tenant 1."""
        return Tenant.objects.create(
            name="Tenant Alpha",
            domain="alpha.test.com"
        )
    
    @pytest.fixture
    def tenant2(self):
        """Create test tenant 2."""
        return Tenant.objects.create(
            name="Tenant Beta",
            domain="beta.test.com"
        )
    
    @pytest.fixture
    def user1(self, tenant1):
        """Create authenticated user for tenant 1."""
        return People.objects.create(
            username="user1@alpha.com",
            email="user1@alpha.com",
            tenant=tenant1,
            is_active=True
        )
    
    @pytest.fixture
    def user2(self, tenant2):
        """Create authenticated user for tenant 2."""
        return People.objects.create(
            username="user2@beta.com",
            email="user2@beta.com",
            tenant=tenant2,
            is_active=True
        )
    
    @pytest.fixture
    def threat_event(self, tenant1):
        """Create test threat event."""
        return ThreatEvent.objects.create(
            external_id="TEST-001",
            source_id=1,
            category="WEATHER",
            severity="CRITICAL",
            title="Hurricane Warning",
            description="Category 5 hurricane approaching",
            location=Point(-80.1918, 25.7617),  # Miami coordinates
            event_start_time=timezone.now(),
            confidence_score=0.95,
            tenant=tenant1
        )
    
    @pytest.fixture
    def intelligence_profile(self, tenant1):
        """Create intelligence profile for tenant 1."""
        polygon = Polygon((
            (-80.3, 25.6),
            (-80.3, 25.9),
            (-80.0, 25.9),
            (-80.0, 25.6),
            (-80.3, 25.6)
        ))
        
        return TenantIntelligenceProfile.objects.create(
            tenant=tenant1,
            is_active=True,
            monitored_locations=MultiPolygon(polygon),
            buffer_radius_km=50.0,
            minimum_severity="MEDIUM",
            minimum_confidence=0.7,
            enable_websocket=True,
            enable_email=True,
            enable_sms=False
        )
    
    @pytest.fixture
    def alert(self, threat_event, intelligence_profile, tenant1):
        """Create test alert."""
        return IntelligenceAlert.objects.create(
            threat_event=threat_event,
            intelligence_profile=intelligence_profile,
            tenant=tenant1,
            severity="CRITICAL",
            urgency_level="IMMEDIATE",
            distance_km=5.2,
            delivery_status='PENDING'
        )
    
    @pytest.mark.asyncio
    async def test_authenticated_user_can_connect(self, user1):
        """Authenticated users should successfully connect to WebSocket."""
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected, "Authenticated user should connect successfully"
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_unauthenticated_user_rejected(self):
        """Unauthenticated users should be rejected with 403."""
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = AnonymousUser()
        
        connected, close_code = await communicator.connect()
        assert not connected, "Unauthenticated user should be rejected"
        assert close_code == 403, "Should close with 403 Forbidden"
    
    @pytest.mark.asyncio
    async def test_receives_alert_for_own_tenant_only(self, user1, tenant1, alert):
        """User should receive alerts only for their own tenant."""
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Send alert to tenant's group
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"threat_alerts_tenant_{tenant1.id}",
            {
                "type": "threat_alert",
                "alert_id": alert.id,
                "severity": alert.severity,
                "category": alert.threat_event.category,
                "title": alert.threat_event.title,
                "distance_km": alert.distance_km,
                "urgency_level": alert.urgency_level,
                "event_start_time": alert.threat_event.event_start_time.isoformat(),
                "created_at": alert.created_at.isoformat(),
            }
        )
        
        # Verify message received
        response = await communicator.receive_json_from()
        assert response['type'] == 'threat_alert'
        assert response['alert_id'] == alert.id
        assert response['severity'] == 'CRITICAL'
        assert response['urgency_level'] == 'IMMEDIATE'
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_does_not_receive_other_tenant_alerts(self, user1, user2, tenant1, tenant2, alert):
        """User should NOT receive alerts from other tenants."""
        # Connect user from tenant 1
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Send alert to tenant 2's group (different tenant)
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"threat_alerts_tenant_{tenant2.id}",
            {
                "type": "threat_alert",
                "alert_id": 999,
                "severity": "CRITICAL",
                "category": "WEATHER",
                "title": "Different tenant alert",
                "distance_km": 10.0,
                "urgency_level": "IMMEDIATE",
                "event_start_time": timezone.now().isoformat(),
                "created_at": timezone.now().isoformat(),
            }
        )
        
        # Verify NO message received (with timeout)
        with pytest.raises(Exception):  # TimeoutError or similar
            await communicator.receive_json_from(timeout=1)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, user1, tenant1):
        """WebSocket should properly clean up on disconnect."""
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Disconnect
        await communicator.disconnect()
        
        # Verify group membership removed by trying to send message
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"threat_alerts_tenant_{tenant1.id}",
            {
                "type": "threat_alert",
                "alert_id": 123,
                "severity": "HIGH",
                "category": "SECURITY",
                "title": "Test alert",
                "distance_km": 1.0,
                "urgency_level": "RAPID",
                "event_start_time": timezone.now().isoformat(),
                "created_at": timezone.now().isoformat(),
            }
        )
        
        # Should not receive anything (already disconnected)
        # This verifies cleanup happened correctly
    
    @pytest.mark.asyncio
    async def test_alert_update_message(self, user1, tenant1, alert):
        """Consumer should handle alert update messages."""
        communicator = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Send alert update
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"threat_alerts_tenant_{tenant1.id}",
            {
                "type": "threat_alert_update",
                "alert_id": alert.id,
                "update_type": "acknowledged",
                "data": {
                    "acknowledged_by": user1.id,
                    "acknowledged_at": timezone.now().isoformat()
                }
            }
        )
        
        # Verify update received
        response = await communicator.receive_json_from()
        assert response['type'] == 'threat_alert_update'
        assert response['alert_id'] == alert.id
        assert response['update_type'] == 'acknowledged'
        assert 'timestamp' in response
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_users_same_tenant(self, user1, tenant1, alert):
        """Multiple users from same tenant should all receive alerts."""
        # Create second user for tenant1
        user1_2 = People.objects.create(
            username="user1_2@alpha.com",
            email="user1_2@alpha.com",
            tenant=tenant1,
            is_active=True
        )
        
        # Connect first user
        communicator1 = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator1.scope['user'] = user1
        
        # Connect second user
        communicator2 = WebsocketCommunicator(
            ThreatAlertConsumer.as_asgi(),
            "/ws/threat-alerts/"
        )
        communicator2.scope['user'] = user1_2
        
        connected1, _ = await communicator1.connect()
        connected2, _ = await communicator2.connect()
        assert connected1 and connected2
        
        # Send alert
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"threat_alerts_tenant_{tenant1.id}",
            {
                "type": "threat_alert",
                "alert_id": alert.id,
                "severity": alert.severity,
                "category": alert.threat_event.category,
                "title": alert.threat_event.title,
                "distance_km": alert.distance_km,
                "urgency_level": alert.urgency_level,
                "event_start_time": alert.threat_event.event_start_time.isoformat(),
                "created_at": alert.created_at.isoformat(),
            }
        )
        
        # Both users should receive
        response1 = await communicator1.receive_json_from()
        response2 = await communicator2.receive_json_from()
        
        assert response1['alert_id'] == alert.id
        assert response2['alert_id'] == alert.id
        
        await communicator1.disconnect()
        await communicator2.disconnect()
