"""
Scheduling Service

Extracts scheduling business logic from views including:
- Tour creation and management
- Checkpoint assignment and validation
- Schedule conflict resolution
- Resource allocation
- Guard tour orchestration
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, time, timedelta, date
from decimal import Decimal

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, DatabaseError, OperationalError
from django.http import QueryDict

from apps.core.services import BaseService, with_transaction, transaction_manager
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    SystemException,
    EnhancedValidationException,
    BusinessLogicException
)
from apps.core.utils_new.db_utils import get_current_db_name
from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
import apps.schedhuler.utils as sutils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    """Checkpoint data structure."""
    seqno: int
    asset_id: int
    checkpoint_name: str
    qset_id: int
    location: Optional[str] = None
    expiry_time: Optional[int] = None


@dataclass
class TourConfiguration:
    """Tour configuration data structure."""
    job_name: str
    start_time: time
    end_time: time
    expiry_time: int
    identifier: str
    priority: str
    scan_type: str
    grace_time: int
    from_date: datetime
    upto_date: datetime
    checkpoints: List[CheckpointData]
    parent_job: Optional[Job] = None
    asset: Optional[Asset] = None


@dataclass
class SchedulingResult:
    """Scheduling operation result."""
    success: bool
    job: Optional[Job] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    checkpoints_created: int = 0
    checkpoints_updated: int = 0


class SchedulingService(BaseService):
    """
    Service for handling scheduling business logic.

    Extracted from schedhuler/views.py to separate concerns and improve testability.
    """

    def __init__(self):
        super().__init__()
        self.default_tour_config = {
            "start_time": time(0, 0, 0),
            "end_time": time(0, 0, 0),
            "expiry_time": 0,
            "identifier": Job.Identifier.INTERNALTOUR,
            "priority": Job.Priority.LOW,
            "scan_type": Job.Scantype.QR,
            "grace_time": 5,
            "from_date": datetime.combine(date.today(), time(0, 0, 0)),
            "upto_date": datetime.combine(date.today(), time(23, 0, 0)) + timedelta(days=2)
        }

    @BaseService.monitor_performance("create_guard_tour")
    def create_guard_tour(
        self,
        tour_config: TourConfiguration,
        user,
        session: Dict[str, Any],
        update_existing: bool = False,
        existing_job_id: Optional[int] = None
    ) -> SchedulingResult:
        """
        Create or update a guard tour with checkpoints.

        Args:
            tour_config: Tour configuration data
            user: User creating the tour
            session: User session data
            update_existing: Whether this is an update operation
            existing_job_id: ID of existing job to update

        Returns:
            SchedulingResult with operation status
        """
        saga_id = f"guard_tour_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Create saga for distributed tour creation
            transaction_manager.create_saga(saga_id)

            # Step 1: Validate tour configuration
            transaction_manager.add_saga_step(
                saga_id,
                "validate_tour_config",
                lambda: self._validate_tour_configuration(tour_config),
                lambda result: self._log_validation_rollback(result)
            )

            # Step 2: Create or update job
            if update_existing and existing_job_id:
                transaction_manager.add_saga_step(
                    saga_id,
                    "update_job",
                    lambda: self._update_tour_job(existing_job_id, tour_config, user, session),
                    lambda job: self._rollback_job_update(job, existing_job_id)
                )
            else:
                transaction_manager.add_saga_step(
                    saga_id,
                    "create_job",
                    lambda: self._create_tour_job(tour_config, user, session),
                    lambda job: self._rollback_job_creation(job)
                )

            # Step 3: Save checkpoints
            transaction_manager.add_saga_step(
                saga_id,
                "save_checkpoints",
                lambda: self._save_tour_checkpoints(tour_config.checkpoints, saga_id, user, session),
                lambda result: self._rollback_checkpoints(result)
            )

            # Execute the saga
            saga_result = transaction_manager.execute_saga(saga_id)

            if saga_result['status'] == 'committed':
                job = saga_result['results']['create_job'] if not update_existing else saga_result['results']['update_job']
                checkpoint_result = saga_result['results']['save_checkpoints']

                self.logger.info(f"Guard tour {'updated' if update_existing else 'created'} successfully: {job.jobname}")

                return SchedulingResult(
                    success=True,
                    job=job,
                    message=f"Guard tour {'updated' if update_existing else 'created'} successfully",
                    checkpoints_created=checkpoint_result.get('created', 0),
                    checkpoints_updated=checkpoint_result.get('updated', 0)
                )
            else:
                return SchedulingResult(
                    success=False,
                    error_message=saga_result.get('error', 'Tour creation failed'),
                    correlation_id=saga_result.get('correlation_id')
                )

        except (ValidationError, ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'create_guard_tour',
                    'tour_name': tour_config.job_name,
                    'checkpoint_count': len(tour_config.checkpoints),
                    'error_type': 'validation'
                },
                level='warning'
            )
            return SchedulingResult(
                success=False,
                error_message=f"Invalid tour configuration: {str(e)}",
                correlation_id=correlation_id
            )
        except (DatabaseException, OperationalError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'create_guard_tour',
                    'tour_name': tour_config.job_name,
                    'error_type': 'database'
                },
                level='error'
            )
            return SchedulingResult(
                success=False,
                error_message="Database service unavailable, please try again",
                correlation_id=correlation_id
            )
        except SchedulingException as e:
            # Already a scheduling exception, just pass through with correlation ID
            correlation_id = getattr(e, 'correlation_id', ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_guard_tour', 'tour_name': tour_config.job_name},
                level='error'
            ))
            return SchedulingResult(
                success=False,
                error_message=str(e),
                correlation_id=correlation_id
            )

    def _validate_tour_configuration(self, tour_config: TourConfiguration) -> Dict[str, Any]:
        """
        Validate tour configuration for business rules.

        Args:
            tour_config: Tour configuration to validate

        Returns:
            Validation result
        """
        validation_rules = {
            'valid_date_range': lambda config: config.from_date < config.upto_date,
            'valid_time_range': lambda config: config.start_time < config.end_time or config.start_time == config.end_time,
            'has_checkpoints': lambda config: len(config.checkpoints) > 0,
            'valid_expiry_time': lambda config: config.expiry_time >= 0,
            'valid_grace_time': lambda config: config.grace_time >= 0,
            'unique_checkpoint_sequence': lambda config: len(set(cp.seqno for cp in config.checkpoints)) == len(config.checkpoints)
        }

        self.validate_business_rules(tour_config.__dict__, validation_rules)

        return {'validation': 'passed', 'tour_name': tour_config.job_name}

    @with_transaction()
    def _create_tour_job(
        self,
        tour_config: TourConfiguration,
        user,
        session: Dict[str, Any]
    ) -> Job:
        """
        Create a new tour job.

        Args:
            tour_config: Tour configuration
            user: User creating the job
            session: User session data

        Returns:
            Created Job instance
        """
        try:
            job = Job(
                jobname=tour_config.job_name,
                starttime=tour_config.start_time,
                endtime=tour_config.end_time,
                expirytime=tour_config.expiry_time,
                identifier=tour_config.identifier,
                priority=tour_config.priority,
                scantype=tour_config.scan_type,
                gracetime=tour_config.grace_time,
                fromdate=tour_config.from_date,
                uptodate=tour_config.upto_date,
                parent=tour_config.parent_job,
                asset=tour_config.asset,
                qset_id=-1  # Keep existing qset logic
            )

            job.save()
            job = putils.save_userinfo(job, user, session, create=True)

            self.logger.info(f"Created tour job: {job.jobname} (ID: {job.id})")
            return job

        except IntegrityError as e:
            self.logger.error(f"Database integrity error creating tour job: {str(e)}")
            raise DatabaseException(
                "Tour job creation failed due to data integrity constraints",
                original_exception=e
            ) from e

        except (ValidationError, ValueError) as e:
            self.logger.error(f"Validation error creating tour job: {str(e)}")
            raise SchedulingException(
                f"Invalid tour data: {str(e)}"
            ) from e
        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error creating tour job: {str(e)}", exc_info=True)
            raise DatabaseException(
                "Failed to create tour job due to database error",
                original_exception=e
            ) from e

    @with_transaction()
    def _update_tour_job(
        self,
        job_id: int,
        tour_config: TourConfiguration,
        user,
        session: Dict[str, Any]
    ) -> Job:
        """
        Update an existing tour job.

        Args:
            job_id: ID of job to update
            tour_config: New tour configuration
            user: User updating the job
            session: User session data

        Returns:
            Updated Job instance
        """
        try:
            job = Job.objects.get(id=job_id)

            # Update job fields
            job.jobname = tour_config.job_name
            job.starttime = tour_config.start_time
            job.endtime = tour_config.end_time
            job.expirytime = tour_config.expiry_time
            job.gracetime = tour_config.grace_time
            job.fromdate = tour_config.from_date
            job.uptodate = tour_config.upto_date

            job.save()
            job = putils.save_userinfo(job, user, session, create=False)

            self.logger.info(f"Updated tour job: {job.jobname} (ID: {job.id})")
            return job

        except Job.DoesNotExist:
            raise SchedulingException(f"Tour job with ID {job_id} not found")

        except (ValidationError, ValueError) as e:
            self.logger.error(f"Validation error updating tour job {job_id}: {str(e)}")
            raise SchedulingException(
                f"Invalid tour update data: {str(e)}"
            ) from e
        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error updating tour job {job_id}: {str(e)}", exc_info=True)
            raise DatabaseException(
                "Failed to update tour job due to database error",
                original_exception=e
            ) from e

    @with_transaction()
    def _save_tour_checkpoints(
        self,
        checkpoints: List[CheckpointData],
        saga_id: str,
        user,
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save tour checkpoints with comprehensive error handling.

        Args:
            checkpoints: List of checkpoint data
            saga_id: Saga identifier for context
            user: User saving checkpoints
            session: User session data

        Returns:
            Dictionary with creation/update counts
        """
        created_count = 0
        updated_count = 0
        saved_checkpoints = []

        try:
            # Get the job from saga context (this is a simplified approach)
            job = self._get_job_from_saga_context(saga_id)

            self.logger.info(f"Saving {len(checkpoints)} checkpoints for job {job.jobname}")

            for checkpoint_data in checkpoints:
                try:
                    # Prepare checkpoint fields
                    checkpoint_fields = {
                        'expirytime': checkpoint_data.expiry_time,
                        'asset_id': checkpoint_data.asset_id,
                        'qset_id': checkpoint_data.qset_id,
                        'seqno': checkpoint_data.seqno,
                    }

                    # Create or update checkpoint
                    checkpoint, created = Job.objects.update_or_create(
                        parent_id=job.id,
                        asset_id=checkpoint_data.asset_id,
                        qset_id=checkpoint_data.qset_id,
                        defaults=self._build_checkpoint_fields(job, checkpoint_data)
                    )

                    checkpoint.save()
                    saved_checkpoints.append(checkpoint)

                    if created:
                        created_count += 1
                        status = "CREATED"
                    else:
                        updated_count += 1
                        status = "UPDATED"

                    self.logger.info(
                        f"Checkpoint {checkpoint_data.checkpoint_name} {status} "
                        f"for job {job.jobname} with expiry time {checkpoint_data.expiry_time}"
                    )

                except (ValidationError, ValueError) as checkpoint_error:
                    self.logger.error(
                        f"Validation error saving checkpoint {checkpoint_data.checkpoint_name}: {str(checkpoint_error)}"
                    )
                    raise SchedulingException(
                        f"Invalid checkpoint data: {checkpoint_data.checkpoint_name} - {str(checkpoint_error)}"
                    ) from checkpoint_error
                except (IntegrityError, DatabaseError) as checkpoint_error:
                    self.logger.error(
                        f"Database error saving checkpoint {checkpoint_data.checkpoint_name}: {str(checkpoint_error)}",
                        exc_info=True
                    )
                    raise DatabaseException(
                        f"Failed to save checkpoint: {checkpoint_data.checkpoint_name}",
                        original_exception=checkpoint_error
                    ) from checkpoint_error

            self.logger.info(f"Checkpoints saved successfully: {created_count} created, {updated_count} updated")

            return {
                'created': created_count,
                'updated': updated_count,
                'checkpoints': saved_checkpoints,
                'job_id': job.id
            }

        except (ValidationError, ValueError, TypeError) as e:
            self.logger.error(f"Validation error saving tour checkpoints: {str(e)}")
            raise SchedulingException(
                f"Invalid checkpoint data: {str(e)}"
            ) from e
        except (DatabaseError, OperationalError, IntegrityError) as e:
            self.logger.error(f"Database error saving tour checkpoints: {str(e)}", exc_info=True)
            raise DatabaseException(
                "Failed to save checkpoints due to database error",
                original_exception=e
            ) from e

    def _build_checkpoint_fields(self, job: Job, checkpoint_data: CheckpointData) -> Dict[str, Any]:
        """
        Build checkpoint fields using utility function.

        Args:
            job: Parent job
            checkpoint_data: Checkpoint data

        Returns:
            Dictionary of checkpoint fields
        """
        # Convert checkpoint data to the format expected by sutils.job_fields
        checkpoint_tuple = (
            checkpoint_data.seqno,
            checkpoint_data.asset_id,
            checkpoint_data.checkpoint_name,
            checkpoint_data.qset_id,
            checkpoint_data.location,
            checkpoint_data.expiry_time
        )

        return sutils.job_fields(job, checkpoint_tuple)

    def _get_job_from_saga_context(self, saga_id: str) -> Job:
        """
        Get job from saga context (simplified implementation).

        Args:
            saga_id: Saga identifier

        Returns:
            Job instance
        """
        # This is a simplified implementation
        # In practice, this would retrieve the job from the saga context
        # For now, we'll need to pass the job explicitly or use a different approach

        # Placeholder implementation - in real scenario, we'd get this from saga results
        # or pass it as a parameter
        raise NotImplementedError("Job retrieval from saga context needs implementation")

    def _log_validation_rollback(self, result: Dict[str, Any]) -> None:
        """Log validation rollback."""
        self.logger.info(f"Validation rollback for tour: {result.get('tour_name', 'unknown')}")

    def _rollback_job_creation(self, job: Job) -> None:
        """Rollback job creation."""
        try:
            job.delete()
            self.logger.info(f"Rolled back job creation: {job.jobname}")
        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error during job rollback: {str(e)}", exc_info=True)
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Job rollback data error: {str(e)}")

    def _rollback_job_update(self, job: Job, original_job_id: int) -> None:
        """Rollback job update."""
        self.logger.info(f"Job update rollback for ID: {original_job_id}")

    def _rollback_checkpoints(self, result: Dict[str, Any]) -> None:
        """Rollback checkpoint creation."""
        try:
            checkpoints = result.get('checkpoints', [])
            for checkpoint in checkpoints:
                checkpoint.delete()
            self.logger.info(f"Rolled back {len(checkpoints)} checkpoints")
        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error during checkpoint rollback: {str(e)}", exc_info=True)
        except (TypeError, AttributeError, KeyError) as e:
            self.logger.error(f"Checkpoint rollback data error: {str(e)}")

    @BaseService.monitor_performance("validate_schedule_conflicts")
    def validate_schedule_conflicts(
        self,
        job: Job,
        proposed_time_range: Tuple[datetime, datetime]
    ) -> List[Dict[str, Any]]:
        """
        Validate schedule conflicts for a job.

        Args:
            job: Job to check conflicts for
            proposed_time_range: Tuple of (start_time, end_time)

        Returns:
            List of conflicts found
        """
        try:
            start_time, end_time = proposed_time_range
            conflicts = []

            # Check for overlapping jobs
            overlapping_jobs = Job.objects.filter(
                fromdate__lt=end_time,
                uptodate__gt=start_time,
                asset=job.asset
            ).exclude(id=job.id if job.id else None)

            for conflict_job in overlapping_jobs:
                conflicts.append({
                    'conflict_type': 'schedule_overlap',
                    'conflicting_job': conflict_job.jobname,
                    'conflicting_time': f"{conflict_job.fromdate} - {conflict_job.uptodate}",
                    'asset': conflict_job.asset.assetname if conflict_job.asset else None
                })

            return conflicts

        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error validating conflicts: {str(e)}", exc_info=True)
            return []
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Data error validating conflicts: {str(e)}")
            return []

    @BaseService.monitor_performance("get_tour_analytics")
    def get_tour_analytics(self, tour_id: int) -> Dict[str, Any]:
        """
        Get analytics for a specific tour.

        Args:
            tour_id: Tour job ID

        Returns:
            Dictionary containing tour analytics
        """
        try:
            job = Job.objects.get(id=tour_id)

            # Get child checkpoints
            checkpoints = Job.objects.filter(parent_id=tour_id)

            analytics = {
                'tour_name': job.jobname,
                'total_checkpoints': checkpoints.count(),
                'completed_checkpoints': checkpoints.filter(status='COMPLETED').count(),
                'pending_checkpoints': checkpoints.filter(status='PENDING').count(),
                'tour_duration': (job.uptodate - job.fromdate).total_seconds() / SECONDS_IN_HOUR,  # hours
                'average_checkpoint_time': job.gracetime,
                'tour_efficiency': 0.0  # Placeholder for efficiency calculation
            }

            if analytics['total_checkpoints'] > 0:
                analytics['completion_rate'] = (
                    analytics['completed_checkpoints'] / analytics['total_checkpoints'] * 100
                )

            return analytics

        except Job.DoesNotExist:
            raise SchedulingException(f"Tour with ID {tour_id} not found")

        except (DatabaseError, OperationalError) as e:
            self.logger.error(f"Database error getting tour analytics: {str(e)}", exc_info=True)
            raise DatabaseException(
                "Failed to retrieve tour analytics - database unavailable",
                original_exception=e
            ) from e
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.error(f"Data error getting tour analytics: {str(e)}")
            raise SchedulingException(
                f"Failed to retrieve tour analytics: {str(e)}"
            ) from e

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "SchedulingService"