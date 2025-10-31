"""
Internal Tour Service

Handles all business logic for internal tour scheduling including:
- Tour creation and updates
- Checkpoint management
- Tour retrieval and filtering
- Schedule validation

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for internal tours
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.db.models import QuerySet, Q

from apps.core.services.base_service import BaseService
from apps.core.services.transaction_manager import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    SystemException,
    EnhancedValidationException,
    BusinessLogicException
)
from apps.core.utils_new.db_utils import get_current_db_name
from apps.activity.models.job_model import Job, Jobneed
import apps.scheduler.utils as sutils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class InternalTourService(BaseService):
    """Service for internal tour business logic."""

    def __init__(self):
        super().__init__()
        self.model = Job

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "InternalTourService"

    @with_transaction
    def create_tour_with_checkpoints(
        self,
        form_data: Dict[str, Any],
        checkpoints: List[List],
        user,
        session
    ) -> Tuple[Job, bool]:
        """
        Create internal tour with associated checkpoints.

        Args:
            form_data: Validated form data for job creation
            checkpoints: List of checkpoint data [[seqno, asset_id, name, qset_id, ...]]
            user: User creating the tour
            session: User session data

        Returns:
            Tuple of (job instance, success boolean)

        Raises:
            ValidationError: If data validation fails
            IntegrityError: If database constraints violated
            SchedulingException: If scheduling logic fails
        """
        logger.info("Creating internal tour with checkpoints [START]")

        try:
            job = self._create_tour_job(form_data)
            job = putils.save_userinfo(job, user, session, create=True)
            self._save_checkpoints_for_tour(checkpoints, job, user, session)

            logger.info(f"Internal tour '{job.jobname}' created successfully")
            return job, True

        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Internal tour creation validation error"
            )
            logger.warning(f"Tour creation validation failed - {correlation_id}")
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Internal tour creation database error"
            )
            logger.error(f"Database error creating tour - {correlation_id}")
            raise
        except SchedulingException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Internal tour scheduling error"
            )
            logger.warning(f"Scheduling error - {correlation_id}")
            raise
        finally:
            logger.info("Creating internal tour with checkpoints [END]")

    @with_transaction
    def update_tour_with_checkpoints(
        self,
        tour_id: int,
        form_data: Dict[str, Any],
        checkpoints: List[List],
        user,
        session
    ) -> Tuple[Job, bool]:
        """
        Update existing internal tour and its checkpoints.

        Args:
            tour_id: ID of tour to update
            form_data: Updated form data
            checkpoints: Updated checkpoint data
            user: User updating the tour
            session: User session data

        Returns:
            Tuple of (updated job instance, success boolean)
        """
        logger.info(f"Updating internal tour ID {tour_id} [START]")

        try:
            job = self.model.objects.get(id=tour_id)

            for field, value in form_data.items():
                setattr(job, field, value)

            job.save()
            job = putils.save_userinfo(job, user, session, create=False)

            self._save_checkpoints_for_tour(checkpoints, job, user, session)

            logger.info(f"Internal tour '{job.jobname}' updated successfully")
            return job, True

        except self.model.DoesNotExist:
            logger.error(f"Tour with ID {tour_id} not found")
            raise ValidationError(f"Tour not found")
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Internal tour update validation error"
            )
            logger.warning(f"Tour update validation failed - {correlation_id}")
            raise
        finally:
            logger.info(f"Updating internal tour ID {tour_id} [END]")

    def get_tour_with_checkpoints(self, tour_id: int) -> Tuple[Job, QuerySet]:
        """
        Retrieve tour with its associated checkpoints.

        Args:
            tour_id: ID of tour to retrieve

        Returns:
            Tuple of (job instance, checkpoints queryset)
        """
        try:
            job = self.model.objects.select_related(
                'jobneed', 'asset', 'asset__location',
                'people', 'people__shift', 'people__bt'
            ).get(id=tour_id)

            checkpoints = self._get_checkpoints(job)

            return job, checkpoints

        except self.model.DoesNotExist:
            logger.error(f"Tour with ID {tour_id} not found")
            raise ValidationError(f"Tour not found")
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error retrieving tour with checkpoints"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_tours_list(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """
        Get paginated list of internal tours with filters.

        Args:
            filters: Dictionary of filter parameters
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            QuerySet of Job instances
        """
        try:
            queryset = self.model.objects.select_related(
                'people', 'asset', 'pgroup'
            ).filter(
                Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling (must be first)
                identifier=Job.Identifier.INTERNALTOUR
            )

            if filters:
                queryset = self._apply_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error retrieving tours list"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def _create_tour_job(self, form_data: Dict[str, Any]) -> Job:
        """Create base tour job instance."""
        job = self.model(**form_data)
        job.parent = None
        job.asset = None
        job.qset_id = -1
        job.save()
        return job

    def _save_checkpoints_for_tour(
        self,
        checkpoints: List[List],
        job: Job,
        user,
        session
    ) -> None:
        """
        Save/update checkpoints for a tour.

        Args:
            checkpoints: List of checkpoint data
            job: Parent job instance
            user: User performing the operation
            session: User session data
        """
        logger.info(f"Saving {len(checkpoints)} checkpoints for tour '{job.jobname}'")

        try:
            for cp in checkpoints:
                checkpoint_data = {
                    "expirytime": cp[5] if len(cp) > 5 else 0,
                    "asset_id": cp[1],
                    "qset_id": cp[3],
                    "seqno": cp[0],
                }

                checkpoint, created = self.model.objects.update_or_create(
                    parent_id=job.id,
                    asset_id=checkpoint_data["asset_id"],
                    qset_id=checkpoint_data["qset_id"],
                    defaults=sutils.job_fields(job, cp),
                )

                checkpoint.save()
                putils.save_userinfo(checkpoint, user, session, create=created)

                status = "CREATED" if created else "UPDATED"
                logger.info(f"Checkpoint {cp[2]} {status} for tour '{job.jobname}'")

        except (ValueError, TypeError, IndexError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Data processing error saving checkpoints"
            )
            logger.error(f"Invalid checkpoint data - {correlation_id}")
            raise ValidationError("Invalid checkpoint data format")
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Database error saving checkpoints"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def _get_checkpoints(self, job: Job) -> QuerySet:
        """Retrieve checkpoints for a given tour."""
        return self.model.objects.select_related(
            "parent", "asset", "qset", "pgroup", "people"
        ).filter(parent_id=job.id).values(
            "seqno",
            "asset__assetname",
            "asset__id",
            "qset__qset_name",
            "qset__id",
            "expirytime",
            "id",
        )

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to tours queryset."""
        if 'jobname' in filters:
            queryset = queryset.filter(jobname__icontains=filters['jobname'])
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        return queryset

    def delete_checkpoint(self, checkpoint_id: int, user) -> bool:
        """
        Delete a checkpoint from a tour.

        Args:
            checkpoint_id: ID of checkpoint to delete
            user: User performing deletion

        Returns:
            True if successful
        """
        try:
            checkpoint = self.model.objects.get(id=checkpoint_id, parent__isnull=False)

            tour_name = checkpoint.parent.jobname
            checkpoint.delete()

            logger.info(f"Checkpoint {checkpoint_id} deleted from tour '{tour_name}'")
            return True

        except self.model.DoesNotExist:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            raise ValidationError("Checkpoint not found")
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error deleting checkpoint"
            )
            logger.error(f"Database error - {correlation_id}")
            raise


class InternalTourJobneedService(BaseService):
    """Service for internal tour jobneed operations."""

    def __init__(self):
        super().__init__()
        self.model = Jobneed

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "InternalTourJobneedService"

    def get_jobneed_list(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """Get paginated list of internal tour jobneeds."""
        try:
            queryset = self.model.objects.select_related(
                'job', 'people'
            ).filter(
                job__identifier=Job.Identifier.INTERNALTOUR
            )

            if filters:
                queryset = self._apply_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error retrieving jobneed list"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_jobneed_by_id(self, jobneed_id: int) -> Jobneed:
        """Retrieve specific jobneed by ID."""
        try:
            return self.model.objects.select_related(
                'job', 'people', 'job__asset'
            ).get(id=jobneed_id)

        except self.model.DoesNotExist:
            logger.error(f"Jobneed {jobneed_id} not found")
            raise ValidationError("Jobneed not found")

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to jobneed queryset."""
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        return queryset