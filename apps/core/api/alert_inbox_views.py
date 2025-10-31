"""
Alert Inbox API Views
=====================
REST API endpoints for unified alert inbox.

Endpoints:
- GET /api/v1/alerts/inbox/ - Get unified alert feed
- POST /api/v1/alerts/{alert_id}/mark-read/ - Mark alert as read
- POST /api/v1/alerts/mark-all-read/ - Mark all alerts as read

Follows .claude/rules.md:
- Rule #7: Delegate to service layer
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.http import JsonResponse
from django.views import View
from pydantic import ValidationError as PydanticValidationError

from apps.core.services.alert_inbox_service import AlertInboxService
from apps.core.serializers.alert_serializers import (
    AlertInboxResponse,
    MarkAlertReadRequest,
    MarkAlertReadResponse,
)

logger = logging.getLogger(__name__)


class AlertInboxView(LoginRequiredMixin, View):
    """
    GET /api/v1/alerts/inbox/

    Returns unified alert feed from all sources.
    """

    def get(self, request):
        try:
            # Parse query parameters
            scope_json = request.GET.get("scope", "{}")
            scope = json.loads(scope_json) if scope_json != "{}" else {}

            tenant_id = request.user.tenant_id
            client_ids = scope.get("client_ids")
            bu_ids = scope.get("bu_ids")
            severity_filter = request.GET.get("severity")
            unread_only = request.GET.get("unread_only", "false").lower() == "true"
            limit = int(request.GET.get("limit", 50))

            # Get alerts from service
            service = AlertInboxService()
            alerts = service.get_unified_alerts(
                tenant_id=tenant_id,
                client_ids=client_ids,
                bu_ids=bu_ids,
                severity_filter=severity_filter,
                unread_only=unread_only,
                limit=limit
            )

            # Calculate counts
            unread_count = sum(1 for a in alerts if not a["is_read"])

            # Build response
            response = AlertInboxResponse(
                alerts=alerts,
                unread_count=unread_count,
                total_count=len(alerts),
                scope=scope
            )

            return JsonResponse(response.model_dump(), safe=False)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid request parameters: {e}")
            return JsonResponse({"error": "Invalid parameters", "message": str(e)}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching alerts: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class MarkAlertReadView(LoginRequiredMixin, View):
    """
    POST /api/v1/alerts/{alert_id}/mark-read/

    Mark a specific alert as read.
    """

    def post(self, request, alert_id):
        try:
            service = AlertInboxService()
            success = service.mark_alert_read(alert_id, request.user.id)

            if not success:
                return JsonResponse(
                    {"error": "Could not mark alert as read"},
                    status=400
                )

            # Get updated unread count
            alerts = service.get_unified_alerts(
                tenant_id=request.user.tenant_id,
                unread_only=True,
                limit=100
            )
            unread_count = len(alerts)

            response = MarkAlertReadResponse(
                success=True,
                message="Alert marked as read",
                unread_count=unread_count
            )

            return JsonResponse(response.model_dump())

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error marking alert as read: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class MarkAllAlertsReadView(LoginRequiredMixin, View):
    """
    POST /api/v1/alerts/mark-all-read/

    Mark all user's alerts as read.
    """

    def post(self, request):
        try:
            # Get all unread NOC alerts for user's tenant
            from apps.noc.models import NOCAlertEvent

            filters = {
                "tenant_id": request.user.tenant_id,
                "acknowledged_at__isnull": True
            }

            # Update NOC alerts
            updated_count = NOCAlertEvent.objects.filter(**filters).update(
                acknowledged_at=timezone.now(),
                acknowledged_by=request.user,
                status="ACKNOWLEDGED"
            )

            logger.info(f"User {request.user.id} marked {updated_count} alerts as read")

            # TODO: Add read tracking for other alert types when implemented

            response = MarkAlertReadResponse(
                success=True,
                message=f"Marked {updated_count} alerts as read",
                unread_count=0
            )

            return JsonResponse(response.model_dump())

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error marking all alerts as read: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


__all__ = [
    "AlertInboxView",
    "MarkAlertReadView",
    "MarkAllAlertsReadView",
]
