"""
Performance optimization utilities module.

Provides N+1 query detection and Django ORM optimization suggestions.
"""

from .n_plus_one import (
    NPlusOneDetector,
    QueryPattern,
    detect_n_plus_one,
    QueryAnalyzer,
)
from .query_optimizer import (
    QueryOptimizer,
    suggest_optimizations,
)

__all__ = [
    'NPlusOneDetector',
    'QueryPattern',
    'detect_n_plus_one',
    'QueryAnalyzer',
    'QueryOptimizer',
    'suggest_optimizations',
]
