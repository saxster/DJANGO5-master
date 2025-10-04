"""
Monitoring Views

Django views for monitoring dashboard and management interfaces.
"""

import logging
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone

from apps.monitoring.services.monitoring_service import monitoring_service

logger = logging.getLogger(__name__)


class MonitoringDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main monitoring dashboard view.

    Displays real-time monitoring interface with charts and alerts.
    """

    template_name = 'monitoring/dashboard.html'

    def get_context_data(self, **kwargs):
        """Add monitoring context to template"""
        context = super().get_context_data(**kwargs)

        try:
            # Get initial dashboard data
            system_health = monitoring_service.get_system_health()
            active_alerts = monitoring_service.alert_service.get_active_alerts()

            context.update({
                'system_health': system_health,
                'active_alerts': active_alerts,
                'user_permissions': {
                    'can_acknowledge_alerts': True,
                    'can_resolve_alerts': self.request.user.is_staff or self.request.user.isadmin,
                    'can_manage_rules': self.request.user.is_staff,
                    'can_view_all_sites': self.request.user.is_staff
                },
                'dashboard_config': {
                    'auto_refresh_interval': 30,  # seconds
                    'chart_update_interval': 60,  # seconds
                    'alert_sound_enabled': True
                }
            })

        except Exception as e:
            logger.error(f"Error getting dashboard context: {str(e)}")
            context['error'] = str(e)

        return context


class AlertManagementView(LoginRequiredMixin, TemplateView):
    """
    Alert management interface.

    Provides detailed alert management and rule configuration.
    """

    template_name = 'monitoring/alert_management.html'

    def get_context_data(self, **kwargs):
        """Add alert management context"""
        context = super().get_context_data(**kwargs)

        try:
            # Get alert statistics
            alert_stats = monitoring_service.alert_service.get_alert_statistics(days=30)

            context.update({
                'alert_statistics': alert_stats,
                'can_manage_rules': self.request.user.is_staff
            })

        except Exception as e:
            logger.error(f"Error getting alert management context: {str(e)}")
            context['error'] = str(e)

        return context


class TicketManagementView(LoginRequiredMixin, TemplateView):
    """
    Ticket management interface.

    Provides ticket tracking and management capabilities.
    """

    template_name = 'monitoring/ticket_management.html'

    def get_context_data(self, **kwargs):
        """Add ticket management context"""
        context = super().get_context_data(**kwargs)

        try:
            from apps.monitoring.services.ticket_service import TicketService

            ticket_service = TicketService()
            ticket_stats = ticket_service.get_ticket_statistics(days=30)

            # Get user's tickets
            user_tickets = ticket_service.get_user_tickets(self.request.user.id)

            context.update({
                'ticket_statistics': ticket_stats,
                'user_tickets': user_tickets,
                'can_manage_tickets': self.request.user.is_staff
            })

        except Exception as e:
            logger.error(f"Error getting ticket management context: {str(e)}")
            context['error'] = str(e)

        return context


class MonitoringAPIDocView(TemplateView):
    """
    API documentation view for monitoring endpoints.
    """

    template_name = 'monitoring/api_documentation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['api_endpoints'] = [
            {
                'name': 'Monitor Device',
                'method': 'GET',
                'url': '/api/monitoring/',
                'parameters': 'user_id, device_id',
                'description': 'Get comprehensive device monitoring status'
            },
            {
                'name': 'Get Active Alerts',
                'method': 'GET',
                'url': '/api/monitoring/alerts/',
                'parameters': 'status, severity, user_id',
                'description': 'Get filtered list of alerts'
            },
            {
                'name': 'Acknowledge Alert',
                'method': 'POST',
                'url': '/api/monitoring/alerts/{id}/acknowledge/',
                'parameters': 'notes (optional)',
                'description': 'Acknowledge an active alert'
            },
            {
                'name': 'System Health',
                'method': 'GET',
                'url': '/api/monitoring/system-health/',
                'parameters': 'None',
                'description': 'Get overall system health status'
            },
            {
                'name': 'Device Status',
                'method': 'GET',
                'url': '/api/monitoring/device-status/',
                'parameters': 'user_id, device_id',
                'description': 'Get device status and health information'
            }
        ]

        return context