"""
Global Cross-Domain Search & Insights

Enterprise-grade unified search across all entities with:
- PostgreSQL FTS (tsvector + GIN) for fast text search
- pg_trgm for fuzzy/typo tolerance
- pgvector for semantic similarity
- Permission-aware results with tenant isolation
- Smart actions for direct entity manipulation
- Saved searches with alert notifications
"""

default_app_config = 'apps.search.apps.SearchConfig'

__version__ = '1.0.0'