"""
Wellness Models Package

Refactored from 697-line monolithic file into focused modules.
Complies with .claude/rules.md Rule #7 (Model Complexity Limits).

Architecture:
- content_models.py: Content and delivery configuration (168 lines)
- user_progress.py: User progress and gamification (91 lines)
- interaction_models.py: Engagement tracking (104 lines)

All models < 150 lines per file, following Single Responsibility Principle.
"""

from .content_models import (
    WellnessContentCategory,
    WellnessDeliveryContext,
    WellnessContentLevel,
    EvidenceLevel,
    WellnessContent,
)

from .user_progress import WellnessUserProgress

from .interaction_models import WellnessContentInteraction

from .mental_health_interventions import (
    MentalHealthInterventionType,
    InterventionDeliveryTiming,
    InterventionEvidenceBase,
    MentalHealthIntervention,
    InterventionDeliveryLog,
)

from .wisdom_conversations import (
    ConversationThread,
    WisdomConversation,
    ConversationEngagement,
    ConversationBookmark,
)

from .conversation_translation import (
    WisdomConversationTranslation,
    TranslationQualityFeedback,
)

__all__ = [
    # Enums
    'WellnessContentCategory',
    'WellnessDeliveryContext',
    'WellnessContentLevel',
    'EvidenceLevel',
    'MentalHealthInterventionType',
    'InterventionDeliveryTiming',
    'InterventionEvidenceBase',

    # Models
    'WellnessContent',
    'WellnessUserProgress',
    'WellnessContentInteraction',
    'MentalHealthIntervention',
    'InterventionDeliveryLog',

    # Wisdom Conversations
    'ConversationThread',
    'WisdomConversation',
    'ConversationEngagement',
    'ConversationBookmark',

    # Translation Models
    'WisdomConversationTranslation',
    'TranslationQualityFeedback',
]