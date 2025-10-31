"""
HelpBot Admin Module

Modular admin interfaces for HelpBot functionality.
Split into focused modules for maintainability and CLAUDE.md compliance.

Module Structure:
- base.py: Shared filters, inlines, and utilities
- session_admin.py: HelpBotSession administration
- message_admin.py: HelpBotMessage administration
- knowledge_admin.py: HelpBotKnowledge administration
- feedback_admin.py: HelpBotFeedback administration
- context_admin.py: HelpBotContext administration
- analytics_admin.py: HelpBotAnalytics administration

Each module is <200 lines, following architectural limits.
"""

# Import all admin classes for backward compatibility
from apps.helpbot.admin.base import (
    MessageCountFilter,
    RecentSessionFilter,
    HelpBotMessageInline,
    HelpBotFeedbackInline
)
from apps.helpbot.admin.session_admin import HelpBotSessionAdmin
from apps.helpbot.admin.message_admin import HelpBotMessageAdmin
from apps.helpbot.admin.knowledge_admin import HelpBotKnowledgeAdmin
from apps.helpbot.admin.feedback_admin import HelpBotFeedbackAdmin
from apps.helpbot.admin.context_admin import HelpBotContextAdmin
from apps.helpbot.admin.analytics_admin import HelpBotAnalyticsAdmin

__all__ = [
    # Filters and Inlines
    'MessageCountFilter',
    'RecentSessionFilter',
    'HelpBotMessageInline',
    'HelpBotFeedbackInline',
    # Admin Classes
    'HelpBotSessionAdmin',
    'HelpBotMessageAdmin',
    'HelpBotKnowledgeAdmin',
    'HelpBotFeedbackAdmin',
    'HelpBotContextAdmin',
    'HelpBotAnalyticsAdmin',
]
