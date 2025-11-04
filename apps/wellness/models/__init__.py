"""
Wellness Models Package

Refactored from 697-line monolithic file into focused modules.
Complies with .claude/rules.md Rule #7 (Model Complexity Limits).

Architecture:
- enums.py: Content categorization and delivery enums
- content.py: WellnessContent model (evidence-based content delivery)
- progress.py: WellnessUserProgress model (gamification and tracking)
- interaction.py: WellnessContentInteraction model (engagement tracking)

Related: Ultrathink Code Review Phase 3 - ARCH-001
All models < 150 lines per file, following Single Responsibility Principle.
"""

from .enums import (
    WellnessContentCategory,
    WellnessDeliveryContext,
    WellnessContentLevel,
    EvidenceLevel,
)

from .content import WellnessContent

from .progress import WellnessUserProgress

from .interaction import WellnessContentInteraction

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