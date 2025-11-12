"""
Search services module

Contains business logic for:
- Search aggregation across entities
- Ranking algorithm implementation
- Alert processing
- Analytics tracking
- Unified semantic search (Feature #3)
"""

from .unified_semantic_search_service import UnifiedSemanticSearchService

__all__ = [
    'SearchAggregatorService',
    'RankingService',
    'AlertService',
    'UnifiedSemanticSearchService',
]