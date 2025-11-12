"""
Ticket Management Package

Contains optimized manager classes and query methods for the ticket system.
"""

from .optimized_managers import OptimizedTicketManagerMixin
from .base import TicketManager, ESCManager

# Backward compatibility alias for legacy imports
OptimizedTicketManager = TicketManager

# Backward compatibility for migrations
# EscalationMatrixManager was removed during refactoring - use ESCManager
EscalationMatrixManager = ESCManager

__all__ = [
    'OptimizedTicketManagerMixin',
    'TicketManager',
    'OptimizedTicketManager',
    'ESCManager',
    'EscalationMatrixManager',  # Backward compatibility
]
