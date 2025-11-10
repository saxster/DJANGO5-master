"""
Ticket Management Package

Contains optimized manager classes and query methods for the ticket system.
"""

from django.db import models
from .optimized_managers import OptimizedTicketManagerMixin, OptimizedTicketManager
from apps.tenants.managers import TenantAwareManager

# Backward compatibility aliases
# TicketManager and ESCManager expected by models.py
TicketManager = OptimizedTicketManager


class EscalationMatrixManager(TenantAwareManager):
    """Tenant-aware manager for escalation matrices."""
    use_in_migrations = True


ESCManager = EscalationMatrixManager

__all__ = [
    'OptimizedTicketManagerMixin',
    'OptimizedTicketManager',
    'TicketManager',
    'ESCManager'
]
