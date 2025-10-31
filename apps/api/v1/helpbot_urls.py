"""
HelpBot API URLs (v1)

Domain: /api/v1/helpbot/

Handles AI helpbot sessions and knowledge base.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.helpbot.api.viewsets import HelpBotViewSet, KnowledgeViewSet

app_name = 'helpbot'

router = DefaultRouter()

# HelpBot session endpoints (legacy API replacement)
router.register(r'sessions', HelpBotViewSet, basename='helpbot-sessions')

# Knowledge base endpoints (legacy API replacement)
router.register(r'knowledge', KnowledgeViewSet, basename='helpbot-knowledge')

urlpatterns = [
    # HelpBot endpoints (replace legacy API):
    # - sessions/ (POST) → StartHelpBotSession mutation
    # - sessions/{id}/messages/ → SendHelpBotMessage mutation
    # - sessions/{id}/history/ → helpbot_session_history query
    # - sessions/{id}/feedback/ → SubmitHelpBotFeedback mutation
    # - knowledge/search/ → helpbot_search_knowledge query
    # - knowledge/{id}/ → helpbot_knowledge_article query
    path('', include(router.urls)),
]
