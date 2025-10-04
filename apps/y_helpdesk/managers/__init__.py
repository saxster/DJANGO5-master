"""
Ticket Management Package

Contains optimized manager classes and query methods for the ticket system.
"""

from .optimized_managers import OptimizedTicketManagerMixin, OptimizedTicketManager

__all__ = [
    'OptimizedTicketManagerMixin',
    'OptimizedTicketManager'
]