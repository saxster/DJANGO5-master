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

    # Additional API endpoints provided by WellnessContentViewSet custom actions:
    # POST /api/content/{id}/track_interaction/ - Track user interaction with content
    # GET /api/content/categories/ - Get wellness categories with content counts
]