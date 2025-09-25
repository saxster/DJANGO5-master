"""
Information Architecture Monitoring Views
Provides comprehensive dashboard for tracking URL migration and navigation patterns
"""
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import json

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware


@method_decorator(staff_member_required, name='dispatch')
class IAMonitoringDashboard(TemplateView):
    """
    Comprehensive dashboard for monitoring Information Architecture improvements
    Tracks URL migration, navigation patterns, and provides actionable insights
    """
    
    template_name = 'core/monitoring/ia_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request
        days = int(self.request.GET.get('days', 7))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get comprehensive analytics
        context.update({
            # URL Migration Metrics
            'migration_report': OptimizedURLRouter.get_migration_report(),
            
            # Navigation Analytics
            'navigation_analytics': NavigationTrackingMiddleware.get_navigation_analytics(),
            
            # URL Structure Validation
            'structure_validation': OptimizedURLRouter.validate_url_structure(),
            
            # Performance Metrics
            'performance_metrics': self._get_performance_metrics(start_date, end_date),
            
            # User Experience Metrics
            'ux_metrics': self._get_ux_metrics(start_date, end_date),
            
            # Date Range
            'date_range': {
                'start': start_date,
                'end': end_date,
                'days': days
            },
            
            # Quick Stats
            'quick_stats': self._get_quick_stats(),
        })
        
        return context
    
    def _get_performance_metrics(self, start_date, end_date):
        """Calculate performance metrics for the date range"""
        # Get navigation data from cache
        popular_paths = cache.get('nav_tracking_popular_paths', {})
        
        # Calculate metrics
        total_visits = sum(data['count'] for data in popular_paths.values())
        avg_response_time = 0
        slow_pages = []
        fast_pages = []
        
        if popular_paths:
            response_times = [
                data.get('avg_response_time', 0) 
                for data in popular_paths.values() 
                if data.get('avg_response_time', 0) > 0
            ]
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                
                # Identify slow and fast pages
                sorted_by_time = sorted(
                    [(path, data.get('avg_response_time', 0)) 
                     for path, data in popular_paths.items()
                     if data.get('avg_response_time', 0) > 0],
                    key=lambda x: x[1]
                )
                
                fast_pages = sorted_by_time[:5]  # Top 5 fastest
                slow_pages = sorted_by_time[-5:]  # Top 5 slowest
        
        return {
            'total_page_visits': total_visits,
            'avg_response_time': round(avg_response_time, 3),
            'slow_pages': [
                {'path': path, 'time': round(time, 3)} 
                for path, time in slow_pages
            ],
            'fast_pages': [
                {'path': path, 'time': round(time, 3)} 
                for path, time in fast_pages
            ],
            'performance_score': self._calculate_performance_score(avg_response_time)
        }
    
    def _calculate_performance_score(self, avg_response_time):
        """Calculate a performance score (0-100)"""
        if avg_response_time <= 0.5:
            return 100
        elif avg_response_time <= 1.0:
            return 90
        elif avg_response_time <= 2.0:
            return 70
        elif avg_response_time <= 3.0:
            return 50
        else:
            return max(0, 100 - (avg_response_time * 10))
    
    def _get_ux_metrics(self, start_date, end_date):
        """Calculate user experience metrics"""
        # Get navigation analytics
        nav_analytics = NavigationTrackingMiddleware.get_navigation_analytics()
        
        # Calculate bounce rate (sessions with only 1 page view)
        user_flows = cache.get('nav_tracking_user_flows', {})
        single_page_sessions = sum(
            1 for session_data in user_flows.values()
            if len(session_data.get('paths', [])) == 1
        )
        total_sessions = len(user_flows)
        bounce_rate = (single_page_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        # Calculate average pages per session
        total_pages = sum(
            len(session_data.get('paths', []))
            for session_data in user_flows.values()
        )
        avg_pages_per_session = (total_pages / total_sessions) if total_sessions > 0 else 0
        
        # Get 404 error rate
        dead_urls = nav_analytics.get('dead_urls', {})
        total_404s = sum(
            url_data['count'] 
            for url_data in dead_urls.get('top_dead_urls', [])
        )
        
        # Calculate navigation efficiency (how directly users reach their goals)
        common_flows = nav_analytics.get('user_flows', {}).get('common_navigation_flows', [])
        
        return {
            'bounce_rate': round(bounce_rate, 1),
            'avg_pages_per_session': round(avg_pages_per_session, 1),
            'total_404_errors': total_404s,
            'dead_links_count': dead_urls.get('total_dead_urls', 0),
            'most_common_paths': common_flows[:5],
            'ux_score': self._calculate_ux_score(bounce_rate, avg_pages_per_session, total_404s)
        }
    
    def _calculate_ux_score(self, bounce_rate, avg_pages_per_session, total_404s):
        """Calculate a UX score (0-100)"""
        score = 100
        
        # Penalize high bounce rate
        if bounce_rate > 70:
            score -= 30
        elif bounce_rate > 50:
            score -= 20
        elif bounce_rate > 30:
            score -= 10
        
        # Reward good engagement
        if avg_pages_per_session > 3:
            score += 10
        elif avg_pages_per_session < 2:
            score -= 10
        
        # Penalize 404 errors
        if total_404s > 100:
            score -= 20
        elif total_404s > 50:
            score -= 10
        elif total_404s > 10:
            score -= 5
        
        return max(0, min(100, score))
    
    def _get_quick_stats(self):
        """Get quick statistics for the dashboard header"""
        migration_report = OptimizedURLRouter.get_migration_report()
        nav_analytics = NavigationTrackingMiddleware.get_navigation_analytics()
        
        return {
            'adoption_rate': migration_report['summary']['adoption_rate'],
            'total_redirects': migration_report['summary']['total_redirects'],
            'active_sessions': nav_analytics.get('user_flows', {}).get('active_sessions', 0),
            'dead_urls': nav_analytics.get('dead_urls', {}).get('total_dead_urls', 0),
            'deprecated_urls_used': nav_analytics.get('deprecated_usage', {}).get('total_deprecated_urls_used', 0),
        }


class IAMonitoringAPI(TemplateView):
    """API endpoints for real-time monitoring data"""
    
    def get(self, request, *args, **kwargs):
        """Return monitoring data as JSON"""
        action = request.GET.get('action', 'summary')
        
        if action == 'migration_report':
            data = OptimizedURLRouter.get_migration_report()
        elif action == 'navigation_analytics':
            data = NavigationTrackingMiddleware.get_navigation_analytics()
        elif action == 'structure_validation':
            data = OptimizedURLRouter.validate_url_structure()
        elif action == 'live_stats':
            data = self._get_live_stats()
        else:
            data = self._get_summary()
        
        return JsonResponse(data, safe=False)
    
    def _get_live_stats(self):
        """Get live statistics for real-time dashboard updates"""
        return {
            'timestamp': timezone.now().isoformat(),
            'active_users': self._get_active_users_count(),
            'current_popular_pages': self._get_current_popular_pages(),
            'recent_404s': self._get_recent_404s(),
            'system_health': self._get_system_health()
        }
    
    def _get_active_users_count(self):
        """Count currently active users"""
        user_flows = cache.get('nav_tracking_user_flows', {})
        cutoff = timezone.now() - timedelta(minutes=5)
        
        active_count = sum(
            1 for session_data in user_flows.values()
            if session_data.get('last_activity') and 
            datetime.fromisoformat(session_data['last_activity']) > cutoff
        )
        
        return active_count
    
    def _get_current_popular_pages(self):
        """Get currently popular pages (last hour)"""
        popular_paths = cache.get('nav_tracking_popular_paths', {})
        cutoff = timezone.now() - timedelta(hours=1)
        
        recent_paths = [
            {'path': path, 'visits': data['count']}
            for path, data in popular_paths.items()
            if data.get('last_accessed') and 
            datetime.fromisoformat(data['last_accessed']) > cutoff
        ]
        
        return sorted(recent_paths, key=lambda x: x['visits'], reverse=True)[:5]
    
    def _get_recent_404s(self):
        """Get recent 404 errors"""
        dead_urls = cache.get('nav_tracking_404_urls', {})
        cutoff = timezone.now() - timedelta(hours=1)
        
        recent_404s = [
            {'url': url, 'count': data['count']}
            for url, data in dead_urls.items()
            if data.get('last_seen') and 
            datetime.fromisoformat(data['last_seen']) > cutoff
        ]
        
        return sorted(recent_404s, key=lambda x: x['count'], reverse=True)[:5]
    
    def _get_system_health(self):
        """Calculate overall system health score"""
        migration_report = OptimizedURLRouter.get_migration_report()
        nav_analytics = NavigationTrackingMiddleware.get_navigation_analytics()
        
        health_score = 100
        issues = []
        
        # Check adoption rate
        adoption_rate = migration_report['summary']['adoption_rate']
        if adoption_rate < 50:
            health_score -= 20
            issues.append('Low new URL adoption rate')
        
        # Check 404 errors
        dead_urls_count = nav_analytics.get('dead_urls', {}).get('total_dead_urls', 0)
        if dead_urls_count > 20:
            health_score -= 15
            issues.append(f'{dead_urls_count} dead URLs detected')
        
        # Check deprecated URL usage
        deprecated_count = nav_analytics.get('deprecated_usage', {}).get('total_deprecated_urls_used', 0)
        if deprecated_count > 10:
            health_score -= 10
            issues.append(f'{deprecated_count} legacy URLs still in use')
        
        return {
            'score': max(0, health_score),
            'status': 'healthy' if health_score >= 70 else 'warning' if health_score >= 40 else 'critical',
            'issues': issues
        }
    
    def _get_summary(self):
        """Get summary of all monitoring data"""
        return {
            'migration': OptimizedURLRouter.get_migration_report()['summary'],
            'navigation': {
                'dead_urls': NavigationTrackingMiddleware.get_navigation_analytics()['dead_urls']['total_dead_urls'],
                'active_sessions': self._get_active_users_count(),
            },
            'health': self._get_system_health(),
            'timestamp': timezone.now().isoformat()
        }