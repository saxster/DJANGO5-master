"""
Search Tasks Package

Celery tasks for search indexing and maintenance.
"""

from .indexing_tasks import (
    search_index_tickets,
    search_index_work_orders,
    search_index_assets,
    search_index_people,
    search_rebuild_unified_index,
    search_incremental_index_update,
)

__all__ = [
    'search_index_tickets',
    'search_index_work_orders',
    'search_index_assets',
    'search_index_people',
    'search_rebuild_unified_index',
    'search_incremental_index_update',
]
