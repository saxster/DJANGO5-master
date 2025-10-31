"""
Ticket Management Package

Contains optimized manager classes and query methods for the ticket system.
"""

from django.db import models
from .optimized_managers import OptimizedTicketManagerMixin, OptimizedTicketManager

# Backward compatibility aliases
# TicketManager and ESCManager expected by models.py
TicketManager = OptimizedTicketManager
ESCManager = models.Manager  # Base manager for EscalationMatrix

__all__ = [
    'OptimizedTicketManagerMixin',
    'OptimizedTicketManager',
    'TicketManager',
    'ESCManager'
]