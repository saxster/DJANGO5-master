"""
Base Services for Scheduling Application

This module provides abstract base classes for scheduling services
to reduce code duplication and improve maintainability.

Follows Rule 8: All methods < 50 lines
Follows SRP: Each service has single responsibility
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services.transaction_manager import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    SystemException,
    EnhancedValidationException,
)
from apps.activity.models.job_model import Job, Jobneed
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class BaseSchedulingService(BaseService, ABC):
    """
    Abstract base class for all scheduling services.

    Provides common functionality for task and tour services including:
    - Standard CRUD operations
    - Error handling patterns
    - Query optimization
    - Pagination support
    """

    def __init__(self):
        """Initialize base scheduling service."""
        super().__init__()
        self.model = Job

    @abstractmethod
    def get_identifier(self):
        """Return the Job.Identifier for this service type."""
        pass

    def get_base_queryset(self, optimized=True):
        """
        Get base queryset with common optimizations.

        NOTE: Uses transitional parent query to handle both NULL and sentinel (id=1).
        - Modern: parent__isnull=True (preferred)
        - Legacy: parent_id=1 (sentinel "NONE" record)

        Args:
            optimized: Whether to apply select_related optimizations

        Returns:
            QuerySet: Base queryset for this service
        """
        from django.db.models import Q

        queryset = self.model.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling
            identifier=self.get_identifier()
        )

        if optimized:
            queryset = queryset.select_related(
                'people', 'asset', 'pgroup'
            )

        return queryset

    def get_list(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """
        Get paginated list with filters.

        Args:
            filters: Dictionary of filter parameters
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            QuerySet: Filtered and paginated results
        """
        try:
            queryset = self.get_base_queryset()

            if filters:
                queryset = self.apply_filters(queryset, filters)

            return self.paginate_queryset(queryset, page, page_size)

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, f"Error retrieving {self.get_identifier()} list"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_by_id(self, obj_id: int):
        """
        Retrieve object by ID with optimized query.

        Args:
            obj_id: Object ID

        Returns:
            Job: Job instance

        Raises:
            ValidationError: If object not found
        """
        try:
            return self.get_base_queryset().get(id=obj_id)

        except self.model.DoesNotExist:
            logger.error(f"{self.get_identifier()} {obj_id} not found")
            raise ValidationError(f"{self.get_identifier()} not found")

    def apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """
        Apply common filters to queryset.

        Args:
            queryset: Base queryset
            filters: Filter parameters

        Returns:
            QuerySet: Filtered queryset
        """
        filter_mapping = {
            'jobname': 'jobname__icontains',
            'people_id': 'people_id',
            'asset_id': 'asset_id',
            'is_active': 'is_active',
        }

        for filter_key, filter_value in filters.items():
            if filter_key in filter_mapping and filter_value is not None:
                django_filter = filter_mapping[filter_key]
                queryset = queryset.filter(**{django_filter: filter_value})

        return queryset

    def paginate_queryset(self, queryset: QuerySet, page: int, page_size: int) -> QuerySet:
        """
        Apply pagination to queryset.

        Args:
            queryset: QuerySet to paginate
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            QuerySet: Paginated slice
        """
        start = (page - 1) * page_size
        end = start + page_size
        return queryset[start:end]

    @with_transaction
    def create_job(
        self,
        form_data: Dict[str, Any],
        user,
        session,
        **kwargs
    ) -> Tuple[Job, bool]:
        """
        Create a new job with common patterns.

        Args:
            form_data: Validated form data
            user: User creating the job
            session: User session data
            **kwargs: Additional job-specific parameters

        Returns:
            Tuple of (job instance, success boolean)
        """
        logger.info(f"Creating {self.get_identifier()} [START]")

        try:
            job = self._create_job_instance(form_data, **kwargs)
            job = putils.save_userinfo(job, user, session, create=True)

            logger.info(f"{self.get_identifier()} '{job.jobname}' created successfully")
            return job, True

        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, f"{self.get_identifier()} creation validation error"
            )
            logger.warning(f"Creation validation failed - {correlation_id}")
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, f"{self.get_identifier()} creation database error"
            )
            logger.error(f"Database error creating job - {correlation_id}")
            raise

    @with_transaction
    def update_job(
        self,
        job_id: int,
        form_data: Dict[str, Any],
        user,
        session,
        **kwargs
    ) -> Tuple[Job, bool]:
        """
        Update existing job with common patterns.

        Args:
            job_id: ID of job to update
            form_data: Updated form data
            user: User updating the job
            session: User session data
            **kwargs: Additional update parameters

        Returns:
            Tuple of (updated job instance, success boolean)
        """
        logger.info(f"Updating {self.get_identifier()} ID {job_id} [START]")

        try:
            job = self.get_by_id(job_id)

            # Update job fields
            for field, value in form_data.items():
                setattr(job, field, value)

            job.save()
            job = putils.save_userinfo(job, user, session, create=False)

            # Perform any additional update operations
            self._perform_additional_updates(job, user, session, **kwargs)

            logger.info(f"{self.get_identifier()} '{job.jobname}' updated successfully")
            return job, True

        except ValidationError:
            logger.error(f"{self.get_identifier()} with ID {job_id} not found")
            raise

    def _create_job_instance(self, form_data: Dict[str, Any], **kwargs) -> Job:
        """
        Create job instance with identifier.

        Args:
            form_data: Form data for job creation
            **kwargs: Additional parameters

        Returns:
            Job: Created job instance
        """
        job = self.model(**form_data)
        job.identifier = self.get_identifier()
        job.parent = None
        job.save()
        return job

    def _perform_additional_updates(self, job: Job, user, session, **kwargs):
        """
        Override in subclasses for additional update operations.

        Args:
            job: Updated job instance
            user: User performing update
            session: User session data
            **kwargs: Additional parameters
        """
        pass


class BaseTourService(BaseSchedulingService):
    """
    Abstract base class for tour services.

    Provides common functionality for both internal and external tours.
    """

    def get_tour_with_details(self, tour_id: int):
        """
        Get tour with all related details.

        Args:
            tour_id: Tour ID

        Returns:
            Tuple of (job instance, related data)
        """
        try:
            job = self.model.objects.select_related(
                'jobneed', 'asset', 'asset__location',
                'people', 'people__shift', 'people__bt'
            ).get(id=tour_id)

            related_data = self._get_tour_related_data(job)

            return job, related_data

        except self.model.DoesNotExist:
            logger.error(f"Tour with ID {tour_id} not found")
            raise ValidationError("Tour not found")

    @abstractmethod
    def _get_tour_related_data(self, job: Job):
        """
        Get tour-specific related data.

        Args:
            job: Tour job instance

        Returns:
            Related data specific to tour type
        """
        pass


class BaseJobneedService(BaseService):
    """
    Base service for jobneed operations across different job types.
    """

    def __init__(self, job_identifier):
        """
        Initialize jobneed service for specific job type.

        Args:
            job_identifier: Job.Identifier enum value
        """
        super().__init__()
        self.model = Jobneed
        self.job_identifier = job_identifier

    def get_jobneed_list(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """
        Get paginated list of jobneeds for this job type.

        Args:
            filters: Filter parameters
            page: Page number
            page_size: Items per page

        Returns:
            QuerySet: Filtered jobneeds
        """
        try:
            queryset = self.model.objects.select_related(
                'job', 'people'
            ).filter(
                job__identifier=self.job_identifier
            )

            if filters:
                queryset = self._apply_jobneed_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, f"Error retrieving {self.job_identifier} jobneeds"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_jobneed_by_id(self, jobneed_id: int) -> Jobneed:
        """
        Retrieve specific jobneed by ID.

        Args:
            jobneed_id: Jobneed ID

        Returns:
            Jobneed: Jobneed instance

        Raises:
            ValidationError: If jobneed not found
        """
        try:
            return self.model.objects.select_related(
                'job', 'people', 'job__asset'
            ).get(id=jobneed_id)

        except self.model.DoesNotExist:
            logger.error(f"Jobneed {jobneed_id} not found")
            raise ValidationError("Jobneed not found")

    def _apply_jobneed_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """
        Apply filters to jobneed queryset.

        Args:
            queryset: Base queryset
            filters: Filter parameters

        Returns:
            QuerySet: Filtered queryset
        """
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        return queryset