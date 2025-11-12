"""
NFC REST API Views (Sprint 4.3)

REST API endpoints for NFC tag management:
- POST /api/v1/assets/nfc/bind/ - Bind tag to asset
- POST /api/v1/assets/nfc/scan/ - Record NFC scan
- GET  /api/v1/assets/nfc/history/ - Get scan history
- PUT  /api/v1/assets/nfc/status/ - Update tag status

All endpoints require authentication and tenant isolation.

Author: Development Team
Date: October 2025
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError

from apps.activity.services.nfc_service import NFCService
from .nfc_serializers import (
    NFCTagBindSerializer,
    NFCTagBindResponseSerializer,
    NFCScanSerializer,
    NFCScanResponseSerializer,
    NFCScanHistorySerializer,
    NFCScanHistoryResponseSerializer,
    NFCTagStatusUpdateSerializer,
    NFCTagStatusUpdateResponseSerializer,
)
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


class NFCTagBindView(APIView):
    """
    NFC Tag Binding API Endpoint.

    POST /api/v1/assets/nfc/bind/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Bind an NFC tag to an asset.

        Request Body (JSON):
            - tag_uid: NFC tag UID (hexadecimal)
            - asset_id: Asset ID to bind to
            - metadata: Optional metadata

        Returns:
            201: Tag bound successfully
            400: Invalid request data
            404: Asset not found
            409: Tag already bound to different asset
            500: Internal error
        """
        serializer = NFCTagBindSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get tenant from request user
            tenant_id = request.user.tenant_id

            # Bind tag using service
            nfc_service = NFCService()
            result = nfc_service.bind_tag_to_asset(
                tag_uid=data['tag_uid'],
                asset_id=data['asset_id'],
                tenant_id=tenant_id,
                metadata=data.get('metadata')
            )

            if result['success']:
                response_data = {
                    'success': True,
                    'tag_id': str(result['nfc_tag'].id) if result.get('nfc_tag') else None,
                    'tag_uid': data['tag_uid'],
                    'asset_name': result['nfc_tag'].asset.assetname if result.get('nfc_tag') else None,
                    'message': result['message']
                }

                response_serializer = NFCTagBindResponseSerializer(response_data)

                # Return 201 for new binding, 200 for existing
                http_status = status.HTTP_201_CREATED if 'already bound' not in result['message'] else status.HTTP_200_OK

                return Response(response_serializer.data, status=http_status)
            else:
                # Check error type
                if 'already bound' in result['message']:
                    http_status = status.HTTP_409_CONFLICT
                elif 'not found' in result['message']:
                    http_status = status.HTTP_404_NOT_FOUND
                else:
                    http_status = status.HTTP_400_BAD_REQUEST

                return Response(
                    {'success': False, 'message': result['message']},
                    status=http_status
                )

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Unexpected error in NFC tag binding: {e}")
            return Response(
                {'success': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NFCScanView(APIView):
    """
    NFC Tag Scanning API Endpoint.

    POST /api/v1/assets/nfc/scan/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Record an NFC tag scan.

        Request Body (JSON):
            - tag_uid: NFC tag UID
            - device_id: Device ID performing scan
            - scan_type: Type of scan (optional)
            - location_id: Location ID (optional)
            - metadata: Scan metadata (optional)

        Returns:
            200: Scan recorded successfully
            400: Invalid request data
            404: Tag or device not found
            500: Internal error
        """
        serializer = NFCScanSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get tenant from request user
            tenant_id = request.user.tenant_id

            # Record scan using service
            nfc_service = NFCService()
            result = nfc_service.record_nfc_scan(
                tag_uid=data['tag_uid'],
                device_id=data['device_id'],
                tenant_id=tenant_id,
                scanned_by_id=request.user.id,
                scan_type=data.get('scan_type', 'INSPECTION'),
                location_id=data.get('location_id'),
                metadata=data.get('metadata')
            )

            if result['success']:
                response_data = {
                    'success': True,
                    'scan_id': result['scan_log'].id if result.get('scan_log') else None,
                    'asset': result.get('asset'),
                    'scan_result': result.get('scan_result', 'SUCCESS'),
                    'message': result['message'],
                    'scan_time': result['scan_log'].cdtz.isoformat() if result.get('scan_log') else None
                }

                response_serializer = NFCScanResponseSerializer(response_data)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                # Determine HTTP status based on error
                if 'not found' in result['message']:
                    http_status = status.HTTP_404_NOT_FOUND
                else:
                    http_status = status.HTTP_400_BAD_REQUEST

                return Response(
                    {
                        'success': False,
                        'scan_result': result.get('scan_result', 'FAILED'),
                        'message': result['message']
                    },
                    status=http_status
                )

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Unexpected error recording NFC scan: {e}")
            return Response(
                {'success': False, 'scan_result': 'FAILED', 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NFCScanHistoryView(APIView):
    """
    NFC Scan History API Endpoint.

    GET /api/v1/assets/nfc/history/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get NFC scan history.

        Query Parameters:
            - tag_uid: Filter by tag UID (optional)
            - asset_id: Filter by asset ID (optional)
            - days: Days to look back (default: 30)

        Returns:
            200: Scan history
            400: Invalid query parameters
            500: Internal error
        """
        serializer = NFCScanHistorySerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get tenant from request user
            tenant_id = request.user.tenant_id

            # Get scan history using service
            nfc_service = NFCService()
            result = nfc_service.get_scan_history(
                tag_uid=data.get('tag_uid'),
                asset_id=data.get('asset_id'),
                tenant_id=tenant_id,
                days=data.get('days', 30)
            )

            response_serializer = NFCScanHistoryResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Error retrieving NFC scan history: {e}")
            return Response(
                {'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NFCTagStatusView(APIView):
    """
    NFC Tag Status Update API Endpoint.

    PUT /api/v1/assets/nfc/status/
    """

    permission_classes = [IsAuthenticated]

    def put(self, request):
        """
        Update NFC tag status.

        Request Body (JSON):
            - tag_uid: NFC tag UID
            - status: New status (ACTIVE, INACTIVE, DAMAGED, LOST, DECOMMISSIONED)

        Returns:
            200: Status updated successfully
            400: Invalid request data
            404: Tag not found
            500: Internal error
        """
        serializer = NFCTagStatusUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get tenant from request user
            tenant_id = request.user.tenant_id

            # Update status using service
            nfc_service = NFCService()
            result = nfc_service.update_tag_status(
                tag_uid=data['tag_uid'],
                new_status=data['status'],
                tenant_id=tenant_id
            )

            if result['success']:
                response_serializer = NFCTagStatusUpdateResponseSerializer(result)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                http_status = status.HTTP_404_NOT_FOUND if 'not found' in result['message'] else status.HTTP_400_BAD_REQUEST

                return Response(
                    {'success': False, 'message': result['message']},
                    status=http_status
                )

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Error updating NFC tag status: {e}")
            return Response(
                {'success': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
