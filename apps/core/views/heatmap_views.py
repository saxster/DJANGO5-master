"""
Heatmap visualization views for advanced user behavior analytics
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from collections import defaultdict

    HeatmapSession, ClickHeatmap, ScrollHeatmap, 
    AttentionHeatmap, ElementInteraction, HeatmapAggregation
)


class HeatmapDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Main heatmap visualization dashboard"""
    
    def test_func(self):
        """Only allow staff users to access heatmap dashboard"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Render the heatmap dashboard"""
        context = {
            'title': 'User Behavior Heatmaps',
            'page_list': self._get_tracked_pages(),
            'device_types': ['all', 'desktop', 'tablet', 'mobile'],
            'time_ranges': self._get_time_ranges(),
        }
        return render(request, 'core/heatmap_dashboard.html', context)
    
    def _get_tracked_pages(self):
        """Get list of pages with heatmap data"""
        pages = HeatmapSession.objects.values('page_url', 'page_title').annotate(
            session_count=Count('id'),
            last_tracked=Max('start_time')
        ).order_by('-session_count')[:50]
        
        return list(pages)
    
    def _get_time_ranges(self):
        """Get available time ranges for filtering"""
        return [
            {'value': '1h', 'label': 'Last Hour'},
            {'value': '24h', 'label': 'Last 24 Hours'},
            {'value': '7d', 'label': 'Last 7 Days'},
            {'value': '30d', 'label': 'Last 30 Days'},
            {'value': 'custom', 'label': 'Custom Range'},
        ]


class HeatmapDataAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    """API endpoint for retrieving heatmap data"""
    
    def test_func(self):
        """Only allow staff users to access heatmap data"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get heatmap data for visualization"""
        # Get parameters
        page_url = request.GET.get('page_url')
        device_type = request.GET.get('device_type', 'all')
        time_range = request.GET.get('time_range', '24h')
        heatmap_type = request.GET.get('type', 'click')
        
        if not page_url:
            return JsonResponse({'error': 'page_url parameter required'}, status=400)
        
        # Calculate date range
        end_date = timezone.now()
        start_date = self._calculate_start_date(time_range, end_date)
        
        # Check cache
        cache_key = f"heatmap:{page_url}:{device_type}:{time_range}:{heatmap_type}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return JsonResponse(cached_data)
        
        # Get heatmap data based on type
        if heatmap_type == 'click':
            data = self._get_click_heatmap(page_url, device_type, start_date, end_date)
        elif heatmap_type == 'scroll':
            data = self._get_scroll_heatmap(page_url, device_type, start_date, end_date)
        elif heatmap_type == 'attention':
            data = self._get_attention_heatmap(page_url, device_type, start_date, end_date)
        elif heatmap_type == 'interaction':
            data = self._get_interaction_heatmap(page_url, device_type, start_date, end_date)
        else:
            return JsonResponse({'error': 'Invalid heatmap type'}, status=400)
        
        # Cache the result
        cache.set(cache_key, data, 300)  # Cache for 5 minutes
        
        return JsonResponse(data)
    
    def _calculate_start_date(self, time_range, end_date):
        """Calculate start date based on time range"""
        if time_range == '1h':
            return end_date - timedelta(hours=1)
        elif time_range == '24h':
            return end_date - timedelta(days=1)
        elif time_range == '7d':
            return end_date - timedelta(days=7)
        elif time_range == '30d':
            return end_date - timedelta(days=30)
        else:
            return end_date - timedelta(days=1)  # Default to 24h
    
    def _get_click_heatmap(self, page_url, device_type, start_date, end_date):
        """Generate click heatmap data"""
        # Get sessions
        sessions = self._get_sessions(page_url, device_type, start_date, end_date)
        
        # Get clicks for these sessions
        clicks = ClickHeatmap.objects.filter(
            session__in=sessions
        ).values('x_position', 'y_position', 'element_type', 'is_navigation')
        
        # Process click data
        click_points = []
        navigation_clicks = []
        
        for click in clicks:
            point = {
                'x': click['x_position'],
                'y': click['y_position'],
                'value': 1  # Weight for heatmap
            }
            
            if click['is_navigation']:
                navigation_clicks.append(point)
            else:
                click_points.append(point)
        
        # Generate heatmap matrix
        heatmap_matrix = self._generate_heatmap_matrix(click_points)
        
        return {
            'type': 'click',
            'page_url': page_url,
            'session_count': sessions.count(),
            'total_clicks': len(click_points) + len(navigation_clicks),
            'click_points': click_points[:1000],  # Limit for performance
            'navigation_clicks': navigation_clicks[:500],
            'heatmap_matrix': heatmap_matrix,
            'statistics': self._calculate_click_statistics(clicks),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_scroll_heatmap(self, page_url, device_type, start_date, end_date):
        """Generate scroll depth heatmap data"""
        sessions = self._get_sessions(page_url, device_type, start_date, end_date)
        
        # Get scroll data
        scrolls = ScrollHeatmap.objects.filter(
            session__in=sessions
        ).values('scroll_depth_percentage').annotate(
            count=Count('id'),
            avg_time=Avg('time_at_position')
        )
        
        # Create scroll depth distribution
        depth_distribution = defaultdict(int)
        for scroll in scrolls:
            depth = int(scroll['scroll_depth_percentage'] / 10) * 10  # Round to nearest 10%
            depth_distribution[depth] += scroll['count']
        
        # Calculate average max scroll depth per session
        max_depths = ScrollHeatmap.objects.filter(
            session__in=sessions
        ).values('session').annotate(
            max_depth=Max('scroll_depth_percentage')
        )
        
        avg_max_depth = max_depths.aggregate(avg=Avg('max_depth'))['avg'] or 0
        
        return {
            'type': 'scroll',
            'page_url': page_url,
            'session_count': sessions.count(),
            'depth_distribution': dict(depth_distribution),
            'avg_max_depth': round(avg_max_depth, 1),
            'scroll_velocity_data': self._get_scroll_velocity_data(sessions),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_attention_heatmap(self, page_url, device_type, start_date, end_date):
        """Generate attention heatmap data"""
        sessions = self._get_sessions(page_url, device_type, start_date, end_date)
        
        # Get attention zones
        attention_zones = AttentionHeatmap.objects.filter(
            session__in=sessions
        ).values(
            'x_start', 'y_start', 'x_end', 'y_end',
            'content_type', 'has_interaction'
        ).annotate(
            total_duration=Sum('attention_duration'),
            avg_score=Avg('attention_score'),
            interaction_count=Sum('interaction_count')
        )
        
        # Process attention data
        zones = []
        for zone in attention_zones:
            zones.append({
                'bounds': {
                    'x_start': zone['x_start'],
                    'y_start': zone['y_start'],
                    'x_end': zone['x_end'],
                    'y_end': zone['y_end']
                },
                'attention_score': round(zone['avg_score'], 3),
                'total_duration': round(zone['total_duration'], 1),
                'content_type': zone['content_type'],
                'has_interaction': zone['has_interaction'],
                'interaction_count': zone['interaction_count']
            })
        
        # Sort by attention score
        zones.sort(key=lambda x: x['attention_score'], reverse=True)
        
        return {
            'type': 'attention',
            'page_url': page_url,
            'session_count': sessions.count(),
            'attention_zones': zones[:100],  # Top 100 zones
            'content_type_breakdown': self._get_content_type_breakdown(attention_zones),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_interaction_heatmap(self, page_url, device_type, start_date, end_date):
        """Generate element interaction heatmap data"""
        sessions = self._get_sessions(page_url, device_type, start_date, end_date)
        
        # Get interactions
        interactions = ElementInteraction.objects.filter(
            session__in=sessions
        ).values(
            'element_selector', 'element_type', 'interaction_type'
        ).annotate(
            count=Count('id'),
            avg_duration=Avg('duration')
        ).order_by('-count')
        
        # Process interaction data
        interaction_map = defaultdict(lambda: defaultdict(int))
        element_stats = []
        
        for interaction in interactions[:50]:  # Top 50 elements
            element_stats.append({
                'selector': interaction['element_selector'],
                'element_type': interaction['element_type'],
                'interaction_type': interaction['interaction_type'],
                'count': interaction['count'],
                'avg_duration': round(interaction['avg_duration'] or 0, 2)
            })
            
            interaction_map[interaction['element_selector']][interaction['interaction_type']] = interaction['count']
        
        return {
            'type': 'interaction',
            'page_url': page_url,
            'session_count': sessions.count(),
            'top_interactions': element_stats,
            'interaction_map': dict(interaction_map),
            'interaction_types': self._get_interaction_type_distribution(sessions),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_sessions(self, page_url, device_type, start_date, end_date):
        """Get sessions based on filters"""
        sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        if device_type != 'all':
            sessions = sessions.filter(device_type=device_type)
        
        return sessions
    
    def _generate_heatmap_matrix(self, points, grid_size=50):
        """Generate heatmap matrix from points"""
        if not points:
            return []
        
        # Create grid
        matrix = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        
        # Map points to grid
        for point in points:
            x = min(int(point['x'] * grid_size), grid_size - 1)
            y = min(int(point['y'] * grid_size), grid_size - 1)
            matrix[y][x] += point.get('value', 1)
        
        # Apply Gaussian blur for smoothing
        matrix = self._apply_gaussian_blur(matrix)
        
        # Normalize values
        max_val = max(max(row) for row in matrix) if matrix else 1
        if max_val > 0:
            matrix = [[val / max_val for val in row] for row in matrix]
        
        return matrix
    
    def _apply_gaussian_blur(self, matrix, sigma=1.5):
        """Apply Gaussian blur to heatmap matrix"""
        try:
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(matrix, sigma=sigma).tolist()
        except ImportError:
            # If scipy not available, return original matrix
            return matrix
    
    def _calculate_click_statistics(self, clicks):
        """Calculate click statistics"""
        total = len(list(clicks))
        if total == 0:
            return {}
        
        element_types = defaultdict(int)
        for click in clicks:
            element_types[click['element_type']] += 1
        
        return {
            'total_clicks': total,
            'navigation_clicks': sum(1 for c in clicks if c['is_navigation']),
            'element_type_distribution': dict(element_types)
        }
    
    def _get_scroll_velocity_data(self, sessions):
        """Get scroll velocity statistics"""
        velocities = ScrollHeatmap.objects.filter(
            session__in=sessions,
            scroll_velocity__isnull=False
        ).values_list('scroll_velocity', flat=True)
        
        if not velocities:
            return {}
        
        velocities = list(velocities)
        return {
            'avg_velocity': round(sum(velocities) / len(velocities), 2),
            'max_velocity': round(max(velocities), 2),
            'min_velocity': round(min(velocities), 2)
        }
    
    def _get_content_type_breakdown(self, attention_zones):
        """Get breakdown by content type"""
        breakdown = defaultdict(lambda: {'count': 0, 'total_duration': 0})
        
        for zone in attention_zones:
            content_type = zone['content_type']
            breakdown[content_type]['count'] += 1
            breakdown[content_type]['total_duration'] += zone['total_duration']
        
        return dict(breakdown)
    
    def _get_interaction_type_distribution(self, sessions):
        """Get distribution of interaction types"""
        distribution = ElementInteraction.objects.filter(
            session__in=sessions
        ).values('interaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {item['interaction_type']: item['count'] for item in distribution}


class HeatmapComparisonView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View for comparing heatmaps across different segments"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get comparison data"""
        page_url = request.GET.get('page_url')
        comparison_type = request.GET.get('comparison', 'device')
        
        if not page_url:
            return JsonResponse({'error': 'page_url required'}, status=400)
        
        if comparison_type == 'device':
            data = self._compare_by_device(page_url)
        elif comparison_type == 'time':
            data = self._compare_by_time(page_url)
        elif comparison_type == 'user_segment':
            data = self._compare_by_user_segment(page_url)
        else:
            return JsonResponse({'error': 'Invalid comparison type'}, status=400)
        
        return JsonResponse(data)
    
    def _compare_by_device(self, page_url):
        """Compare heatmaps across device types"""
        devices = ['desktop', 'tablet', 'mobile']
        comparison_data = {}
        
        for device in devices:
            sessions = HeatmapSession.objects.filter(
                page_url=page_url,
                device_type=device,
                start_time__gte=timezone.now() - timedelta(days=7)
            )
            
            if sessions.exists():
                # Get click distribution
                clicks = ClickHeatmap.objects.filter(
                    session__in=sessions
                ).aggregate(
                    total=Count('id'),
                    avg_y=Avg('y_position')
                )
                
                # Get scroll depth
                scrolls = ScrollHeatmap.objects.filter(
                    session__in=sessions
                ).aggregate(
                    avg_depth=Avg('max_scroll_depth')
                )
                
                comparison_data[device] = {
                    'session_count': sessions.count(),
                    'total_clicks': clicks['total'],
                    'avg_click_y': round(clicks['avg_y'] or 0, 3),
                    'avg_scroll_depth': round(scrolls['avg_depth'] or 0, 1)
                }
        
        return {
            'type': 'device_comparison',
            'page_url': page_url,
            'data': comparison_data,
            'timestamp': timezone.now().isoformat()
        }
    
    def _compare_by_time(self, page_url):
        """Compare heatmaps across time periods"""
        periods = [
            {'label': 'Today', 'start': timezone.now().replace(hour=0, minute=0, second=0)},
            {'label': 'Yesterday', 'start': (timezone.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0)},
            {'label': 'Last Week', 'start': timezone.now() - timedelta(days=7)},
        ]
        
        comparison_data = {}
        
        for period in periods:
            sessions = HeatmapSession.objects.filter(
                page_url=page_url,
                start_time__gte=period['start'],
                start_time__lt=period['start'] + timedelta(days=1) if period['label'] != 'Last Week' else timezone.now()
            )
            
            if sessions.exists():
                comparison_data[period['label']] = {
                    'session_count': sessions.count(),
                    'unique_users': sessions.values('user').distinct().count(),
                    'avg_duration': sessions.aggregate(avg=Avg('duration_seconds'))['avg'] or 0
                }
        
        return {
            'type': 'time_comparison',
            'page_url': page_url,
            'data': comparison_data,
            'timestamp': timezone.now().isoformat()
        }
    
    def _compare_by_user_segment(self, page_url):
        """Compare heatmaps across user segments"""
        # Compare authenticated vs anonymous
        auth_sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            user__isnull=False,
            start_time__gte=timezone.now() - timedelta(days=7)
        )
        
        anon_sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            user__isnull=True,
            start_time__gte=timezone.now() - timedelta(days=7)
        )
        
        comparison_data = {
            'authenticated': self._get_segment_stats(auth_sessions),
            'anonymous': self._get_segment_stats(anon_sessions)
        }
        
        return {
            'type': 'user_segment_comparison',
            'page_url': page_url,
            'data': comparison_data,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_segment_stats(self, sessions):
        """Get statistics for a session segment"""
        if not sessions.exists():
            return None
        
        clicks = ClickHeatmap.objects.filter(session__in=sessions)
        interactions = ElementInteraction.objects.filter(session__in=sessions)
        
        return {
            'session_count': sessions.count(),
            'avg_duration': sessions.aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
            'total_clicks': clicks.count(),
            'total_interactions': interactions.count(),
            'interaction_rate': interactions.count() / sessions.count() if sessions.count() > 0 else 0
        }


class HeatmapExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export heatmap data in various formats"""
    
    def test_func(self):
        """Only allow staff users"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Export heatmap data"""
        page_url = request.GET.get('page_url')
        export_format = request.GET.get('format', 'json')
        time_range = request.GET.get('time_range', '7d')
        
        if not page_url:
            return JsonResponse({'error': 'page_url required'}, status=400)
        
        # Get data
        end_date = timezone.now()
        start_date = self._calculate_start_date(time_range, end_date)
        
        sessions = HeatmapSession.objects.filter(
            page_url=page_url,
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        if export_format == 'json':
            return self._export_json(sessions, page_url)
        elif export_format == 'csv':
            return self._export_csv(sessions, page_url)
        else:
            return JsonResponse({'error': 'Invalid export format'}, status=400)
    
    def _calculate_start_date(self, time_range, end_date):
        """Calculate start date from time range"""
        if time_range == '1d':
            return end_date - timedelta(days=1)
        elif time_range == '7d':
            return end_date - timedelta(days=7)
        elif time_range == '30d':
            return end_date - timedelta(days=30)
        else:
            return end_date - timedelta(days=7)
    
    def _export_json(self, sessions, page_url):
        """Export as JSON"""
        data = {
            'page_url': page_url,
            'export_date': timezone.now().isoformat(),
            'session_count': sessions.count(),
            'sessions': [],
            'summary': self._generate_summary(sessions)
        }
        
        # Add session details (limited for performance)
        for session in sessions[:100]:
            session_data = {
                'session_id': session.session_id,
                'user': session.user.username if session.user else 'anonymous',
                'device_type': session.device_type,
                'duration': session.duration_seconds,
                'clicks': session.clicks.count(),
                'scrolls': session.scrolls.count(),
                'interactions': session.element_interactions.count()
            }
            data['sessions'].append(session_data)
        
        response = JsonResponse(data)
        response['Content-Disposition'] = f'attachment; filename="heatmap_{page_url.replace("/", "_")}.json"'
        return response
    
    def _export_csv(self, sessions, page_url):
        """Export as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="heatmap_{page_url.replace("/", "_")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Session ID', 'User', 'Device', 'Duration', 'Clicks', 'Scrolls', 'Interactions', 'Start Time'])
        
        for session in sessions:
            writer.writerow([
                session.session_id,
                session.user.username if session.user else 'anonymous',
                session.device_type,
                session.duration_seconds or 0,
                session.clicks.count(),
                session.scrolls.count(),
                session.element_interactions.count(),
                session.start_time.isoformat()
            ])
        
        return response
    
    def _generate_summary(self, sessions):
        """Generate summary statistics"""
        if not sessions.exists():
            return {}
        
        total_clicks = ClickHeatmap.objects.filter(session__in=sessions).count()
        total_scrolls = ScrollHeatmap.objects.filter(session__in=sessions).count()
        total_interactions = ElementInteraction.objects.filter(session__in=sessions).count()
        
        return {
            'total_sessions': sessions.count(),
            'unique_users': sessions.values('user').distinct().count(),
            'avg_duration': sessions.aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
            'total_clicks': total_clicks,
            'total_scrolls': total_scrolls,
            'total_interactions': total_interactions,
            'device_breakdown': dict(sessions.values('device_type').annotate(count=Count('id')).values_list('device_type', 'count'))
        }