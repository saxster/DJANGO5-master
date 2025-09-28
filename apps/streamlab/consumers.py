"""
WebSocket Consumers for Real-time Dashboard Updates
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from .models import TestRun, StreamEvent
from ..issue_tracker.models import AnomalyOccurrence


class StreamMetricsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time stream metrics updates
    """

    async def connect(self):
        # Check if user is staff
        if self.scope["user"] is AnonymousUser or not (
            self.scope["user"].is_staff or self.scope["user"].is_superuser
        ):
            await self.close(code=4403)
            return

        self.room_name = "stream_metrics"
        self.room_group_name = f"streamlab_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Start sending periodic updates
        asyncio.create_task(self.send_periodic_updates())

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'get_metrics':
                await self.send_metrics_update()
            elif message_type == 'get_anomalies':
                await self.send_anomalies_update()

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def send_periodic_updates(self):
        """Send periodic metric updates every 5 seconds"""
        while True:
            try:
                await asyncio.sleep(5)
                await self.send_metrics_update()
            except (ConnectionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
                # Consumer might be disconnected
                break

    async def send_metrics_update(self):
        """Send current metrics to client"""
        try:
            metrics = await self.get_current_metrics()

            await self.send(text_data=json.dumps({
                'type': 'metrics_update',
                'data': metrics
            }))

        except (ConnectionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def send_anomalies_update(self):
        """Send recent anomalies to client"""
        try:
            anomalies = await self.get_recent_anomalies()

            await self.send(text_data=json.dumps({
                'type': 'anomalies_update',
                'data': anomalies
            }))

        except (ConnectionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def get_current_metrics(self):
        """Get current stream metrics"""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        last_5_min = now - timedelta(minutes=5)

        # Get active runs
        active_runs = list(TestRun.objects.filter(
            status='running'
        ).select_related('scenario').values(
            'id', 'scenario__name', 'scenario__protocol',
            'total_events', 'successful_events', 'failed_events',
            'started_at'
        ))

        # Get recent events for active runs
        run_metrics = []
        for run in active_runs:
            recent_events = StreamEvent.objects.filter(
                run_id=run['id'],
                timestamp__gte=last_5_min
            )

            # Calculate metrics
            events_count = recent_events.count()
            if events_count > 0:
                avg_latency = recent_events.aggregate(
                    avg=models.Avg('latency_ms')
                )['avg'] or 0

                error_count = recent_events.filter(outcome='error').count()
                error_rate = (error_count / events_count) * 100 if events_count > 0 else 0
            else:
                avg_latency = 0
                error_rate = 0

            duration = (now - run['started_at']).total_seconds()

            run_metrics.append({
                'run_id': str(run['id']),
                'scenario_name': run['scenario__name'],
                'protocol': run['scenario__protocol'],
                'total_events': run['total_events'],
                'successful_events': run['successful_events'],
                'failed_events': run['failed_events'],
                'avg_latency_ms': round(avg_latency, 2),
                'error_rate': round(error_rate, 2),
                'duration_seconds': round(duration, 0),
                'events_last_5min': events_count
            })

        return {
            'active_runs': run_metrics,
            'timestamp': now.isoformat(),
            'total_active_runs': len(active_runs)
        }

    @database_sync_to_async
    def get_recent_anomalies(self):
        """Get recent anomalies"""
        from django.utils import timezone
        from datetime import timedelta

        last_hour = timezone.now() - timedelta(hours=1)

        anomalies = list(AnomalyOccurrence.objects.filter(
            created_at__gte=last_hour,
            status__in=['new', 'investigating']
        ).select_related('signature').values(
            'id', 'created_at', 'endpoint', 'error_message',
            'signature__anomaly_type', 'signature__severity',
            'latency_ms', 'status'
        ).order_by('-created_at')[:10])

        return [{
            'id': str(anomaly['id']),
            'type': anomaly['signature__anomaly_type'],
            'severity': anomaly['signature__severity'],
            'endpoint': anomaly['endpoint'],
            'error_message': anomaly['error_message'][:100] if anomaly['error_message'] else '',
            'latency_ms': anomaly['latency_ms'],
            'status': anomaly['status'],
            'created_at': anomaly['created_at'].isoformat()
        } for anomaly in anomalies]

    # Channel layer message handlers
    async def stream_event(self, event):
        """Handle stream events from channel layer"""
        await self.send(text_data=json.dumps({
            'type': 'stream_event',
            'data': event['data']
        }))

    async def anomaly_detected(self, event):
        """Handle anomaly detection events"""
        await self.send(text_data=json.dumps({
            'type': 'anomaly_detected',
            'data': event['data']
        }))


class AnomalyAlertsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time anomaly alerts
    """

    async def connect(self):
        # Check if user is staff
        if self.scope["user"] is AnonymousUser or not (
            self.scope["user"].is_staff or self.scope["user"].is_superuser
        ):
            await self.close(code=4403)
            return

        self.room_name = "anomaly_alerts"
        self.room_group_name = f"streamlab_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'acknowledge_anomaly':
                anomaly_id = text_data_json.get('anomaly_id')
                await self.acknowledge_anomaly(anomaly_id)

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    @database_sync_to_async
    def acknowledge_anomaly(self, anomaly_id):
        """Acknowledge an anomaly"""
        try:
            anomaly = AnomalyOccurrence.objects.get(id=anomaly_id)
            anomaly.status = 'investigating'
            anomaly.assigned_to = self.scope["user"]
            anomaly.save()

            return {
                'success': True,
                'anomaly_id': str(anomaly_id)
            }

        except AnomalyOccurrence.DoesNotExist:
            return {
                'success': False,
                'error': 'Anomaly not found'
            }

    # Channel layer message handlers
    async def new_anomaly(self, event):
        """Handle new anomaly alerts"""
        await self.send(text_data=json.dumps({
            'type': 'new_anomaly',
            'data': event['data']
        }))

    async def critical_anomaly(self, event):
        """Handle critical anomaly alerts"""
        await self.send(text_data=json.dumps({
            'type': 'critical_anomaly',
            'data': event['data']
        }))

    async def recurring_anomaly(self, event):
        """Handle recurring anomaly alerts"""
        await self.send(text_data=json.dumps({
            'type': 'recurring_anomaly',
            'data': event['data']
        }))

    async def escalation_alert(self, event):
        """Handle escalation alerts"""
        await self.send(text_data=json.dumps({
            'type': 'escalation_alert',
            'data': event['data']
        }))


# Helper function to send real-time updates
async def send_stream_event_update(event_data):
    """Send stream event update to dashboard"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            "streamlab_stream_metrics",
            {
                "type": "stream_event",
                "data": event_data
            }
        )


async def send_anomaly_alert(anomaly_data):
    """Send anomaly alert to dashboard"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            "streamlab_anomaly_alerts",
            {
                "type": "new_anomaly" if anomaly_data['severity'] != 'critical' else "critical_anomaly",
                "data": anomaly_data
            }
        )