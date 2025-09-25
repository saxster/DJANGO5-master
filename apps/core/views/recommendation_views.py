"""
Views for recommendation system interactions
"""
import json
import logging
from typing import Dict, List, Any

from django.http import JsonResponse, Http404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from apps.core.recommendation_engine import RecommendationEngine
from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, NavigationRecommendation,
    RecommendationFeedback, UserSimilarity
)

logger = logging.getLogger(__name__)


class RecommendationAPIView(LoginRequiredMixin, View):
    """API endpoint for getting user recommendations"""
    
    def get(self, request):
        """Get recommendations for the authenticated user"""
        try:
            engine = RecommendationEngine()
            
            # Get parameters
            limit = min(int(request.GET.get('limit', 10)), 50)  # Cap at 50
            rec_type = request.GET.get('type', 'all')  # 'content', 'navigation', or 'all'
            
            result = {}
            
            if rec_type in ['content', 'all']:
                content_recommendations = engine.generate_user_recommendations(
                    request.user, limit=limit
                )
                result['content_recommendations'] = [
                    self._serialize_content_recommendation(rec)
                    for rec in content_recommendations
                ]
            
            if rec_type in ['navigation', 'all']:
                navigation_recommendations = engine.generate_navigation_recommendations()
                result['navigation_recommendations'] = [
                    self._serialize_navigation_recommendation(rec)
                    for rec in navigation_recommendations[:limit]
                ]
            
            # Add user profile info
            profile = UserBehaviorProfile.objects.filter(user=request.user).first()
            if profile:
                result['user_profile'] = {
                    'exploration_tendency': profile.exploration_tendency,
                    'preferred_device': profile.preferred_device_type,
                    'top_pages': profile.get_top_pages(5)
                }
            
            result['generated_at'] = timezone.now().isoformat()
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error in RecommendationAPIView: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def _serialize_content_recommendation(self, rec):
        """Serialize ContentRecommendation to dict"""
        return {
            'id': rec.id if hasattr(rec, 'id') else None,
            'type': rec.content_type,
            'title': rec.content_title,
            'url': rec.content_url,
            'description': rec.content_description,
            'reason': rec.reason,
            'relevance_score': rec.relevance_score,
            'algorithm': rec.recommendation_algorithm,
            'shown_count': getattr(rec, 'shown_count', 0)
        }
    
    def _serialize_navigation_recommendation(self, rec):
        """Serialize NavigationRecommendation to dict"""
        return {
            'id': rec.id if hasattr(rec, 'id') else None,
            'type': rec.recommendation_type,
            'title': rec.title,
            'description': rec.description,
            'suggested_action': rec.suggested_action,
            'expected_impact': rec.expected_impact,
            'confidence_score': rec.confidence_score,
            'priority': rec.priority,
            'target_page': rec.target_page
        }


@method_decorator(csrf_exempt, name='dispatch')
class RecommendationInteractionView(LoginRequiredMixin, View):
    """Handle recommendation interactions (clicks, dismissals, feedback)"""
    
    def post(self, request):
        """Record recommendation interaction"""
        try:
            data = json.loads(request.body)
            interaction_type = data.get('type')
            rec_id = data.get('rec_id')
            rec_type = data.get('rec_type')  # 'content' or 'navigation'
            
            if not all([interaction_type, rec_id, rec_type]):
                return JsonResponse({'error': 'Missing required parameters'}, status=400)
            
            if rec_type == 'content':
                try:
                    recommendation = ContentRecommendation.objects.get(
                        id=rec_id, 
                        user=request.user
                    )
                    
                    if interaction_type == 'click':
                        recommendation.mark_clicked()
                    elif interaction_type == 'dismiss':
                        recommendation.mark_dismissed()
                    elif interaction_type == 'shown':
                        recommendation.mark_shown()
                    
                except ContentRecommendation.DoesNotExist:
                    return JsonResponse({'error': 'Recommendation not found'}, status=404)
            
            elif rec_type == 'navigation':
                # Navigation recommendations don't have user-specific instances
                # We could track interactions in a separate model if needed
                pass
            
            # Record feedback if provided
            if 'feedback' in data:
                self._record_feedback(request.user, rec_id, rec_type, data['feedback'])
            
            return JsonResponse({'status': 'success'})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error recording recommendation interaction: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def _record_feedback(self, user, rec_id, rec_type, feedback_data):
        """Record user feedback on recommendation"""
        try:
            from django.contrib.contenttypes.models import ContentType
            
            if rec_type == 'content':
                content_type = ContentType.objects.get_for_model(ContentRecommendation)
            elif rec_type == 'navigation':
                content_type = ContentType.objects.get_for_model(NavigationRecommendation)
            else:
                return
            
            RecommendationFeedback.objects.update_or_create(
                content_type=content_type,
                object_id=rec_id,
                user=user,
                defaults={
                    'feedback_type': feedback_data.get('type', 'helpful'),
                    'rating': feedback_data.get('rating'),
                    'comments': feedback_data.get('comments', '')
                }
            )
            
        except Exception as e:
            logger.error(f"Error recording feedback: {str(e)}")


class UserRecommendationDashboardView(LoginRequiredMixin, View):
    """Dashboard view for user's recommendations"""
    
    def get(self, request):
        """Render user recommendation dashboard"""
        # Get user's content recommendations
        content_recs = ContentRecommendation.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-relevance_score', '-created_at')
        
        # Paginate content recommendations
        content_paginator = Paginator(content_recs, 10)
        content_page = content_paginator.get_page(request.GET.get('content_page'))
        
        # Get navigation recommendations (global)
        nav_recs = NavigationRecommendation.objects.filter(
            status='pending'
        ).order_by('-priority', '-confidence_score')[:5]
        
        # Get user behavior profile
        profile = UserBehaviorProfile.objects.filter(user=request.user).first()
        
        # Get similar users
        similar_users = []
        if profile:
            similarities = UserSimilarity.objects.filter(
                models.Q(user1=request.user) | models.Q(user2=request.user)
            ).order_by('-similarity_score')[:5]
            
            for sim in similarities:
                other_user = sim.user2 if sim.user1 == request.user else sim.user1
                similar_users.append({
                    'user': other_user,
                    'similarity_score': sim.similarity_score
                })
        
        context = {
            'content_recommendations': content_page,
            'navigation_recommendations': nav_recs,
            'user_profile': profile,
            'similar_users': similar_users,
            'recommendation_stats': self._get_recommendation_stats(request.user),
        }
        
        return render(request, 'core/recommendation_dashboard.html', context)
    
    def _get_recommendation_stats(self, user):
        """Get recommendation statistics for user"""
        content_recs = ContentRecommendation.objects.filter(user=user)
        
        return {
            'total_recommendations': content_recs.count(),
            'clicked_recommendations': content_recs.filter(clicked_count__gt=0).count(),
            'dismissed_recommendations': content_recs.filter(dismissed_count__gt=0).count(),
            'total_clicks': sum(rec.clicked_count for rec in content_recs),
            'average_relevance_score': content_recs.aggregate(
                avg_score=models.Avg('relevance_score')
            )['avg_score'] or 0,
        }


class RecommendationFeedbackView(LoginRequiredMixin, View):
    """Handle detailed recommendation feedback"""
    
    def get(self, request, rec_type, rec_id):
        """Show feedback form"""
        if rec_type == 'content':
            try:
                recommendation = ContentRecommendation.objects.get(
                    id=rec_id,
                    user=request.user
                )
            except ContentRecommendation.DoesNotExist:
                raise Http404
        elif rec_type == 'navigation':
            try:
                recommendation = NavigationRecommendation.objects.get(id=rec_id)
            except NavigationRecommendation.DoesNotExist:
                raise Http404
        else:
            raise Http404
        
        # Get existing feedback
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(recommendation.__class__)
        
        existing_feedback = RecommendationFeedback.objects.filter(
            content_type=content_type,
            object_id=rec_id,
            user=request.user
        ).first()
        
        context = {
            'recommendation': recommendation,
            'rec_type': rec_type,
            'existing_feedback': existing_feedback,
        }
        
        return render(request, 'core/recommendation_feedback.html', context)
    
    def post(self, request, rec_type, rec_id):
        """Submit feedback"""
        if rec_type == 'content':
            try:
                recommendation = ContentRecommendation.objects.get(
                    id=rec_id,
                    user=request.user
                )
            except ContentRecommendation.DoesNotExist:
                raise Http404
        elif rec_type == 'navigation':
            try:
                recommendation = NavigationRecommendation.objects.get(id=rec_id)
            except NavigationRecommendation.DoesNotExist:
                raise Http404
        else:
            raise Http404
        
        # Save feedback
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(recommendation.__class__)
        
        feedback_type = request.POST.get('feedback_type')
        rating = request.POST.get('rating')
        comments = request.POST.get('comments', '')
        
        try:
            rating = int(rating) if rating else None
        except (ValueError, TypeError):
            rating = None
        
        RecommendationFeedback.objects.update_or_create(
            content_type=content_type,
            object_id=rec_id,
            user=request.user,
            defaults={
                'feedback_type': feedback_type,
                'rating': rating,
                'comments': comments
            }
        )
        
        messages.success(request, 'Thank you for your feedback!')
        return redirect('recommendation_dashboard')


class RecommendationManagementView(LoginRequiredMixin, View):
    """View for managing user's recommendations"""
    
    def post(self, request):
        """Handle recommendation management actions"""
        action = request.POST.get('action')
        rec_ids = request.POST.getlist('recommendation_ids')
        
        if not rec_ids:
            messages.error(request, 'No recommendations selected')
            return redirect('recommendation_dashboard')
        
        try:
            if action == 'dismiss_selected':
                ContentRecommendation.objects.filter(
                    id__in=rec_ids,
                    user=request.user
                ).update(is_active=False)
                messages.success(request, f'Dismissed {len(rec_ids)} recommendations')
            
            elif action == 'mark_helpful':
                for rec_id in rec_ids:
                    self._add_quick_feedback(request.user, rec_id, 'helpful')
                messages.success(request, f'Marked {len(rec_ids)} recommendations as helpful')
            
            elif action == 'mark_not_helpful':
                for rec_id in rec_ids:
                    self._add_quick_feedback(request.user, rec_id, 'not_helpful')
                messages.success(request, f'Marked {len(rec_ids)} recommendations as not helpful')
        
        except Exception as e:
            logger.error(f"Error in recommendation management: {str(e)}")
            messages.error(request, 'An error occurred while processing your request')
        
        return redirect('recommendation_dashboard')
    
    def _add_quick_feedback(self, user, rec_id, feedback_type):
        """Add quick feedback for a recommendation"""
        try:
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(ContentRecommendation)
            
            RecommendationFeedback.objects.update_or_create(
                content_type=content_type,
                object_id=rec_id,
                user=user,
                defaults={'feedback_type': feedback_type}
            )
        except Exception as e:
            logger.error(f"Error adding quick feedback: {str(e)}")


class AdminRecommendationView(LoginRequiredMixin, View):
    """Admin view for managing navigation recommendations"""
    
    def get(self, request):
        """Show navigation recommendations for admin review"""
        if not request.user.is_staff:
            raise Http404
        
        # Get pending navigation recommendations
        pending_recs = NavigationRecommendation.objects.filter(
            status='pending'
        ).order_by('-priority', '-confidence_score')
        
        # Get recent feedback
        recent_feedback = RecommendationFeedback.objects.select_related(
            'user', 'content_type'
        ).order_by('-created_at')[:20]
        
        context = {
            'pending_recommendations': pending_recs,
            'recent_feedback': recent_feedback,
            'recommendation_stats': self._get_admin_stats(),
        }
        
        return render(request, 'core/admin_recommendations.html', context)
    
    def post(self, request):
        """Handle admin actions on recommendations"""
        if not request.user.is_staff:
            raise Http404
        
        action = request.POST.get('action')
        rec_id = request.POST.get('recommendation_id')
        
        try:
            recommendation = NavigationRecommendation.objects.get(id=rec_id)
            
            if action == 'approve':
                recommendation.status = 'approved'
                messages.success(request, f'Approved recommendation: {recommendation.title}')
            
            elif action == 'reject':
                recommendation.status = 'rejected'
                messages.success(request, f'Rejected recommendation: {recommendation.title}')
            
            elif action == 'implement':
                recommendation.apply_recommendation(request.user)
                messages.success(request, f'Marked as implemented: {recommendation.title}')
            
            recommendation.save()
            
        except NavigationRecommendation.DoesNotExist:
            messages.error(request, 'Recommendation not found')
        except Exception as e:
            logger.error(f"Error in admin recommendation action: {str(e)}")
            messages.error(request, 'An error occurred')
        
        return redirect('admin_recommendations')
    
    def _get_admin_stats(self):
        """Get admin statistics for recommendations"""
        nav_recs = NavigationRecommendation.objects.all()
        content_recs = ContentRecommendation.objects.all()
        
        return {
            'total_navigation_recommendations': nav_recs.count(),
            'pending_navigation_recommendations': nav_recs.filter(status='pending').count(),
            'approved_navigation_recommendations': nav_recs.filter(status='approved').count(),
            'implemented_navigation_recommendations': nav_recs.filter(status='implemented').count(),
            'total_content_recommendations': content_recs.count(),
            'active_content_recommendations': content_recs.filter(is_active=True).count(),
            'total_feedback_items': RecommendationFeedback.objects.count(),
            'users_with_profiles': UserBehaviorProfile.objects.count(),
        }