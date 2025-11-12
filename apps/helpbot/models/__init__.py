"""
HelpBot Models Package - Backward Compatibility Layer

This package provides 100% backward compatibility for the refactored helpbot models.
All model classes are re-exported from their new locations in focused modules.

Migration Date: 2025-11-05
Original File: apps/helpbot/models.py (543 lines)
New Structure: 6 domain-focused modules + __init__.py

Usage:
    # Old import (still works):
    from apps.helpbot.models import HelpBotSession, HelpBotMessage

    # New import (recommended):
    from apps.helpbot.models.session import HelpBotSession
    from apps.helpbot.models.message import HelpBotMessage
"""

# Session management
from .session import HelpBotSession

# Message handling
from .message import HelpBotMessage

# Knowledge base
from .knowledge import HelpBotKnowledge

# User feedback
from .feedback import HelpBotFeedback

# Context tracking
from .context import HelpBotContext

# Analytics and metrics
from .analytics import HelpBotAnalytics


__all__ = [
    # Session
    'HelpBotSession',

    # Message
    'HelpBotMessage',

    # Knowledge
    'HelpBotKnowledge',

    # Feedback
    'HelpBotFeedback',

    # Context
    'HelpBotContext',

    # Analytics
    'HelpBotAnalytics',
]
