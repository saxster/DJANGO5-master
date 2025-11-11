"""
Business logic services for the scheduler app.

This module contains business logic extracted from views to improve
code organization and maintainability.

Note: This app is named 'scheduler' due to legacy reasons.
The correct spelling would be 'scheduler' but changing it would
require significant refactoring of URLs, imports, and potentially
database references throughout the codebase.
"""

import logging
from django.db import transaction
from django.db.utils import IntegrityError
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


# TourJobService removed - functionality exists in:
# - apps/scheduler/services/scheduling_service.py (SchedulingService)
# - apps/scheduler/services/internal_tour_service.py (InternalTourService)
# Dead code with missing imports: Job, DatabaseConstants, DatabaseError, ObjectDoesNotExist


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