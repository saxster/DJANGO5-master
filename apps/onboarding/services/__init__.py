"""
Onboarding Services Package

Business logic services extracted from models and views.

Following CLAUDE.md Rule #7: Keep models lean (<150 lines),
complex business logic belongs in service classes.
"""

from .knowledge_review_service import KnowledgeReviewService

__all__ = [
    'KnowledgeReviewService',
]
