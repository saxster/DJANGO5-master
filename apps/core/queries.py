"""
Django ORM-based queries - backward compatibility shim.

This module maintains backward compatibility with existing imports while
delegating to the new modular query implementation in apps/core/queries/.

The original monolithic file (2,202 lines) has been refactored into:
    - apps/core/queries/base.py (shared utilities)
    - apps/core/queries/capability_queries.py
    - apps/core/queries/asset_queries.py
    - apps/core/queries/job_queries.py
    - apps/core/queries/ticket_queries.py
    - apps/core/queries/report_queries/ (domain-specific reports)

This refactoring follows .claude/rules.md requirements:
    - Each file < 200 lines
    - Single Responsibility Principle
    - Domain-driven organization
    - Improved maintainability

For new code, import directly from the queries package:
    from apps.core.queries import QueryRepository, ReportQueryRepository

Original file backed up as: queries_original_2202lines.py
"""

from apps.core.queries.base import TreeTraversal, AttachmentHelper
from apps.core.queries import (
    QueryRepository,
    ReportQueryRepository,
    get_query,
)

__all__ = [
    'TreeTraversal',
    'AttachmentHelper',
    'QueryRepository',
    'ReportQueryRepository',
    'get_query',
]