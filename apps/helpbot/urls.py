"""
HelpBot URL Configuration

Provides both REST API endpoints and traditional Django view endpoints
for HelpBot functionality.
"""

from django.urls import path, include
from .views import (
    SecurityScorecardView,
    HelpBotChatView,
    HelpBotFeedbackView,
    HelpBotKnowledgeView,
    HelpBotAnalyticsView,
    HelpBotContextView,
    HelpBotWidgetView,
    helpbot_health,
    helpbot_config,
    HelpBotChatPageView,
)

app_name = 'helpbot'

# REST API endpoints
api_patterns = [
    path('chat/', HelpBotChatView.as_view(), name='api_chat'),
    path('feedback/', HelpBotFeedbackView.as_view(), name='api_feedback'),
    path('knowledge/', HelpBotKnowledgeView.as_view(), name='api_knowledge'),
    path('analytics/', HelpBotAnalyticsView.as_view(), name='api_analytics'),
    path('context/', HelpBotContextView.as_view(), name='api_context'),
    path('scorecard/', SecurityScorecardView.as_view(), name='api_scorecard'),
    path('health/', helpbot_health, name='api_health'),
    path('config/', helpbot_config, name='api_config'),
]

# Traditional Django view endpoints for widget integration
widget_patterns = [
    path('widget/', HelpBotWidgetView.as_view(), name='widget'),
    path('chat/', HelpBotChatPageView.as_view(), name='chat_page'),
]

urlpatterns = [
    # REST API routes
    path('api/v1/', include(api_patterns)),

    # Widget routes for existing template integration
    path('', include(widget_patterns)),
]