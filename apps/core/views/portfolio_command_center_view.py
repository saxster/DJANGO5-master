"""
Portfolio Command Center View
==============================
Multi-site portfolio overview for executive/regional managers.

Features:
- Interactive site map with RAG status
- Portfolio-wide KPIs
- Critical alerts feed
- Top sites ranking
- Drill-down to site dashboards

Follows .claude/rules.md:
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError
from django.views.generic import TemplateView

from apps.core.models import UserScope
from apps.onboarding.models import Bt, Shift
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class PortfolioCommandCenterView(LoginRequiredMixin, TemplateView):
    """
    Portfolio Command Center - Multi-site overview dashboard.

    ZOOM LEVEL 1: Birds-eye view across multiple sites.

    Access: Portfolio managers, regional managers, executives
    """

    template_name = "command_center/portfolio.html"

    def get_context_data(self, **kwargs):
        """Build context for portfolio view"""
        context = super().get_context_data(**kwargs)

        try:
            # Get user's saved scope
            user_scope = self._get_user_scope()

            # Get available options for scope bar
            available_data = self._get_available_options()

            # Build current scope for UI
            current_scope = self._build_current_scope(user_scope)

            # Add to context
            context.update({
                "page_title": "Command Center: Portfolio Overview",
                "page_subtitle": "Multi-site operations dashboard",
                "current_scope": current_scope,
                "available_tenants": available_data["tenants"],
                "available_clients": available_data["clients"],
                "available_sites": available_data["sites"],
                "available_shifts": available_data["shifts"],
                "user": self.request.user,
            })

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Error building portfolio context: {e}", exc_info=True)
            context.update({
                "error": "Could not load dashboard data",
                "current_scope": {},
                "available_tenants": [],
                "available_clients": [],
                "available_sites": [],
                "available_shifts": [],
            })

        return context

    def _get_user_scope(self) -> UserScope:
        """Get or create user scope"""
        user_scope, created = UserScope.objects.get_or_create(
            user=self.request.user,
            tenant=self.request.user.tenant,
            defaults={
                "selected_clients": [self.request.user.client_id] if self.request.user.client_id else [],
                "selected_sites": [self.request.user.bu_id] if self.request.user.bu_id else [],
                "time_range": "TODAY",
            }
        )
        return user_scope

    def _get_available_options(self) -> dict:
        """Get available tenants, clients, sites, shifts for scope selector"""
        user = self.request.user

        # Tenants (superuser only)
        if user.is_superuser:
            tenants = Tenant.objects.all()
        else:
            tenants = Tenant.objects.filter(id=user.tenant_id)

        # Clients
        if user.is_superuser:
            clients = Bt.objects.filter(tenant=user.tenant, btype="C")
        else:
            clients = Bt.objects.filter(
                tenant=user.tenant,
                id=user.client_id,
                btype="C"
            )

        # Sites/Business Units
        if user.is_superuser:
            sites = Bt.objects.filter(tenant=user.tenant, btype="B")
        else:
            sites = Bt.objects.filter(
                tenant=user.tenant,
                client_id=user.client_id,
                btype="B"
            )

        # Shifts
        shifts = Shift.objects.filter(tenant=user.tenant, client=user.client)

        return {
            "tenants": tenants,
            "clients": clients,
            "sites": sites,
            "shifts": shifts,
        }

    def _build_current_scope(self, user_scope: UserScope) -> dict:
        """Build current scope dictionary for template"""
        return {
            "tenant_id": user_scope.tenant_id,
            "client_ids": user_scope.selected_clients or [],
            "bu_ids": user_scope.selected_sites or [],
            "time_range": user_scope.time_range,
            "date_from": user_scope.date_from,
            "date_to": user_scope.date_to,
            "shift_id": user_scope.shift_id,
        }


__all__ = ["PortfolioCommandCenterView"]
