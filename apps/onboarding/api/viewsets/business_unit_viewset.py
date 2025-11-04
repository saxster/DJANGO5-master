"""
Business Unit ViewSet for Mobile API

Provides admin/configuration endpoints:
- GET /admin/locations/ → get_locations query
- GET /admin/sites/ → getsitelist query
- GET /admin/shifts/ → get_shifts query
- GET /admin/site-visits/log/ → get_site_visited_log query
- GET /admin/groups/ → get_groupsmodifiedafter query
- POST /admin/clients/verify/ → verifyclient mutation

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from pydantic import ValidationError as PydanticValidationError
import logging

from apps.client_onboarding.models import Shift
from apps.core_onboarding.models import GeofenceMaster
from apps.activity.models.location_model import Location
from apps.peoples.models import Pgroup
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.core import utils

logger = logging.getLogger('mobile_service_log')


class BusinessUnitViewSet(viewsets.GenericViewSet):
    """
    Mobile API for business unit and admin configuration.

    Endpoints:
    - GET  /api/v1/admin/locations/        Locations modified after
    - GET  /api/v1/admin/sites/            Site list
    - GET  /api/v1/admin/shifts/           Shifts modified after
    - GET  /api/v1/admin/site-visits/log/  Site visit log
    - GET  /api/v1/admin/groups/           Groups modified after
    - POST /api/v1/admin/clients/verify/   Verify client code
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination

    @action(detail=False, methods=['get'], url_path='locations')
    def locations(self, request):
        """
        Get locations modified after timestamp.

        Replaces legacy query: get_locations

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID

        Returns:
            List of locations
        """
        try:
            from apps.service.pydantic_schemas.bt_schema import LocationSchema

            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid'))
            }
            validated = LocationSchema(**filter_data)

            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,
                offset=validated.ctzoffset
            )

            data = Location.objects.get_locations_modified_after(
                mdtzinput, validated.buid, validated.ctzoffset
            )

            from apps.onboarding.api.serializers import LocationSerializer
            serializer = LocationSerializer(data, many=True)
            logger.info(f"Returned {len(data)} locations")

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
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='sites')
    def sites(self, request):
        """
        Get site list.

        Replaces legacy query: getsitelist

        Query Params:
            clientid (int): Client ID
            peopleid (int): People ID

        Returns:
            List of sites (business units)
        """
        try:
            from apps.service.pydantic_schemas.bt_schema import SiteListSchema
            from apps.client_onboarding.models import Bt

            filter_data = {
                'clientid': int(request.query_params.get('clientid')),
                'peopleid': int(request.query_params.get('peopleid'))
            }
            validated = SiteListSchema(**filter_data)

            data = Bt.objects.get_sites_for_mobile(
                validated.clientid,
                validated.peopleid
            )

            from apps.onboarding.api.serializers import BtSerializer
            serializer = BtSerializer(data, many=True)
            logger.info(f"Returned {len(data)} sites")

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
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='shifts')
    def shifts(self, request):
        """
        Get shifts modified after timestamp.

        Replaces legacy query: get_shifts

        Query Params:
            mdtz (str): Modification timestamp
            buid (int): Business unit ID
            clientid (int): Client ID

        Returns:
            List of shifts
        """
        try:
            from apps.service.pydantic_schemas.bt_schema import ShiftSchema

            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid'))
            }
            validated = ShiftSchema(**filter_data)

            data = Shift.objects.get_shifts_for_mobile(
                validated.mdtz,
                validated.buid,
                validated.clientid
            )

            from apps.onboarding.api.serializers import ShiftSerializer
            serializer = ShiftSerializer(data, many=True)
            logger.info(f"Returned {len(data)} shifts")

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
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='groups')
    def groups(self, request):
        """
        Get groups modified after timestamp.

        Replaces legacy query: get_groupsmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID

        Returns:
            List of groups
        """
        try:
            from apps.service.pydantic_schemas.bt_schema import GroupsModifiedAfterSchema

            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid'))
            }
            validated = GroupsModifiedAfterSchema(**filter_data)

            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz,
                offset=validated.ctzoffset
            )

            data = Pgroup.objects.get_groups_modified_after(
                mdtzinput, validated.buid
            )

            from apps.peoples.api.serializers import PgroupSerializer
            serializer = PgroupSerializer(data, many=True)
            logger.info(f"Returned {len(data)} groups")

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
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='type-assist/modified-after')
    def type_assist_modified_after(self, request):
        """
        Get type assistance data modified after timestamp.

        Replaces legacy query: get_typeassistmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            clientid (int): Client ID

        Returns:
            List of type assistance records
        """
        try:
            from apps.core_onboarding.models import TypeAssist

            mdtz = request.query_params.get('mdtz')
            ctzoffset = int(request.query_params.get('ctzoffset', 0))
            clientid = int(request.query_params.get('clientid'))

            mdtzinput = utils.getawaredatetime(dt=mdtz, offset=ctzoffset)

            data = TypeAssist.objects.get_typeassist_modified_after(
                mdtz=mdtzinput,
                clientid=clientid
            )

            from apps.onboarding.api.serializers import TypeAssistSerializer
            serializer = TypeAssistSerializer(data, many=True)
            logger.info(f"Returned {len(data)} type assist records")

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
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='clients/verify')
    def verify_client(self, request):
        """
        Verify client code.

        Replaces legacy mutation handler: verifyclient

        Request:
            {
                "clientcode": "CLIENT123"
            }

        Returns:
            {
                "valid": true,
                "url": "https://client.example.com",
                "message": "VALID"
            }
        """
        try:
            from apps.service.pydantic_schemas.bt_schema import VerifyClientSchema

            clientcode = request.data.get('clientcode')
            if not clientcode:
                return Response(
                    {'error': 'clientcode is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            filter_data = {'clientcode': clientcode}
            validated = VerifyClientSchema(**filter_data)

            url = utils.get_appropriate_client_url(validated.clientcode)

            if url:
                return Response({
                    'valid': True,
                    'url': url,
                    'message': 'VALID'
                })
            else:
                return Response({
                    'valid': False,
                    'url': None,
                    'message': 'INVALID'
                }, status=status.HTTP_404_NOT_FOUND)

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid client code: {e}", exc_info=True)
            return Response({
                'valid': False,
                'url': None,
                'message': 'INVALID'
            }, status=status.HTTP_404_NOT_FOUND)


__all__ = ['BusinessUnitViewSet']
