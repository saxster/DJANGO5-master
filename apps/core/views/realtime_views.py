"""
Real-time dashboard views for analytics
"""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.ab_testing.models import Experiment, Assignment, Conversion
from apps.core.consumers import send_heatmap_update, send_ab_test_update, send_dashboard_alert


class RealtimeDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Main real-time analytics dashboard"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Render the real-time dashboard"""
        context = {
            'title': 'Real-time Analytics Dashboard',
            'websocket_protocol': 'wss' if request.is_secure() else 'ws',
            'websocket_host': request.get_host(),
        }
        return render(request, 'core/realtime_dashboard.html', context)


class RealtimeHeatmapView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Real-time heatmap visualization"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Render real-time heatmap view"""
        page_url = request.GET.get('page_url', '')
        
        context = {
            'title': 'Real-time Heatmap',
            'page_url': page_url,
            'websocket_protocol': 'wss' if request.is_secure() else 'ws',
            'websocket_host': request.get_host(),
        }
        return render(request, 'core/realtime_heatmap.html', context)


class RealtimeABTestView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Real-time A/B testing dashboard"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Render real-time A/B testing view"""
        experiment_id = request.GET.get('experiment_id', '')
        
        context = {
            'title': 'Real-time A/B Testing',
            'experiment_id': experiment_id,
            'websocket_protocol': 'wss' if request.is_secure() else 'ws',
            'websocket_host': request.get_host(),
        }
        return render(request, 'core/realtime_ab_test.html', context)


class LiveMetricsAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    """API for live metrics data"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get live metrics data"""
        metric_type = request.GET.get('type', 'overview')
        time_range = request.GET.get('range', '1h')
        
        if metric_type == 'overview':
            data = self._get_overview_metrics(time_range)
        elif metric_type == 'heatmap':
            page_url = request.GET.get('page_url', '')
            data = self._get_heatmap_metrics(page_url, time_range)
        elif metric_type == 'ab_test':
            experiment_id = request.GET.get('experiment_id', '')
            data = self._get_ab_test_metrics(experiment_id, time_range)
        else:
            return JsonResponse({'error': 'Invalid metric type'}, status=400)
        
        return JsonResponse(data)
    
    def _get_overview_metrics(self, time_range):
        """Get overview metrics"""
        end_date = timezone.now()
        
        if time_range == '1h':
            start_date = end_date - timedelta(hours=1)
        elif time_range == '24h':
            start_date = end_date - timedelta(days=1)
        elif time_range == '7d':
            start_date = end_date - timedelta(days=7)
        else:
            start_date = end_date - timedelta(hours=1)
        
        # Heatmap metrics
        recent_sessions = HeatmapSession.objects.filter(
            start_time__gte=start_date
        ).count()
        
        active_sessions = HeatmapSession.objects.filter(
            is_active=True
        ).count()
        
        pages_tracked = HeatmapSession.objects.filter(
            start_time__gte=start_date
        ).values('page_url').distinct().count()
        
        # A/B testing metrics
        running_experiments = Experiment.objects.filter(
            status='running',
            is_active=True
        ).count()
        
        recent_assignments = Assignment.objects.filter(
            first_exposure__gte=start_date
        ).count()
        
        recent_conversions = Conversion.objects.filter(
            converted_at__gte=start_date
        ).count()
        
        return {
            'heatmaps': {
                'recent_sessions': recent_sessions,
                'active_sessions': active_sessions,
                'pages_tracked': pages_tracked
            },
            'ab_testing': {
                'running_experiments': running_experiments,
                'recent_assignments': recent_assignments,
                'recent_conversions': recent_conversions
            },
            'time_range': time_range,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_heatmap_metrics(self, page_url, time_range):
        """Get heatmap-specific metrics"""
        end_date = timezone.now()
        
        if time_range == '1h':
            start_date = end_date - timedelta(hours=1)
        elif time_range == '24h':
            start_date = end_date - timedelta(days=1)
        else:
            start_date = end_date - timedelta(hours=1)
        
        sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            start_time__gte=start_date
        )
        
        # Calculate metrics
        session_count = sessions.count()
        active_count = sessions.filter(is_active=True).count()
        
        total_clicks = 0
        total_scrolls = 0
        total_interactions = 0
        
        for session in sessions:
            total_clicks += session.clicks.count()
            total_scrolls += session.scrolls.count()
            total_interactions += session.element_interactions.count()
        
        # Device breakdown
        device_breakdown = {}
        for device in ['desktop', 'tablet', 'mobile']:
            device_count = sessions.filter(device_type=device).count()
            if device_count > 0:
                device_breakdown[device] = device_count
        
        return {
            'page_url': page_url,
            'session_count': session_count,
            'active_sessions': active_count,
            'total_clicks': total_clicks,
            'total_scrolls': total_scrolls,
            'total_interactions': total_interactions,
            'device_breakdown': device_breakdown,
            'avg_clicks_per_session': total_clicks / session_count if session_count > 0 else 0,
            'time_range': time_range,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_ab_test_metrics(self, experiment_id, time_range):
        """Get A/B testing metrics"""
        try:
            experiment = Experiment.objects.get(id=experiment_id)
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
        
        end_date = timezone.now()
        
        if time_range == '1h':
            start_date = end_date - timedelta(hours=1)
        elif time_range == '24h':
            start_date = end_date - timedelta(days=1)
        else:
            start_date = end_date - timedelta(hours=1)
        
        # Get recent assignments and conversions
        recent_assignments = Assignment.objects.filter(
            experiment=experiment,
            first_exposure__gte=start_date
        )
        
        recent_conversions = Conversion.objects.filter(
            assignment__experiment=experiment,
            converted_at__gte=start_date
        )
        
        # Variant breakdown
        variant_data = []
        for variant in experiment.variants.all():
            variant_assignments = recent_assignments.filter(variant=variant)
            variant_conversions = recent_conversions.filter(assignment__variant=variant)
            
            conversion_rate = 0
            if variant_assignments.count() > 0:
                conversion_rate = variant_conversions.count() / variant_assignments.count()
            
            variant_data.append({
                'id': variant.id,
                'name': variant.name,
                'is_control': variant.is_control,
                'assignments': variant_assignments.count(),
                'conversions': variant_conversions.count(),
                'conversion_rate': conversion_rate
            })
        
        return {
            'experiment': {
                'id': experiment.id,
                'name': experiment.name,
                'status': experiment.status
            },
            'total_assignments': recent_assignments.count(),
            'total_conversions': recent_conversions.count(),
            'variants': variant_data,
            'time_range': time_range,
            'timestamp': timezone.now().isoformat()
        }


class TriggerUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Trigger real-time updates manually (for testing)"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def post(self, request):
        """Trigger an update"""
        update_type = request.POST.get('type')
        
        if update_type == 'heatmap':
            page_url = request.POST.get('page_url', '/')
            
            # Get current data
            sessions = HeatmapSession.objects.filter(page_url=page_url)
            data = {
                'session_count': sessions.count(),
                'active_sessions': sessions.filter(is_active=True).count(),
                'timestamp': timezone.now().isoformat()
            }
            
            # Trigger WebSocket update
            channel_layer = get_channel_layer()
            async_to_sync(send_heatmap_update)(page_url, data)
            
            return JsonResponse({'status': 'success', 'message': 'Heatmap update sent'})
        
        elif update_type == 'ab_test':
            experiment_id = request.POST.get('experiment_id', '')
            
            try:
                experiment = Experiment.objects.get(id=experiment_id)
                
                # Get current data
                assignments = Assignment.objects.filter(experiment=experiment)
                conversions = Conversion.objects.filter(assignment__experiment=experiment)
                
                data = {
                    'total_assignments': assignments.count(),
                    'total_conversions': conversions.count(),
                    'timestamp': timezone.now().isoformat()
                }
                
                # Trigger WebSocket update
                channel_layer = get_channel_layer()
                async_to_sync(send_ab_test_update)(experiment_id, data)
                
                return JsonResponse({'status': 'success', 'message': 'A/B test update sent'})
                
            except Experiment.DoesNotExist:
                return JsonResponse({'error': 'Experiment not found'}, status=404)
        
        elif update_type == 'alert':
            message = request.POST.get('message', 'Test alert')
            level = request.POST.get('level', 'info')
            
            # Trigger dashboard alert
            channel_layer = get_channel_layer()
            async_to_sync(send_dashboard_alert)(message, level)
            
            return JsonResponse({'status': 'success', 'message': 'Alert sent'})
        
        else:
            return JsonResponse({'error': 'Invalid update type'}, status=400)


class SystemHealthView(LoginRequiredMixin, UserPassesTestMixin, View):
    """System health and performance monitoring"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get system health metrics"""
        # Database health
        db_health = self._check_database_health()
        
        # Cache health
        cache_health = self._check_cache_health()
        
        # WebSocket health
        websocket_health = self._check_websocket_health()
        
        # Recent activity
        activity_metrics = self._get_activity_metrics()
        
        return JsonResponse({
            'database': db_health,
            'cache': cache_health,
            'websockets': websocket_health,
            'activity': activity_metrics,
            'timestamp': timezone.now().isoformat()
        })
    
    def _check_database_health(self):
        """Check database connectivity and performance"""
        try:
            from django.db import connection
            
            start_time = timezone.now()
            
            # Simple query to test database
            HeatmapSession.objects.count()
            
            end_time = timezone.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # ms
            
            return {
                'status': 'healthy',
                'response_time_ms': response_time,
                'connections': len(connection.queries) if hasattr(connection, 'queries') else 0
            }
            
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_cache_health(self):
        """Check cache connectivity"""
        try:
            # Test cache
            test_key = 'health_check'
            test_value = 'ok'
            
            cache.set(test_key, test_value, 60)
            result = cache.get(test_key)
            
            if result == test_value:
                cache.delete(test_key)
                return {'status': 'healthy'}
            else:
                return {'status': 'unhealthy', 'error': 'Cache read/write failed'}
                
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_websocket_health(self):
        """Check WebSocket functionality"""
        try:
            channel_layer = get_channel_layer()
            
            if channel_layer is None:
                return {'status': 'unavailable', 'error': 'No channel layer configured'}
            
            return {'status': 'available', 'backend': str(type(channel_layer).__name__)}
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _get_activity_metrics(self):
        """Get recent activity metrics"""
        recent_time = timezone.now() - timedelta(minutes=5)
        
        return {
            'recent_heatmap_sessions': HeatmapSession.objects.filter(
                start_time__gte=recent_time
            ).count(),
            'active_heatmap_sessions': HeatmapSession.objects.filter(
                is_active=True
            ).count(),
            'recent_ab_assignments': Assignment.objects.filter(
                first_exposure__gte=recent_time
            ).count(),
            'recent_conversions': Conversion.objects.filter(
                converted_at__gte=recent_time
            ).count()
        }


class RealtimeConfigView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Configuration for real-time features"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get real-time configuration"""
        config = {
            'websocket_enabled': True,
            'update_intervals': {
                'heatmap': 10000,  # 10 seconds
                'ab_test': 15000,  # 15 seconds
                'dashboard': 30000  # 30 seconds
            },
            'max_connections_per_room': 100,
            'data_retention': {
                'live_updates': 300,  # 5 minutes
                'cached_data': 3600   # 1 hour
            }
        }
        
        return JsonResponse(config)
    
    def post(self, request):
        """Update real-time configuration"""
        try:
            config_data = json.loads(request.body)
            
            # Store configuration in cache
            cache.set('realtime_config', config_data, 86400)  # 24 hours
            
            return JsonResponse({'status': 'success', 'message': 'Configuration updated'})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)