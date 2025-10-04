"""
NOC Maintenance Window Views.

REST API endpoints for managing maintenance windows.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #17 (transaction management).
"""

import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction, DatabaseError
from apps.core.utils_new.db_utils import get_current_db_name
from apps.noc.decorators import require_noc_capability
from apps.noc.models import MaintenanceWindow
from apps.noc.serializers import MaintenanceWindowSerializer, MaintenanceWindowCreateSerializer
from apps.noc.services import NOCRBACService
from .utils import paginated_response, success_response, error_response
from .permissions import CanManageMaintenance

__all__ = ['MaintenanceWindowListCreateView', 'MaintenanceWindowDetailView']

logger = logging.getLogger('noc.views.maintenance')


class MaintenanceWindowListCreateView(APIView):
    """List maintenance windows or create new window."""

    permission_classes = [IsAuthenticated, CanManageMaintenance]

    @require_noc_capability('noc:manage_maintenance')
    def get(self, request):
        """Get list of maintenance windows."""
        try:
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            queryset = MaintenanceWindow.objects.filter(
                client__in=allowed_clients
            ).select_related('client', 'bu', 'created_by')

            return paginated_response(queryset, MaintenanceWindowSerializer, request)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error fetching maintenance windows", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to fetch maintenance windows", {'detail': str(e)})

    @require_noc_capability('noc:manage_maintenance')
    def post(self, request):
        """Create maintenance window."""
        try:
            serializer = MaintenanceWindowCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Invalid data", serializer.errors)

            with transaction.atomic(using=get_current_db_name()):
                window = MaintenanceWindow.objects.create(
                    tenant=request.user.tenant,
                    client_id=serializer.validated_data.get('client_id'),
                    bu_id=serializer.validated_data.get('bu_id'),
                    start_time=serializer.validated_data['start_time'],
                    end_time=serializer.validated_data['end_time'],
                    suppress_alerts=serializer.validated_data.get('suppress_alerts', []),
                    reason=serializer.validated_data['reason'],
                    created_by=request.user
                )

            response_serializer = MaintenanceWindowSerializer(window, context={'user': request.user})
            return success_response(response_serializer.data, status_code=status.HTTP_201_CREATED)

        except (ValueError, DatabaseError) as e:
            logger.error(f"Error creating maintenance window", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to create maintenance window", {'detail': str(e)})


class MaintenanceWindowDetailView(APIView):
    """Delete maintenance window."""

    permission_classes = [IsAuthenticated, CanManageMaintenance]

    @require_noc_capability('noc:manage_maintenance')
    def delete(self, request, pk):
        """Delete maintenance window."""
        try:
            with transaction.atomic(using=get_current_db_name()):
                window = MaintenanceWindow.objects.get(id=pk, tenant=request.user.tenant)
                window.delete()

            return success_response({'message': 'Maintenance window deleted'}, status_code=status.HTTP_204_NO_CONTENT)

        except MaintenanceWindow.DoesNotExist:
            return error_response("Maintenance window not found", status_code=status.HTTP_404_NOT_FOUND)
        except (ValueError, DatabaseError) as e:
            logger.error(f"Error deleting maintenance window", extra={'error': str(e), 'window_id': pk})
            return error_response("Failed to delete maintenance window", {'detail': str(e)})