"""
People Sync ViewSet for Mobile API

Provides people sync endpoints that replace legacy API queries:
- get_peoplemodifiedafter → GET /people/modified-after/
- get_pgbelongingmodifiedafter → GET /groups/memberships/modified-after/
- get_peopleeventlog_history → GET /event-logs/history/
- get_people_event_log_punch_ins → GET /event-logs/punch-ins/
- get_attachments → GET /attachments/

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

from apps.peoples.models import People, Pgbelonging
from apps.attendance.models import PeopleEventlog
from apps.activity.models.attachment_model import Attachment
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.service.pydantic_schemas.people_schema import (
    PeopleModifiedAfterSchema,
    PeopleEventLogPunchInsSchema,
    PgbelongingModifiedAfterSchema,
    PeopleEventLogHistorySchema,
    AttachmentSchema,
)
from apps.core import utils

logger = logging.getLogger('mobile_service_log')


class PeopleSyncViewSet(viewsets.GenericViewSet):
    """
    Mobile sync API for people and related data.

    Endpoints:
    - GET /api/v1/people/modified-after/                People modified after
    - GET /api/v1/people/groups/memberships/modified-after/  Group memberships
    - GET /api/v1/people/event-logs/history/            Event log history
    - GET /api/v1/people/event-logs/punch-ins/          Punch-in events
    - GET /api/v1/people/attachments/                   User attachments
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = People.objects.all()

    @action(detail=False, methods=['get'], url_path='modified-after')
    def modified_after(self, request):
        """
        Get people modified after a given timestamp.

        Replaces legacy query: get_peoplemodifiedafter

        Query Params:
            mdtz (str): Modification timestamp (ISO format)
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID

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
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid'))
            }
            validated = PeopleModifiedAfterSchema(**filter_data)

            # Convert to aware datetime
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,
                offset=validated.ctzoffset
            )

            # Get data
            data = People.objects.get_people_modified_after(
                mdtz=mdtzinput,
                siteid=validated.buid
            )

            # Paginate
            page = self.paginate_queryset(data)
            if page is not None:
                from apps.peoples.api.serializers import PeopleListSerializer
                serializer = PeopleListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            from apps.peoples.api.serializers import PeopleListSerializer
            serializer = PeopleListSerializer(data, many=True)
            logger.info(f"Returned {len(data)} people records")

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

    @action(detail=False, methods=['get'], url_path='groups/memberships/modified-after')
    def group_memberships_modified_after(self, request):
        """
        Get group memberships modified after timestamp.

        Replaces legacy query: get_pgbelongingmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID
            peopleid (int): People ID

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
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid')),
                'peopleid': int(request.query_params.get('peopleid'))
            }
            validated = PgbelongingModifiedAfterSchema(**filter_data)

            # Convert to aware datetime
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,
                offset=validated.ctzoffset
            )

            # Get data
            data = Pgbelonging.objects.get_modified_after(
                mdtz=mdtzinput,
                peopleid=validated.peopleid,
                buid=validated.buid
            )

            from apps.peoples.api.serializers import PgbelongingSerializer
            serializer = PgbelongingSerializer(data, many=True)
            logger.info(f"Returned {len(data)} group memberships")

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

    @action(detail=False, methods=['get'], url_path='event-logs/history')
    def event_log_history(self, request):
        """
        Get people event log history.

        Replaces legacy query: get_peopleeventlog_history

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            peopleid (int): People ID
            buid (int): Business unit ID
            clientid (int): Client ID
            peventtypeid (list[int]): Event type IDs (comma-separated)

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Parse event type IDs
            peventtypeid_str = request.query_params.get('peventtypeid', '')
            peventtypeid = [int(x.strip()) for x in peventtypeid_str.split(',') if x.strip()]

            # Validate parameters
            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'peopleid': int(request.query_params.get('peopleid')),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid')),
                'peventtypeid': peventtypeid
            }
            validated = PeopleEventLogHistorySchema(**filter_data)

            # Convert to aware datetime
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,
                offset=validated.ctzoffset
            )

            # Get data
            data = PeopleEventlog.objects.get_peopleeventlog_history(
                mdtz=mdtzinput,
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
                ctzoffset=validated.ctzoffset,
                peventtypeid=validated.peventtypeid,
            )

            from apps.attendance.api.serializers import PeopleEventlogSerializer
            serializer = PeopleEventlogSerializer(data, many=True)
            logger.info(f"Returned {len(data)} event log records")

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

    @action(detail=False, methods=['get'], url_path='event-logs/punch-ins')
    def event_log_punch_ins(self, request):
        """
        Get people event log punch-ins for a specific date.

        Replaces legacy query: get_people_event_log_punch_ins

        Query Params:
            datefor (str): Date (YYYY-MM-DD format)
            buid (int): Business unit ID
            peopleid (int): People ID

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
                'datefor': request.query_params.get('datefor'),
                'buid': int(request.query_params.get('buid')),
                'peopleid': int(request.query_params.get('peopleid'))
            }
            validated = PeopleEventLogPunchInsSchema(**filter_data)

            # Get data
            data = PeopleEventlog.objects.get_people_event_log_punch_ins(
                datefor=validated.datefor,
                buid=validated.buid,
                peopleid=validated.peopleid,
            )

            from apps.attendance.api.serializers import PeopleEventlogSerializer
            serializer = PeopleEventlogSerializer(data, many=True)
            logger.info(f"Returned {len(data)} punch-in records")

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

    @action(detail=False, methods=['get'], url_path='attachments')
    def attachments(self, request):
        """
        Get attachments for an owner.

        Replaces legacy query: get_attachments

        Query Params:
            owner (str): Owner identifier

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
                'owner': request.query_params.get('owner')
            }
            validated = AttachmentSchema(**filter_data)

            # Get data
            data = Attachment.objects.get_attachements_for_mob(
                ownerid=validated.owner
            )

            from apps.activity.api.serializers import AttachmentSerializer
            serializer = AttachmentSerializer(data, many=True)
            logger.info(f"Returned {len(data)} attachments")

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


__all__ = ['PeopleSyncViewSet']
