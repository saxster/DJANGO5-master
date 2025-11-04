"""
Client Onboarding Models Package - Bounded Context for Client/Business Unit Management.

This app contains models specific to client organizations and their configuration.
Part of the bounded contexts refactoring to separate concerns cleanly.

Client Business Models (apps/client_onboarding/models/):
- business_unit.py: Bt model with hierarchical structure and caching (140 lines)
- scheduling.py: Shift model for workforce management (80 lines)
- infrastructure.py: Device, Subscription, DownTimeHistory for asset management (140 lines)

Original table names preserved - no data migration required.

Related Bounded Contexts:
- apps.core_onboarding: AI/knowledge/conversation models
- apps.site_onboarding: Site audit and security survey models
- apps.people_onboarding: People enrollment models
"""

# Client Business Models
from .business_unit import Bt, bu_defaults
from .scheduling import Shift, shiftdata_json
from .infrastructure import Device, Subscription, DownTimeHistory

__all__ = [
    # Core Business Models
    'Bt',
    'bu_defaults',
    'Shift',
    'shiftdata_json',
    'Device',
    'Subscription',
    'DownTimeHistory',
]