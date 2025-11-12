"""
Scope API Views
===============
REST API endpoints for managing user scope and context.

Endpoints:
- GET /api/v1/scope/current/ - Get current user scope
- POST /api/v1/scope/update/ - Update user scope
- GET /api/v1/scope/options/ - Get available options (clients, sites, shifts)

Follows .claude/rules.md:
- Rule #7: Service layer for business logic
- Rule #11: Specific exception handling
- Rule #14: No SQL injection via parameterized queries
"""

import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from pydantic import ValidationError as PydanticValidationError

from apps.core.models import UserScope
from apps.core.serializers.scope_serializers import (
    ScopeConfig,
    ScopeUpdateRequest,
    ScopeResponse,
)
from apps.client_onboarding.models import Bt, Shift
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class CurrentScopeView(LoginRequiredMixin, View):
    """
    GET /api/v1/scope/current/

    Returns the current user's scope configuration.
    Creates default scope if none exists.
    """

    def get(self, request, *args, **kwargs):
        try:
            # Get or create user scope
            user_scope, created = UserScope.objects.get_or_create(
                user=request.user,
                tenant=request.user.tenant,
                defaults={
                    "selected_clients": [request.user.client_id] if request.user.client_id else [],
                    "selected_sites": [request.user.bu_id] if request.user.bu_id else [],
                    "time_range": "TODAY",
                }
            )

            if created:
                logger.info(f"Created default scope for user {request.user.id}")

            # Build response
            scope_dict = user_scope.get_scope_dict()
            response_data = {
                "scope": scope_dict,
                "user_id": request.user.id,
                "last_updated": user_scope.mdtz.isoformat() if user_scope.mdtz else timezone.now().isoformat()
            }

            # Validate with Pydantic
            validated = ScopeResponse(**response_data)

            return JsonResponse(validated.model_dump(), safe=False)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error fetching scope: {e}", exc_info=True)
            return JsonResponse(
                {"error": "Database error", "message": "Could not retrieve scope"},
                status=500
            )


class UpdateScopeView(LoginRequiredMixin, View):
    """
    POST /api/v1/scope/update/

    Updates the user's scope configuration.
    Validates input with Pydantic schema.
    """

    def post(self, request, *args, **kwargs):
        try:
            # Parse request body
            body = json.loads(request.body)

            # Validate with Pydantic
            try:
                scope_update = ScopeUpdateRequest(**body)
            except PydanticValidationError as e:
                return JsonResponse(
                    {"error": "Validation error", "details": e.errors()},
                    status=400
                )

            # Get or create user scope
            user_scope, created = UserScope.objects.get_or_create(
                user=request.user,
                tenant=request.user.tenant
            )

            # Update from validated data
            scope_data = scope_update.scope.model_dump()
            user_scope.update_from_dict(scope_data)

            logger.info(
                f"User {request.user.id} updated scope: "
                f"clients={scope_data.get('client_ids')}, "
                f"sites={scope_data.get('bu_ids')}"
            )

            # Return updated scope
            response_data = {
                "scope": user_scope.get_scope_dict(),
                "user_id": request.user.id,
                "last_updated": user_scope.mdtz.isoformat()
            }

            validated = ScopeResponse(**response_data)
            return JsonResponse(validated.model_dump(), safe=False)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in scope update: {e}")
            return JsonResponse(
                {"error": "Invalid JSON", "message": str(e)},
                status=400
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error updating scope: {e}", exc_info=True)
            return JsonResponse(
                {"error": "Database error", "message": "Could not update scope"},
                status=500
            )


class ScopeOptionsView(LoginRequiredMixin, View):
    """
    GET /api/v1/scope/options/

    Returns available options for scope selectors based on user permissions.
    Uses tenant-aware filtering and RBAC.
    """

    def get(self, request, *args, **kwargs):
        try:
            user = request.user

            # Get available clients (based on user's tenant and permissions)
            if user.is_superuser:
                available_clients = Bt.objects.filter(
                    tenant=user.tenant,
                    btype="C"  # Client type
                ).values("id", "buname", "tenant_id")
            else:
                # Filter by user's client
                available_clients = Bt.objects.filter(
                    tenant=user.tenant,
                    id=user.client_id,
                    btype="C"
                ).values("id", "buname", "tenant_id")

            # Get available sites/BUs (based on selected clients or user's access)
            if user.is_superuser:
                available_sites = Bt.objects.filter(
                    tenant=user.tenant,
                    btype="B"  # Business Unit/Site type
                ).values("id", "buname", "client_id", "tenant_id")
            else:
                # Filter by user's client
                available_sites = Bt.objects.filter(
                    tenant=user.tenant,
                    client_id=user.client_id,
                    btype="B"
                ).values("id", "buname", "client_id", "tenant_id")

            # Get available shifts
            available_shifts = Shift.objects.filter(
                tenant=user.tenant,
                client=user.client
            ).values("id", "shiftname", "starttime", "endtime")

            response_data = {
                "tenant": {
                    "id": user.tenant_id,
                    "name": user.tenant.name if user.tenant else "Unknown"
                },
                "clients": list(available_clients),
                "sites": list(available_sites),
                "shifts": list(available_shifts),
                "user_defaults": {
                    "client_id": user.client_id,
                    "bu_id": user.bu_id,
                }
            }

            return JsonResponse(response_data, safe=False)

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching scope options: {e}", exc_info=True)
            return JsonResponse(
                {"error": "Database error", "message": "Could not fetch options"},
                status=500
            )


__all__ = ["CurrentScopeView", "UpdateScopeView", "ScopeOptionsView"]
