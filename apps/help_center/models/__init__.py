"""
Help Center Models

Refactored from god file (554 lines) on 2025-11-04.

Backward compatibility maintained - all imports work unchanged.

Models:
- HelpTag: Simple tagging for articles
- HelpCategory: Hierarchical categorization
- HelpArticle: Knowledge base articles with FTS + pgvector
- HelpSearchHistory: Search analytics tracking
- HelpArticleInteraction: User engagement metrics
- HelpTicketCorrelation: Ticket correlation for effectiveness

Following CLAUDE.md:
- Rule #7: Each model < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes
- Multi-tenant isolation via TenantAwareModel
"""

from apps.help_center.models.tag import HelpTag
from apps.help_center.models.category import HelpCategory
from apps.help_center.models.article import HelpArticle
from apps.help_center.models.search_history import HelpSearchHistory
from apps.help_center.models.interaction import HelpArticleInteraction
from apps.help_center.models.ticket_correlation import HelpTicketCorrelation

__all__ = [
    'HelpTag',
    'HelpCategory',
    'HelpArticle',
    'HelpSearchHistory',
    'HelpArticleInteraction',
    'HelpTicketCorrelation',
]
