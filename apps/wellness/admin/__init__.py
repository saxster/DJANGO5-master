"""
Wellness Admin Package

Modular admin interface for the wellness application.

Structure:
- base.py: Shared utilities and mixins
- content_admin.py: WellnessContent and WellnessContentInteraction
- progress_admin.py: WellnessUserProgress
- translation_admin.py: WisdomConversationTranslation and TranslationQualityFeedback
- wisdom_conversation_admin.py: Wisdom conversation models

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: Modular structure, <200 lines per file
"""

# Import base classes
from .base import WellnessBaseModelAdmin, WellnessAdminMixin

# Import content admin
from .content_admin import (
    WellnessContentAdmin,
    WellnessContentInteractionAdmin,
)

# Import progress admin
from .progress_admin import WellnessUserProgressAdmin

# Import translation admin
from .translation_admin import (
    WisdomConversationTranslationAdmin,
    TranslationQualityFeedbackAdmin,
)

# Import wisdom conversation admin
from .wisdom_conversation_admin import (
    ConversationThreadAdmin,
    WisdomConversationAdmin,
    ConversationEngagementAdmin,
    ConversationBookmarkAdmin,
)

__all__ = [
    # Base classes
    'WellnessBaseModelAdmin',
    'WellnessAdminMixin',
    # Content admin
    'WellnessContentAdmin',
    'WellnessContentInteractionAdmin',
    # Progress admin
    'WellnessUserProgressAdmin',
    # Translation admin
    'WisdomConversationTranslationAdmin',
    'TranslationQualityFeedbackAdmin',
    # Wisdom conversation admin
    'ConversationThreadAdmin',
    'WisdomConversationAdmin',
    'ConversationEngagementAdmin',
    'ConversationBookmarkAdmin',
]
