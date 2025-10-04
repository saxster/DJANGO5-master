"""
HelpBot URL Configuration

Provides both REST API endpoints and traditional Django view endpoints
for HelpBot functionality.
"""

from django.urls import path, include
from . import views

app_name = 'helpbot'

# REST API endpoints
api_patterns = [
    path('chat/', views.HelpBotChatView.as_view(), name='api_chat'),
    path('feedback/', views.HelpBotFeedbackView.as_view(), name='api_feedback'),
    path('knowledge/', views.HelpBotKnowledgeView.as_view(), name='api_knowledge'),
    path('analytics/', views.HelpBotAnalyticsView.as_view(), name='api_analytics'),
    path('context/', views.HelpBotContextView.as_view(), name='api_context'),
    path('scorecard/', views.SecurityScorecardView.as_view(), name='api_scorecard'),
    path('health/', views.helpbot_health, name='api_health'),
    path('config/', views.helpbot_config, name='api_config'),
]

# Traditional Django view endpoints for widget integration
widget_patterns = [
    path('widget/', views.HelpBotWidgetView.as_view(), name='widget'),
    path('chat/', views.HelpBotChatPageView.as_view(), name='chat_page'),
]

urlpatterns = [
    # REST API routes
    path('api/v1/', include(api_patterns)),

    # Widget routes for existing template integration
    path('', include(widget_patterns)),
]