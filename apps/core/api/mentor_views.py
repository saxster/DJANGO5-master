"""
AI Mentor API Views - REST Endpoints for Admin Mentor

Provides API endpoints for the AI mentor system to deliver
contextual suggestions, answer questions, and track interactions.

Following .claude/rules.md:
- Rule #8: View methods <30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #14: No blocking I/O
"""

import json
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.core.services.admin_mentor_service import AdminMentorService
from apps.core.services.admin_tutorial_service import AdminTutorialService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.services.base_service import logger


class MentorSuggestionsAPI(LoginRequiredMixin, View):
    """Get contextual suggestions for current page"""
    
    def post(self, request):
        """
        Get AI-powered suggestions.
        
        Request body:
            {
                "url": "/admin/tickets/",
                "context": {"unassigned_count": 15}
            }
        
        Returns:
            List of suggestion objects
        """
        try:
            data = json.loads(request.body)
            
            suggestions = AdminMentorService.get_contextual_suggestions(
                user=request.user,
                page_url=data.get('url', ''),
                context=data.get('context', {})
            )
            
            return JsonResponse(suggestions, safe=False)
            
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'Invalid JSON'},
                status=400
            )
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to get suggestions'},
                status=500
            )


class MentorAskAPI(LoginRequiredMixin, View):
    """Answer admin's question"""
    
    def post(self, request):
        """
        Answer a question using ontology.
        
        Request body:
            {"question": "How do I use quick actions?"}
        
        Returns:
            {
                "title": "Quick Actions Guide",
                "answer": "Quick actions are...",
                "related_articles": [...]
            }
        """
        try:
            data = json.loads(request.body)
            question = data.get('question', '').strip()
            
            if not question:
                return JsonResponse(
                    {'error': 'Question is required'},
                    status=400
                )
            
            answer = AdminMentorService.answer_question(
                question=question,
                user=request.user
            )
            
            return JsonResponse(answer)
            
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'Invalid JSON'},
                status=400
            )
        except Exception as e:
            logger.error(f"Error answering question: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to answer question'},
                status=500
            )


class MentorTrackSuggestionAPI(LoginRequiredMixin, View):
    """Track that user followed a suggestion"""
    
    def post(self, request):
        """
        Track suggestion followed.
        
        Request body:
            {"suggestion_id": "smart_assign_tickets"}
        """
        try:
            data = json.loads(request.body)
            suggestion_id = data.get('suggestion_id')
            
            if not suggestion_id:
                return JsonResponse(
                    {'error': 'suggestion_id is required'},
                    status=400
                )
            
            AdminMentorService.track_suggestion_followed(
                user=request.user,
                suggestion_id=suggestion_id
            )
            
            return JsonResponse({'success': True})
            
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'Invalid JSON'},
                status=400
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error tracking suggestion: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to track suggestion'},
                status=500
            )


class MentorEfficiencyAPI(LoginRequiredMixin, View):
    """Get user's efficiency report"""
    
    def get(self, request):
        """
        Get efficiency analysis.
        
        Query params:
            ?days=30
        
        Returns:
            {
                "total_time_saved": 3600,
                "features_adopted": 7,
                "efficiency_score": 75,
                "recommendations": [...]
            }
        """
        try:
            days = int(request.GET.get('days', 30))
            
            analysis = AdminMentorService.analyze_efficiency(
                user=request.user,
                days=days
            )
            
            return JsonResponse(analysis)
            
        except ValueError:
            return JsonResponse(
                {'error': 'Invalid days parameter'},
                status=400
            )
        except Exception as e:
            logger.error(f"Error getting efficiency: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to get efficiency report'},
                status=500
            )


class TutorialListAPI(LoginRequiredMixin, View):
    """List available tutorials"""
    
    def get(self, request):
        """
        Get all tutorials or recommendations.
        
        Query params:
            ?recommended=true  # Get personalized recommendations
        
        Returns:
            List of tutorial objects
        """
        try:
            if request.GET.get('recommended') == 'true':
                tutorials = AdminTutorialService.get_recommended_tutorials(
                    user=request.user
                )
            else:
                tutorials = AdminTutorialService.list_tutorials()
            
            return JsonResponse(tutorials, safe=False)
            
        except Exception as e:
            logger.error(f"Error listing tutorials: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to list tutorials'},
                status=500
            )


class TutorialDetailAPI(LoginRequiredMixin, View):
    """Get tutorial details"""
    
    def get(self, request, tutorial_id):
        """
        Get specific tutorial.
        
        Returns:
            Tutorial object with steps
        """
        try:
            tutorial = AdminTutorialService.get_tutorial(tutorial_id)
            
            if not tutorial:
                return JsonResponse(
                    {'error': 'Tutorial not found'},
                    status=404
                )
            
            return JsonResponse(tutorial)
            
        except Exception as e:
            logger.error(f"Error getting tutorial: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to get tutorial'},
                status=500
            )


class MentorBriefingAPI(LoginRequiredMixin, View):
    """Get daily briefing"""
    
    def get(self, request):
        """
        Get personalized daily briefing.
        
        Returns:
            {
                "greeting": "Good morning, John!",
                "date": "Monday, November 7, 2025",
                "summary": {"my_tasks": 5, "urgent_items": 2},
                "priorities": [...],
                "suggestions": [...],
                "tip_of_day": "..."
            }
        """
        try:
            briefing = AdminMentorService.generate_daily_briefing(
                user=request.user
            )
            
            return JsonResponse(briefing)
            
        except Exception as e:
            logger.error(f"Error generating briefing: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to generate briefing'},
                status=500
            )


class MentorNextActionAPI(LoginRequiredMixin, View):
    """Get next best action suggestion"""
    
    def post(self, request):
        """
        Get AI suggestion for next best action.
        
        Request body:
            {"context": {...}}  # Optional context
        
        Returns:
            {
                "action": "Handle Urgent Items",
                "reason": "3 items might miss deadlines",
                "url": "/admin/dashboard/...",
                "priority": "HIGH",
                "estimated_time": "30 minutes"
            }
        """
        try:
            data = json.loads(request.body) if request.body else {}
            context = data.get('context')
            
            next_action = AdminMentorService.suggest_next_best_action(
                user=request.user,
                context=context
            )
            
            return JsonResponse(next_action)
            
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'Invalid JSON'},
                status=400
            )
        except Exception as e:
            logger.error(f"Error suggesting next action: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to suggest next action'},
                status=500
            )


class MentorLearningPathAPI(LoginRequiredMixin, View):
    """Get personalized learning path"""
    
    def get(self, request):
        """
        Get personalized learning recommendations.
        
        Returns:
            {
                "current_level": "INTERMEDIATE",
                "features_mastered": 5,
                "features_remaining": 4,
                "next_steps": [...],
                "estimated_time": 30
            }
        """
        try:
            learning_path = AdminMentorService.create_personalized_learning_path(
                user=request.user
            )
            
            return JsonResponse(learning_path)
            
        except Exception as e:
            logger.error(f"Error creating learning path: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to create learning path'},
                status=500
            )


class MentorAchievementsAPI(LoginRequiredMixin, View):
    """Get user achievements and gamification stats"""
    
    def get(self, request):
        """
        Get achievements and points.
        
        Returns:
            {
                "total_points": 135,
                "achievements": [...],
                "next_achievement": {...}
            }
        """
        try:
            achievements = AdminMentorService.get_user_achievements(
                user=request.user
            )
            
            return JsonResponse(achievements)
            
        except Exception as e:
            logger.error(f"Error getting achievements: {e}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to get achievements'},
                status=500
            )
