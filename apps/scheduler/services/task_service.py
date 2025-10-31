"""
Task Service

Handles business logic for task scheduling including:
- Task creation and updates
- Task retrieval and filtering
- Task assignment

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for tasks
"""

import logging
from typing import Dict, Any, Tuple

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services.transaction_manager import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import DatabaseException
from apps.activity.models.job_model import Job, Jobneed
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class TaskService(BaseService):
    """Service for task management business logic."""

    def __init__(self):
        super().__init__()
        self.model = Job

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "TaskService"

    @with_transaction
    def create_task(
        self,
        form_data: Dict[str, Any],
        user,
        session
    ) -> Tuple[Job, bool]:
        """Create a new task."""
        logger.info("Creating task [START]")

        try:
            job = self.model(**form_data)
            job.identifier = Job.Identifier.TASK
            job.parent = None
            job.save()

            job = putils.save_userinfo(job, user, session, create=True)

            logger.info(f"Task '{job.jobname}' created successfully")
            return job, True

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Task creation error")
            logger.error(f"Error creating task - {correlation_id}")
            raise

    @with_transaction
    def update_task(
        self,
        task_id: int,
        form_data: Dict[str, Any],
        user,
        session
    ) -> Tuple[Job, bool]:
        """Update existing task."""
        logger.info(f"Updating task ID {task_id}")

        try:
            job = self.model.objects.get(id=task_id)

            for field, value in form_data.items():
                setattr(job, field, value)

            job.save()
            job = putils.save_userinfo(job, user, session, create=False)

            logger.info(f"Task '{job.jobname}' updated successfully")
            return job, True

        except self.model.DoesNotExist:
            logger.error(f"Task with ID {task_id} not found")
            raise ValidationError("Task not found")

    def get_tasks_list(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """Get paginated list of tasks."""
        try:
            queryset = self.model.objects.select_related(
                'people', 'asset'
            ).filter(
                identifier=Job.Identifier.TASK
            )

            if filters:
                queryset = self._apply_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Error retrieving tasks")
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_task_by_id(self, task_id: int) -> Job:
        """Retrieve specific task by ID."""
        try:
            return self.model.objects.select_related(
                'people', 'asset', 'asset__location'
            ).get(id=task_id)

        except self.model.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to tasks queryset."""
        if 'jobname' in filters:
            queryset = queryset.filter(jobname__icontains=filters['jobname'])
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'asset_id' in filters:
            queryset = queryset.filter(asset_id=filters['asset_id'])
        return queryset


class TaskJobneedService(BaseService):
    """Service for task jobneed operations."""

    def __init__(self):
        super().__init__()
        self.model = Jobneed

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "TaskJobneedService"

    def get_task_jobneeds(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """Get paginated list of task jobneeds."""
        try:
            queryset = self.model.objects.select_related(
                'job', 'people'
            ).filter(
                job__identifier=Job.Identifier.TASK
            )

            if filters:
                queryset = self._apply_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Error retrieving task jobneeds")
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_task_jobneed_by_id(self, jobneed_id: int) -> Jobneed:
        """Retrieve specific task jobneed by ID."""
        try:
            return self.model.objects.select_related(
                'job', 'people', 'job__asset'
            ).get(id=jobneed_id)

        except self.model.DoesNotExist:
            logger.error(f"Task jobneed {jobneed_id} not found")
            raise ValidationError("Task jobneed not found")

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to task jobneed queryset."""
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        return queryset