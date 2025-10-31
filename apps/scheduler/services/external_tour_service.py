"""
External Tour Service

Handles business logic for external tour scheduling including:
- External tour creation and updates
- Site assignment to tours
- External tour tracking
- Checkpoint management for external tours

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for external tours
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

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
)
from apps.activity.models.job_model import Job, Jobneed
import apps.scheduler.utils as sutils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class ExternalTourService(BaseService):
    """Service for external tour business logic."""

    def __init__(self):
        super().__init__()
        self.model = Job

    def get_service_name(self) -> str:
        """Return the service name for logging and monitoring."""
        return "ExternalTourService"

    @with_transaction
    def create_external_tour(
        self,
        form_data: Dict[str, Any],
        assigned_sites: List[Dict],
        user,
        session
    ) -> Tuple[Job, bool]:
        """
        Create external tour with assigned sites.

        Args:
            form_data: Validated form data
            assigned_sites: List of site assignments
            user: User creating the tour
            session: User session data

        Returns:
            Tuple of (job instance, success boolean)
        """
        logger.info("Creating external tour [START]")

        try:
            job = self._create_external_job(form_data)
            job = putils.save_userinfo(job, user, session, create=True)

            if assigned_sites:
                self._assign_sites_to_tour(job, assigned_sites, user, session)

            logger.info(f"External tour '{job.jobname}' created successfully")
            return job, True

        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "External tour creation validation error"
            )
            logger.warning(f"External tour validation failed - {correlation_id}")
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "External tour database error"
            )
            logger.error(f"Database error - {correlation_id}")
            raise
        finally:
            logger.info("Creating external tour [END]")

    @with_transaction
    def update_external_tour(
        self,
        tour_id: int,
        form_data: Dict[str, Any],
        assigned_sites: List[Dict],
        user,
        session
    ) -> Tuple[Job, bool]:
        """Update existing external tour."""
        logger.info(f"Updating external tour ID {tour_id} [START]")

        try:
            job = self.model.objects.get(id=tour_id)

            for field, value in form_data.items():
                setattr(job, field, value)

            job.save()
            job = putils.save_userinfo(job, user, session, create=False)

            if assigned_sites:
                self._update_sites_for_tour(job, assigned_sites, user, session)

            logger.info(f"External tour '{job.jobname}' updated successfully")
            return job, True

        except self.model.DoesNotExist:
            logger.error(f"External tour with ID {tour_id} not found")
            raise ValidationError("Tour not found")
        finally:
            logger.info(f"Updating external tour ID {tour_id} [END]")

    def get_external_tours(
        self,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> QuerySet:
        """Get list of external tours with optional filters."""
        try:
            queryset = self.model.objects.select_related(
                'people', 'asset'
            ).filter(
                Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling (must be first)
                identifier=Job.Identifier.EXTERNALTOUR
            )

            if filters:
                queryset = self._apply_filters(queryset, filters)

            start = (page - 1) * page_size
            end = start + page_size

            return queryset[start:end]

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Error retrieving external tours"
            )
            logger.error(f"Database error - {correlation_id}")
            raise

    def get_tour_with_sites(self, tour_id: int) -> Tuple[Job, QuerySet]:
        """Retrieve external tour with assigned sites."""
        try:
            job = self.model.objects.select_related(
                'people', 'asset'
            ).get(id=tour_id)

            sites = self.model.objects.filter(parent_id=tour_id).select_related(
                'asset', 'asset__location'
            )

            return job, sites

        except self.model.DoesNotExist:
            logger.error(f"External tour with ID {tour_id} not found")
            raise ValidationError("Tour not found")

    def get_site_checkpoints(self, jobneed_id: int) -> Dict[str, Any]:
        """Get checkpoint locations for tracking external tour."""
        try:
            jobneed = Jobneed.objects.select_related('job').get(id=jobneed_id)

            checkpoints = self.model.objects.filter(
                parent_id=jobneed.job_id
            ).select_related(
                'asset', 'asset__location'
            ).values(
                'id',
                'asset__assetname',
                'asset__location__latitude',
                'asset__location__longitude',
                'seqno',
                'expirytime'
            )

            return {
                'jobneed_id': jobneed_id,
                'checkpoints': list(checkpoints),
                'tour_name': jobneed.job.jobname
            }

        except Jobneed.DoesNotExist:
            logger.error(f"Jobneed {jobneed_id} not found")
            raise ValidationError("Jobneed not found")

    def _create_external_job(self, form_data: Dict[str, Any]) -> Job:
        """Create base external tour job."""
        job = self.model(**form_data)
        job.identifier = Job.Identifier.EXTERNALTOUR
        job.parent = None
        job.save()
        return job

    def _assign_sites_to_tour(
        self,
        job: Job,
        sites: List[Dict],
        user,
        session
    ) -> None:
        """Assign sites as checkpoints to external tour."""
        logger.info(f"Assigning {len(sites)} sites to tour '{job.jobname}'")

        try:
            for idx, site in enumerate(sites):
                site_job = self.model.objects.create(
                    parent=job,
                    asset_id=site.get('asset_id'),
                    seqno=idx + 1,
                    jobname=f"{job.jobname}_site_{idx+1}",
                    **sutils.job_fields(job.__dict__, site, external=True)
                )
                putils.save_userinfo(site_job, user, session, bu=site.get('buid'))

            logger.info(f"Successfully assigned {len(sites)} sites")

        except (ValueError, KeyError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e, "Invalid site data format"
            )
            logger.error(f"Data error - {correlation_id}")
            raise ValidationError("Invalid site data")

    def _update_sites_for_tour(
        self,
        job: Job,
        sites: List[Dict],
        user,
        session
    ) -> None:
        """Update sites for external tour."""
        self.model.objects.filter(parent_id=job.id).delete()
        self._assign_sites_to_tour(job, sites, user, session)

    def _apply_filters(self, queryset: QuerySet, filters: Dict[str, Any]) -> QuerySet:
        """Apply filters to external tours queryset."""
        if 'jobname' in filters:
            queryset = queryset.filter(jobname__icontains=filters['jobname'])
        if 'people_id' in filters:
            queryset = queryset.filter(people_id=filters['people_id'])
        return queryset