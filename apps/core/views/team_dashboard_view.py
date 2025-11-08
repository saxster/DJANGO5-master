"""
Team Dashboard View

User-friendly unified operations dashboard showing all tasks, tickets, 
incidents, and alerts that need attention.

Following CLAUDE.md:
- Rule #7: Service layer for business logic
- Rule #11: Specific exception handling
- Rule #17: Multi-tenant isolation
- CSRF protection for all mutation operations
"""

import json
import logging
from typing import Dict, Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from apps.core.decorators import csrf_protect_ajax
from apps.core.services.team_dashboard_service import TeamDashboardService
from apps.core.services.quick_actions import QuickActionsService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class TeamDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main Team Dashboard view.
    
    Displays unified view of all work items (tickets, incidents, jobs)
    with user-friendly interface and quick actions.
    """
    template_name = 'admin/core/team_dashboard.html'
    
    def get_context_data(self, **kwargs):
        """Build context with dashboard data."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get filters from query params
        filters = {
            'status': self.request.GET.get('status', 'mine'),
            'priority': self.request.GET.get('priority'),
            'assigned_to': self.request.GET.get('assigned_to'),
            'item_type': self.request.GET.get('item_type'),
            'search': self.request.GET.get('search'),
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v}
        
        try:
            # Get dashboard items
            items = TeamDashboardService.get_dashboard_items(
                tenant_id=user.tenant.id,
                user_id=user.id,
                filters=filters
            )
            
            # Get statistics
            stats = TeamDashboardService.get_dashboard_stats(
                tenant_id=user.tenant.id,
                user_id=user.id
            )
            
            context.update({
                'items': items,
                'stats': stats,
                'current_filter': filters.get('status', 'mine'),
                'quick_filters': self._get_quick_filters(),
                'priority_badges': self._get_priority_badges(),
                'urgency_badges': self._get_urgency_badges(),
            })
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error loading team dashboard for user {user.id}: {e}",
                exc_info=True,
                extra={'user_id': user.id, 'tenant_id': user.tenant.id}
            )
            context.update({
                'items': [],
                'stats': {},
                'error': 'Unable to load dashboard. Please try again.',
            })
        
        return context
    
    def _get_quick_filters(self) -> list:
        """Get quick filter options."""
        return [
            {'value': 'mine', 'label': '📋 My Tasks', 'icon': '👤'},
            {'value': 'team', 'label': '👥 All Tasks', 'icon': '🏢'},
            {'value': 'unassigned', 'label': '🆘 Needs Assignment', 'icon': '⚠️'},
        ]
    
    def _get_priority_badges(self) -> Dict[str, Dict[str, str]]:
        """Get priority badge configurations."""
        return {
            'CRITICAL': {'color': 'danger', 'icon': '🔥', 'label': 'Critical'},
            'HIGH': {'color': 'danger', 'icon': '🔴', 'label': 'High'},
            'MEDIUM': {'color': 'warning', 'icon': '🟠', 'label': 'Medium'},
            'NORMAL': {'color': 'info', 'icon': '🟢', 'label': 'Normal'},
            'LOW': {'color': 'secondary', 'icon': '⚪', 'label': 'Low'},
        }
    
    def _get_urgency_badges(self) -> Dict[str, Dict[str, str]]:
        """Get urgency badge configurations."""
        return {
            'OVERDUE': {'color': 'danger', 'icon': '⏰', 'label': 'Overdue!'},
            'URGENT': {'color': 'warning', 'icon': '⚡', 'label': 'Due Soon'},
            'SOON': {'color': 'info', 'icon': '📅', 'label': 'Coming Up'},
            'ON_TRACK': {'color': 'success', 'icon': '✅', 'label': 'On Track'},
        }


class TeamDashboardAPIView(LoginRequiredMixin, View):
    """
    API endpoint for dashboard actions.
    
    Handles:
    - Taking ownership (assign to me)
    - Marking complete
    - Requesting help
    - Refreshing data
    """
    
    @method_decorator(csrf_protect_ajax)
    def post(self, request, *args, **kwargs):
        """Handle dashboard actions."""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            item_type = data.get('item_type')
            item_id = data.get('item_id')
            
            if not all([action, item_type, item_id]):
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required parameters.'
                }, status=400)
            
            # Route to appropriate action
            if action == 'assign_to_me':
                result = QuickActionsService.assign_to_me(
                    item_type=item_type,
                    item_id=item_id,
                    user=request.user,
                    note=data.get('note')
                )
            elif action == 'mark_complete':
                result = QuickActionsService.mark_complete(
                    item_type=item_type,
                    item_id=item_id,
                    user=request.user,
                    note=data.get('note')
                )
            elif action == 'request_help':
                help_message = data.get('help_message', '')
                if not help_message:
                    return JsonResponse({
                        'success': False,
                        'message': 'Please describe what help you need.'
                    }, status=400)
                
                result = QuickActionsService.request_help(
                    item_type=item_type,
                    item_id=item_id,
                    user=request.user,
                    help_message=help_message
                )
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Unknown action: {action}'
                }, status=400)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data.'
            }, status=400)
        except Exception as e:
            logger.error(
                f"Error processing dashboard action: {e}",
                exc_info=True,
                extra={
                    'user_id': request.user.id,
                    'action': action if 'action' in locals() else None,
                }
            )
            return JsonResponse({
                'success': False,
                'message': 'An error occurred. Please try again.'
            }, status=500)
    
    def get(self, request, *args, **kwargs):
        """Get dashboard data (for AJAX refresh)."""
        user = request.user
        
        # Get filters from query params
        filters = {
            'status': request.GET.get('status', 'mine'),
            'priority': request.GET.get('priority'),
            'assigned_to': request.GET.get('assigned_to'),
            'item_type': request.GET.get('item_type'),
            'search': request.GET.get('search'),
        }
        filters = {k: v for k, v in filters.items() if v}
        
        try:
            items = TeamDashboardService.get_dashboard_items(
                tenant_id=user.tenant.id,
                user_id=user.id,
                filters=filters
            )
            
            stats = TeamDashboardService.get_dashboard_stats(
                tenant_id=user.tenant.id,
                user_id=user.id
            )
            
            return JsonResponse({
                'success': True,
                'items': items,
                'stats': stats,
            })
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error fetching dashboard data: {e}",
                exc_info=True,
                extra={'user_id': user.id, 'tenant_id': user.tenant.id}
            )
            return JsonResponse({
                'success': False,
                'message': 'Unable to load dashboard data.'
            }, status=500)
