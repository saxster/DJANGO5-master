"""
Legacy Onboarding Models Shim
=============================

Provides backward-compatible symbols for modules that still import
``apps.onboarding.models`` after the bounded-context split. The actual models
live in ``apps.client_onboarding`` and ``apps.core_onboarding``.
"""

from apps.client_onboarding.models import (
    Bt,
    Bu,
    Shift,
    Device,
    Subscription,
    DownTimeHistory,
    bu_defaults,
    shiftdata_json,
)
from apps.core_onboarding.models import TypeAssist, GeofenceMaster

# Backward compatibility aliases
BusinessUnit = Bt
Site = Bt

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
    'bu_defaults',
    'shiftdata_json',
]
