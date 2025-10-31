"""
Saved Views API
===============
REST API for creating, retrieving, and managing saved dashboard views.

Endpoints:
- GET /api/v1/saved-views/ - List user's saved views
- POST /api/v1/saved-views/ - Create new saved view
- GET /api/v1/saved-views/{id}/ - Get specific saved view
- PUT /api/v1/saved-views/{id}/ - Update saved view
- DELETE /api/v1/saved-views/{id}/ - Delete saved view
- POST /api/v1/saved-views/{id}/set-default/ - Set as default view

Follows .claude/rules.md:
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from pydantic import ValidationError as PydanticValidationError

from apps.core.models import DashboardSavedView
from apps.core.serializers.scope_serializers import (
    SavedViewCreate,
    SavedViewResponse,
    SavedViewListResponse,
)

logger = logging.getLogger(__name__)


class SavedViewsListCreateView(LoginRequiredMixin, View):
    """List and create saved views"""

    def get(self, request):
        """List user's accessible saved views"""
        try:
            # Get views created by user
            own_views = DashboardSavedView.objects.filter(
                cuser=request.user
            ).select_related("cuser")

            # Get shared views
            shared_views = DashboardSavedView.objects.filter(
                tenant=request.user.tenant
            ).exclude(
                cuser=request.user
            ).select_related("cuser")

            # Filter shared views by access permissions
            accessible_views = [
                v for v in shared_views if v.can_user_access(request.user)
            ]

            # Combine and serialize
            all_views = list(own_views) + accessible_views
            serialized = [self._serialize_view(v) for v in all_views]

            response = SavedViewListResponse(
                views=serialized,
                count=len(serialized)
            )

            return JsonResponse(response.model_dump(), safe=False)

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error listing saved views: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)

    def post(self, request):
        """Create new saved view"""
        try:
            body = json.loads(request.body)

            # Validate with Pydantic
            try:
                view_data = SavedViewCreate(**body)
            except PydanticValidationError as e:
                return JsonResponse({"error": "Validation error", "details": e.errors()}, status=400)

            # Create saved view
            saved_view = DashboardSavedView.objects.create(
                name=view_data.name,
                description=view_data.description,
                view_type=view_data.view_type,
                scope_config=view_data.scope_config.model_dump(),
                filters=view_data.filters,
                visible_panels=view_data.visible_panels,
                sort_order=view_data.sort_order,
                sharing_level=view_data.sharing_level,
                page_url=view_data.page_url,
                tenant=request.user.tenant,
                cuser=request.user
            )

            logger.info(f"User {request.user.id} created saved view: {saved_view.name}")

            # Serialize response
            serialized = self._serialize_view(saved_view)
            return JsonResponse(serialized.model_dump(), status=201)

        except json.JSONDecodeError as e:
            return JsonResponse({"error": "Invalid JSON", "message": str(e)}, status=400)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error creating saved view: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)

    def _serialize_view(self, view: DashboardSavedView) -> SavedViewResponse:
        """Serialize saved view to Pydantic model"""
        return SavedViewResponse(
            id=view.id,
            name=view.name,
            description=view.description,
            view_type=view.view_type,
            scope_config=ScopeConfig(**view.scope_config),
            filters=view.filters,
            visible_panels=view.visible_panels,
            sort_order=view.sort_order,
            sharing_level=view.sharing_level,
            is_default=view.is_default,
            view_count=view.view_count,
            created_by_username=view.cuser.username,
            created_at=view.cdtz.isoformat() if view.cdtz else "",
            last_accessed_at=view.last_accessed_at.isoformat() if view.last_accessed_at else None
        )


class SavedViewDetailView(LoginRequiredMixin, View):
    """Get, update, or delete a specific saved view"""

    def get(self, request, view_id):
        """Get saved view details"""
        try:
            view = DashboardSavedView.objects.select_related("cuser").get(
                id=view_id,
                tenant=request.user.tenant
            )

            # Check access
            if not view.can_user_access(request.user):
                raise PermissionDenied("You don't have access to this view")

            # Update access tracking
            view.view_count += 1
            view.last_accessed_at = timezone.now()
            view.save(update_fields=["view_count", "last_accessed_at"])

            # Serialize
            serialized = SavedViewsListCreateView()._serialize_view(view)
            return JsonResponse(serialized.model_dump())

        except ObjectDoesNotExist:
            return JsonResponse({"error": "View not found"}, status=404)
        except PermissionDenied as e:
            return JsonResponse({"error": str(e)}, status=403)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error retrieving saved view: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)

    def delete(self, request, view_id):
        """Delete saved view (owner only)"""
        try:
            view = DashboardSavedView.objects.get(
                id=view_id,
                cuser=request.user,  # Only owner can delete
                tenant=request.user.tenant
            )

            view_name = view.name
            view.delete()

            logger.info(f"User {request.user.id} deleted saved view: {view_name}")

            return JsonResponse({"message": "View deleted successfully"}, status=200)

        except ObjectDoesNotExist:
            return JsonResponse({"error": "View not found or access denied"}, status=404)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error deleting saved view: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class SetDefaultViewView(LoginRequiredMixin, View):
    """Set a saved view as default"""

    def post(self, request, view_id):
        """Set view as default (unsets others)"""
        try:
            view = DashboardSavedView.objects.get(
                id=view_id,
                tenant=request.user.tenant
            )

            if not view.can_user_access(request.user):
                raise PermissionDenied("You don't have access to this view")

            # Unset other defaults for this user
            DashboardSavedView.objects.filter(
                cuser=request.user,
                is_default=True
            ).update(is_default=False)

            # Set this view as default
            view.is_default = True
            view.save(update_fields=["is_default"])

            logger.info(f"User {request.user.id} set default view: {view.name}")

            return JsonResponse({"message": "Default view updated"}, status=200)

        except ObjectDoesNotExist:
            return JsonResponse({"error": "View not found"}, status=404)
        except PermissionDenied as e:
            return JsonResponse({"error": str(e)}, status=403)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error setting default view: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


__all__ = [
    "SavedViewsListCreateView",
    "SavedViewDetailView",
    "SetDefaultViewView",
]
