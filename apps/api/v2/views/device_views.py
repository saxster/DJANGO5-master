"""
API v2 Device Management Views

Type-safe device management with Pydantic validation.

Compliance with .claude/rules.md:
- Rule #7: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ObjectDoesNotExist
import logging

from apps.core.services.cross_device_sync_service import cross_device_sync_service
from apps.api.v2.serializers import (
    DeviceListResponseSerializer,
    DeviceRegisterRequestSerializer,
    DeviceRegisterResponseSerializer,
    DeviceSyncStateResponseSerializer,
)
from apps.core.api_responses import (
    create_success_response,
    create_error_response,
    APIError,
)

logger = logging.getLogger('api.v2.devices')


class DeviceListView(APIView):
    """
    List user's devices with type-safe response.

    GET /api/v2/devices/
    - Returns list of devices belonging to authenticated user
    - Response validated via DeviceListResponseSerializer
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's devices."""
        devices = cross_device_sync_service.get_user_devices(request.user)

        # Map Django model to Pydantic contract
        response_data = {
            'devices': [{
                'device_id': d.device_id,
                'device_type': d.device_type,
                'priority': d.priority,
                'device_name': d.device_name,
                'os_type': d.os_type,
                'os_version': d.os_version,
                'app_version': d.app_version,
                'last_seen': d.last_seen,
                'is_active': d.is_active
            } for d in devices]
        }

        # Validate response against contract
        response_serializer = DeviceListResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)

        return Response(create_success_response(response_serializer.data))


class DeviceRegisterView(APIView):
    """
    Register new device with type-safe validation.

    POST /api/v2/devices/register/
    - Validates request using DeviceRegisterRequestSerializer
    - Returns registration result with assigned priority
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Register device."""
        # ✅ Type-safe validation using Pydantic-backed serializer
        serializer = DeviceRegisterRequestSerializer(data=request.data)
        if not serializer.is_valid():
            # Convert DRF errors to standard APIError format
            api_errors = []
            for field, messages in serializer.errors.items():
                for message in (messages if isinstance(messages, list) else [messages]):
                    api_errors.append(APIError(
                        field=field,
                        message=str(message),
                        code='VALIDATION_ERROR'
                    ))
            return Response(
                create_error_response(api_errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data

        # Register device via service
        try:
            device = cross_device_sync_service.register_device(
                user=request.user,
                device_id=validated_data['device_id'],
                device_type=validated_data['device_type'],
                device_name=validated_data.get('device_name', ''),
                os_type=validated_data.get('os_type', ''),
                os_version=validated_data.get('os_version', ''),
                app_version=validated_data.get('app_version', '')
            )

            # Map to response contract
            response_data = {
                'device_id': device.device_id,
                'priority': device.priority,
                'status': 'registered' if device.created_at == device.updated_at else 'updated'
            }

            # Validate response against contract
            response_serializer = DeviceRegisterResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)

            return Response(create_success_response(response_serializer.data))

        except Exception as e:
            logger.error(f"Device registration failed: {e}", exc_info=True)
            return Response(
                create_error_response([APIError(
                    field='device_id',
                    message=f"Registration failed: {str(e)}",
                    code='REGISTRATION_ERROR'
                )]),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeviceDetailView(APIView):
    """
    Device details and management.

    GET /api/v2/devices/{device_id}/
    - Returns device information

    DELETE /api/v2/devices/{device_id}/
    - Deactivates device
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        """Get device details."""
        try:
            device = cross_device_sync_service.get_device_by_id(device_id)

            response_data = {
                'device_id': device.device_id,
                'device_type': device.device_type,
                'priority': device.priority,
                'device_name': device.device_name,
                'os_type': device.os_type,
                'os_version': device.os_version,
                'app_version': device.app_version,
                'last_seen': device.last_seen,
                'is_active': device.is_active
            }

            return Response(create_success_response(response_data))

        except ObjectDoesNotExist:
            return Response(
                create_error_response([APIError(
                    field='device_id',
                    message='Device not found',
                    code='NOT_FOUND'
                )]),
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, device_id):
        """Deactivate device."""
        try:
            success = cross_device_sync_service.deactivate_device(device_id)

            return Response(create_success_response({
                'device_id': device_id,
                'deactivated': success
            }))

        except Exception as e:
            logger.error(f"Device deactivation failed: {e}", exc_info=True)
            return Response(
                create_error_response([APIError(
                    field='device_id',
                    message=f"Deactivation failed: {str(e)}",
                    code='DEACTIVATION_ERROR'
                )]),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeviceSyncStateView(APIView):
    """
    Device sync state with type-safe response.

    GET /api/v2/devices/{device_id}/sync-state/
    - Returns sync state for all domains on the device
    - Response validated via DeviceSyncStateResponseSerializer
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        """Get sync state for device."""
        try:
            # Get sync states from service
            sync_states = cross_device_sync_service.get_device_sync_states(device_id)

            # Map to response contract
            response_data = {
                'device_id': device_id,
                'sync_state': [{
                    'domain': state.domain,
                    'last_sync_version': state.last_sync_version,
                    'last_sync_timestamp': state.last_sync_timestamp
                } for state in sync_states]
            }

            # Validate response against contract
            response_serializer = DeviceSyncStateResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)

            return Response(create_success_response(response_serializer.data))

        except ObjectDoesNotExist:
            return Response(
                create_error_response([APIError(
                    field='device_id',
                    message='Device not found',
                    code='NOT_FOUND'
                )]),
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to get sync state: {e}", exc_info=True)
            return Response(
                create_error_response([APIError(
                    field='device_id',
                    message=f"Failed to retrieve sync state: {str(e)}",
                    code='SYNC_STATE_ERROR'
                )]),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )