"""
Monitoring Dashboard WebSocket Consumer

Real-time updates for operational monitoring dashboard.
Provides live alerts, device status, and system metrics.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.core.cache import cache

from apps.monitoring.services.monitoring_service import monitoring_service

logger = logging.getLogger('monitoring.websocket')


class MonitoringDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time monitoring dashboard.

    Provides:
    - Live alert streams
    - Device status updates
    - System health metrics
    - Interactive dashboard controls
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_role = None
        self.dashboard_id = str(uuid.uuid4())
        self.subscriptions = set()
        self.update_task = None
        self.heartbeat_task = None

    async def connect(self):
        """Handle WebSocket connection for monitoring dashboard"""
        try:
            # Authenticate user
            self.user = self.scope.get('user')

            if self.user is None or isinstance(self.user, AnonymousUser):
                logger.warning("Unauthorized monitoring dashboard connection attempt")
                await self.close(code=4401)
                return

            # Check if user has monitoring permissions
            if not await self._has_monitoring_permissions():
                logger.warning(f"User {self.user.id} lacks monitoring permissions")
                await self.close(code=4403)
                return

            # Join monitoring dashboard group
            await self.channel_layer.group_add(
                'monitoring_dashboard',
                self.channel_name
            )

            # Join user-specific group for personalized updates
            await self.channel_layer.group_add(
                f'monitoring_user_{self.user.id}',
                self.channel_name
            )

            await self.accept()

            # Send initial dashboard data
            await self._send_initial_dashboard_data()

            # Start periodic updates
            self.update_task = asyncio.create_task(self._periodic_updates())
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(f"Monitoring dashboard connected for user {self.user.id}")

        except Exception as e:
            logger.error(f"Error connecting monitoring dashboard: {str(e)}", exc_info=True)
            await self.close(code=4500)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Cancel background tasks
            if self.update_task:
                self.update_task.cancel()
            if self.heartbeat_task:
                self.heartbeat_task.cancel()

            # Leave groups
            await self.channel_layer.group_discard(
                'monitoring_dashboard',
                self.channel_name
            )

            if self.user:
                await self.channel_layer.group_discard(
                    f'monitoring_user_{self.user.id}',
                    self.channel_name
                )

            logger.info(f"Monitoring dashboard disconnected for user {self.user.id if self.user else 'Unknown'}")

        except Exception as e:
            logger.error(f"Error disconnecting monitoring dashboard: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming messages from dashboard"""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')

            logger.debug(f"Dashboard message received: {message_type}")

            if message_type == 'subscribe_alerts':
                await self._handle_alert_subscription(message)
            elif message_type == 'acknowledge_alert':
                await self._handle_alert_acknowledgment(message)
            elif message_type == 'resolve_alert':
                await self._handle_alert_resolution(message)
            elif message_type == 'get_device_status':
                await self._handle_device_status_request(message)
            elif message_type == 'get_system_health':
                await self._handle_system_health_request(message)
            elif message_type == 'force_monitoring_update':
                await self._handle_force_monitoring_update(message)
            elif message_type == 'dashboard_settings':
                await self._handle_dashboard_settings(message)
            else:
                await self._send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in dashboard message")
            await self._send_error("Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling dashboard message: {str(e)}")
            await self._send_error(f"Message processing error: {str(e)}")

    async def _send_initial_dashboard_data(self):
        """Send initial data when dashboard connects"""
        try:
            # Get system overview
            system_health = await self._get_system_health()

            # Get active alerts
            active_alerts = await self._get_active_alerts()

            # Get device status summary
            device_summary = await self._get_device_summary()

            # Get recent metrics
            recent_metrics = await self._get_recent_metrics()

            await self._send_message({
                'type': 'dashboard_initial_data',
                'data': {
                    'system_health': system_health,
                    'active_alerts': active_alerts,
                    'device_summary': device_summary,
                    'recent_metrics': recent_metrics,
                    'dashboard_id': self.dashboard_id,
                    'user_permissions': await self._get_user_permissions(),
                    'timestamp': timezone.now().isoformat()
                }
            })

        except Exception as e:
            logger.error(f"Error sending initial dashboard data: {str(e)}")

    async def _periodic_updates(self):
        """Send periodic updates to dashboard"""
        try:
            while True:
                await asyncio.sleep(30)  # Update every 30 seconds

                # Get updated metrics
                system_health = await self._get_system_health()
                device_summary = await self._get_device_summary()

                await self._send_message({
                    'type': 'dashboard_update',
                    'data': {
                        'system_health': system_health,
                        'device_summary': device_summary,
                        'timestamp': timezone.now().isoformat()
                    }
                })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in periodic updates: {str(e)}")

    async def _heartbeat_loop(self):
        """Send heartbeat to maintain connection"""
        try:
            while True:
                await asyncio.sleep(60)  # Heartbeat every minute

                await self._send_message({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat(),
                    'dashboard_id': self.dashboard_id
                })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {str(e)}")

    async def _handle_alert_subscription(self, message: Dict):
        """Handle alert subscription requests"""
        try:
            subscription_types = message.get('alert_types', [])
            severity_filters = message.get('severity_filters', [])

            # Update subscriptions
            self.subscriptions = set(subscription_types)

            await self._send_message({
                'type': 'subscription_confirmed',
                'subscriptions': list(self.subscriptions),
                'severity_filters': severity_filters
            })

        except Exception as e:
            logger.error(f"Error handling alert subscription: {str(e)}")

    async def _handle_alert_acknowledgment(self, message: Dict):
        """Handle alert acknowledgment from dashboard"""
        try:
            alert_id = message.get('alert_id')
            notes = message.get('notes', '')

            if not alert_id:
                await self._send_error("Missing alert_id")
                return

            # Acknowledge alert
            success = await self._acknowledge_alert(alert_id, self.user.id, notes)

            await self._send_message({
                'type': 'alert_acknowledgment_response',
                'alert_id': alert_id,
                'success': success,
                'acknowledged_by': self.user.peoplename,
                'acknowledged_at': timezone.now().isoformat()
            })

            if success:
                # Broadcast acknowledgment to all dashboard users
                await self.channel_layer.group_send(
                    'monitoring_dashboard',
                    {
                        'type': 'alert_acknowledged',
                        'alert_id': alert_id,
                        'acknowledged_by': self.user.peoplename,
                        'acknowledged_at': timezone.now().isoformat()
                    }
                )

        except Exception as e:
            logger.error(f"Error handling alert acknowledgment: {str(e)}")

    async def _handle_alert_resolution(self, message: Dict):
        """Handle alert resolution from dashboard"""
        try:
            alert_id = message.get('alert_id')
            resolution_notes = message.get('notes', '')

            if not alert_id:
                await self._send_error("Missing alert_id")
                return

            # Resolve alert
            success = await self._resolve_alert(alert_id, self.user.id, resolution_notes)

            await self._send_message({
                'type': 'alert_resolution_response',
                'alert_id': alert_id,
                'success': success,
                'resolved_by': self.user.peoplename,
                'resolved_at': timezone.now().isoformat()
            })

            if success:
                # Broadcast resolution to all dashboard users
                await self.channel_layer.group_send(
                    'monitoring_dashboard',
                    {
                        'type': 'alert_resolved',
                        'alert_id': alert_id,
                        'resolved_by': self.user.peoplename,
                        'resolved_at': timezone.now().isoformat()
                    }
                )

        except Exception as e:
            logger.error(f"Error handling alert resolution: {str(e)}")

    async def _handle_device_status_request(self, message: Dict):
        """Handle device status requests"""
        try:
            device_id = message.get('device_id')
            user_id = message.get('user_id')

            if device_id and user_id:
                # Get detailed device status
                device_status = await self._get_device_status(user_id, device_id)

                await self._send_message({
                    'type': 'device_status_response',
                    'device_id': device_id,
                    'user_id': user_id,
                    'status': device_status
                })

        except Exception as e:
            logger.error(f"Error handling device status request: {str(e)}")

    async def _handle_force_monitoring_update(self, message: Dict):
        """Handle forced monitoring update requests"""
        try:
            user_id = message.get('user_id')
            device_id = message.get('device_id')

            if user_id and device_id:
                # Force monitoring update
                monitoring_result = await self._force_monitoring_update(user_id, device_id)

                await self._send_message({
                    'type': 'monitoring_update_response',
                    'user_id': user_id,
                    'device_id': device_id,
                    'result': monitoring_result
                })

        except Exception as e:
            logger.error(f"Error handling force monitoring update: {str(e)}")

    # Channel layer message handlers

    async def alert_notification(self, event):
        """Handle new alert notifications"""
        try:
            alert_data = event.get('alert', {})

            # Check if user is subscribed to this alert type
            alert_type = alert_data.get('alert_type', '')
            if not self.subscriptions or alert_type in self.subscriptions:
                await self._send_message({
                    'type': 'new_alert',
                    'alert': alert_data
                })

        except Exception as e:
            logger.error(f"Error handling alert notification: {str(e)}")

    async def alert_acknowledged(self, event):
        """Handle alert acknowledgment broadcasts"""
        await self._send_message({
            'type': 'alert_acknowledged',
            'alert_id': event.get('alert_id'),
            'acknowledged_by': event.get('acknowledged_by'),
            'acknowledged_at': event.get('acknowledged_at')
        })

    async def alert_resolved(self, event):
        """Handle alert resolution broadcasts"""
        await self._send_message({
            'type': 'alert_resolved',
            'alert_id': event.get('alert_id'),
            'resolved_by': event.get('resolved_by'),
            'resolved_at': event.get('resolved_at')
        })

    async def system_metric_update(self, event):
        """Handle system metric updates"""
        await self._send_message({
            'type': 'system_metric_update',
            'metrics': event.get('metrics', {})
        })

    async def device_status_update(self, event):
        """Handle device status updates"""
        await self._send_message({
            'type': 'device_status_update',
            'device_updates': event.get('device_updates', [])
        })

    # Database access methods

    @database_sync_to_async
    def _has_monitoring_permissions(self) -> bool:
        """Check if user has monitoring dashboard permissions"""
        try:
            # Simplified permission check - in production would be more sophisticated
            return self.user.is_staff or self.user.isadmin

        except Exception as e:
            logger.error(f"Error checking monitoring permissions: {str(e)}")
            return False

    @database_sync_to_async
    def _get_system_health(self) -> Dict:
        """Get current system health metrics"""
        try:
            return monitoring_service.get_system_health()

        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    @database_sync_to_async
    def _get_active_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        try:
            from apps.monitoring.models import Alert

            alerts = Alert.objects.filter(
                status='ACTIVE'
            ).select_related('user', 'site', 'rule').order_by('-triggered_at')[:50]

            return [{
                'alert_id': str(alert.alert_id),
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity,
                'alert_type': alert.rule.alert_type,
                'user_name': alert.user.peoplename,
                'user_id': alert.user.id,
                'site_name': alert.site.buname if alert.site else 'Unknown',
                'device_id': alert.device_id,
                'triggered_at': alert.triggered_at.isoformat(),
                'escalation_level': alert.escalation_level,
                'is_overdue': alert.is_overdue
            } for alert in alerts]

        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}")
            return []

    @database_sync_to_async
    def _get_device_summary(self) -> Dict:
        """Get device status summary"""
        try:
            from apps.monitoring.models import DeviceHealthSnapshot
            from apps.core.models import UserDevice

            # Get recent device snapshots
            recent_cutoff = timezone.now() - timedelta(minutes=30)
            recent_snapshots = DeviceHealthSnapshot.objects.filter(
                snapshot_taken_at__gte=recent_cutoff
            ).select_related('user')

            # Calculate summary statistics
            total_devices = UserDevice.objects.filter(is_active=True).count()
            online_devices = recent_snapshots.count()

            health_breakdown = {}
            for snapshot in recent_snapshots:
                health = snapshot.overall_health
                health_breakdown[health] = health_breakdown.get(health, 0) + 1

            # Calculate averages
            avg_battery = recent_snapshots.aggregate(
                avg=models.Avg('battery_level')
            )['avg'] or 0

            devices_at_risk = recent_snapshots.filter(risk_score__gt=0.7).count()

            return {
                'total_devices': total_devices,
                'online_devices': online_devices,
                'offline_devices': total_devices - online_devices,
                'health_breakdown': health_breakdown,
                'avg_battery_level': round(avg_battery, 1),
                'devices_at_risk': devices_at_risk,
                'last_updated': timezone.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting device summary: {str(e)}")
            return {}

    @database_sync_to_async
    def _get_recent_metrics(self) -> List[Dict]:
        """Get recent system metrics for charts"""
        try:
            from apps.monitoring.models import MonitoringMetric

            # Get metrics from last hour
            recent_cutoff = timezone.now() - timedelta(hours=1)
            metrics = MonitoringMetric.objects.filter(
                recorded_at__gte=recent_cutoff
            ).order_by('-recorded_at')[:100]

            return [{
                'metric_type': metric.metric_type,
                'value': metric.value,
                'unit': metric.unit,
                'user_id': metric.user.id,
                'device_id': metric.device_id,
                'recorded_at': metric.recorded_at.isoformat()
            } for metric in metrics]

        except Exception as e:
            logger.error(f"Error getting recent metrics: {str(e)}")
            return []

    @database_sync_to_async
    def _acknowledge_alert(self, alert_id: str, user_id: int, notes: str) -> bool:
        """Acknowledge an alert"""
        try:
            return monitoring_service.alert_service.acknowledge_alert(
                alert_id, user_id, 'DASHBOARD', notes
            )

        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            return False

    @database_sync_to_async
    def _resolve_alert(self, alert_id: str, user_id: int, notes: str) -> bool:
        """Resolve an alert"""
        try:
            return monitoring_service.alert_service.resolve_alert(alert_id, user_id, notes)

        except Exception as e:
            logger.error(f"Error resolving alert: {str(e)}")
            return False

    @database_sync_to_async
    def _get_device_status(self, user_id: int, device_id: str) -> Dict:
        """Get detailed device status"""
        try:
            return monitoring_service.monitor_device(user_id, device_id)

        except Exception as e:
            logger.error(f"Error getting device status: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    @database_sync_to_async
    def _force_monitoring_update(self, user_id: int, device_id: str) -> Dict:
        """Force monitoring update for a device"""
        try:
            return monitoring_service.force_monitoring_update(user_id, device_id)

        except Exception as e:
            logger.error(f"Error forcing monitoring update: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    @database_sync_to_async
    def _get_user_permissions(self) -> Dict:
        """Get user permissions for dashboard features"""
        try:
            return {
                'can_acknowledge_alerts': True,
                'can_resolve_alerts': self.user.is_staff or self.user.isadmin,
                'can_create_tickets': True,
                'can_view_all_sites': self.user.is_staff,
                'can_modify_settings': self.user.is_superuser
            }

        except Exception as e:
            logger.error(f"Error getting user permissions: {str(e)}")
            return {}

    # Helper methods

    async def _send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket client"""
        try:
            await self.send(text_data=json.dumps(message, default=str))

        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")

    async def _send_error(self, error_message: str):
        """Send error message to client"""
        try:
            await self._send_message({
                'type': 'error',
                'error': error_message,
                'timestamp': timezone.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")

    async def _handle_dashboard_settings(self, message: Dict):
        """Handle dashboard settings updates"""
        try:
            settings = message.get('settings', {})

            # Update dashboard preferences
            # This could be stored in user preferences
            await self._send_message({
                'type': 'settings_updated',
                'settings': settings
            })

        except Exception as e:
            logger.error(f"Error handling dashboard settings: {str(e)}")

    async def _handle_system_health_request(self, message: Dict):
        """Handle system health status requests"""
        try:
            system_health = await self._get_system_health()

            await self._send_message({
                'type': 'system_health_response',
                'system_health': system_health
            })

        except Exception as e:
            logger.error(f"Error handling system health request: {str(e)}")


class AlertStreamConsumer(AsyncWebsocketConsumer):
    """
    Dedicated consumer for high-frequency alert streaming.

    Optimized for real-time alert delivery with minimal latency.
    """

    async def connect(self):
        """Connect to alert stream"""
        user = self.scope.get('user')

        if user is None or isinstance(user, AnonymousUser):
            await self.close(code=4401)
            return

        # Join alert stream group
        await self.channel_layer.group_add('alert_stream', self.channel_name)
        await self.accept()

        logger.info(f"Alert stream connected for user {user.id}")

    async def disconnect(self, close_code):
        """Disconnect from alert stream"""
        await self.channel_layer.group_discard('alert_stream', self.channel_name)

    async def new_alert(self, event):
        """Handle new alert in stream"""
        await self.send(text_data=json.dumps({
            'type': 'new_alert',
            'alert': event['alert']
        }))

    async def alert_update(self, event):
        """Handle alert status updates"""
        await self.send(text_data=json.dumps({
            'type': 'alert_update',
            'update': event['update']
        }))