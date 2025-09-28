"""
Optimized Django Model Managers for Query Performance.

This module provides optimized managers that automatically apply select_related
and prefetch_related to eliminate N+1 query problems.

Usage:
    from apps.core.managers.optimized_managers import OptimizedJobManager

    class Job(models.Model):
        objects = OptimizedJobManager()
        # ... model fields
"""

import logging
from django.db import models
from django.db.models import QuerySet, Prefetch
from typing import Optional, Dict, Any, List
from apps.core.services.query_optimization_service import QueryOptimizer

logger = logging.getLogger('optimized_managers')


class BaseOptimizedManager(models.Manager):
    """
    Base manager class that provides optimized queryset methods.
    """

    def get_optimized_queryset(self) -> QuerySet:
        """
        Get a queryset with automatic optimization applied.

        Returns:
            QuerySet: Optimized queryset for this model
        """
        queryset = self.get_queryset()
        return QueryOptimizer.optimize_queryset(queryset, profile='default')

    def get_minimal_queryset(self) -> QuerySet:
        """
        Get a queryset with minimal optimization (only critical relationships).

        Returns:
            QuerySet: Minimally optimized queryset
        """
        queryset = self.get_queryset()
        return QueryOptimizer.optimize_queryset(queryset, profile='minimal')

    def get_aggressive_queryset(self) -> QuerySet:
        """
        Get a queryset with aggressive optimization (all relationships).

        Returns:
            QuerySet: Aggressively optimized queryset
        """
        queryset = self.get_queryset()
        return QueryOptimizer.optimize_queryset(queryset, profile='aggressive')

    def optimized_all(self) -> QuerySet:
        """
        Optimized version of all() method.

        Returns:
            QuerySet: All objects with optimization
        """
        return self.get_optimized_queryset()

    def optimized_filter(self, **kwargs) -> QuerySet:
        """
        Optimized version of filter() method.

        Args:
            **kwargs: Filter parameters

        Returns:
            QuerySet: Filtered objects with optimization
        """
        return self.get_optimized_queryset().filter(**kwargs)

    def optimized_get(self, **kwargs):
        """
        Optimized version of get() method.

        Args:
            **kwargs: Lookup parameters

        Returns:
            Model instance with optimized relationships
        """
        return self.get_optimized_queryset().get(**kwargs)

    def with_bulk_optimizations(self, ids: List[int]) -> QuerySet:
        """
        Get multiple objects with bulk optimizations.

        Args:
            ids: List of object IDs to fetch

        Returns:
            QuerySet: Bulk optimized queryset
        """
        return self.get_optimized_queryset().filter(id__in=ids)


class OptimizedPeopleManager(BaseOptimizedManager):
    """
    Optimized manager for People model with specific relationships.
    """

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with People-specific optimizations.

        Returns:
            QuerySet: Base optimized queryset for People
        """
        return super().get_queryset().select_related(
            'shift',
            'bt',
            'user'
        ).prefetch_related(
            'pgbelongs_peoples__pgroup',
            'groups'
        )

    def with_full_profile(self) -> QuerySet:
        """
        Get People queryset with all profile relationships loaded.

        Returns:
            QuerySet: People with complete profile data
        """
        return self.get_queryset().prefetch_related(
            'user_permissions',
            'people_attachments',
            'assigned_jobs',
            'created_assets'
        )

    def active_people(self) -> QuerySet:
        """
        Get only active people with optimizations.

        Returns:
            QuerySet: Active people with optimization
        """
        return self.get_queryset().filter(is_active=True)

    def by_business_unit(self, bt_id: int) -> QuerySet:
        """
        Get people by business unit with optimizations.

        Args:
            bt_id: Business unit ID

        Returns:
            QuerySet: People in the business unit
        """
        return self.get_queryset().filter(bt_id=bt_id)

    def with_shifts(self) -> QuerySet:
        """
        Get people with shift information optimized.

        Returns:
            QuerySet: People with shift data
        """
        return self.get_queryset().select_related('shift__geofences')


class OptimizedJobManager(BaseOptimizedManager):
    """
    Optimized manager for Job model with specific relationships.
    """

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with Job-specific optimizations.

        Returns:
            QuerySet: Base optimized queryset for Job
        """
        return super().get_queryset().select_related(
            'jobneed',
            'asset',
            'asset__location',
            'people',
            'people__shift',
            'people__bt'
        )

    def with_full_details(self) -> QuerySet:
        """
        Get Jobs with all related details loaded.

        Returns:
            QuerySet: Jobs with complete details
        """
        return self.get_queryset().prefetch_related(
            'job_attachments',
            'job_questions',
            'child_jobs',
            'job_logs'
        )

    def active_jobs(self) -> QuerySet:
        """
        Get active/pending jobs with optimizations.

        Returns:
            QuerySet: Active jobs
        """
        return self.get_queryset().filter(status__in=['pending', 'in_progress'])

    def completed_jobs(self) -> QuerySet:
        """
        Get completed jobs with optimizations.

        Returns:
            QuerySet: Completed jobs
        """
        return self.get_queryset().filter(status='completed')

    def by_asset(self, asset_id: int) -> QuerySet:
        """
        Get jobs for a specific asset.

        Args:
            asset_id: Asset ID

        Returns:
            QuerySet: Jobs for the asset
        """
        return self.get_queryset().filter(asset_id=asset_id)

    def by_people(self, people_id: int) -> QuerySet:
        """
        Get jobs assigned to a specific person.

        Args:
            people_id: People ID

        Returns:
            QuerySet: Jobs assigned to the person
        """
        return self.get_queryset().filter(people_id=people_id)

    def tour_jobs(self) -> QuerySet:
        """
        Get tour-related jobs with checkpoint data.

        Returns:
            QuerySet: Tour jobs with checkpoint information
        """
        return self.get_queryset().prefetch_related(
            'child_jobs__asset__location',
            'tour_checkpoints'
        )


class OptimizedAssetManager(BaseOptimizedManager):
    """
    Optimized manager for Asset model with specific relationships.
    """

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with Asset-specific optimizations.

        Returns:
            QuerySet: Base optimized queryset for Asset
        """
        return super().get_queryset().select_related(
            'location',
            'created_by',
            'asset_type'
        )

    def with_maintenance_history(self) -> QuerySet:
        """
        Get assets with maintenance history loaded.

        Returns:
            QuerySet: Assets with maintenance data
        """
        return self.get_queryset().prefetch_related(
            'asset_jobs',
            'asset_attachments',
            'maintenance_logs'
        )

    def active_assets(self) -> QuerySet:
        """
        Get only active assets.

        Returns:
            QuerySet: Active assets
        """
        return self.get_queryset().filter(is_active=True)

    def by_location(self, location_id: int) -> QuerySet:
        """
        Get assets by location.

        Args:
            location_id: Location ID

        Returns:
            QuerySet: Assets in the location
        """
        return self.get_queryset().filter(location_id=location_id)

    def with_current_jobs(self) -> QuerySet:
        """
        Get assets with their current active jobs.

        Returns:
            QuerySet: Assets with current jobs
        """
        return self.get_queryset().prefetch_related(
            Prefetch(
                'asset_jobs',
                queryset=OptimizedJobManager().active_jobs(),
                to_attr='current_jobs'
            )
        )


class OptimizedJobneedManager(BaseOptimizedManager):
    """
    Optimized manager for Jobneed model.
    """

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with Jobneed-specific optimizations.

        Returns:
            QuerySet: Base optimized queryset for Jobneed
        """
        return super().get_queryset().select_related(
            'job',
            'performedby',
            'created_by'
        )

    def with_job_details(self) -> QuerySet:
        """
        Get jobneeds with full job details.

        Returns:
            QuerySet: Jobneeds with job information
        """
        return self.get_queryset().select_related(
            'job__asset',
            'job__asset__location',
            'job__people'
        )

    def pending_jobneeds(self) -> QuerySet:
        """
        Get pending jobneeds.

        Returns:
            QuerySet: Pending jobneeds
        """
        return self.get_queryset().filter(jobstatus='pending')

    def completed_jobneeds(self) -> QuerySet:
        """
        Get completed jobneeds.

        Returns:
            QuerySet: Completed jobneeds
        """
        return self.get_queryset().filter(jobstatus='completed')


class OptimizedGroupManager(BaseOptimizedManager):
    """
    Optimized manager for Pgroup model.
    """

    def get_queryset(self) -> QuerySet:
        """
        Get base queryset with Group-specific optimizations.

        Returns:
            QuerySet: Base optimized queryset for Groups
        """
        return super().get_queryset().prefetch_related(
            'group_members__people'
        )

    def with_member_details(self) -> QuerySet:
        """
        Get groups with full member details.

        Returns:
            QuerySet: Groups with member information
        """
        return self.get_queryset().prefetch_related(
            'group_members__people__shift',
            'group_members__people__bt'
        )

    def active_groups(self) -> QuerySet:
        """
        Get only active groups.

        Returns:
            QuerySet: Active groups
        """
        return self.get_queryset().filter(is_active=True)


# Convenience functions for backward compatibility
def get_optimized_people_queryset() -> QuerySet:
    """Get optimized People queryset."""
    from apps.peoples.models import People
    return People.objects.select_related('shift', 'bt').prefetch_related('groups')


def get_optimized_job_queryset() -> QuerySet:
    """Get optimized Job queryset."""
    from apps.activity.models.job_model import Job
    return Job.objects.select_related('jobneed', 'asset', 'people')


def get_optimized_asset_queryset() -> QuerySet:
    """Get optimized Asset queryset."""
    from apps.activity.models.asset_model import Asset
    return Asset.objects.select_related('location', 'created_by')


# Export all manager classes
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