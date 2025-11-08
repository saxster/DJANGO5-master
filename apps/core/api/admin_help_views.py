"""
Admin Help API Views - REST endpoints for help widget

Provides JSON endpoints for:
- Quick tips for current user
- Contextual help for current page
- Popular help topics
- Search help topics
- Track help usage

Following .claude/rules.md:
- Rule #8: View methods <30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

from apps.core.services.admin_help_service import AdminHelpService
from apps.core.models.admin_help import AdminHelpTopic
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class QuickTipsView(LoginRequiredMixin, View):
    """Get personalized quick tips for the current user."""
    
    @method_decorator(cache_page(60 * 30))  # Cache for 30 minutes
    def get(self, request):
        """Return quick tips as JSON."""
        try:
            limit = int(request.GET.get('limit', 3))
            topics = AdminHelpService.get_quick_tips(request.user, limit=limit)
            
            return JsonResponse({
                'success': True,
                'topics': [
                    {
                        'id': topic.pk,
                        'feature_name': topic.feature_name,
                        'short_description': topic.short_description,
                        'category': topic.get_category_display(),
                        'difficulty': topic.get_difficulty_level_display(),
                    }
                    for topic in topics
                ]
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error loading quick tips: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load quick tips'
            }, status=500)


class ContextualHelpView(LoginRequiredMixin, View):
    """Get contextual help for the current page."""
    
    def get(self, request):
        """Return contextual help as JSON."""
        try:
            page_url = request.GET.get('url', '')
            category = request.GET.get('category', None)
            
            topics = AdminHelpService.get_contextual_help(
                request.user,
                page_url,
                category=category
            )
            
            return JsonResponse({
                'success': True,
                'topics': [
                    {
                        'id': topic.pk,
                        'feature_name': topic.feature_name,
                        'short_description': topic.short_description,
                        'category': topic.get_category_display(),
                        'difficulty': topic.get_difficulty_level_display(),
                    }
                    for topic in topics
                ]
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error loading contextual help: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load contextual help'
            }, status=500)


class PopularTopicsView(LoginRequiredMixin, View):
    """Get most popular help topics."""
    
    @method_decorator(cache_page(60 * 60))  # Cache for 1 hour
    def get(self, request):
        """Return popular topics as JSON."""
        try:
            limit = int(request.GET.get('limit', 5))
            topics = AdminHelpService.get_popular_topics(limit=limit)
            
            return JsonResponse({
                'success': True,
                'topics': [
                    {
                        'id': topic.pk,
                        'feature_name': topic.feature_name,
                        'short_description': topic.short_description,
                        'category': topic.get_category_display(),
                        'difficulty': topic.get_difficulty_level_display(),
                        'view_count': topic.view_count,
                    }
                    for topic in topics
                ]
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error loading popular topics: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load popular topics'
            }, status=500)


class SearchHelpView(LoginRequiredMixin, View):
    """Search help topics."""
    
    def get(self, request):
        """Return search results as JSON."""
        try:
            query = request.GET.get('q', '').strip()
            
            if len(query) < 2:
                return JsonResponse({
                    'success': True,
                    'results': []
                })
            
            limit = int(request.GET.get('limit', 10))
            results = AdminHelpService.search_help(query, limit=limit)
            
            return JsonResponse({
                'success': True,
                'query': query,
                'results': results
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error searching help: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Search failed'
            }, status=500)


class TrackHelpUsageView(LoginRequiredMixin, View):
    """Track help topic views and feedback."""
    
    def post(self, request, topic_id):
        """Track help usage."""
        try:
            topic = AdminHelpTopic.objects.get(pk=topic_id)
            action = request.POST.get('action', 'view')
            
            # Validate action
            if action not in ['view', 'helpful', 'not_helpful']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action'
                }, status=400)
            
            # Track usage
            success = AdminHelpService.track_help_usage(
                request.user,
                topic,
                action=action
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'Help usage tracked: {action}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to track usage'
                }, status=500)
                
        except AdminHelpTopic.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Help topic not found'
            }, status=404)
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error tracking help usage: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to track usage'
            }, status=500)


class HelpTopicDetailView(LoginRequiredMixin, View):
    """Get full details for a help topic."""
    
    def get(self, request, topic_id):
        """Return help topic detail as JSON."""
        try:
            topic = AdminHelpTopic.objects.get(pk=topic_id, is_active=True)
            
            # Track view
            AdminHelpService.track_help_usage(request.user, topic, action='view')
            
            return JsonResponse({
                'success': True,
                'topic': {
                    'id': topic.pk,
                    'feature_name': topic.feature_name,
                    'short_description': topic.short_description,
                    'detailed_explanation': topic.detailed_explanation,
                    'category': topic.get_category_display(),
                    'difficulty': topic.get_difficulty_level_display(),
                    'use_cases': topic.use_cases,
                    'advantages': topic.advantages,
                    'how_to_use': topic.how_to_use,
                    'video_url': topic.video_url,
                    'keywords': topic.keywords,
                    'view_count': topic.view_count,
                    'helpful_count': topic.helpful_count,
                }
            })
        except AdminHelpTopic.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Help topic not found'
            }, status=404)
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error loading help detail: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load help topic'
            }, status=500)
