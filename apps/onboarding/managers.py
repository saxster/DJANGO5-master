"""
Legacy Onboarding Managers Shim
===============================

Historically code imported custom managers from ``apps.onboarding.managers``.
After the bounded-context split those managers live in
``apps.client_onboarding.managers``. This module re-exports them so existing
imports (including old migrations) continue to work.
"""

from apps.client_onboarding.managers import (
    BtManager,
    TypeAssistManager,
    GeofenceManager,
    ShiftManager,
    DeviceManager,
    SubscriptionManger,
)

# Backward-compatible alias for typo'd manager name kept in historical migrations
SubscriptionManager = SubscriptionManger

__all__ = [
    'BtManager',
    'TypeAssistManager',
    'GeofenceManager',
    'ShiftManager',
    'DeviceManager',
    'SubscriptionManger',
    'SubscriptionManager',
]
