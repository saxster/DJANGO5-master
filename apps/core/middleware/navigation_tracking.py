"""
Navigation Tracking Middleware
Tracks user navigation patterns for information architecture optimization
"""
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.utils import timezone
from typing import Dict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NavigationTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track navigation patterns and URL usage
    Helps identify dead links, popular paths, and user flow
    """
    
    # URLs to exclude from tracking
    EXCLUDED_PATTERNS = [
        '/static/',
        '/media/',
        '/__debug__/',
        '/admin/jsi18n/',
        '.js',
        '.css',
        '.png',
        '.jpg',
        '.ico',
    ]
    
    # Cache keys
    CACHE_KEY_404_URLS = 'nav_tracking_404_urls'
    CACHE_KEY_POPULAR_PATHS = 'nav_tracking_popular_paths'
    CACHE_KEY_USER_FLOWS = 'nav_tracking_user_flows'
    CACHE_KEY_DEPRECATED_USAGE = 'nav_tracking_deprecated_usage'
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.session_paths = {}  # Track paths per session
        
    def __call__(self, request):
        # Skip tracking for excluded patterns
        if self._should_exclude(request.path):
            return self.get_response(request)
        
        # Track request start time
        request._nav_tracking_start = timezone.now()
        
        # Get response
        response = self.get_response(request)
        
        # Track navigation after response
        self._track_navigation(request, response)
        
        return response
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from tracking"""
        for pattern in self.EXCLUDED_PATTERNS:
            if pattern in path:
                return True
        return False
    
    def _track_navigation(self, request, response):
        """Track navigation patterns and metrics"""
        try:
            # Get or create session tracking
            session_key = request.session.session_key if hasattr(request, 'session') else None
            if not session_key:
                return
            
            # Calculate response time
            response_time = None
            if hasattr(request, '_nav_tracking_start'):
                response_time = (timezone.now() - request._nav_tracking_start).total_seconds()
            
            # Track based on response status
            if response.status_code == 404:
                self._track_404(request.path, request.user if request.user.is_authenticated else None)
            elif response.status_code == 302 or response.status_code == 301:
                self._track_redirect(request.path, response.get('Location', ''))
            elif 200 <= response.status_code < 300:
                self._track_successful_navigation(
                    request.path,
                    session_key,
                    request.user if request.user.is_authenticated else None,
                    response_time
                )
            
            # Track deprecated URL usage
            self._track_deprecated_url_usage(request.path, request.user if request.user.is_authenticated else None)
            
            # Track user flow
            self._track_user_flow(session_key, request.path)
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error tracking navigation: {e}")
    
    def _track_404(self, path: str, user=None):
        """Track 404 errors to identify dead links"""
        # Get current 404 tracking
        dead_urls = cache.get(self.CACHE_KEY_404_URLS, {})
        
        if path not in dead_urls:
            dead_urls[path] = {
                'count': 0,
                'first_seen': timezone.now().isoformat(),
                'last_seen': None,
                'users': []
            }
        
        dead_urls[path]['count'] += 1
        dead_urls[path]['last_seen'] = timezone.now().isoformat()
        
        if user:
            username = getattr(user, 'loginid', getattr(user, 'username', str(user.id)))
            if username not in dead_urls[path]['users']:
                dead_urls[path]['users'].append(username)
        
        # Cache for 24 hours
        cache.set(self.CACHE_KEY_404_URLS, dead_urls, 86400)
        
        # Log significant 404s
        if dead_urls[path]['count'] % 10 == 0:
            logger.warning(f"Frequent 404: {path} ({dead_urls[path]['count']} times)")
    
    def _track_redirect(self, from_path: str, to_path: str):
        """Track redirects to understand URL migration"""
        try:
            # Store in database if models are available
            from apps.core.models import URLRedirect
            URLRedirect.objects.update_or_create(
                from_url=from_path,
                defaults={
                    'to_url': to_path,
                    'last_accessed': timezone.now(),
                    'access_count': models.F('access_count') + 1
                }
            )
        except (ConnectionError, ValueError):
            # Fallback to cache if models not available
            pass
    
    def _track_successful_navigation(self, path: str, session_key: str, user=None, response_time: float = None):
        """Track successful page visits"""
        # Get current popular paths
        popular_paths = cache.get(self.CACHE_KEY_POPULAR_PATHS, {})
        
        if path not in popular_paths:
            popular_paths[path] = {
                'count': 0,
                'unique_sessions': set(),
                'avg_response_time': 0,
                'total_response_time': 0,
                'last_accessed': None
            }
        
        # Update metrics
        popular_paths[path]['count'] += 1
        
        # Handle unique_sessions as set initially, then convert to list
        unique_sessions = popular_paths[path]['unique_sessions']
        if isinstance(unique_sessions, list):
            unique_sessions = set(unique_sessions)
        
        unique_sessions.add(session_key)
        popular_paths[path]['unique_sessions'] = list(unique_sessions)
        popular_paths[path]['last_accessed'] = timezone.now().isoformat()
        
        # Update response time metrics
        if response_time:
            total_time = popular_paths[path]['total_response_time'] + response_time
            count = popular_paths[path]['count']
            popular_paths[path]['total_response_time'] = total_time
            popular_paths[path]['avg_response_time'] = total_time / count
        
        # Cache for 1 hour
        cache.set(self.CACHE_KEY_POPULAR_PATHS, popular_paths, 3600)
    
    def _track_deprecated_url_usage(self, path: str, user=None):
        """Track usage of deprecated URLs"""
        # Check if this is a deprecated URL
        from apps.core.url_router_optimized import OptimizedURLRouter
        
        # Remove trailing slash for comparison
        clean_path = path.strip('/')
        
        # Check if this matches any old URL pattern
        for old_url in OptimizedURLRouter.URL_MAPPINGS.keys():
            old_pattern = old_url.strip('/').replace('<str:pk>', '*')
            if self._matches_pattern(clean_path, old_pattern):
                # Track deprecated usage
                deprecated_usage = cache.get(self.CACHE_KEY_DEPRECATED_USAGE, {})
                
                if old_url not in deprecated_usage:
                    deprecated_usage[old_url] = {
                        'count': 0,
                        'users': [],
                        'last_used': None
                    }
                
                deprecated_usage[old_url]['count'] += 1
                deprecated_usage[old_url]['last_used'] = timezone.now().isoformat()
                
                if user:
                    username = getattr(user, 'loginid', getattr(user, 'username', str(user.id)))
                    if username not in deprecated_usage[old_url]['users']:
                        deprecated_usage[old_url]['users'].append(username)
                
                cache.set(self.CACHE_KEY_DEPRECATED_USAGE, deprecated_usage, 86400)
                break
    
    def _track_user_flow(self, session_key: str, path: str):
        """Track user navigation flow through the site"""
        # Get current user flows
        user_flows = cache.get(self.CACHE_KEY_USER_FLOWS, {})
        
        if session_key not in user_flows:
            user_flows[session_key] = {
                'paths': [],
                'started': timezone.now().isoformat(),
                'last_activity': None
            }
        
        # Add current path to flow
        user_flows[session_key]['paths'].append({
            'path': path,
            'timestamp': timezone.now().isoformat()
        })
        user_flows[session_key]['last_activity'] = timezone.now().isoformat()
        
        # Keep only last 20 paths per session
        if len(user_flows[session_key]['paths']) > 20:
            user_flows[session_key]['paths'] = user_flows[session_key]['paths'][-20:]
        
        # Clean old sessions (older than 1 hour of inactivity)
        cutoff = timezone.now() - timedelta(hours=1)
        user_flows = {
            k: v for k, v in user_flows.items()
            if datetime.fromisoformat(v['last_activity']) > cutoff
        }
        
        # Cache for 2 hours
        cache.set(self.CACHE_KEY_USER_FLOWS, user_flows, 7200)
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a URL pattern with wildcards"""
        import re
        # Convert pattern to regex
        regex_pattern = pattern.replace('*', '[^/]+')
        regex_pattern = f'^{regex_pattern}$'
        return bool(re.match(regex_pattern, path))
    
    @classmethod
    def get_navigation_analytics(cls) -> Dict:
        """Get comprehensive navigation analytics"""
        return {
            'dead_urls': cls._get_dead_urls_report(),
            'popular_paths': cls._get_popular_paths_report(),
            'deprecated_usage': cls._get_deprecated_usage_report(),
            'user_flows': cls._get_user_flows_report(),
            'recommendations': cls._generate_recommendations()
        }
    
    @classmethod
    def _get_dead_urls_report(cls) -> Dict:
        """Get report of 404 URLs"""
        dead_urls = cache.get(cls.CACHE_KEY_404_URLS, {})
        
        # Sort by frequency
        sorted_urls = sorted(
            dead_urls.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:20]  # Top 20
        
        return {
            'total_dead_urls': len(dead_urls),
            'top_dead_urls': [
                {
                    'url': url,
                    'count': data['count'],
                    'first_seen': data['first_seen'],
                    'last_seen': data['last_seen'],
                    'affected_users': len(data['users'])
                }
                for url, data in sorted_urls
            ]
        }
    
    @classmethod
    def _get_popular_paths_report(cls) -> Dict:
        """Get report of popular paths"""
        popular_paths = cache.get(cls.CACHE_KEY_POPULAR_PATHS, {})
        
        # Sort by visit count
        sorted_paths = sorted(
            popular_paths.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:20]  # Top 20
        
        return {
            'total_tracked_paths': len(popular_paths),
            'top_paths': [
                {
                    'path': path,
                    'visits': data['count'],
                    'unique_visitors': len(data.get('unique_sessions', [])),
                    'avg_response_time': round(data.get('avg_response_time', 0), 3),
                    'last_accessed': data.get('last_accessed')
                }
                for path, data in sorted_paths
            ]
        }
    
    @classmethod
    def _get_deprecated_usage_report(cls) -> Dict:
        """Get report of deprecated URL usage"""
        deprecated_usage = cache.get(cls.CACHE_KEY_DEPRECATED_USAGE, {})
        
        # Sort by usage count
        sorted_usage = sorted(
            deprecated_usage.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        return {
            'total_deprecated_urls_used': len(deprecated_usage),
            'deprecated_url_usage': [
                {
                    'old_url': url,
                    'usage_count': data['count'],
                    'unique_users': len(data['users']),
                    'last_used': data['last_used']
                }
                for url, data in sorted_usage
            ]
        }
    
    @classmethod
    def _get_user_flows_report(cls) -> Dict:
        """Analyze user navigation flows"""
        user_flows = cache.get(cls.CACHE_KEY_USER_FLOWS, {})
        
        # Analyze common paths
        path_sequences = {}
        for session_data in user_flows.values():
            paths = [p['path'] for p in session_data.get('paths', [])]
            for i in range(len(paths) - 1):
                sequence = f"{paths[i]} -> {paths[i+1]}"
                path_sequences[sequence] = path_sequences.get(sequence, 0) + 1
        
        # Sort by frequency
        common_flows = sorted(
            path_sequences.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10
        
        return {
            'active_sessions': len(user_flows),
            'common_navigation_flows': [
                {'flow': flow, 'count': count}
                for flow, count in common_flows
            ]
        }
    
    @classmethod
    def _generate_recommendations(cls) -> list:
        """Generate recommendations based on analytics"""
        recommendations = []
        
        # Check for dead URLs
        dead_urls = cache.get(cls.CACHE_KEY_404_URLS, {})
        if len(dead_urls) > 10:
            recommendations.append({
                'type': 'warning',
                'message': f"Found {len(dead_urls)} dead URLs. Review and fix broken links.",
                'priority': 'high'
            })
        
        # Check deprecated URL usage
        deprecated_usage = cache.get(cls.CACHE_KEY_DEPRECATED_USAGE, {})
        if deprecated_usage:
            high_usage = [url for url, data in deprecated_usage.items() if data['count'] > 50]
            if high_usage:
                recommendations.append({
                    'type': 'info',
                    'message': f"{len(high_usage)} legacy URLs still heavily used. Update references.",
                    'priority': 'medium'
                })
        
        # Check response times
        popular_paths = cache.get(cls.CACHE_KEY_POPULAR_PATHS, {})
        slow_paths = [
            path for path, data in popular_paths.items()
            if data.get('avg_response_time', 0) > 2.0  # Slower than 2 seconds
        ]
        if slow_paths:
            recommendations.append({
                'type': 'warning',
                'message': f"{len(slow_paths)} pages have slow response times. Consider optimization.",
                'priority': 'high'
            })
        
        return recommendations