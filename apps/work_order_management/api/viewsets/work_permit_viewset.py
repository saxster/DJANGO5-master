"""
Work Permit ViewSet for Mobile API

Provides work permit endpoints that replace legacy queries:
- get_wom_records → GET /work-permits/
- get_pdf_url → GET /work-permits/{uuid}/pdf/
- get_approve_workpermit → POST /work-permits/{uuid}/approve/
- get_reject_workpermit → POST /work-permits/{uuid}/reject/
- get_approvers → GET /work-permits/approvers/
- get_vendors → GET /work-permits/vendors/

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
from django.core.exceptions import ValidationError, ObjectDoesNotExist, PermissionDenied
from pydantic import ValidationError as PydanticValidationError
import logging

from apps.work_order_management.models import Wom, Approver, Vendor
from apps.work_order_management.services.work_permit_service import WorkPermitService
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.service.pydantic_schemas.workpermit_schema import (
    WomPdfUrlSchema,
    WomRecordSchema,
    ApproveWorkpermitSchema,
    RejectWorkpermitSchema,
    ApproverSchema,
    VendorSchema,
)

logger = logging.getLogger('mobile_service_log')


class WorkPermitViewSet(viewsets.GenericViewSet):
    """
    Mobile API for work permit management.

    Endpoints:
    - GET  /api/v1/operations/work-permits/              List work permits
    - GET  /api/v1/operations/work-permits/{uuid}/pdf/   Get PDF URL
    - POST /api/v1/operations/work-permits/{uuid}/approve/ Approve work permit
    - POST /api/v1/operations/work-permits/{uuid}/reject/  Reject work permit
    - GET  /api/v1/operations/work-permits/approvers/    Get approvers list
    - GET  /api/v1/operations/work-permits/vendors/      Get vendors list
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = Wom.objects.all()
    lookup_field = 'uuid'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = WorkPermitService()

    def list(self, request):
        """
        Get work permit records with filtering.

        Replaces legacy query: get_wom_records

        Query Params:
            workpermit (str): Work permit type
            peopleid (int): People ID
            buid (int, optional): Business unit ID
            parentid (int, optional): Parent ID
            clientid (int, optional): Client ID
            fromdate (str): From date (ISO format)
            todate (str): To date (ISO format)

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
                'workpermit': request.query_params.get('workpermit'),
                'peopleid': int(request.query_params.get('peopleid')),
                'buid': int(request.query_params.get('buid', 0)) or None,
                'parentid': int(request.query_params.get('parentid', 0)) or None,
                'clientid': int(request.query_params.get('clientid', 0)) or None,
                'fromdate': request.query_params.get('fromdate'),
                'todate': request.query_params.get('todate')
            }
            validated = WomRecordSchema(**filter_data)

            # Get data from model manager
            data = Wom.objects.get_wom_records_for_mobile(
                fromdate=validated.fromdate,
                todate=validated.todate,
                peopleid=validated.peopleid,
                workpermit=validated.workpermit,
                buid=validated.buid,
                clientid=validated.clientid,
                parentid=validated.parentid,
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                # Serialize page
                from apps.work_order_management.api.serializers import WomListSerializer
                serializer = WomListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            from apps.work_order_management.api.serializers import WomListSerializer
            serializer = WomListSerializer(data, many=True)
            logger.info(f"Returned {len(data)} work permits for user {request.user.id}")

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

    @action(detail=True, methods=['get'], url_path='pdf')
    def get_pdf(self, request, uuid=None):
        """
        Get work permit PDF URL.

        Replaces legacy query: get_pdf_url

        Returns:
            {
                "url": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'wom_uuid': uuid,
                'peopleid': request.user.id
            }
            validated = WomPdfUrlSchema(**filter_data)

            # Generate PDF and get URL
            pdf_url = self.service.generate_pdf_url(
                wom_uuid=validated.wom_uuid,
                user_id=validated.peopleid
            )

            logger.info(f"Generated PDF for work permit {uuid}")

            return Response({
                'url': pdf_url
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Work permit not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (IOError, OSError) as e:
            logger.error(f"PDF generation error: {e}", exc_info=True)
            return Response(
                {'error': 'PDF generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, uuid=None):
        """
        Approve work permit.

        Replaces legacy mutation handler: get_approve_workpermit

        Request Body:
            {
                "identifier": "APPROVER" or "VERIFIER"
            }

        Returns:
            {
                "success": true,
                "message": "Work permit approved successfully"
            }
        """
        try:
            # Check permission
            if not request.user.has_perm('work_order_management.can_approve_work_permits'):
                raise PermissionDenied("User does not have approval permission")

            # Validate parameters
            filter_data = {
                'peopleid': request.user.id,
                'identifier': request.data.get('identifier'),
                'wom_uuid': uuid
            }
            validated = ApproveWorkpermitSchema(**filter_data)

            # Process approval
            result = self.service.approve_work_permit(
                wom_uuid=validated.wom_uuid,
                people_id=validated.peopleid,
                identifier=validated.identifier
            )

            logger.info(
                f"Work permit {uuid} approved by user {request.user.id} "
                f"as {validated.identifier}"
            )

            return Response({
                'success': True,
                'message': result.get('message', 'Work permit approved successfully')
            })

        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Work permit not found'},
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
                {'error': 'Approval failed due to database error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, uuid=None):
        """
        Reject work permit.

        Replaces legacy mutation handler: get_reject_workpermit

        Request Body:
            {
                "identifier": "APPROVER" or "VERIFIER",
                "reason": "Rejection reason (optional)"
            }

        Returns:
            {
                "success": true,
                "message": "Work permit rejected"
            }
        """
        try:
            # Check permission
            if not request.user.has_perm('work_order_management.can_approve_work_permits'):
                raise PermissionDenied("User does not have rejection permission")

            # Validate parameters
            filter_data = {
                'peopleid': request.user.id,
                'identifier': request.data.get('identifier'),
                'wom_uuid': uuid
            }
            validated = RejectWorkpermitSchema(**filter_data)

            # Process rejection
            reason = request.data.get('reason', '')
            result = self.service.reject_work_permit(
                wom_uuid=validated.wom_uuid,
                people_id=validated.peopleid,
                identifier=validated.identifier,
                reason=reason
            )

            logger.info(
                f"Work permit {uuid} rejected by user {request.user.id} "
                f"as {validated.identifier}"
            )

            return Response({
                'success': True,
                'message': result.get('message', 'Work permit rejected')
            })

        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Work permit not found'},
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
                {'error': 'Rejection failed due to database error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='approvers')
    def approvers(self, request):
        """
        Get list of approvers for a business unit.

        Replaces legacy query: get_approvers

        Query Params:
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
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid'))
            }
            validated = ApproverSchema(**filter_data)

            # Get approvers
            data = Approver.objects.get_approver_list_for_mobile(
                validated.buid,
                validated.clientid
            )

            from apps.work_order_management.api.serializers import ApproverSerializer
            serializer = ApproverSerializer(data, many=True)
            logger.info(f"Returned {len(data)} approvers")

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

    @action(detail=False, methods=['get'], url_path='vendors')
    def vendors(self, request):
        """
        Get list of vendors.

        Replaces legacy query: get_vendors

        Query Params:
            clientid (int): Client ID
            mdtz (str): Modification timestamp
            buid (int): Business unit ID
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
                'clientid': int(request.query_params.get('clientid')),
                'mdtz': request.query_params.get('mdtz'),
                'buid': int(request.query_params.get('buid')),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0))
            }
            validated = VendorSchema(**filter_data)

            # Get vendors
            data = Vendor.objects.get_vendors_for_mobile(
                request,
                buid=validated.buid,
                mdtz=validated.mdtz,
                ctzoffset=validated.ctzoffset,
                clientid=validated.clientid,
            )

            from apps.work_order_management.api.serializers import VendorSerializer
            serializer = VendorSerializer(data, many=True)
            logger.info(f"Returned {len(data)} vendors")

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


__all__ = ['WorkPermitViewSet']
