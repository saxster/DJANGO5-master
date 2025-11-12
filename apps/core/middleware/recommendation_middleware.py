"""
Recommendation middleware for intelligent content and navigation suggestions
"""
import logging

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from apps.core.recommendation_engine import RecommendationEngine
from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, NavigationRecommendation
)
from apps.core.models.heatmap import HeatmapSession

User = get_user_model()
logger = logging.getLogger(__name__)


class RecommendationMiddleware(MiddlewareMixin):
    """
    Middleware that provides intelligent recommendations based on user behavior
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.engine = RecommendationEngine()
        
        # Configuration
        self.enabled = getattr(settings, 'RECOMMENDATIONS_ENABLED', True)
        self.cache_timeout = getattr(settings, 'RECOMMENDATION_CACHE_TIMEOUT', 3600)  # 1 hour
        self.min_sessions_for_recommendations = getattr(settings, 'MIN_SESSIONS_FOR_RECOMMENDATIONS', 5)
        
        super().__init__(get_response)
    
    def __call__(self, request):
        # Process request
        if self.enabled and request.user.is_authenticated:
            self.process_request_recommendations(request)
        
        response = self.get_response(request)
        
        # Process response
        if self.enabled and request.user.is_authenticated:
            self.process_response_recommendations(request, response)
        
        return response
    
    def process_request_recommendations(self, request):
        """Process incoming request for recommendation opportunities"""
        try:
            user = request.user
            
            # Skip for admin pages or API endpoints
            if self._should_skip_recommendation(request):
                return
            
            # Get or generate user recommendations
            recommendations = self._get_user_recommendations(user)
            
            # Attach recommendations to request for use in views/templates
            request.recommendations = {
                'content': recommendations.get('content', []),
                'navigation': recommendations.get('navigation', []),
                'personalized': True if recommendations else False
            }
            
            # Update user behavior tracking
            self._track_page_visit(request)
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error in recommendation middleware process_request: {str(e)}")
            request.recommendations = {'content': [], 'navigation': [], 'personalized': False}
    
    def process_response_recommendations(self, request, response):
        """Process response to update recommendation data"""
        try:
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return response
            
            # Track recommendation interactions if any
            self._track_recommendation_interactions(request, response)
            
            # Inject recommendations into HTML responses
            if self._should_inject_recommendations(request, response):
                response = self._inject_recommendations_into_response(request, response)
            
            return response
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error in recommendation middleware process_response: {str(e)}")
            return response
    
    def _should_skip_recommendation(self, request) -> bool:
        """Check if recommendations should be skipped for this request"""
        path = request.path.lower()
        
        # Skip for admin, API, static files
        skip_patterns = ['/admin/', '/api/', '/static/', '/media/', '/_debug/']
        for pattern in skip_patterns:
            if pattern in path:
                return True
        
        # Skip for AJAX requests (unless specifically enabled)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        
        # Skip for non-GET requests
        if request.method != 'GET':
            return True
        
        return False
    
    def _get_user_recommendations(self, user: User) -> Dict[str, List]:
        """Get cached or generate fresh recommendations for user"""
        cache_key = f'user_recommendations_{user.id}'
        cached_recommendations = cache.get(cache_key)
        
        if cached_recommendations:
            # Update shown count for cached recommendations
            self._update_recommendation_shown_counts(cached_recommendations.get('content', []))
            return cached_recommendations
        
        # Check if user has enough activity for personalized recommendations
        session_count = HeatmapSession.objects.filter(user=user).count()
        if session_count < self.min_sessions_for_recommendations:
            return self._get_default_recommendations(user)
        
        try:
            # Generate fresh recommendations
            content_recommendations = self.engine.generate_user_recommendations(user, limit=5)
            navigation_recommendations = self.engine.generate_navigation_recommendations()
            
            # Convert to serializable format
            content_data = self._serialize_content_recommendations(content_recommendations)
            navigation_data = self._serialize_navigation_recommendations(navigation_recommendations)
            
            recommendations = {
                'content': content_data,
                'navigation': navigation_data,
                'generated_at': timezone.now().isoformat(),
                'personalized': True
            }
            
            # Cache recommendations
            cache.set(cache_key, recommendations, self.cache_timeout)
            
            # Save content recommendations to database
            self._save_content_recommendations(content_recommendations)
            
            return recommendations
            
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error generating recommendations for user {user.id}: {str(e)}")
            return self._get_default_recommendations(user)
    
    def _get_default_recommendations(self, user: User) -> Dict[str, List]:
        """Get default recommendations for new or low-activity users"""
        default_content = [
            {
                'type': 'page',
                'title': 'Getting Started Guide',
                'url': '/help/getting-started',
                'description': 'Learn the basics of using our platform',
                'reason': 'Popular with new users',
                'relevance_score': 0.8
            },
            {
                'type': 'dashboard',
                'title': 'Main Dashboard',
                'url': '/dashboard',
                'description': 'Your personalized dashboard overview',
                'reason': 'Most visited page',
                'relevance_score': 0.7
            }
        ]
        
        return {
            'content': default_content,
            'navigation': [],
            'generated_at': timezone.now().isoformat(),
            'personalized': False
        }
    
    def _serialize_content_recommendations(self, recommendations: List[ContentRecommendation]) -> List[Dict]:
        """Convert ContentRecommendation objects to serializable format"""
        serialized = []
        for rec in recommendations:
            serialized.append({
                'id': getattr(rec, 'id', None),
                'type': rec.content_type,
                'title': rec.content_title,
                'url': rec.content_url,
                'description': rec.content_description,
                'reason': rec.reason,
                'relevance_score': rec.relevance_score,
                'algorithm': rec.recommendation_algorithm,
                'shown_count': getattr(rec, 'shown_count', 0),
                'context': getattr(rec, 'recommended_context', {})
            })
        return serialized
    
    def _serialize_navigation_recommendations(self, recommendations: List[NavigationRecommendation]) -> List[Dict]:
        """Convert NavigationRecommendation objects to serializable format"""
        serialized = []
        for rec in recommendations:
            serialized.append({
                'id': getattr(rec, 'id', None),
                'type': rec.recommendation_type,
                'title': rec.title,
                'description': rec.description,
                'suggested_action': rec.suggested_action,
                'expected_impact': rec.expected_impact,
                'confidence_score': rec.confidence_score,
                'priority': rec.priority,
                'target_page': rec.target_page
            })
        return serialized
    
    def _save_content_recommendations(self, recommendations: List[ContentRecommendation]):
        """Save content recommendations to database"""
        try:
            for rec in recommendations:
                if not rec.id:  # Only save new recommendations
                    rec.save()
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error saving content recommendations: {str(e)}")
    
    def _track_page_visit(self, request):
        """Track page visit for behavior analysis"""
        try:
            user = request.user
            page_url = request.path
            
            # Get user's current heatmap session or create behavior tracking
            session_data = {
                'page_url': page_url,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now(),
                'device_type': self._detect_device_type(request)
            }
            
            # Update user behavior asynchronously (in a real app, use Celery)
            self.engine.update_user_behavior(user, session_data)
            
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error tracking page visit: {str(e)}")
    
    def _detect_device_type(self, request) -> str:
        """Detect device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'
    
    def _update_recommendation_shown_counts(self, content_recommendations: List[Dict]):
        """Update shown counts for content recommendations"""
        try:
            for rec_data in content_recommendations:
                rec_id = rec_data.get('id')
                if rec_id:
                    ContentRecommendation.objects.filter(id=rec_id).update(
                        shown_count=models.F('shown_count') + 1,
                        last_shown=timezone.now()
                    )
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error updating recommendation shown counts: {str(e)}")
    
    def _track_recommendation_interactions(self, request, response):
        """Track user interactions with recommendations"""
        try:
            from django.core.exceptions import DisallowedHost

            # Check if this is a recommendation click
            referer = request.META.get('HTTP_REFERER', '')
            try:
                current_url = request.build_absolute_uri()
            except DisallowedHost:
                # Fallback to relative URL if host validation fails
                current_url = request.path

            # Look for recommendation tracking parameters
            # SECURITY FIX (IDOR-007): Validate rec_id parameter
            rec_id = request.GET.get('rec_id')
            rec_type = request.GET.get('rec_type')

            if rec_id and rec_type == 'content':
                # Validate rec_id is numeric
                if not str(rec_id).isdigit():
                    logger.warning(f"Invalid rec_id parameter: {rec_id}")
                else:
                    # Track content recommendation click
                    try:
                        rec = ContentRecommendation.objects.get(id=rec_id, user=request.user)
                        rec.mark_clicked()
                    except ContentRecommendation.DoesNotExist:
                        pass
            
            # Track dismissals via AJAX (would be handled separately in views)
            
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error tracking recommendation interactions: {str(e)}")
    
    def _should_inject_recommendations(self, request, response) -> bool:
        """Check if recommendations should be injected into response"""
        # Only inject into HTML responses
        if not response.get('Content-Type', '').startswith('text/html'):
            return False
        
        # Only for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return False
        
        # Check if recommendations exist
        if not hasattr(request, 'recommendations'):
            return False
        
        recommendations = request.recommendations
        if not recommendations.get('content') and not recommendations.get('navigation'):
            return False
        
        return True
    
    def _inject_recommendations_into_response(self, request, response):
        """Inject recommendations into HTML response"""
        try:
            # This is a simplified implementation
            # In a real app, you might use template tags or JavaScript injection
            
            content = response.content.decode('utf-8')
            
            # Find injection point (e.g., before </body>)
            if '</body>' in content:
                recommendations_html = self._generate_recommendations_html(request.recommendations)
                content = content.replace('</body>', f'{recommendations_html}</body>')
                
                response.content = content.encode('utf-8')
                response['Content-Length'] = len(response.content)
            
            return response
            
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error injecting recommendations: {str(e)}")
            return response
    
    def _generate_recommendations_html(self, recommendations: Dict) -> str:
        """Generate HTML for recommendations"""
        html = '<div id="recommendation-panel" class="recommendation-panel">'
        
        # Content recommendations
        content_recs = recommendations.get('content', [])
        if content_recs:
            html += '<div class="content-recommendations">'
            html += '<h4>Recommended for You</h4>'
            html += '<ul class="recommendation-list">'
            
            for rec in content_recs[:3]:  # Show top 3
                url = rec['url']
                if rec.get('id'):
                    url += f"?rec_id={rec['id']}&rec_type=content"
                
                html += f'''
                <li class="recommendation-item" data-rec-id="{rec.get('id', '')}">
                    <a href="{url}" class="recommendation-link">
                        <div class="recommendation-title">{rec['title']}</div>
                        <div class="recommendation-description">{rec['description']}</div>
                        <div class="recommendation-reason">{rec['reason']}</div>
                    </a>
                    <button class="recommendation-dismiss" data-rec-id="{rec.get('id', '')}">×</button>
                </li>
                '''
            
            html += '</ul></div>'
        
        # Add basic CSS and JavaScript
        html += '''
        <style>
        .recommendation-panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 300px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            z-index: 1000;
            max-height: 400px;
            overflow-y: auto;
        }
        .recommendation-item {
            padding: 12px;
            border-bottom: 1px solid #eee;
            position: relative;
        }
        .recommendation-link {
            text-decoration: none;
            color: inherit;
        }
        .recommendation-title {
            font-weight: bold;
            margin-bottom: 4px;
        }
        .recommendation-description {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 4px;
        }
        .recommendation-reason {
            font-size: 0.8em;
            color: #999;
        }
        .recommendation-dismiss {
            position: absolute;
            top: 8px;
            right: 8px;
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
        }
        </style>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Handle recommendation dismissals
            document.querySelectorAll('.recommendation-dismiss').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    var recId = this.getAttribute('data-rec-id');
                    if (recId) {
                        fetch('/api/recommendations/dismiss/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                            },
                            body: JSON.stringify({rec_id: recId, type: 'content'})
                        });
                    }
                    this.parentElement.style.display = 'none';
                });
            });
        });
        </script>
        '''
        
        html += '</div>'
        return html


class RecommendationContextMiddleware(MiddlewareMixin):
    """
    Lightweight middleware to add recommendation context to templates
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_template_response(self, request, response):
        """Add recommendation context to template responses"""
        if hasattr(response, 'context_data') and hasattr(request, 'recommendations'):
            if response.context_data is None:
                response.context_data = {}
            
            response.context_data['recommendations'] = request.recommendations
            response.context_data['has_recommendations'] = bool(
                request.recommendations.get('content') or 
                request.recommendations.get('navigation')
            )
        
        return response


class RecommendationAPIMiddleware:
    """
    Middleware for API endpoints to provide recommendation data
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.engine = RecommendationEngine()
    
    def __call__(self, request):
        # Add recommendation API methods to request
        if request.path.startswith('/api/') and request.user.is_authenticated:
            request.get_user_recommendations = lambda: self._get_api_recommendations(request.user)
        
        response = self.get_response(request)
        return response
    
    def _get_api_recommendations(self, user: User) -> Dict[str, Any]:
        """Get recommendations formatted for API response"""
        try:
            content_recommendations = self.engine.generate_user_recommendations(user, limit=10)
            navigation_recommendations = self.engine.generate_navigation_recommendations()
            
            return {
                'content_recommendations': [
                    {
                        'id': rec.id if hasattr(rec, 'id') else None,
                        'type': rec.content_type,
                        'title': rec.content_title,
                        'url': rec.content_url,
                        'description': rec.content_description,
                        'reason': rec.reason,
                        'relevance_score': rec.relevance_score,
                        'algorithm': rec.recommendation_algorithm
                    }
                    for rec in content_recommendations
                ],
                'navigation_recommendations': [
                    {
                        'id': rec.id if hasattr(rec, 'id') else None,
                        'type': rec.recommendation_type,
                        'title': rec.title,
                        'description': rec.description,
                        'confidence_score': rec.confidence_score,
                        'priority': rec.priority
                    }
                    for rec in navigation_recommendations
                ],
                'user_profile': self._get_user_profile_summary(user)
            }
            
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error getting API recommendations: {str(e)}")
            return {'content_recommendations': [], 'navigation_recommendations': [], 'user_profile': {}}
    
    def _get_user_profile_summary(self, user: User) -> Dict[str, Any]:
        """Get user profile summary for API"""
        try:
            profile = UserBehaviorProfile.objects.filter(user=user).first()
            if not profile:
                return {}
            
            return {
                'preferred_device': profile.preferred_device_type,
                'session_duration_avg': profile.session_duration_avg,
                'exploration_tendency': profile.exploration_tendency,
                'task_completion_rate': profile.task_completion_rate,
                'top_pages': profile.get_top_pages(5),
                'last_updated': profile.last_updated.isoformat() if profile.last_updated else None
            }
            
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error getting user profile summary: {str(e)}")
            return {}