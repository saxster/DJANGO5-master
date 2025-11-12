"""
HelpBot API URLs (V2)

Domain: /api/v2/helpbot/

AI assistant chat, knowledge search, and feedback.
"""

from django.urls import path
from apps.api.v2.views import helpbot_views

app_name = 'helpbot'

urlpatterns = [
    path('chat/', helpbot_views.HelpBotChatView.as_view(), name='chat'),
    path('knowledge/', helpbot_views.HelpBotKnowledgeView.as_view(), name='knowledge'),
    path('feedback/', helpbot_views.HelpBotFeedbackView.as_view(), name='feedback'),
]
