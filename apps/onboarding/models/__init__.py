"""
Legacy Onboarding Models Shim
=============================

Provides backward-compatible symbols for modules that still import
``apps.onboarding.models`` after the bounded-context split. The actual models
live in ``apps.client_onboarding`` and ``apps.core_onboarding``.
"""

from apps.client_onboarding.models import (
    Bt,
    Shift,
    Device,
    Subscription,
    DownTimeHistory,
    bu_defaults,
    shiftdata_json,
)
from apps.core_onboarding.models import (
    TypeAssist,
    GeofenceMaster,
    ConversationSession,
    LLMRecommendation,
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk,
    AIChangeSet,
    AIChangeRecord,
    ChangeSetApproval,
    OnboardingObservation,
)
from apps.site_onboarding.models import (
    OnboardingZone,
    OnboardingSite,
    Asset,
    Checkpoint,
    SitePhoto,
    MeterPoint,
    SOP,
    CoveragePlan,
)

# Backward compatibility aliases
BusinessUnit = Bt
Site = Bt
Bu = Bt
Observation = OnboardingObservation  # Alias for serializers

__all__ = [
    'Bt',
    'Bu',
    'BusinessUnit',
    'Site',
    'Shift',
    'Device',
    'Subscription',
    'DownTimeHistory',
    'TypeAssist',
    'GeofenceMaster',
    'ConversationSession',
    'LLMRecommendation',
    'AuthoritativeKnowledge',
    'AuthoritativeKnowledgeChunk',
    'AIChangeSet',
    'AIChangeRecord',
    'ChangeSetApproval',
    'OnboardingZone',
    'OnboardingSite',
    'Asset',
    'Checkpoint',
    'SitePhoto',
    'MeterPoint',
    'SOP',
    'CoveragePlan',
    'Observation',
    'OnboardingObservation',
    'bu_defaults',
    'shiftdata_json',
]
