"""
Core Signals Module

Provides signal handlers for automatic audit logging and other cross-cutting concerns.

Usage:
    # Import in apps.py ready() method to activate signals
    from apps.core.signals import audit_signals
"""

from .audit_signals import (
    state_transition_signal,
    attach_audit_context,
    skip_audit_for_instance,
    trigger_state_transition_audit,
)

__all__ = [
    'state_transition_signal',
    'attach_audit_context',
    'skip_audit_for_instance',
    'trigger_state_transition_audit',
]
