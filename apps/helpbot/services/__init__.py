"""
HelpBot Services

Core business logic services for the AI HelpBot application.
Integrates with existing AI infrastructure including txtai, semantic search, and knowledge management.
"""

from .knowledge_service import HelpBotKnowledgeService
from .conversation_service import HelpBotConversationService
from .context_service import HelpBotContextService
from .analytics_service import HelpBotAnalyticsService

__all__ = [
    'HelpBotKnowledgeService',
    'HelpBotConversationService',
    'HelpBotContextService',
    'HelpBotAnalyticsService',
]