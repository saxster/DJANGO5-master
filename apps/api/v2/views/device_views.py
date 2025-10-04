"""API v2 Device Management Views."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.services.cross_device_sync_service import cross_device_sync_service


class DeviceListView(APIView):
    """List user's devices."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's devices."""
        devices = cross_device_sync_service.get_user_devices(request.user)

        return Response({
            'devices': [{
                'device_id': d.device_id,
                'device_type': d.device_type,
                'priority': d.priority,
                'last_seen': d.last_seen.isoformat(),
                'is_active': d.is_active
            } for d in devices]
        })


class DeviceRegisterView(APIView):
    """Register new device."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Register device."""
        device = cross_device_sync_service.register_device(
            user=request.user,
            device_id=request.data.get('device_id'),
            device_type=request.data.get('device_type'),
            device_name=request.data.get('device_name', ''),
            os_type=request.data.get('os_type', ''),
            os_version=request.data.get('os_version', ''),
            app_version=request.data.get('app_version', '')
        )

        return Response({
            'device_id': device.device_id,
            'priority': device.priority,
            'status': 'registered'
        })


class DeviceDetailView(APIView):
    """Device details."""

    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        """Get device details."""
        return Response({'device_id': device_id})

    def delete(self, request, device_id):
        """Deactivate device."""
        success = cross_device_sync_service.deactivate_device(device_id)

        return Response({'deactivated': success})


class DeviceSyncStateView(APIView):
    """Device sync state."""

    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        """Get sync state for device."""
        return Response({'device_id': device_id, 'sync_state': []})