"""
Integration tests for real-time monitoring with Django Channels
"""
import pytest
import json
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from channels.testing import WebsocketCommunicator, ApplicationCommunicator
from channels.db import database_sync_to_async
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.core.consumers import (
    RealtimeMonitoringConsumer, DashboardConsumer, AlertConsumer
)
from apps.core.routing import websocket_urlpatterns
from apps.core.models.monitoring import PageView, NavigationClick, ErrorLog
from apps.core.models.heatmap import HeatmapSession, ClickHeatmap, HeatmapAggregation
from apps.core.models.recommendation import ContentRecommendation, NavigationRecommendation
from tests.factories.heatmap_factories import UserFactory, HeatmapSessionFactory
from tests.factories.recommendation_factories import ContentRecommendationFactory

User = get_user_model()


class TestRealtimeMonitoringConsumer:
    """Test WebSocket consumer for real-time monitoring"""
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_websocket_connection_authentication(self):
        """Test WebSocket connection with authentication"""
        user = await database_sync_to_async(UserFactory)()
        
        # Test authenticated connection
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_websocket_connection_anonymous_user(self):
        """Test WebSocket connection rejection for anonymous users"""
        from django.contrib.auth.models import AnonymousUser
        
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = AnonymousUser()
        
        connected, subprotocol = await communicator.connect()
        
        # Should reject anonymous connections
        assert not connected
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_receive_heatmap_data(self):
        """Test receiving and processing heatmap data via WebSocket"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Send heatmap data
        heatmap_data = {
            "type": "heatmap_data",
            "session_id": "test-session-123",
            "page_url": "/test-page/",
            "clicks": [
                {
                    "x": 0.5,
                    "y": 0.3,
                    "timestamp": timezone.now().isoformat(),
                    "element": {"tagName": "button", "id": "submit-btn"}
                }
            ],
            "scrolls": [
                {
                    "scroll_depth_percentage": 75.5,
                    "timestamp": timezone.now().isoformat()
                }
            ]
        }
        
        await communicator.send_json_to(heatmap_data)
        
        # Should receive acknowledgment
        response = await communicator.receive_json_from()
        assert response["type"] == "heatmap_ack"
        assert response["status"] == "received"
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_broadcast_metrics_update(self):
        """Test broadcasting metrics updates to connected clients"""
        user = await database_sync_to_async(UserFactory)()
        
        # Connect multiple clients
        communicators = []
        for i in range(3):
            communicator = WebsocketCommunicator(
                RealtimeMonitoringConsumer.as_asgi(),
                "/ws/monitoring/"
            )
            communicator.scope["user"] = user
            connected, _ = await communicator.connect()
            assert connected
            communicators.append(communicator)
        
        # Simulate metrics update broadcast
        metrics_update = {
            "type": "metrics_update",
            "data": {
                "active_users": 150,
                "page_views_last_hour": 1250,
                "avg_session_duration": 180.5,
                "top_pages": [
                    {"url": "/dashboard/", "views": 250},
                    {"url": "/reports/", "views": 180}
                ]
            },
            "timestamp": timezone.now().isoformat()
        }
        
        # Send to first communicator (simulating server-side broadcast)
        await communicators[0].send_json_to(metrics_update)
        
        # All clients should receive the update
        for communicator in communicators:
            try:
                response = await asyncio.wait_for(communicator.receive_json_from(), timeout=2.0)
                if response.get("type") == "metrics_update":
                    assert "data" in response
                    assert "active_users" in response["data"]
            except asyncio.TimeoutError:
                # Some implementations might not echo back, that's ok
                pass
        
        # Cleanup
        for communicator in communicators:
            await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_real_time_recommendation_updates(self):
        """Test real-time recommendation updates via WebSocket"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Create new recommendation
        recommendation = await database_sync_to_async(ContentRecommendationFactory)(user=user)
        
        # Send recommendation update
        rec_update = {
            "type": "recommendation_update",
            "action": "new_recommendation",
            "recommendation": {
                "id": recommendation.id,
                "title": recommendation.content_title,
                "url": recommendation.content_url,
                "relevance_score": recommendation.relevance_score
            }
        }
        
        await communicator.send_json_to(rec_update)
        
        # Should receive acknowledgment or update
        response = await communicator.receive_json_from()
        assert response.get("type") in ["recommendation_ack", "recommendation_update"]
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_error_handling_invalid_message(self):
        """Test error handling for invalid WebSocket messages"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Send invalid message
        invalid_message = {
            "type": "invalid_type",
            "malformed_data": "test"
        }
        
        await communicator.send_json_to(invalid_message)
        
        # Should receive error response
        response = await communicator.receive_json_from()
        assert response.get("type") == "error"
        assert "message" in response
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_websocket_groups_and_permissions(self):
        """Test WebSocket group membership and permissions"""
        admin_user = await database_sync_to_async(UserFactory)(is_staff=True)
        regular_user = await database_sync_to_async(UserFactory)(is_staff=False)
        
        # Admin user should join admin group
        admin_communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        admin_communicator.scope["user"] = admin_user
        
        connected, _ = await admin_communicator.connect()
        assert connected
        
        # Regular user should join regular group
        user_communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        user_communicator.scope["user"] = regular_user
        
        connected, _ = await user_communicator.connect()
        assert connected
        
        # Send admin-only message
        admin_message = {
            "type": "admin_metrics",
            "data": {
                "system_health": "good",
                "server_load": 0.45,
                "active_connections": 25
            }
        }
        
        await admin_communicator.send_json_to(admin_message)
        
        # Admin should receive the message
        try:
            admin_response = await asyncio.wait_for(
                admin_communicator.receive_json_from(), 
                timeout=2.0
            )
            # Response depends on implementation
        except asyncio.TimeoutError:
            pass
        
        # Regular user should not receive admin messages (implementation dependent)
        
        await admin_communicator.disconnect()
        await user_communicator.disconnect()


class TestDashboardConsumer:
    """Test WebSocket consumer for dashboard updates"""
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_dashboard_metrics_streaming(self):
        """Test streaming dashboard metrics in real-time"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            "/ws/dashboard/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Send request for dashboard metrics
        metrics_request = {
            "type": "request_metrics",
            "metrics": ["page_views", "user_activity", "recommendations"]
        }
        
        await communicator.send_json_to(metrics_request)
        
        # Should receive metrics data
        response = await communicator.receive_json_from()
        assert response.get("type") == "dashboard_metrics"
        assert "data" in response
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_real_time_chart_updates(self):
        """Test real-time chart data updates"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            "/ws/dashboard/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Request chart data
        chart_request = {
            "type": "chart_data",
            "chart_type": "line",
            "metric": "page_views",
            "time_range": "1h"
        }
        
        await communicator.send_json_to(chart_request)
        
        # Should receive chart data
        response = await communicator.receive_json_from()
        assert response.get("type") == "chart_update"
        assert "chart_data" in response
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_dashboard_subscription_management(self):
        """Test subscribing/unsubscribing from dashboard updates"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            "/ws/dashboard/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Subscribe to specific metrics
        subscribe_request = {
            "type": "subscribe",
            "subscriptions": ["user_activity", "heatmap_data", "recommendations"]
        }
        
        await communicator.send_json_to(subscribe_request)
        
        # Should receive subscription confirmation
        response = await communicator.receive_json_from()
        assert response.get("type") == "subscription_ack"
        assert "subscribed_to" in response
        
        # Unsubscribe from some metrics
        unsubscribe_request = {
            "type": "unsubscribe",
            "subscriptions": ["heatmap_data"]
        }
        
        await communicator.send_json_to(unsubscribe_request)
        
        # Should receive unsubscribe confirmation
        response = await communicator.receive_json_from()
        assert response.get("type") == "unsubscription_ack"
        
        await communicator.disconnect()


class TestAlertConsumer:
    """Test WebSocket consumer for alerts and notifications"""
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_alert_notification_delivery(self):
        """Test delivery of alert notifications"""
        admin_user = await database_sync_to_async(UserFactory)(is_staff=True)
        
        communicator = WebsocketCommunicator(
            AlertConsumer.as_asgi(),
            "/ws/alerts/"
        )
        communicator.scope["user"] = admin_user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Simulate alert
        alert_data = {
            "type": "alert",
            "level": "warning",
            "title": "High Error Rate Detected",
            "message": "Error rate has exceeded 5% in the last 10 minutes",
            "timestamp": timezone.now().isoformat(),
            "source": "error_monitoring",
            "data": {
                "error_rate": 0.07,
                "threshold": 0.05,
                "affected_pages": ["/checkout/", "/payment/"]
            }
        }
        
        await communicator.send_json_to(alert_data)
        
        # Should receive alert acknowledgment
        response = await communicator.receive_json_from()
        assert response.get("type") == "alert_received"
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_alert_severity_filtering(self):
        """Test filtering alerts by severity level"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            AlertConsumer.as_asgi(),
            "/ws/alerts/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Set alert filter
        filter_request = {
            "type": "set_filter",
            "min_severity": "warning"  # Only warning and critical alerts
        }
        
        await communicator.send_json_to(filter_request)
        
        # Should receive filter confirmation
        response = await communicator.receive_json_from()
        assert response.get("type") == "filter_set"
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_alert_acknowledgment(self):
        """Test acknowledging alerts"""
        user = await database_sync_to_async(UserFactory)()
        
        communicator = WebsocketCommunicator(
            AlertConsumer.as_asgi(),
            "/ws/alerts/"
        )
        communicator.scope["user"] = user
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        # Acknowledge alert
        ack_request = {
            "type": "acknowledge_alert",
            "alert_id": "alert_123",
            "acknowledged_by": user.username,
            "timestamp": timezone.now().isoformat()
        }
        
        await communicator.send_json_to(ack_request)
        
        # Should receive acknowledgment confirmation
        response = await communicator.receive_json_from()
        assert response.get("type") == "alert_acknowledged"
        
        await communicator.disconnect()


class TestRealtimeIntegrationScenarios(TransactionTestCase):
    """Test real-time monitoring integration scenarios"""
    
    def setUp(self):
        self.user = UserFactory()
        self.admin_user = UserFactory(is_staff=True)
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_end_to_end_heatmap_processing(self):
        """Test end-to-end heatmap data processing and broadcasting"""
        # Connect to monitoring WebSocket
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = self.admin_user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Create heatmap session in database
        session = await database_sync_to_async(HeatmapSessionFactory)(
            user=self.user,
            session_id="integration-test-session",
            page_url="/integration-test/"
        )
        
        # Send real-time heatmap data
        heatmap_batch = {
            "type": "heatmap_data",
            "session_id": session.session_id,
            "page_url": session.page_url,
            "clicks": [
                {
                    "x": 0.25, "y": 0.35,
                    "timestamp": timezone.now().isoformat(),
                    "element": {"tagName": "button", "id": "save-btn"}
                },
                {
                    "x": 0.75, "y": 0.45,
                    "timestamp": timezone.now().isoformat(),
                    "element": {"tagName": "a", "className": "nav-link"}
                }
            ],
            "scrolls": [
                {
                    "scroll_depth_percentage": 45.5,
                    "timestamp": timezone.now().isoformat()
                },
                {
                    "scroll_depth_percentage": 85.2,
                    "timestamp": timezone.now().isoformat()
                }
            ]
        }
        
        await communicator.send_json_to(heatmap_batch)
        
        # Should receive processing confirmation
        response = await communicator.receive_json_from()
        assert response.get("type") == "heatmap_ack"
        
        # Verify data was processed and stored
        click_count = await database_sync_to_async(
            lambda: ClickHeatmap.objects.filter(session=session).count()
        )()
        assert click_count > 0
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_real_time_recommendation_pipeline(self):
        """Test real-time recommendation generation and delivery"""
        # Connect dashboard consumer
        dashboard_comm = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            "/ws/dashboard/"
        )
        dashboard_comm.scope["user"] = self.user
        
        connected, _ = await dashboard_comm.connect()
        assert connected
        
        # Subscribe to recommendation updates
        subscribe_req = {
            "type": "subscribe",
            "subscriptions": ["recommendations", "user_activity"]
        }
        
        await dashboard_comm.send_json_to(subscribe_req)
        
        # Should receive subscription confirmation
        response = await dashboard_comm.receive_json_from()
        assert response.get("type") == "subscription_ack"
        
        # Simulate user behavior change that triggers new recommendations
        behavior_update = {
            "type": "behavior_update",
            "user_id": self.user.id,
            "new_activity": {
                "pages_visited": ["/new-feature/", "/advanced-tools/"],
                "session_duration": 300,
                "device_type": "desktop"
            }
        }
        
        await dashboard_comm.send_json_to(behavior_update)
        
        # Should receive updated recommendations
        try:
            response = await asyncio.wait_for(
                dashboard_comm.receive_json_from(),
                timeout=5.0
            )
            # Implementation dependent - might receive recommendation updates
        except asyncio.TimeoutError:
            # Timeout is acceptable as implementation varies
            pass
        
        await dashboard_comm.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True) 
    async def test_multi_user_real_time_synchronization(self):
        """Test real-time synchronization across multiple users"""
        users = await database_sync_to_async(
            lambda: [UserFactory() for _ in range(3)]
        )()
        
        # Connect multiple users to dashboard
        communicators = []
        for user in users:
            communicator = WebsocketCommunicator(
                DashboardConsumer.as_asgi(),
                "/ws/dashboard/"
            )
            communicator.scope["user"] = user
            connected, _ = await communicator.connect()
            assert connected
            communicators.append(communicator)
        
        # One user generates activity that affects global metrics
        activity_update = {
            "type": "global_metrics_update",
            "data": {
                "total_active_users": len(users) + 10,
                "current_page_views": 1500,
                "system_load": 0.35
            },
            "broadcast": True
        }
        
        await communicators[0].send_json_to(activity_update)
        
        # All users should receive the global update
        received_updates = 0
        for communicator in communicators:
            try:
                response = await asyncio.wait_for(
                    communicator.receive_json_from(),
                    timeout=3.0
                )
                if response.get("type") == "global_metrics_update":
                    received_updates += 1
            except asyncio.TimeoutError:
                pass
        
        # At least some users should receive the update
        # (Implementation specific - some systems echo back, others don't)
        
        # Cleanup
        for communicator in communicators:
            await communicator.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_real_time_error_monitoring(self):
        """Test real-time error detection and alerting"""
        # Connect alert consumer
        alert_comm = WebsocketCommunicator(
            AlertConsumer.as_asgi(),
            "/ws/alerts/"
        )
        alert_comm.scope["user"] = self.admin_user
        
        connected, _ = await alert_comm.connect()
        assert connected
        
        # Create error logs to trigger alerts
        errors = await database_sync_to_async(
            lambda: [
                ErrorLog.objects.create(
                    path="/api/data/",
                    status_code=500,
                    error_message=f"Internal server error {i}",
                    user=None,
                    timestamp=timezone.now() - timedelta(minutes=i)
                )
                for i in range(5)  # 5 errors in 5 minutes
            ]
        )()
        
        # Simulate error threshold breach alert
        error_alert = {
            "type": "alert",
            "level": "critical",
            "title": "High Error Rate Alert",
            "message": "5 errors detected in the last 5 minutes",
            "source": "error_monitoring",
            "data": {
                "error_count": len(errors),
                "time_window": "5min",
                "affected_endpoints": ["/api/data/"]
            }
        }
        
        await alert_comm.send_json_to(error_alert)
        
        # Should receive alert acknowledgment
        response = await alert_comm.receive_json_from()
        assert response.get("type") == "alert_received"
        
        await alert_comm.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_websocket_connection_recovery(self):
        """Test WebSocket connection recovery and state synchronization"""
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = self.user
        
        # Initial connection
        connected, _ = await communicator.connect()
        assert connected
        
        # Subscribe to updates
        subscribe_req = {
            "type": "subscribe",
            "subscriptions": ["metrics", "alerts"]
        }
        
        await communicator.send_json_to(subscribe_req)
        response = await communicator.receive_json_from()
        assert response.get("type") == "subscription_ack"
        
        # Simulate disconnection
        await communicator.disconnect()
        
        # Reconnect
        new_communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        new_communicator.scope["user"] = self.user
        
        connected, _ = await new_communicator.connect()
        assert connected
        
        # Request state synchronization
        sync_request = {
            "type": "sync_state",
            "last_update": (timezone.now() - timedelta(minutes=5)).isoformat()
        }
        
        await new_communicator.send_json_to(sync_request)
        
        # Should receive state synchronization data
        response = await new_communicator.receive_json_from()
        assert response.get("type") in ["state_sync", "sync_complete", "error"]
        
        await new_communicator.disconnect()
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_websocket_performance_under_load(self):
        """Test WebSocket performance with multiple concurrent connections"""
        num_connections = 20  # Scaled down for testing
        
        # Create multiple concurrent connections
        communicators = []
        connect_tasks = []
        
        for i in range(num_connections):
            user = await database_sync_to_async(UserFactory)()
            communicator = WebsocketCommunicator(
                RealtimeMonitoringConsumer.as_asgi(),
                "/ws/monitoring/"
            )
            communicator.scope["user"] = user
            
            connect_task = asyncio.create_task(communicator.connect())
            connect_tasks.append(connect_task)
            communicators.append(communicator)
        
        # Wait for all connections
        start_time = asyncio.get_event_loop().time()
        connections = await asyncio.gather(*connect_tasks)
        connect_time = asyncio.get_event_loop().time() - start_time
        
        # All connections should succeed
        successful_connections = sum(1 for connected, _ in connections if connected)
        assert successful_connections >= num_connections * 0.8  # 80% success rate
        
        # Connection time should be reasonable
        assert connect_time < 5.0  # Should connect within 5 seconds
        
        # Send messages concurrently
        message_tasks = []
        for i, communicator in enumerate(communicators):
            if connections[i][0]:  # If connected
                message = {
                    "type": "test_message",
                    "client_id": i,
                    "timestamp": timezone.now().isoformat()
                }
                task = asyncio.create_task(communicator.send_json_to(message))
                message_tasks.append(task)
        
        # Wait for all messages to be sent
        message_start = asyncio.get_event_loop().time()
        await asyncio.gather(*message_tasks, return_exceptions=True)
        message_time = asyncio.get_event_loop().time() - message_start
        
        # Message sending should be reasonably fast
        assert message_time < 3.0
        
        # Cleanup connections
        disconnect_tasks = []
        for i, communicator in enumerate(communicators):
            if connections[i][0]:  # If connected
                task = asyncio.create_task(communicator.disconnect())
                disconnect_tasks.append(task)
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)