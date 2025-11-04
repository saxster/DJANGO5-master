"""
URL configuration for help center app.

REST API routes:
- /api/v2/help-center/articles/ - Article list/detail
- /api/v2/help-center/search/ - Hybrid search
- /api/v2/help-center/categories/ - Category list
- /api/v2/help-center/analytics/ - Analytics endpoints

WebSocket routes (configured in routing.py):
- /ws/help-center/chat/<session_id>/ - AI assistant streaming chat

Following CLAUDE.md URL patterns.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.help_center import views

app_name = 'help_center'

# REST API router
router = DefaultRouter()
router.register(r'articles', views.HelpArticleViewSet, basename='help-article')
router.register(r'categories', views.HelpCategoryViewSet, basename='help-category')
router.register(r'analytics', views.HelpAnalyticsViewSet, basename='help-analytics')

urlpatterns = [
    # REST API endpoints at /api/v2/help-center/
    path('api/v2/help-center/', include(router.urls)),
]
