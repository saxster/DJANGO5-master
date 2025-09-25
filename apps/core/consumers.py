"""
WebSocket consumers for real-time analytics features
"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from apps.core.models.heatmap import HeatmapSession, HeatmapAggregation
from apps.ab_testing.models import Experiment, Assignment, Conversion
from apps.ab_testing.analytics import ExperimentAnalyzer

User = get_user_model()


class HeatmapRealtimeConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time heatmap data updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.page_url = self.scope['url_route']['kwargs'].get('page_url', '')
        self.room_group_name = f'heatmap_{self.page_url.replace("/", "_")}'
        
        # Check user permissions
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial heatmap data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_live_data':
                await self.send_live_data()
            elif message_type == 'change_filters':
                await self.handle_filter_change(text_data_json.get('filters', {}))
            elif message_type == 'subscribe_to_page':
                await self.handle_page_subscription(text_data_json.get('page_url', ''))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    async def send_initial_data(self):
        """Send initial heatmap data for the page"""
        data = await self.get_heatmap_data()
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'data': data
        }))
    
    async def send_live_data(self):
        """Send live heatmap data updates"""
        data = await self.get_live_heatmap_data()
        await self.send(text_data=json.dumps({
            'type': 'live_update',
            'data': data
        }))
    
    async def handle_filter_change(self, filters):
        """Handle filter changes from client"""
        # Store filters in session/cache for this connection
        cache_key = f'heatmap_filters_{self.channel_name}'
        cache.set(cache_key, filters, 3600)  # 1 hour
        
        # Send updated data with new filters
        data = await self.get_heatmap_data(filters)
        await self.send(text_data=json.dumps({
            'type': 'filtered_data',
            'data': data,
            'filters': filters
        }))
    
    async def handle_page_subscription(self, page_url):
        """Handle subscription to a different page"""
        # Leave current group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Join new group
        self.page_url = page_url
        self.room_group_name = f'heatmap_{page_url.replace("/", "_")}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Send data for new page
        await self.send_initial_data()
    
    @database_sync_to_async
    def get_heatmap_data(self, filters=None):
        """Get heatmap data for the page"""
        if not filters:
            filters = {}
        
        # Calculate time range
        time_range = filters.get('time_range', '1h')
        device_type = filters.get('device_type', 'all')
        
        end_date = timezone.now()
        if time_range == '1h':
            start_date = end_date - timedelta(hours=1)
        elif time_range == '24h':
            start_date = end_date - timedelta(days=1)
        elif time_range == '7d':
            start_date = end_date - timedelta(days=7)
        else:
            start_date = end_date - timedelta(hours=1)
        
        # Get sessions
        sessions = HeatmapSession.objects.filter(
            page_url=self.page_url,
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        if device_type != 'all':
            sessions = sessions.filter(device_type=device_type)
        
        # Get aggregated data
        try:
            aggregation = HeatmapAggregation.objects.filter(
                page_url=self.page_url,
                period_start__gte=start_date,
                device_type=device_type if device_type != 'all' else 'all'
            ).order_by('-period_start').first()
            
            if aggregation:
                return {
                    'session_count': aggregation.session_count,
                    'total_clicks': aggregation.total_clicks,
                    'total_scrolls': aggregation.total_scrolls,
                    'avg_session_duration': aggregation.avg_session_duration,
                    'avg_scroll_depth': aggregation.avg_scroll_depth,
                    'click_heatmap_data': aggregation.click_heatmap_data,
                    'scroll_depth_distribution': aggregation.scroll_depth_distribution,
                    'interaction_summary': aggregation.interaction_summary,
                    'last_updated': aggregation.created_at.isoformat()
                }
        except Exception:
            pass
        
        # Fallback to real-time calculation
        session_count = sessions.count()
        total_clicks = sum(session.clicks.count() for session in sessions)
        total_scrolls = sum(session.scrolls.count() for session in sessions)
        
        avg_duration = 0
        if session_count > 0:
            durations = [s.duration_seconds for s in sessions if s.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'session_count': session_count,
            'total_clicks': total_clicks,
            'total_scrolls': total_scrolls,
            'avg_session_duration': avg_duration,
            'avg_scroll_depth': 0,  # Would need calculation
            'last_updated': timezone.now().isoformat()
        }
    
    @database_sync_to_async
    def get_live_heatmap_data(self):
        """Get live heatmap data (last few minutes)"""
        end_date = timezone.now()
        start_date = end_date - timedelta(minutes=5)
        
        recent_sessions = HeatmapSession.objects.filter(
            page_url=self.page_url,
            start_time__gte=start_date
        )
        
        live_data = {
            'recent_sessions': recent_sessions.count(),
            'active_sessions': recent_sessions.filter(is_active=True).count(),
            'recent_clicks': sum(session.clicks.filter(
                timestamp__gte=start_date
            ).count() for session in recent_sessions),
            'timestamp': timezone.now().isoformat()
        }
        
        return live_data
    
    # Group message handlers
    async def heatmap_update(self, event):
        """Handle heatmap update from group"""
        await self.send(text_data=json.dumps({
            'type': 'heatmap_update',
            'data': event['data']
        }))
    
    async def new_session(self, event):
        """Handle new session notification"""
        await self.send(text_data=json.dumps({
            'type': 'new_session',
            'session_data': event['session_data']
        }))


class ABTestRealtimeConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time A/B testing data updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.experiment_id = self.scope['url_route']['kwargs'].get('experiment_id', '')
        self.room_group_name = f'ab_test_{self.experiment_id}'
        
        # Check user permissions
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial experiment data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_live_stats':
                await self.send_live_stats()
            elif message_type == 'analyze_experiment':
                await self.analyze_experiment()
            elif message_type == 'subscribe_to_experiment':
                await self.handle_experiment_subscription(
                    text_data_json.get('experiment_id', '')
                )
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    async def send_initial_data(self):
        """Send initial experiment data"""
        data = await self.get_experiment_data()
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'data': data
        }))
    
    async def send_live_stats(self):
        """Send live experiment statistics"""
        stats = await self.get_live_stats()
        await self.send(text_data=json.dumps({
            'type': 'live_stats',
            'data': stats
        }))
    
    async def analyze_experiment(self):
        """Perform real-time experiment analysis"""
        analysis = await self.perform_analysis()
        await self.send(text_data=json.dumps({
            'type': 'analysis_results',
            'data': analysis
        }))
    
    async def handle_experiment_subscription(self, experiment_id):
        """Handle subscription to different experiment"""
        # Leave current group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Join new group
        self.experiment_id = experiment_id
        self.room_group_name = f'ab_test_{experiment_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Send data for new experiment
        await self.send_initial_data()
    
    @database_sync_to_async
    def get_experiment_data(self):
        """Get experiment data"""
        try:
            experiment = Experiment.objects.get(id=self.experiment_id)
            
            # Get variant data
            variants = []
            for variant in experiment.variants.all():
                assignments = Assignment.objects.filter(
                    experiment=experiment,
                    variant=variant
                )
                
                conversions = Conversion.objects.filter(
                    assignment__in=assignments,
                    goal_type=experiment.primary_metric
                )
                
                variants.append({
                    'id': variant.id,
                    'name': variant.name,
                    'is_control': variant.is_control,
                    'participants': assignments.count(),
                    'conversions': conversions.count(),
                    'conversion_rate': conversions.count() / assignments.count() if assignments.count() > 0 else 0,
                    'weight': variant.weight
                })
            
            return {
                'experiment': {
                    'id': experiment.id,
                    'name': experiment.name,
                    'status': experiment.status,
                    'primary_metric': experiment.primary_metric
                },
                'variants': variants,
                'last_updated': timezone.now().isoformat()
            }
            
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
    
    @database_sync_to_async
    def get_live_stats(self):
        """Get live experiment statistics"""
        try:
            experiment = Experiment.objects.get(id=self.experiment_id)
            
            # Get recent activity (last 5 minutes)
            recent_time = timezone.now() - timedelta(minutes=5)
            
            recent_assignments = Assignment.objects.filter(
                experiment=experiment,
                first_exposure__gte=recent_time
            ).count()
            
            recent_conversions = Conversion.objects.filter(
                assignment__experiment=experiment,
                converted_at__gte=recent_time
            ).count()
            
            total_assignments = Assignment.objects.filter(experiment=experiment).count()
            total_conversions = Conversion.objects.filter(
                assignment__experiment=experiment,
                goal_type=experiment.primary_metric
            ).count()
            
            overall_conversion_rate = total_conversions / total_assignments if total_assignments > 0 else 0
            
            return {
                'recent_assignments': recent_assignments,
                'recent_conversions': recent_conversions,
                'total_assignments': total_assignments,
                'total_conversions': total_conversions,
                'overall_conversion_rate': overall_conversion_rate,
                'timestamp': timezone.now().isoformat()
            }
            
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
    
    @database_sync_to_async
    def perform_analysis(self):
        """Perform real-time experiment analysis"""
        try:
            experiment = Experiment.objects.get(id=self.experiment_id)
            analyzer = ExperimentAnalyzer(experiment)
            results = analyzer.analyze()
            
            return {
                'analysis': results,
                'timestamp': timezone.now().isoformat()
            }
            
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
    
    # Group message handlers
    async def experiment_update(self, event):
        """Handle experiment update from group"""
        await self.send(text_data=json.dumps({
            'type': 'experiment_update',
            'data': event['data']
        }))
    
    async def new_assignment(self, event):
        """Handle new assignment notification"""
        await self.send(text_data=json.dumps({
            'type': 'new_assignment',
            'assignment_data': event['assignment_data']
        }))
    
    async def new_conversion(self, event):
        """Handle new conversion notification"""
        await self.send(text_data=json.dumps({
            'type': 'new_conversion',
            'conversion_data': event['conversion_data']
        }))


class UnifiedDashboardConsumer(AsyncWebsocketConsumer):
    """Consumer for unified analytics dashboard real-time updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_group_name = 'unified_dashboard'
        
        # Check user permissions
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Start periodic updates
        asyncio.create_task(self.send_periodic_updates())
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_dashboard_data':
                await self.send_dashboard_data()
            elif message_type == 'get_system_metrics':
                await self.send_system_metrics()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
    
    async def send_dashboard_data(self):
        """Send unified dashboard data"""
        data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'dashboard_data',
            'data': data
        }))
    
    async def send_system_metrics(self):
        """Send system performance metrics"""
        metrics = await self.get_system_metrics()
        await self.send(text_data=json.dumps({
            'type': 'system_metrics',
            'data': metrics
        }))
    
    async def send_periodic_updates(self):
        """Send periodic updates every 30 seconds"""
        while True:
            try:
                await asyncio.sleep(30)  # Wait 30 seconds
                
                # Send updated dashboard data
                await self.send_dashboard_data()
                
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue on any error
                pass
    
    @database_sync_to_async
    def get_dashboard_data(self):
        """Get unified dashboard data"""
        # Get heatmap summary
        recent_time = timezone.now() - timedelta(hours=24)
        
        recent_sessions = HeatmapSession.objects.filter(
            start_time__gte=recent_time
        ).count()
        
        active_sessions = HeatmapSession.objects.filter(
            is_active=True
        ).count()
        
        # Get A/B testing summary
        running_experiments = Experiment.objects.filter(
            status='running',
            is_active=True
        ).count()
        
        recent_assignments = Assignment.objects.filter(
            first_exposure__gte=recent_time
        ).count()
        
        recent_conversions = Conversion.objects.filter(
            converted_at__gte=recent_time
        ).count()
        
        return {
            'heatmaps': {
                'recent_sessions': recent_sessions,
                'active_sessions': active_sessions,
                'pages_tracked': HeatmapSession.objects.values('page_url').distinct().count()
            },
            'ab_testing': {
                'running_experiments': running_experiments,
                'recent_assignments': recent_assignments,
                'recent_conversions': recent_conversions
            },
            'timestamp': timezone.now().isoformat()
        }
    
    @database_sync_to_async
    def get_system_metrics(self):
        """Get system performance metrics"""
        # Basic system metrics
        import psutil
        
        try:
            cpu_usage = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory.percent,
                'memory_available': memory.available,
                'disk_usage': disk.percent,
                'disk_free': disk.free,
                'timestamp': timezone.now().isoformat()
            }
        except Exception:
            return {
                'error': 'System metrics not available',
                'timestamp': timezone.now().isoformat()
            }
    
    # Group message handlers
    async def dashboard_update(self, event):
        """Handle dashboard update from group"""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }))
    
    async def alert_notification(self, event):
        """Handle alert notifications"""
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'data': event['data']
        }))


# Utility functions for sending updates to groups
async def send_heatmap_update(page_url, data):
    """Send heatmap update to all connected clients"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    room_group_name = f'heatmap_{page_url.replace("/", "_")}'
    
    await channel_layer.group_send(
        room_group_name,
        {
            'type': 'heatmap_update',
            'data': data
        }
    )


async def send_ab_test_update(experiment_id, data):
    """Send A/B test update to all connected clients"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    room_group_name = f'ab_test_{experiment_id}'
    
    await channel_layer.group_send(
        room_group_name,
        {
            'type': 'experiment_update',
            'data': data
        }
    )


async def send_dashboard_alert(message, level='info'):
    """Send alert to dashboard"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        'unified_dashboard',
        {
            'type': 'alert_notification',
            'data': {
                'message': message,
                'level': level,
                'timestamp': timezone.now().isoformat()
            }
        }
    )