"""
Task Sync ViewSet for Mobile API

Provides mobile sync endpoints that replace legacy queries:
- get_jobneedmodifiedafter → GET /modified-after/
- get_jndmodifiedafter → GET /details/modified-after/
- get_externaltourmodifiedafter → GET /external-tours/modified-after/
- InsertRecord mutation → POST /sync/
- TaskTourUpdate mutation → PATCH /{id}/update/

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling (no bare except)
- Delegates to service layer
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from pydantic import ValidationError as PydanticValidationError
import logging

from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.activity.services.task_sync_service import TaskSyncService
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.service.pydantic_schemas.job_schema import (
    JobneedModifiedAfterSchema,
    JobneedDetailsModifiedAfterSchema,
    ExternalTourModifiedAfterSchema,
)
from apps.activity.api.serializers import (
    JobneedListSerializer,
    JobneedDetailSerializer,
    JobneedDetailsSerializer,
)

logger = logging.getLogger('mobile_service_log')


class TaskSyncViewSet(viewsets.GenericViewSet):
    """
    Mobile sync API for tasks and tours.

    Endpoints:
    - GET  /api/v1/operations/tasks/modified-after/            Get modified jobneeds
    - GET  /api/v1/operations/tasks/details/modified-after/    Get modified jobneed details
    - GET  /api/v1/operations/tours/external/modified-after/   Get external tours
    - POST /api/v1/operations/tasks/sync/                      Bulk sync tasks
    - PATCH /api/v1/operations/tasks/{id}/update/              Update task/tour
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = Jobneed.objects.all()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_service = TaskSyncService()

    @action(detail=False, methods=['get'], url_path='modified-after')
    def modified_after(self, request):
        """
        Get jobneeds modified after a given timestamp.

        Replaces legacy query: get_jobneedmodifiedafter

        Query Params:
            peopleid (int): People ID
            buid (int): Business unit ID
            clientid (int): Client ID

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'peopleid': int(request.query_params.get('peopleid')),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid'))
            }
            validated = JobneedModifiedAfterSchema(**filter_data)

            # Get data from model manager
            data = Jobneed.objects.get_job_needs(
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                serializer = JobneedListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = JobneedListSerializer(data, many=True)
            logger.info(f"Returned {len(data)} jobneeds for user {request.user.id}")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='details/modified-after')
    def details_modified_after(self, request):
        """
        Get jobneed details modified after a given timestamp.

        Replaces legacy query: get_jndmodifiedafter

        Query Params:
            jobneedids (str): Comma-separated jobneed IDs
            ctzoffset (int): Client timezone offset

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'jobneedids': request.query_params.get('jobneedids'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0))
            }
            validated = JobneedDetailsModifiedAfterSchema(**filter_data)

            # Get data from model manager
            data = JobneedDetails.objects.get_jndmodifiedafter(
                jobneedid=validated.jobneedids
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                serializer = JobneedDetailsSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = JobneedDetailsSerializer(data, many=True)
            logger.info(f"Returned {len(data)} jobneed details for user {request.user.id}")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='tours/external/modified-after')
    def external_tours_modified_after(self, request):
        """
        Get external tours modified after a given timestamp.

        Replaces legacy query: get_externaltourmodifiedafter

        Query Params:
            peopleid (int): People ID
            buid (int): Business unit ID
            clientid (int): Client ID

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'peopleid': int(request.query_params.get('peopleid')),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid'))
            }
            validated = ExternalTourModifiedAfterSchema(**filter_data)

            # Get data from model manager
            data = Jobneed.objects.get_external_tour_job_needs(
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                serializer = JobneedListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = JobneedListSerializer(data, many=True)
            logger.info(f"Returned {len(data)} external tours for user {request.user.id}")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='sync')
    def sync_tasks(self, request):
        """
        Bulk sync tasks from mobile client.

        Replaces legacy mutation handler: InsertRecord

        Request:
            {
                "entries": [
                    {"id": 123, "status": "completed", ...},
                    ...
                ],
                "last_sync_timestamp": "2025-10-01T00:00:00Z",
                "client_id": 1
            }

        Returns:
            {
                "synced_items": [...],
                "conflicts": [...],
                "errors": [...]
            }
        """
        try:
            result = self.sync_service.sync_tasks(
                user=request.user,
                sync_data=request.data,
                serializer_class=JobneedDetailSerializer
            )

            logger.info(
                f"Synced {len(result.get('synced_items', []))} tasks "
                f"for user {request.user.id}"
            )

            return Response(result, status=status.HTTP_200_OK)

        except ValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Sync failed due to database error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['patch'], url_path='update')
    def update_task_tour(self, request, pk=None):
        """
        Update task/tour status and metadata.

        Replaces legacy mutation handler: TaskTourUpdate

        PATCH /api/v1/operations/tasks/{id}/update/

        Request:
            {
                "status": "completed",
                "completion_notes": "All checks passed",
                ...
            }

        Returns:
            Updated jobneed object
        """
        try:
            jobneed = self.get_object()

            # Validate status transition if status is being updated
            new_status = request.data.get('status')
            if new_status and new_status != jobneed.status:
                is_valid = self.sync_service.validate_task_status_transition(
                    current_status=jobneed.status,
                    new_status=new_status
                )
                if not is_valid:
                    return Response(
                        {
                            'error': f'Invalid status transition: '
                                    f'{jobneed.status} → {new_status}'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update with partial data
            serializer = JobneedDetailSerializer(
                jobneed,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Updated jobneed {pk} by user {request.user.id}")

            return Response(serializer.data)

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Jobneed not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Update failed due to database error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = ['TaskSyncViewSet']
