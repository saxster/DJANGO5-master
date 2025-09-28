"""
Jobneed Management Service

Handles business logic for jobneed CRUD operations across all job types.

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for jobneed management
"""

import logging
from typing import Dict, Any, List

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.core.services.base_service import BaseService
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import DatabaseException
from apps.activity.models.job_model import Jobneed, JobneedDetails

logger = logging.getLogger(__name__)


class JobneedManagementService(BaseService):
    """Service for generic jobneed management."""

    def __init__(self):
        super().__init__()
        self.jobneed_model = Jobneed
        self.jnd_model = JobneedDetails

    def get_jobneed_with_details(self, jobneed_id: int) -> Dict[str, Any]:
        """Get jobneed with its details."""
        try:
            jobneed = self.jobneed_model.objects.select_related(
                'job', 'people', 'job__asset'
            ).get(id=jobneed_id)

            details = self.jnd_model.objects.filter(
                jobneed_id=jobneed_id
            ).values(
                'id', 'quesname', 'answertype', 'min', 'max',
                'options', 'alerton', 'ismandatory'
            )

            return {
                'jobneed': jobneed,
                'details': list(details)
            }

        except self.jobneed_model.DoesNotExist:
            logger.error(f"Jobneed {jobneed_id} not found")
            raise ValidationError("Jobneed not found")

    def update_jobneed_details(
        self,
        jobneed_id: int,
        details_data: List[Dict[str, Any]]
    ) -> bool:
        """Update jobneed details."""
        try:
            for detail in details_data:
                detail_id = detail.get('id')
                if detail_id:
                    self.jnd_model.objects.filter(id=detail_id).update(**detail)
                else:
                    self.jnd_model.objects.create(jobneed_id=jobneed_id, **detail)

            logger.info(f"Jobneed {jobneed_id} details updated")
            return True

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Error updating jobneed details")
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_jobneeds_by_job_type(
        self,
        job_type: str,
        filters: Dict[str, Any] = None
    ) -> QuerySet:
        """Get jobneeds filtered by job type."""
        try:
            queryset = self.jobneed_model.objects.select_related(
                'job', 'people'
            ).filter(job__identifier=job_type)

            if filters:
                queryset = self._apply_filters(queryset, filters)

            return queryset

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Error retrieving jobneeds")
            logger.error(f"Database error - {correlation_id}")
            raise

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to jobneed queryset."""
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'job_id' in filters:
            queryset = queryset.filter(job_id=filters['job_id'])
        return queryset