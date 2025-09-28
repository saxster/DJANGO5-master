"""
Business logic services for the scheduler app.

This module contains business logic extracted from views to improve
code organization and maintainability.

Note: This app is named 'schedhuler' due to legacy reasons.
The correct spelling would be 'scheduler' but changing it would
require significant refactoring of URLs, imports, and potentially
database references throughout the codebase.
"""

import logging
from django.db import transaction
from django.db.utils import IntegrityError
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class TourJobService:
    """Service for tour job related business logic."""

    @staticmethod
    def create_tour_job(job_data, assigned_checkpoints, user, session):
        """
        Create a new tour job with its checkpoints.

        Args:
            job_data: Dictionary containing job information
            assigned_checkpoints: List of checkpoint data
            user: User creating the job
            session: User session data

        Returns:
            tuple: (job_instance, success_boolean)

        Raises:
            IntegrityError: If database constraints are violated
            ValueError: If data is invalid
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                # Create main job
                job = Job.objects.create(**job_data)
                job.parent_id = DatabaseConstants.ID_ROOT
                job.asset_id = DatabaseConstants.ID_NONE
                job.qset_id = DatabaseConstants.ID_NONE
                job.save()

                # Save user information
                from apps.peoples import utils as putils
                job = putils.save_userinfo(job, user, session, create=True)

                # Create checkpoints
                TourJobService._create_checkpoints(assigned_checkpoints, job, user, session)

                logger.info(f"Tour job '{job.jobname}' created successfully with {len(assigned_checkpoints)} checkpoints")
                return job, True

        except IntegrityError as e:
            logger.error(f"Database integrity error creating tour job: {e}", exc_info=True)
            raise
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid data for tour job creation: {e}", exc_info=True)
            raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.critical(f"Unexpected error creating tour job: {e}", exc_info=True)
            raise

    @staticmethod
    def _create_checkpoints(checkpoints, parent_job, user, session):
        """
        Create checkpoints for a tour job.

        Args:
            checkpoints: List of checkpoint data
            parent_job: Parent Job instance
            user: User creating checkpoints
            session: User session data
        """
        import apps.schedhuler.utils as sutils
        from apps.peoples import utils as putils

        logger.info(f"Creating {len(checkpoints)} checkpoints for job {parent_job.jobname}")

        for cp in checkpoints:
            try:
                checkpoint_data = {
                    'parent_id': parent_job.id,
                    'asset_id': cp[1],
                    'qset_id': cp[3],
                    'seqno': cp[0],
                    'expirytime': cp[5],
                }

                # Merge additional job fields
                checkpoint_data.update(sutils.job_fields(parent_job, cp))

                checkpoint, created = Job.objects.update_or_create(
                    parent_id=parent_job.id,
                    asset_id=cp[1],
                    qset_id=cp[3],
                    defaults=checkpoint_data
                )

                putils.save_userinfo(checkpoint, user, session, create=created)

                status = "CREATED" if created else "UPDATED"
                logger.debug(f"Checkpoint {cp[2]} {status} for job {parent_job.jobname}")

            except (IndexError, ValueError) as e:
                logger.error(f"Invalid checkpoint data: {cp}, error: {e}", exc_info=True)
                raise ValueError(f"Invalid checkpoint data at index: {checkpoints.index(cp)}")


class TaskJobService:
    """Service for task job related business logic."""

    @staticmethod
    def create_task_job(job_data, user, session):
        """
        Create a new task job.

        Args:
            job_data: Dictionary containing job information
            user: User creating the job
            session: User session data

        Returns:
            Job: Created job instance
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                job = Job.objects.create(**job_data)

                # Save user information
                from apps.peoples import utils as putils
                job = putils.save_userinfo(job, user, session)

                logger.info(f"Task job '{job.jobname}' created successfully")
                return job

        except IntegrityError as e:
            logger.error(f"Database integrity error creating task job: {e}", exc_info=True)
            raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.critical(f"Unexpected error creating task job: {e}", exc_info=True)
            raise


class ScheduleService:
    """Service for schedule-related operations."""

    @staticmethod
    def generate_schedule_preview(cron_expression, preview_count=10):
        """
        Generate preview dates for a cron expression.

        Args:
            cron_expression: Cron format string
            preview_count: Number of future dates to generate

        Returns:
            list: List of formatted datetime strings

        Raises:
            ValueError: If cron expression is invalid
        """
        try:
            from croniter import croniter
            from datetime import datetime

            if not croniter.is_valid(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")

            base = datetime.now()
            cron = croniter(cron_expression, base)

            schedule_dates = []
            for _ in range(preview_count):
                next_date = cron.get_next(datetime)
                schedule_dates.append(next_date.strftime('%Y-%m-%d %H:%M:%S'))

            logger.debug(f"Generated {len(schedule_dates)} schedule dates for cron: {cron_expression}")
            return schedule_dates

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error generating schedule preview: {e}", exc_info=True)
            raise ValueError(f"Failed to generate schedule preview: {str(e)}")


# Constants are now imported from apps.core.constants
# This provides centralized constant management across the application