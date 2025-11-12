"""
AI Mentor URL Configuration

Routes for AI mentor system including dashboard, API endpoints,
tutorials, and help center.
"""

from django.urls import path
from apps.core.api.mentor_views import (
    MentorSuggestionsAPI,
    MentorAskAPI,
    MentorTrackSuggestionAPI,
    MentorEfficiencyAPI,
    MentorBriefingAPI,
    MentorNextActionAPI,
    MentorLearningPathAPI,
    MentorAchievementsAPI,
    TutorialListAPI,
    TutorialDetailAPI,
)
from apps.core.views import mentor_views

app_name = 'mentor'

urlpatterns = [
    # Dashboard
    path('dashboard/', mentor_views.MentorDashboardView.as_view(), name='dashboard'),
    
    # API Endpoints
    path('api/suggestions/', MentorSuggestionsAPI.as_view(), name='api_suggestions'),
    path('api/ask/', MentorAskAPI.as_view(), name='api_ask'),
    path('api/track/', MentorTrackSuggestionAPI.as_view(), name='api_track'),
    path('api/efficiency/', MentorEfficiencyAPI.as_view(), name='api_efficiency'),
    path('api/briefing/', MentorBriefingAPI.as_view(), name='api_briefing'),
    path('api/next-action/', MentorNextActionAPI.as_view(), name='api_next_action'),
    path('api/learning-path/', MentorLearningPathAPI.as_view(), name='api_learning_path'),
    path('api/achievements/', MentorAchievementsAPI.as_view(), name='api_achievements'),
    
    # Tutorials
    path('api/tutorials/', TutorialListAPI.as_view(), name='api_tutorials_list'),
    path('api/tutorials/<str:tutorial_id>/', TutorialDetailAPI.as_view(), name='api_tutorial_detail'),
]
