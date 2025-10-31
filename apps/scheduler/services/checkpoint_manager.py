"""
Checkpoint Manager Service

This service handles all checkpoint-related operations for tours,
extracting common functionality from individual tour services.

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for checkpoint management
"""

import logging
from typing import Dict, Any, List, Optional

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.core.services.base_service import BaseService
from apps.core.services.transaction_manager import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import DatabaseException
from apps.activity.models.job_model import Job
import apps.scheduler.utils as sutils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class CheckpointManagerService(BaseService):
    """
    Service for managing tour checkpoints.

    Provides centralized checkpoint operations for both internal
    and external tours to reduce code duplication.
    """

    def __init__(self):
        """Initialize checkpoint manager service."""
        super().__init__()
        self.model = Job

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "CheckpointManagerService"

    @with_transaction
    def save_checkpoints_for_tour(
        self,
        checkpoints: List[List],
        tour_job: Job,
        user,
        session
    ) -> None:
        """
        Save or update checkpoints for a tour.

        Args:
            checkpoints: List of checkpoint data arrays
            tour_job: Parent tour job instance
            user: User performing the operation
            session: User session data

        Raises:
            ValidationError: If checkpoint data is invalid
            DatabaseException: If database operation fails
        """
        logger.info(f"Saving {len(checkpoints)} checkpoints for tour '{tour_job.jobname}'")

        try:
            for checkpoint_data in checkpoints:
                self._save_single_checkpoint(checkpoint_data, tour_job, user, session)

        except (ValueError, TypeError, IndexError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Data processing error saving checkpoints"
            )
            logger.error(f"Invalid checkpoint data - {correlation_id}")
            raise ValidationError(_("Invalid checkpoint data format"))
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Database error saving checkpoints"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def _save_single_checkpoint(
        self,
        checkpoint_data: List,
        tour_job: Job,
        user,
        session
    ) -> Job:
        """
        Save or update a single checkpoint.

        Args:
            checkpoint_data: Checkpoint data array
            tour_job: Parent tour job
            user: User performing operation
            session: User session data

        Returns:
            Job: Created or updated checkpoint job
        """
        # Extract checkpoint data with safe defaults
        checkpoint_fields = self._extract_checkpoint_fields(checkpoint_data)

        # Create or update checkpoint
        checkpoint, created = self.model.objects.update_or_create(
            parent_id=tour_job.id,
            asset_id=checkpoint_fields["asset_id"],
            qset_id=checkpoint_fields["qset_id"],
            defaults=sutils.job_fields(tour_job, checkpoint_data),
        )

        checkpoint.save()
        putils.save_userinfo(checkpoint, user, session, create=created)

        status = "CREATED" if created else "UPDATED"
        checkpoint_name = checkpoint_data[2] if len(checkpoint_data) > 2 else "Unknown"
        logger.info(f"Checkpoint {checkpoint_name} {status} for tour '{tour_job.jobname}'")

        return checkpoint

    def _extract_checkpoint_fields(self, checkpoint_data: List) -> Dict[str, Any]:
        """
        Extract checkpoint fields from checkpoint data array.

        Args:
            checkpoint_data: Array containing checkpoint information

        Returns:
            dict: Extracted checkpoint fields

        Raises:
            ValueError: If required data is missing
        """
        if len(checkpoint_data) < 4:
            raise ValueError("Checkpoint data must contain at least 4 elements")

        return {
            "seqno": checkpoint_data[0],
            "asset_id": checkpoint_data[1],
            "qset_id": checkpoint_data[3],
            "expirytime": checkpoint_data[5] if len(checkpoint_data) > 5 else 0,
        }

    def get_checkpoints_for_tour(self, tour_job: Job) -> QuerySet:
        """
        Retrieve checkpoints for a given tour.

        Args:
            tour_job: Tour job instance

        Returns:
            QuerySet: Checkpoints with related data
        """
        return self.model.objects.select_related(
            "parent", "asset", "qset", "pgroup", "people"
        ).filter(parent_id=tour_job.id).values(
            "seqno",
            "asset__assetname",
            "asset__id",
            "qset__qset_name",
            "qset__id",
            "expirytime",
            "id",
        )

    @with_transaction
    def delete_checkpoint(self, checkpoint_id: int, user) -> bool:
        """
        Delete a checkpoint from a tour.

        Args:
            checkpoint_id: ID of checkpoint to delete
            user: User performing deletion

        Returns:
            bool: True if successful

        Raises:
            ValidationError: If checkpoint not found
            DatabaseException: If database operation fails
        """
        try:
            checkpoint = self.model.objects.get(
                id=checkpoint_id,
                parent__isnull=False
            )

            tour_name = checkpoint.parent.jobname
            checkpoint.delete()

            logger.info(f"Checkpoint {checkpoint_id} deleted from tour '{tour_name}'")
            return True

        except self.model.DoesNotExist:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            raise ValidationError(_("Checkpoint not found"))
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error deleting checkpoint"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_checkpoint_by_id(self, checkpoint_id: int) -> Job:
        """
        Retrieve checkpoint by ID with related data.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Job: Checkpoint instance

        Raises:
            ValidationError: If checkpoint not found
        """
        try:
            return self.model.objects.select_related(
                'parent', 'asset', 'qset'
            ).get(
                id=checkpoint_id,
                parent__isnull=False
            )

        except self.model.DoesNotExist:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            raise ValidationError(_("Checkpoint not found"))

    def validate_checkpoint_data(self, checkpoints: List[List]) -> bool:
        """
        Validate checkpoint data before processing.

        Args:
            checkpoints: List of checkpoint data arrays

        Returns:
            bool: True if valid

        Raises:
            ValidationError: If validation fails
        """
        if not checkpoints:
            raise ValidationError(_("At least one checkpoint is required"))

        for i, checkpoint in enumerate(checkpoints):
            if not isinstance(checkpoint, list):
                raise ValidationError(f"Checkpoint {i} must be a list")

            if len(checkpoint) < 4:
                raise ValidationError(
                    f"Checkpoint {i} must contain at least 4 elements"
                )

            # Validate sequence number
            try:
                seqno = int(checkpoint[0])
                if seqno < 0:
                    raise ValidationError(f"Checkpoint {i} sequence number must be >= 0")
            except (ValueError, TypeError):
                raise ValidationError(f"Checkpoint {i} sequence number must be an integer")

            # Validate asset and qset IDs
            try:
                asset_id = int(checkpoint[1])
                qset_id = int(checkpoint[3])
                if asset_id <= 0 or qset_id <= 0:
                    raise ValidationError(f"Checkpoint {i} asset and qset IDs must be > 0")
            except (ValueError, TypeError):
                raise ValidationError(f"Checkpoint {i} asset and qset IDs must be integers")

        return True

    def reorder_checkpoints(
        self,
        tour_job: Job,
        checkpoint_order: List[int],
        user,
        session
    ) -> bool:
        """
        Reorder checkpoints for a tour.

        Args:
            tour_job: Tour job instance
            checkpoint_order: List of checkpoint IDs in new order
            user: User performing reorder
            session: User session data

        Returns:
            bool: True if successful

        Raises:
            ValidationError: If checkpoint order is invalid
            DatabaseException: If database operation fails
        """
        try:
            checkpoints = self.model.objects.filter(
                parent_id=tour_job.id
            ).in_bulk(checkpoint_order)

            if len(checkpoints) != len(checkpoint_order):
                raise ValidationError(_("Invalid checkpoint IDs provided"))

            # Update sequence numbers
            for new_seqno, checkpoint_id in enumerate(checkpoint_order, 1):
                checkpoint = checkpoints[checkpoint_id]
                checkpoint.seqno = new_seqno
                checkpoint.save()

                putils.save_userinfo(checkpoint, user, session, create=False)

            logger.info(f"Reordered {len(checkpoint_order)} checkpoints for tour '{tour_job.jobname}'")
            return True

        except (KeyError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error reordering checkpoints"
            )
            logger.error(f"Validation error - {correlation_id}")
            raise ValidationError(_("Invalid checkpoint order"))
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Database error reordering checkpoints"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_checkpoint_statistics(self, tour_job: Job) -> Dict[str, Any]:
        """
        Get statistics for tour checkpoints.

        Args:
            tour_job: Tour job instance

        Returns:
            dict: Checkpoint statistics
        """
        checkpoints = self.model.objects.filter(parent_id=tour_job.id)

        stats = {
            'total_checkpoints': checkpoints.count(),
            'active_checkpoints': checkpoints.filter(is_active=True).count(),
            'has_expiry_times': checkpoints.exclude(expirytime=0).count(),
            'avg_expiry_time': 0,
        }

        # Calculate average expiry time for checkpoints that have it
        expiry_checkpoints = checkpoints.exclude(expirytime=0)
        if expiry_checkpoints.exists():
            total_expiry = sum(cp.expirytime for cp in expiry_checkpoints)
            stats['avg_expiry_time'] = total_expiry / expiry_checkpoints.count()

        return stats