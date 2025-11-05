"""
HelpBot Views Package

Exports all view classes and functions for URL configuration.
"""

# REST API Views
from .session_views import SecurityScorecardView
from .message_views import HelpBotChatView
from .feedback_views import HelpBotFeedbackView
from .knowledge_views import HelpBotKnowledgeView
from .analytics_views import HelpBotAnalyticsView
from .context_views import HelpBotContextView

# Traditional Django Views
from .widget_views import HelpBotWidgetView

# Function-based and Template Views
from .utility_views import (
    helpbot_health,
    helpbot_config,
    HelpBotChatPageView,
)

__all__ = [
    # REST API Views
    'SecurityScorecardView',
    'HelpBotChatView',
    'HelpBotFeedbackView',
    'HelpBotKnowledgeView',
    'HelpBotAnalyticsView',
    'HelpBotContextView',
    # Traditional Django Views
    'HelpBotWidgetView',
    # Function-based and Template Views
    'helpbot_health',
    'helpbot_config',
    'HelpBotChatPageView',
]
