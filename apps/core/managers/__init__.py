"""
Optimized Django Model Managers.

This package provides optimized managers for database query performance.
"""

from .optimized_managers import (
    BaseOptimizedManager,
    OptimizedPeopleManager,
    OptimizedJobManager,
    OptimizedAssetManager,
    OptimizedJobneedManager,
    OptimizedGroupManager,
    get_optimized_people_queryset,
    get_optimized_job_queryset,
    get_optimized_asset_queryset,
)

__all__ = [
    'BaseOptimizedManager',
    'OptimizedPeopleManager',
    'OptimizedJobManager',
    'OptimizedAssetManager',
    'OptimizedJobneedManager',
    'OptimizedGroupManager',
    'get_optimized_people_queryset',
    'get_optimized_job_queryset',
    'get_optimized_asset_queryset',
]