"""
NOC Saved View Configuration Views.

REST API endpoints for managing saved dashboard views.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #17 (transactions).
"""

import logging
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.noc.models import NOCSavedView
from apps.noc.serializers import (
    NOCSavedViewSerializer,
    NOCSavedViewListSerializer,
    ViewShareSerializer,
)
from apps.noc.services import NOCViewService
from apps.noc.decorators import require_noc_capability, audit_noc_access
from apps.noc.views.utils import error_response
from apps.core.utils_new.db_utils import get_current_db_name

__all__ = [
    'NOCSavedViewListCreateView',
    'NOCSavedViewDetailView',
    'set_default_view',
    'share_view',
    'clone_view',
]

logger = logging.getLogger('noc.views.view_config')


class NOCSavedViewListCreateView(ListCreateAPIView):
    """List user's saved views or create new view."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NOCSavedViewSerializer
        return NOCSavedViewListSerializer

    @require_noc_capability('noc:view')
    def get_queryset(self):
        """Get user's accessible views (owned + shared)."""
        return NOCViewService.get_user_views(self.request.user)

    @require_noc_capability('noc:configure')
    @audit_noc_access('saved_view')
    def post(self, request, *args, **kwargs):
        """Create new saved view."""
        try:
            with transaction.atomic(using=get_current_db_name()):
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)

                view = serializer.save(
                    tenant=request.user.tenant,
                    user=request.user
                )

                if request.data.get('is_default'):
                    NOCViewService.set_default_view(
                        request.user,
                        view.id
                    )

                logger.info(
                    f"Created saved view",
                    extra={'user_id': request.user.id, 'view_id': view.id}
                )

                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED
                )

        except (ValueError, TypeError) as e:
            logger.error(
                f"Error creating view: {e}",
                extra={'user_id': request.user.id}
            )
            return error_response(
                "Failed to create view",
                {'detail': str(e)}
            )


class NOCSavedViewDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a saved view."""

    serializer_class = NOCSavedViewSerializer
    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get_queryset(self):
        """Get user's accessible views."""
        return NOCViewService.get_user_views(self.request.user)

    @require_noc_capability('noc:configure')
    @audit_noc_access('saved_view')
    def update(self, request, *args, **kwargs):
        """Update saved view."""
        try:
            with transaction.atomic(using=get_current_db_name()):
                instance = self.get_object()

                if instance.user_id != request.user.id:
                    return error_response(
                        "Cannot modify shared view",
                        status_code=status.HTTP_403_FORBIDDEN
                    )

                instance.increment_version()

                serializer = self.get_serializer(
                    instance,
                    data=request.data,
                    partial=kwargs.get('partial', False)
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()

                return Response(serializer.data)

        except (ValueError, TypeError) as e:
            logger.error(
                f"Error updating view: {e}",
                extra={'user_id': request.user.id}
            )
            return error_response(
                "Failed to update view",
                {'detail': str(e)}
            )

    @require_noc_capability('noc:configure')
    def destroy(self, request, *args, **kwargs):
        """Delete saved view."""
        try:
            instance = self.get_object()

            if instance.user_id != request.user.id:
                return error_response(
                    "Cannot delete shared view",
                    status_code=status.HTTP_403_FORBIDDEN
                )

            view_id = instance.id
            instance.delete()

            logger.info(
                f"Deleted saved view",
                extra={'user_id': request.user.id, 'view_id': view_id}
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except (ValueError, TypeError) as e:
            logger.error(
                f"Error deleting view: {e}",
                extra={'user_id': request.user.id}
            )
            return error_response(
                "Failed to delete view",
                {'detail': str(e)}
            )


@api_view(['POST'])
@require_noc_capability('noc:configure')
@audit_noc_access('saved_view')
def set_default_view(request, pk):
    """Set a view as user's default."""
    try:
        view = NOCViewService.set_default_view(request.user, pk)

        return Response({
            'status': 'success',
            'message': f"Set '{view.name}' as default view",
            'view_id': view.id
        })

    except NOCSavedView.DoesNotExist:
        return error_response(
            "View not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Error setting default view: {e}",
            extra={'user_id': request.user.id, 'view_id': pk}
        )
        return error_response(
            "Failed to set default view",
            {'detail': str(e)}
        )


@api_view(['POST'])
@require_noc_capability('noc:configure')
@audit_noc_access('saved_view')
def share_view(request, pk):
    """Share view with other users."""
    try:
        view = NOCSavedView.objects.get(
            id=pk,
            tenant=request.user.tenant,
            user=request.user
        )

        serializer = ViewShareSerializer(
            data=request.data,
            context={'view': view}
        )
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data['user_ids']
        action = serializer.validated_data.get('action', 'share')

        if action == 'share':
            success = NOCViewService.share_view(view, user_ids)
            message = f"Shared view with {len(user_ids)} users"
        else:
            success = NOCViewService.unshare_view(view, user_ids)
            message = f"Unshared view from {len(user_ids)} users"

        if success:
            return Response({
                'status': 'success',
                'message': message
            })
        else:
            return error_response("Failed to update sharing")

    except NOCSavedView.DoesNotExist:
        return error_response(
            "View not found or not owned by user",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Error sharing view: {e}",
            extra={'user_id': request.user.id, 'view_id': pk}
        )
        return error_response(
            "Failed to share view",
            {'detail': str(e)}
        )


@api_view(['POST'])
@require_noc_capability('noc:view')
@audit_noc_access('saved_view')
def clone_view(request, pk):
    """Clone an existing view."""
    try:
        source_view = NOCSavedView.objects.get(
            id=pk,
            tenant=request.user.tenant
        )

        if not (source_view.user_id == request.user.id or
                source_view.is_shared and
                request.user in source_view.shared_with.all()):
            return error_response(
                "View not accessible",
                status_code=status.HTTP_403_FORBIDDEN
            )

        new_name = request.data.get('name')
        if not new_name:
            return error_response(
                "Name required for cloned view",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        cloned_view = NOCViewService.clone_view(
            source_view,
            new_name,
            request.user
        )

        serializer = NOCSavedViewSerializer(cloned_view)

        return Response({
            'status': 'success',
            'message': f"Cloned view as '{new_name}'",
            'view': serializer.data
        }, status=status.HTTP_201_CREATED)

    except NOCSavedView.DoesNotExist:
        return error_response(
            "View not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Error cloning view: {e}",
            extra={'user_id': request.user.id, 'view_id': pk}
        )
        return error_response(
            "Failed to clone view",
            {'detail': str(e)}
        )