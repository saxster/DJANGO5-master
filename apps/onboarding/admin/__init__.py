"""
Onboarding Admin Module - Backward Compatibility Layer

This module provides 100% backward compatibility for the refactored onboarding admin.
All admin classes, resource classes, and helper functions are re-exported from their new locations.

Migration Date: 2025-09-30
Original File: apps/onboarding/admin.py (1,705 lines)
New Structure: 8 domain-focused modules (base, typeassist, business_unit, shift, geofence,
                                         conversation, changeset, knowledge)

Usage:
    # Old import (still works):
    from apps.onboarding.admin import TaAdmin, BtAdmin

    # New import (recommended):
    from apps.onboarding.admin.typeassist_admin import TaAdmin
    from apps.onboarding.admin.business_unit_admin import BtAdmin
"""

# Base classes and helpers
from .base import (
    BaseResource,
    BaseFieldSet2,
    default_ta,
)

# TypeAssist admin
from .typeassist_admin import (
    clean_nan,
    TaResource,
    TaResourceUpdate,
    TaAdmin,
)

# Business Unit admin
from .business_unit_admin import (
    BtResource,
    BtResourceUpdate,
    BtAdmin,
)

# Shift admin
from .shift_admin import (
    ShiftResource,
    ShiftAdmin,
)

# Geofence resources
from .geofence_resources import (
    GeofenceResource,
    GeofencePeopleResource,
)

# Conversation admin (AI-powered onboarding)
from .conversation_admin import (
    ConversationSessionAdmin,
    LLMRecommendationAdmin,
)

# Changeset admin (AI-generated changes)
from .changeset_admin import (
    AIChangeRecordInline,
    AIChangeSetAdmin,
    AIChangeRecordAdmin,
)

# Knowledge admin (Authoritative knowledge base)
from .knowledge_admin import (
    AuthoritativeKnowledgeChunkInline,
    AuthoritativeKnowledgeAdmin,
    AuthoritativeKnowledgeChunkAdmin,
)

# Explicit __all__ for clarity and documentation
__all__ = [
    # Base
    "BaseResource",
    "BaseFieldSet2",
    "default_ta",
    # TypeAssist
    "clean_nan",
    "TaResource",
    "TaResourceUpdate",
    "TaAdmin",
    # Business Unit
    "BtResource",
    "BtResourceUpdate",
    "BtAdmin",
    # Shift
    "ShiftResource",
    "ShiftAdmin",
    # Geofence
    "GeofenceResource",
    "GeofencePeopleResource",
    # Conversation (AI Onboarding)
    "ConversationSessionAdmin",
    "LLMRecommendationAdmin",
    # Changeset (AI Changes)
    "AIChangeRecordInline",
    "AIChangeSetAdmin",
    "AIChangeRecordAdmin",
    # Knowledge Base
    "AuthoritativeKnowledgeChunkInline",
    "AuthoritativeKnowledgeAdmin",
    "AuthoritativeKnowledgeChunkAdmin",
]
