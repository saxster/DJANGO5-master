"""
Tutorial API Views

REST API endpoints for interactive tutorial system.

Following .claude/rules.md:
- Rule #8: View methods <30 lines (delegate to services)
- Rule #11: Specific exception handling
"""

import json
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from apps.core.services.tutorial_engine import TutorialEngine
from apps.core.tutorials.content import TUTORIALS
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.services.base_service import logger


@method_decorator(csrf_protect, name='dispatch')
class TutorialListAPI(LoginRequiredMixin, View):
    """List all available tutorials"""
    
    def get(self, request):
        """Get list of tutorials"""
        try:
            tutorials = [
                {
                    'id': t['id'],
                    'title': t['title'],
                    'description': t['description'],
                    'duration': t['duration'],
                    'difficulty': t.get('difficulty', 'BEGINNER'),
                    'points': t.get('points', 10),
                    'badge_icon': t.get('badge_icon', '🎓'),
                    'steps_count': len(t['steps'])
                }
                for t in TUTORIALS.values()
            ]
            
            return JsonResponse({
                'success': True,
                'tutorials': tutorials,
                'total': len(tutorials)
            })
        except Exception as e:
            logger.error(f"Error listing tutorials: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load tutorials'
            }, status=500)


@method_decorator(csrf_protect, name='dispatch')
class TutorialStartAPI(LoginRequiredMixin, View):
    """Start a tutorial"""
    
    def post(self, request):
        """Start tutorial and return first step"""
        try:
            data = json.loads(request.body)
            tutorial_id = data.get('tutorial_id')
            
            if not tutorial_id:
                return JsonResponse({
                    'success': False,
                    'error': 'tutorial_id is required'
                }, status=400)
            
            if tutorial_id not in TUTORIALS:
                return JsonResponse({
                    'success': False,
                    'error': f'Tutorial not found: {tutorial_id}'
                }, status=404)
            
            engine = TutorialEngine(tutorial_id, request.user)
            first_step = engine.start()
            
            return JsonResponse({
                'success': True,
                **first_step
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error starting tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Database error'
            }, status=500)
        except Exception as e:
            logger.error(f"Error starting tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to start tutorial'
            }, status=500)


@method_decorator(csrf_protect, name='dispatch')
class TutorialStepAPI(LoginRequiredMixin, View):
    """Navigate tutorial steps"""
    
    def post(self, request):
        """Get specific tutorial step"""
        try:
            data = json.loads(request.body)
            tutorial_id = data.get('tutorial_id')
            step_index = data.get('step_index')
            action = data.get('action', 'next')
            
            if not tutorial_id or step_index is None:
                return JsonResponse({
                    'success': False,
                    'error': 'tutorial_id and step_index are required'
                }, status=400)
            
            engine = TutorialEngine(tutorial_id, request.user)
            
            if action == 'next':
                step_data = engine.next_step(step_index)
            elif action == 'prev':
                step_data = engine.previous_step(step_index)
            else:
                step_data = engine.get_step(step_index)
            
            return JsonResponse({
                'success': True,
                **step_data
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error navigating tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Database error'
            }, status=500)
        except Exception as e:
            logger.error(f"Error navigating tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to navigate tutorial'
            }, status=500)


@method_decorator(csrf_protect, name='dispatch')
class TutorialCompleteAPI(LoginRequiredMixin, View):
    """Complete a tutorial"""
    
    def post(self, request):
        """Mark tutorial as completed"""
        try:
            data = json.loads(request.body)
            tutorial_id = data.get('tutorial_id')
            
            if not tutorial_id:
                return JsonResponse({
                    'success': False,
                    'error': 'tutorial_id is required'
                }, status=400)
            
            engine = TutorialEngine(tutorial_id, request.user)
            result = engine.complete()
            
            return JsonResponse({
                'success': True,
                **result
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error completing tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Database error'
            }, status=500)
        except Exception as e:
            logger.error(f"Error completing tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to complete tutorial'
            }, status=500)


@method_decorator(csrf_protect, name='dispatch')
class TutorialSkipAPI(LoginRequiredMixin, View):
    """Skip a tutorial"""
    
    def post(self, request):
        """Mark tutorial as skipped"""
        try:
            data = json.loads(request.body)
            tutorial_id = data.get('tutorial_id')
            
            if not tutorial_id:
                return JsonResponse({
                    'success': False,
                    'error': 'tutorial_id is required'
                }, status=400)
            
            engine = TutorialEngine(tutorial_id, request.user)
            result = engine.skip()
            
            return JsonResponse({
                'success': True,
                **result
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error skipping tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Database error'
            }, status=500)
        except Exception as e:
            logger.error(f"Error skipping tutorial: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to skip tutorial'
            }, status=500)


@method_decorator(csrf_protect, name='dispatch')
class TutorialProgressAPI(LoginRequiredMixin, View):
    """Get user's tutorial progress"""
    
    def get(self, request):
        """Get overall tutorial progress"""
        try:
            progress = TutorialEngine.get_user_progress(request.user)
            
            return JsonResponse({
                'success': True,
                **progress
            })
        except Exception as e:
            logger.error(f"Error getting tutorial progress: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to load progress'
            }, status=500)
