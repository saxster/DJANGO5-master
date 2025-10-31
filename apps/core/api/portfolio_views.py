"""
Portfolio Overview API Views
=============================
REST API endpoints for multi-site portfolio metrics and health scores.

Endpoints:
- GET /api/v1/overview/summary - Complete portfolio summary
- GET /api/v1/overview/attendance - Attendance metrics with breakdown
- GET /api/v1/overview/tours - Tours adherence metrics
- GET /api/v1/overview/tickets - Ticket metrics with SLA risks
- GET /api/v1/overview/work-orders - Work order metrics
- GET /api/v1/sites/{bu_id}/overview - Single site overview

Follows .claude/rules.md:
- Rule #7: Delegate to service layer
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from pydantic import ValidationError as PydanticValidationError

from apps.core.services.portfolio_metrics_service import PortfolioMetricsService
from apps.core.serializers.scope_serializers import ScopeConfig
from apps.core.serializers.portfolio_serializers import PortfolioSummaryResponse

logger = logging.getLogger(__name__)


class PortfolioSummaryView(LoginRequiredMixin, View):
    """
    GET /api/v1/overview/summary

    Returns complete portfolio summary with all metrics.
    """

    def get(self, request):
        try:
            # Parse scope from query params
            scope_data = self._parse_scope_params(request)

            # Validate with Pydantic
            try:
                scope = ScopeConfig(**scope_data)
            except PydanticValidationError as e:
                return JsonResponse(
                    {"error": "Invalid scope", "details": e.errors()},
                    status=400
                )

            # Get metrics from service
            service = PortfolioMetricsService()
            summary = service.get_portfolio_summary(scope)

            # Build response
            response = PortfolioSummaryResponse(
                attendance=summary["attendance"],
                tours=summary["tours"],
                tickets=summary["tickets"],
                work_orders=summary["work_orders"],
                top_sites=summary["top_sites"],
                scope=scope.model_dump(),
                generated_at=summary["generated_at"],
                cached=summary.get("cached", False)
            )

            return JsonResponse(response.model_dump(), safe=False)

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid request parameters: {e}")
            return JsonResponse({"error": "Invalid parameters"}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error generating portfolio summary: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)

    def _parse_scope_params(self, request) -> dict:
        """Parse scope parameters from request"""
        return {
            "tenant_id": request.user.tenant_id,
            "client_ids": self._parse_int_list(request.GET.get("client_ids", "")),
            "bu_ids": self._parse_int_list(request.GET.get("bu_ids", "")),
            "time_range": request.GET.get("time_range", "TODAY"),
            "date_from": request.GET.get("date_from"),
            "date_to": request.GET.get("date_to"),
            "shift_id": int(request.GET["shift_id"]) if request.GET.get("shift_id") else None,
            "tz": request.GET.get("tz", "Asia/Kolkata")
        }

    def _parse_int_list(self, value: str) -> list:
        """Parse comma-separated integers"""
        if not value:
            return []
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except ValueError:
            return []


class AttendanceMetricsView(LoginRequiredMixin, View):
    """GET /api/v1/overview/attendance"""

    def get(self, request):
        try:
            scope_data = PortfolioSummaryView()._parse_scope_params(request)
            scope = ScopeConfig(**scope_data)

            service = PortfolioMetricsService()
            metrics = service.get_attendance_metrics(scope)

            return JsonResponse(metrics, safe=False)

        except PydanticValidationError as e:
            return JsonResponse({"error": "Invalid scope", "details": e.errors()}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching attendance metrics: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class ToursMetricsView(LoginRequiredMixin, View):
    """GET /api/v1/overview/tours"""

    def get(self, request):
        try:
            scope_data = PortfolioSummaryView()._parse_scope_params(request)
            scope = ScopeConfig(**scope_data)

            service = PortfolioMetricsService()
            metrics = service.get_tours_metrics(scope)

            return JsonResponse(metrics, safe=False)

        except PydanticValidationError as e:
            return JsonResponse({"error": "Invalid scope", "details": e.errors()}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching tours metrics: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class TicketsMetricsView(LoginRequiredMixin, View):
    """GET /api/v1/overview/tickets"""

    def get(self, request):
        try:
            scope_data = PortfolioSummaryView()._parse_scope_params(request)
            scope = ScopeConfig(**scope_data)

            service = PortfolioMetricsService()
            metrics = service.get_tickets_metrics(scope)

            return JsonResponse(metrics, safe=False)

        except PydanticValidationError as e:
            return JsonResponse({"error": "Invalid scope", "details": e.errors()}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching tickets metrics: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class WorkOrdersMetricsView(LoginRequiredMixin, View):
    """GET /api/v1/overview/work-orders"""

    def get(self, request):
        try:
            scope_data = PortfolioSummaryView()._parse_scope_params(request)
            scope = ScopeConfig(**scope_data)

            service = PortfolioMetricsService()
            metrics = service.get_work_orders_metrics(scope)

            return JsonResponse(metrics, safe=False)

        except PydanticValidationError as e:
            return JsonResponse({"error": "Invalid scope", "details": e.errors()}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching work orders metrics: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


class SiteOverviewView(LoginRequiredMixin, View):
    """
    GET /api/v1/sites/{bu_id}/overview

    Returns comprehensive overview for single site.
    """

    def get(self, request, bu_id):
        try:
            # Build scope for single site
            scope_data = {
                "tenant_id": request.user.tenant_id,
                "bu_ids": [int(bu_id)],
                "time_range": request.GET.get("time_range", "TODAY"),
                "shift_id": int(request.GET["shift_id"]) if request.GET.get("shift_id") else None,
                "tz": request.GET.get("tz", "Asia/Kolkata")
            }

            scope = ScopeConfig(**scope_data)

            # Get all metrics
            service = PortfolioMetricsService()
            summary = service.get_portfolio_summary(scope)

            # Calculate RAG status
            rag_status = service.calculate_site_rag_status(int(bu_id), scope)

            # Add site-specific data
            summary["rag_status"] = rag_status
            summary["bu_id"] = int(bu_id)

            return JsonResponse(summary, safe=False)

        except PydanticValidationError as e:
            return JsonResponse({"error": "Invalid scope", "details": e.errors()}, status=400)
        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error fetching site overview: {e}", exc_info=True)
            return JsonResponse({"error": "Database error"}, status=500)


__all__ = [
    "PortfolioSummaryView",
    "AttendanceMetricsView",
    "ToursMetricsView",
    "TicketsMetricsView",
    "WorkOrdersMetricsView",
    "SiteOverviewView",
]
