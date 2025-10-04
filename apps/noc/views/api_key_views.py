"""
NOC API Key Management Views.

REST API endpoints for managing NOC API keys.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #17 (transactions).
"""

import logging
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringAPIAccessLog
from apps.noc.serializers import (
    NOCAPIKeySerializer,
    NOCAPIKeyCreateSerializer,
    APIKeyUsageSerializer,
)
from apps.noc.decorators import require_noc_capability, audit_noc_access
from apps.noc.views.utils import error_response
from apps.core.utils_new.db_utils import get_current_db_name

__all__ = [
    'NOCAPIKeyListCreateView',
    'NOCAPIKeyDetailView',
    'rotate_api_key',
    'api_key_usage_stats',
]

logger = logging.getLogger('noc.views.api_key')


class NOCAPIKeyListCreateView(ListCreateAPIView):
    """List user's NOC API keys or create new key."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NOCAPIKeyCreateSerializer
        return NOCAPIKeySerializer

    @require_noc_capability('noc:configure')
    def get_queryset(self):
        """Get user's NOC API keys."""
        return MonitoringAPIKey.objects.filter(
            created_by=self.request.user,
            monitoring_system__in=['custom', 'prometheus', 'grafana']
        ).order_by('-created_at')

    @require_noc_capability('noc:configure')
    @audit_noc_access('api_key')
    def post(self, request, *args, **kwargs):
        """Create new NOC API key."""
        try:
            with transaction.atomic(using=get_current_db_name()):
                serializer = self.get_serializer(
                    data=request.data,
                    context={'request': request}
                )
                serializer.is_valid(raise_exception=True)

                api_key_instance = serializer.save()

                raw_api_key = api_key_instance.raw_api_key

                response_data = NOCAPIKeySerializer(api_key_instance).data
                response_data['api_key'] = raw_api_key

                logger.info(
                    f"Created NOC API key",
                    extra={
                        'user_id': request.user.id,
                        'key_id': api_key_instance.id
                    }
                )

                return Response({
                    'status': 'success',
                    'message': 'API key created successfully. '
                               'Save the key securely - it cannot be retrieved again.',
                    'data': response_data
                }, status=status.HTTP_201_CREATED)

        except (ValueError, TypeError) as e:
            logger.error(
                f"Error creating API key: {e}",
                extra={'user_id': request.user.id}
            )
            return error_response(
                "Failed to create API key",
                {'detail': str(e)}
            )


class NOCAPIKeyDetailView(RetrieveDestroyAPIView):
    """Retrieve or revoke (delete) an API key."""

    serializer_class = NOCAPIKeySerializer
    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:configure')
    def get_queryset(self):
        """Get user's NOC API keys."""
        return MonitoringAPIKey.objects.filter(
            created_by=self.request.user
        )

    @require_noc_capability('noc:configure')
    @audit_noc_access('api_key')
    def destroy(self, request, *args, **kwargs):
        """Revoke (delete) an API key."""
        try:
            instance = self.get_object()
            key_id = instance.id
            key_name = instance.name

            instance.is_active = False
            instance.save(update_fields=['is_active'])

            logger.info(
                f"Revoked API key",
                extra={'user_id': request.user.id, 'key_id': key_id}
            )

            return Response({
                'status': 'success',
                'message': f"API key '{key_name}' has been revoked"
            }, status=status.HTTP_200_OK)

        except (ValueError, TypeError) as e:
            logger.error(
                f"Error revoking API key: {e}",
                extra={'user_id': request.user.id}
            )
            return error_response(
                "Failed to revoke API key",
                {'detail': str(e)}
            )


@api_view(['POST'])
@require_noc_capability('noc:configure')
@audit_noc_access('api_key')
def rotate_api_key(request, pk):
    """Rotate an API key (create new key, deprecate old)."""
    try:
        api_key = MonitoringAPIKey.objects.get(
            id=pk,
            created_by=request.user
        )

        if not api_key.is_active:
            return error_response(
                "Cannot rotate inactive API key",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic(using=get_current_db_name()):
            new_key_instance, raw_api_key = api_key.rotate_key(
                created_by=request.user
            )

            response_data = NOCAPIKeySerializer(new_key_instance).data
            response_data['api_key'] = raw_api_key

            logger.info(
                f"Rotated API key",
                extra={
                    'user_id': request.user.id,
                    'old_key_id': pk,
                    'new_key_id': new_key_instance.id
                }
            )

            return Response({
                'status': 'success',
                'message': f"API key rotated successfully. "
                           f"Old key valid for {api_key.rotation_grace_period_hours} hours.",
                'data': response_data
            })

    except MonitoringAPIKey.DoesNotExist:
        return error_response(
            "API key not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Error rotating API key: {e}",
            extra={'user_id': request.user.id, 'key_id': pk}
        )
        return error_response(
            "Failed to rotate API key",
            {'detail': str(e)}
        )


@api_view(['GET'])
@require_noc_capability('noc:configure')
def api_key_usage_stats(request, pk):
    """Get usage statistics for an API key."""
    try:
        api_key = MonitoringAPIKey.objects.get(
            id=pk,
            created_by=request.user
        )

        days = int(request.GET.get('days', 7))

        usage_summary = MonitoringAPIAccessLog.get_usage_summary(
            api_key,
            days=days
        )

        response_data = {
            'api_key_id': api_key.id,
            'api_key_name': api_key.name,
            'total_requests': usage_summary['total_requests'],
            'unique_ips': usage_summary['unique_ips'],
            'by_endpoint': list(usage_summary['by_endpoint']),
            'by_status': list(usage_summary['by_status']),
            'avg_response_time': usage_summary['avg_response_time'],
            'error_count': usage_summary['error_count'],
            'period_days': days
        }

        serializer = APIKeyUsageSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)

        return Response({
            'status': 'success',
            'data': serializer.data
        })

    except MonitoringAPIKey.DoesNotExist:
        return error_response(
            "API key not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Error fetching usage stats: {e}",
            extra={'user_id': request.user.id, 'key_id': pk}
        )
        return error_response(
            "Failed to fetch usage statistics",
            {'detail': str(e)}
        )