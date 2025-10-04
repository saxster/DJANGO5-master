"""
Wellness App URLs Configuration

Complete URL patterns for the wellness education system API endpoints with:
- Evidence-based content delivery with WHO/CDC compliance
- Daily wellness tips with intelligent personalization
- Contextual content delivery based on journal patterns
- ML-powered personalized recommendations
- User progress tracking with gamification
- Analytics and effectiveness measurement
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    WellnessContentViewSet, DailyWellnessTipView,
    ContextualWellnessContentView, PersonalizedWellnessContentView,
    WellnessProgressView, WellnessAnalyticsView
)

# Import wisdom conversation views
from .views.wisdom_conversation_views import (
    conversations_with_wisdom_view,
    toggle_conversation_bookmark,
    track_conversation_engagement,
    conversation_reflection_view,
    conversation_export_view,
    conversation_analytics_api,
    conversation_search_api,
)

# Import translation API views
from .views.translation_api_views import (
    translate_conversation,
    get_supported_languages,
    get_translation_status,
    submit_translation_feedback,
    get_translation_analytics,
    batch_translate_conversations,
)
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

app_name = 'wellness'

# REST API router for wellness content
router = DefaultRouter()
router.register(r'content', WellnessContentViewSet, basename='wellnesscontent')

urlpatterns = [
    # Web UI Templates
    path('content/', login_required(TemplateView.as_view(template_name='wellness/content_discovery.html')), name='wellness-content-discovery'),
    path('settings/', login_required(TemplateView.as_view(template_name='wellness/settings.html')), name='wellness-settings'),

    # Conversations with Wisdom - Main feature
    path('conversations/', conversations_with_wisdom_view, name='conversations_with_wisdom'),
    path('conversations/wisdom/', conversations_with_wisdom_view, name='conversations_with_wisdom_alt'),

    # Conversation interaction APIs
    path('conversations/<uuid:conversation_id>/bookmark/', toggle_conversation_bookmark, name='toggle_bookmark'),
    path('conversations/<uuid:conversation_id>/track/', track_conversation_engagement, name='track_engagement'),
    path('conversations/<uuid:conversation_id>/reflect/', conversation_reflection_view, name='conversation_reflection'),

    # Export and conversation analytics
    path('conversations/export/', conversation_export_view, name='conversation_export'),
    path('api/conversations/analytics/', conversation_analytics_api, name='conversation_analytics'),
    path('api/conversations/search/', conversation_search_api, name='conversation_search'),

    # REST API endpoints from router
    path('api/', include(router.urls)),

    # Intelligent content delivery endpoints
    path('api/daily-tip/', DailyWellnessTipView.as_view(), name='daily-wellness-tip'),
    path('api/contextual/', ContextualWellnessContentView.as_view(), name='contextual-wellness-content'),
    path('api/personalized/', PersonalizedWellnessContentView.as_view(), name='personalized-wellness-content'),

    # User progress and gamification
    path('api/progress/', WellnessProgressView.as_view(), name='wellness-progress'),

    # Analytics and insights
    path('api/analytics/', WellnessAnalyticsView.as_view(), name='wellness-analytics'),

    # Translation API endpoints
    path('api/translate-conversation/', translate_conversation, name='translate_conversation'),
    path('api/supported-languages/', get_supported_languages, name='supported_languages'),
    path('api/translation-status/<uuid:conversation_id>/', get_translation_status, name='translation_status'),
    path('api/translation-feedback/', submit_translation_feedback, name='translation_feedback'),
    path('api/translation-analytics/', get_translation_analytics, name='translation_analytics'),
    path('api/batch-translate/', batch_translate_conversations, name='batch_translate'),

    # Additional API endpoints provided by WellnessContentViewSet custom actions:
    # POST /api/content/{id}/track_interaction/ - Track user interaction with content
    # GET /api/content/categories/ - Get wellness categories with content counts
]