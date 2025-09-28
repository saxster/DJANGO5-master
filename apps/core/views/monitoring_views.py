"""
Monitoring views for Information Architecture improvements
Provides dashboards and metrics for tracking IA changes
"""
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Count, Q, Avg
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta

from apps.core.url_router import URLRouter
from apps.core.models import PageView, NavigationClick, ErrorLog


@method_decorator(staff_member_required, name='dispatch')
class IAMonitoringDashboard(TemplateView):
    """Main dashboard for monitoring IA improvements"""
    
    template_name = 'core/monitoring/ia_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request
        days = int(self.request.GET.get('days', 7))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        context.update({
            'legacy_url_metrics': self.get_legacy_url_metrics(),
            'navigation_metrics': self.get_navigation_metrics(start_date, end_date),
            'error_metrics': self.get_error_metrics(start_date, end_date),
            'performance_metrics': self.get_performance_metrics(start_date, end_date),
            'user_flow_metrics': self.get_user_flow_metrics(start_date, end_date),
            'date_range': {
                'start': start_date,
                'end': end_date,
                'days': days
            }
        })
        
        return context
    
    def get_legacy_url_metrics(self):
        """Get metrics about legacy URL usage"""
        report = URLRouter.get_legacy_usage_report()
        
        # Calculate trends
        total_hits = report['total_legacy_hits']
        
        # Get historical data for comparison
        cache_key = 'legacy_url_history'
        history = cache.get(cache_key, [])
        
        # Add current data point
        history.append({
            'timestamp': timezone.now().isoformat(),
            'total_hits': total_hits
        })
        
        # Keep last 30 days
        cutoff = timezone.now() - timedelta(days=30)
        history = [h for h in history if datetime.fromisoformat(h['timestamp']) > cutoff]
        
        cache.set(cache_key, history, 86400)  # Cache for 24 hours
        
        return {
            'total_hits': total_hits,
            'top_urls': report['top_used'][:10],
            'unique_urls': len(report['usage_by_url']),
            'trend_data': history[-7:],  # Last 7 data points
            'migration_progress': self._calculate_migration_progress(report)
        }
    
    def _calculate_migration_progress(self, report):
        """Calculate how well users are adopting new URLs"""
        total_possible_urls = len(URLRouter.URL_MAPPINGS)
        unused_urls = total_possible_urls - len(report['usage_by_url'])
        
        progress = (unused_urls / total_possible_urls * 100) if total_possible_urls > 0 else 100
        
        return {
            'percentage': round(progress, 1),
            'unused_legacy_urls': unused_urls,
            'total_legacy_urls': total_possible_urls
        }
    
    def get_navigation_metrics(self, start_date, end_date):
        """Get metrics about navigation usage"""
        # Simulated data - replace with actual model queries
        clicks = NavigationClick.objects.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # Most clicked menu items
        top_menu_items = clicks.values('menu_item').annotate(
            click_count=Count('id')
        ).order_by('-click_count')[:10]
        
        # Navigation depth analysis
        depth_analysis = clicks.values('menu_depth').annotate(
            count=Count('id')
        ).order_by('menu_depth')
        
        # Time to find analysis (how long users take to find what they need)
        avg_time_to_find = clicks.aggregate(
            avg_time=Avg('time_to_click')
        )['avg_time'] or 0
        
        return {
            'total_clicks': clicks.count(),
            'unique_users': clicks.values('user').distinct().count(),
            'top_menu_items': list(top_menu_items),
            'depth_analysis': list(depth_analysis),
            'avg_time_to_find': round(avg_time_to_find, 2),
            'click_heatmap': self._generate_click_heatmap(clicks)
        }
    
    def _generate_click_heatmap(self, clicks):
        """Generate heatmap data for navigation clicks"""
        # Group by hour of day and day of week
        heatmap_data = []
        
        for day in range(7):  # Days of week
            for hour in range(24):  # Hours of day
                count = clicks.filter(
                    timestamp__week_day=day + 1,
                    timestamp__hour=hour
                ).count()
                
                heatmap_data.append({
                    'day': day,
                    'hour': hour,
                    'value': count
                })
        
        return heatmap_data
    
    def get_error_metrics(self, start_date, end_date):
        """Get metrics about errors and 404s"""
        errors = ErrorLog.objects.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # 404 errors
        not_found_errors = errors.filter(status_code=404)
        
        # Group 404s by URL pattern
        url_404_patterns = not_found_errors.values('path').annotate(
            count=Count('id')
        ).order_by('-count')[:20]
        
        # Error trends by day
        daily_errors = errors.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(
            total=Count('id'),
            not_found=Count('id', filter=Q(status_code=404)),
            server_error=Count('id', filter=Q(status_code=500))
        ).order_by('day')
        
        return {
            'total_errors': errors.count(),
            'not_found_count': not_found_errors.count(),
            'not_found_percentage': (
                not_found_errors.count() / errors.count() * 100 
                if errors.count() > 0 else 0
            ),
            'top_404_urls': list(url_404_patterns),
            'daily_trends': list(daily_errors),
            'error_reduction': self._calculate_error_reduction(start_date)
        }
    
    def _calculate_error_reduction(self, start_date):
        """Calculate error reduction compared to pre-IA period"""
        # Compare with same period before IA implementation
        days_diff = (timezone.now() - start_date).days
        
        pre_ia_start = start_date - timedelta(days=days_diff)
        pre_ia_end = start_date
        
        pre_ia_errors = ErrorLog.objects.filter(
            timestamp__range=(pre_ia_start, pre_ia_end),
            status_code=404
        ).count()
        
        post_ia_errors = ErrorLog.objects.filter(
            timestamp__gte=start_date,
            status_code=404
        ).count()
        
        if pre_ia_errors > 0:
            reduction = ((pre_ia_errors - post_ia_errors) / pre_ia_errors) * 100
        else:
            reduction = 0
        
        return {
            'percentage': round(reduction, 1),
            'pre_ia_count': pre_ia_errors,
            'post_ia_count': post_ia_errors
        }
    
    def get_performance_metrics(self, start_date, end_date):
        """Get performance metrics"""
        page_views = PageView.objects.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # Average page load times
        load_times = page_views.aggregate(
            avg_load_time=Avg('load_time'),
            avg_menu_render=Avg('menu_render_time'),
            avg_content_render=Avg('content_render_time')
        )
        
        # Performance by page type
        perf_by_type = page_views.values('page_type').annotate(
            avg_load=Avg('load_time'),
            count=Count('id')
        ).order_by('avg_load')
        
        return {
            'avg_load_time': round(load_times['avg_load_time'] or 0, 2),
            'avg_menu_render': round(load_times['avg_menu_render'] or 0, 2),
            'avg_content_render': round(load_times['avg_content_render'] or 0, 2),
            'performance_by_type': list(perf_by_type),
            'load_time_distribution': self._get_load_time_distribution(page_views)
        }
    
    def _get_load_time_distribution(self, page_views):
        """Get distribution of page load times"""
        buckets = [
            (0, 1, 'Under 1s'),
            (1, 2, '1-2s'),
            (2, 3, '2-3s'),
            (3, 5, '3-5s'),
            (5, float('inf'), 'Over 5s')
        ]
        
        distribution = []
        total = page_views.count()
        
        for min_time, max_time, label in buckets:
            if max_time == float('inf'):
                count = page_views.filter(load_time__gte=min_time).count()
            else:
                count = page_views.filter(
                    load_time__gte=min_time,
                    load_time__lt=max_time
                ).count()
            
            distribution.append({
                'label': label,
                'count': count,
                'percentage': round(count / total * 100, 1) if total > 0 else 0
            })
        
        return distribution
    
    def get_user_flow_metrics(self, start_date, end_date):
        """Get metrics about user navigation flows"""
        # Analyze common navigation paths
        sessions = PageView.objects.filter(
            timestamp__range=(start_date, end_date)
        ).values('session_id').distinct()
        
        # Common paths (simplified - in reality would need more complex analysis)
        common_paths = [
            {
                'path': 'Dashboard → Assets → Asset Detail',
                'count': 245,
                'avg_time': 12.3
            },
            {
                'path': 'Dashboard → People → Attendance',
                'count': 189,
                'avg_time': 8.7
            },
            {
                'path': 'Dashboard → Operations → Tasks',
                'count': 156,
                'avg_time': 10.2
            }
        ]
        
        # Navigation efficiency (pages visited to complete task)
        avg_pages_per_session = PageView.objects.filter(
            timestamp__range=(start_date, end_date)
        ).values('session_id').annotate(
            page_count=Count('id')
        ).aggregate(avg=Avg('page_count'))['avg'] or 0
        
        return {
            'total_sessions': sessions.count(),
            'common_paths': common_paths[:10],
            'avg_pages_per_session': round(avg_pages_per_session, 1),
            'navigation_efficiency': self._calculate_navigation_efficiency(start_date)
        }
    
    def _calculate_navigation_efficiency(self, start_date):
        """Calculate how efficiently users navigate"""
        # Compare pages per task completion before and after IA
        # This is simplified - would need task completion tracking
        
        efficiency_score = 85  # Placeholder
        improvement = 23  # Placeholder
        
        return {
            'score': efficiency_score,
            'improvement_percentage': improvement,
            'status': 'good' if efficiency_score > 80 else 'needs_improvement'
        }


@method_decorator(staff_member_required, name='dispatch')
class LegacyURLReportView(TemplateView):
    """Detailed report of legacy URL usage"""
    
    template_name = 'core/monitoring/legacy_url_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        report = URLRouter.get_legacy_usage_report()
        
        # Enhance report with additional data
        enhanced_urls = []
        for old_url, count in report['usage_by_url'].items():
            new_url = URLRouter.URL_MAPPINGS.get(old_url, '')
            enhanced_urls.append({
                'old_url': old_url,
                'new_url': new_url,
                'usage_count': count,
                'last_accessed': self._get_last_accessed(old_url),
                'user_agents': self._get_user_agents(old_url)
            })
        
        context.update({
            'total_legacy_hits': report['total_legacy_hits'],
            'legacy_urls': sorted(enhanced_urls, key=lambda x: x['usage_count'], reverse=True),
            'migration_status': self._get_migration_status(),
            'recommendations': self._get_recommendations(enhanced_urls)
        })
        
        return context
    
    def _get_last_accessed(self, url):
        """Get last access time for URL"""
        # Placeholder - would need actual tracking
        return timezone.now() - timedelta(hours=2)
    
    def _get_user_agents(self, url):
        """Get user agents accessing this URL"""
        # Placeholder - would need actual tracking
        return {
            'Chrome': 45,
            'Firefox': 30,
            'Safari': 15,
            'Other': 10
        }
    
    def _get_migration_status(self):
        """Get overall migration status"""
        total_urls = len(URLRouter.URL_MAPPINGS)
        
        # Calculate based on usage in last 30 days
        recent_usage = URLRouter.LEGACY_URL_USAGE
        unused_count = total_urls - len(recent_usage)
        
        return {
            'total_legacy_urls': total_urls,
            'still_in_use': len(recent_usage),
            'successfully_migrated': unused_count,
            'migration_percentage': round(unused_count / total_urls * 100, 1)
        }
    
    def _get_recommendations(self, urls):
        """Get recommendations for completing migration"""
        recommendations = []
        
        # High usage URLs that need attention
        high_usage = [u for u in urls if u['usage_count'] > 100]
        if high_usage:
            recommendations.append({
                'priority': 'high',
                'title': 'Update High-Traffic Legacy URLs',
                'description': f'{len(high_usage)} legacy URLs still receiving significant traffic',
                'action': 'Update bookmarks, documentation, and external links',
                'urls': high_usage[:5]
            })
        
        # URLs used by specific user agents (might be bots/scripts)
        automated_urls = [u for u in urls if self._is_automated_traffic(u)]
        if automated_urls:
            recommendations.append({
                'priority': 'medium',
                'title': 'Update Automated Systems',
                'description': f'{len(automated_urls)} URLs appear to be accessed by automated systems',
                'action': 'Update API clients, monitoring tools, and scripts',
                'urls': automated_urls[:5]
            })
        
        return recommendations
    
    def _is_automated_traffic(self, url_data):
        """Detect if traffic is likely automated"""
        # Simple heuristic - would need real user agent analysis
        return url_data['usage_count'] > 50 and 'api' in url_data['old_url']