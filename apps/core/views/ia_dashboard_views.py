"""
Information Architecture Dashboard Views
Provides analytics and monitoring for URL optimization and navigation patterns
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware
from apps.core.url_router_optimized import OptimizedURLRouter
from collections import Counter


class IADashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Main Information Architecture Dashboard
    Displays comprehensive analytics about URL usage and navigation patterns
    """
    
    def test_func(self):
        """Only allow staff users to access IA dashboard"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Render the IA dashboard"""
        context = {
            'title': 'Information Architecture Dashboard',
            'analytics_url': '/admin/ia-analytics/',
        }
        return render(request, 'core/ia_dashboard.html', context)


class IAAnalyticsAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    API endpoint for IA analytics data
    Returns JSON data for dashboard charts and tables
    """
    
    def test_func(self):
        """Only allow staff users to access IA analytics"""
        return self.request.user.is_staff
    
    def get(self, request):
        """Get comprehensive IA analytics"""
        try:
            # Get navigation analytics from middleware
            nav_analytics = NavigationTrackingMiddleware.get_navigation_analytics()
            
            # Get URL mapping statistics
            url_stats = self._get_url_mapping_stats()
            
            # Get performance metrics
            performance_metrics = self._get_performance_metrics()
            
            # Get migration progress
            migration_progress = self._get_migration_progress()
            
            analytics_data = {
                'timestamp': datetime.now().isoformat(),
                'navigation': nav_analytics,
                'url_mappings': url_stats,
                'performance': performance_metrics,
                'migration': migration_progress,
                'summary': self._generate_summary(nav_analytics, url_stats),
            }
            
            return JsonResponse(analytics_data)
            
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'error': f'Failed to load analytics: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }, status=500)
    
    def _get_url_mapping_stats(self):
        """Get statistics about URL mappings"""
        total_mappings = len(OptimizedURLRouter.URL_MAPPINGS)
        
        # Categorize mappings by domain
        domain_counts = Counter()
        for old_url, new_url in OptimizedURLRouter.URL_MAPPINGS.items():
            if new_url.startswith('operations/'):
                domain_counts['Operations'] += 1
            elif new_url.startswith('assets/'):
                domain_counts['Assets'] += 1
            elif new_url.startswith('people/'):
                domain_counts['People'] += 1
            elif new_url.startswith('help-desk/'):
                domain_counts['Help Desk'] += 1
            elif new_url.startswith('reports/'):
                domain_counts['Reports'] += 1
            else:
                domain_counts['Other'] += 1
        
        return {
            'total_mappings': total_mappings,
            'domain_breakdown': dict(domain_counts),
            'mapping_examples': list(OptimizedURLRouter.URL_MAPPINGS.items())[:10]
        }
    
    def _get_performance_metrics(self):
        """Get performance-related metrics"""
        popular_paths = cache.get('nav_tracking_popular_paths', {})
        
        slow_pages = []
        fast_pages = []
        
        for path, data in popular_paths.items():
            avg_time = data.get('avg_response_time', 0)
            if avg_time > 2.0:  # Slower than 2 seconds
                slow_pages.append({
                    'path': path,
                    'avg_response_time': round(avg_time, 3),
                    'visits': data.get('count', 0)
                })
            elif avg_time > 0 and avg_time < 0.5:  # Faster than 500ms
                fast_pages.append({
                    'path': path,
                    'avg_response_time': round(avg_time, 3),
                    'visits': data.get('count', 0)
                })
        
        return {
            'slow_pages': sorted(slow_pages, key=lambda x: x['avg_response_time'], reverse=True)[:10],
            'fast_pages': sorted(fast_pages, key=lambda x: x['visits'], reverse=True)[:10],
            'total_tracked_pages': len(popular_paths)
        }
    
    def _get_migration_progress(self):
        """Get migration progress metrics"""
        deprecated_usage = cache.get('nav_tracking_deprecated_usage', {})
        url_usage_analytics = cache.get('url_usage_analytics', {})
        
        # Calculate migration metrics
        total_legacy_urls = len(OptimizedURLRouter.URL_MAPPINGS)
        still_used_legacy = len([url for url in deprecated_usage.keys() 
                                if deprecated_usage[url].get('count', 0) > 0])
        
        migration_percentage = 0
        if total_legacy_urls > 0:
            migration_percentage = ((total_legacy_urls - still_used_legacy) / total_legacy_urls) * 100
        
        # Most frequently used legacy URLs
        top_legacy_usage = sorted(
            deprecated_usage.items(),
            key=lambda x: x[1].get('count', 0),
            reverse=True
        )[:10]
        
        return {
            'total_legacy_urls': total_legacy_urls,
            'migrated_urls': total_legacy_urls - still_used_legacy,
            'still_used_legacy': still_used_legacy,
            'migration_percentage': round(migration_percentage, 1),
            'top_legacy_usage': [
                {
                    'url': url,
                    'usage_count': data.get('count', 0),
                    'unique_users': len(data.get('users', [])),
                    'last_used': data.get('last_used'),
                    'new_url': OptimizedURLRouter.URL_MAPPINGS.get(url, 'Unknown')
                }
                for url, data in top_legacy_usage
            ]
        }
    
    def _generate_summary(self, nav_analytics, url_stats):
        """Generate executive summary of IA status"""
        dead_urls_count = len(nav_analytics.get('dead_urls', {}).get('top_dead_urls', []))
        popular_paths_count = nav_analytics.get('popular_paths', {}).get('total_tracked_paths', 0)
        deprecated_usage_count = nav_analytics.get('deprecated_usage', {}).get('total_deprecated_urls_used', 0)
        
        recommendations = nav_analytics.get('recommendations', [])
        high_priority_issues = len([r for r in recommendations if r.get('priority') == 'high'])
        
        return {
            'total_url_mappings': url_stats.get('total_mappings', 0),
            'tracked_pages': popular_paths_count,
            'dead_urls': dead_urls_count,
            'legacy_urls_still_used': deprecated_usage_count,
            'high_priority_issues': high_priority_issues,
            'system_health': self._calculate_system_health(dead_urls_count, deprecated_usage_count, high_priority_issues)
        }
    
    def _calculate_system_health(self, dead_urls, deprecated_usage, high_priority_issues):
        """Calculate overall system health score (0-100)"""
        health_score = 100
        
        # Deduct points for issues
        health_score -= min(dead_urls * 2, 20)  # Max 20 points for dead URLs
        health_score -= min(deprecated_usage * 1, 15)  # Max 15 points for deprecated usage
        health_score -= min(high_priority_issues * 10, 25)  # Max 25 points for high priority issues
        
        return max(health_score, 0)