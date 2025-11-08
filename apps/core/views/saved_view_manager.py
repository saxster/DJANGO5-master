"""
Saved View Manager Views
========================
Allow users to manage their saved dashboard views and access shared views.

Follows .claude/rules.md:
- Rule #4: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #13: Security first
"""

import json
import logging
from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.models.dashboard_saved_view import DashboardSavedView
from apps.core.services.view_export_service import ViewExportService

logger = logging.getLogger(__name__)


class SavedViewManagerView(LoginRequiredMixin, TemplateView):
    """
    Manage user's saved views.
    Shows personal views and views shared with the user.
    """
    template_name = 'admin/core/my_saved_views.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # User's own views
        my_views = DashboardSavedView.objects.filter(
            cuser=user
        ).select_related('cuser').prefetch_related(
            'shared_with_users',
            'shared_with_groups',
            'email_recipients'
        )

        # Views shared with user
        shared_views = DashboardSavedView.objects.filter(
            Q(shared_with_users=user) |
            Q(shared_with_groups__people=user)
        ).exclude(
            cuser=user
        ).select_related('cuser').distinct()

        context.update({
            'my_views': my_views,
            'shared_views': shared_views,
            'view_types': DashboardSavedView.ViewType.choices,
            'email_frequencies': DashboardSavedView.EmailFrequency.choices,
            'export_formats': DashboardSavedView.ExportFormat.choices,
        })

        return context


class SaveViewAPIView(LoginRequiredMixin, View):
    """API endpoint to save current view configuration"""

    def post(self, request):
        try:
            data = json.loads(request.body)

            # Validate required fields
            required_fields = ['name', 'view_type', 'page_url']
            missing_fields = [f for f in required_fields if not data.get(f)]
            if missing_fields:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)

            # Create saved view
            view = DashboardSavedView.objects.create(
                cuser=request.user,
                tenant=request.user.tenant,
                name=data['name'],
                description=data.get('description', ''),
                view_type=data['view_type'],
                scope_config=data.get('scope_config', {}),
                filters=data.get('filters', {}),
                visible_panels=data.get('visible_panels', []),
                sort_order=data.get('sort_order', []),
                page_url=data['page_url'],
                sharing_level=data.get('sharing_level', 'PRIVATE'),
                is_default=data.get('is_default', False),
                email_frequency=data.get('email_frequency', 'NONE')
            )

            # If set as default, unset other defaults
            if view.is_default:
                DashboardSavedView.objects.filter(
                    cuser=request.user
                ).exclude(id=view.id).update(is_default=False)

            # Schedule export if requested
            if data.get('email_frequency') and data['email_frequency'] != 'NONE':
                from apps.core.services.view_export_service import ViewExportService
                ViewExportService.schedule_export(
                    view,
                    frequency=data['email_frequency'],
                    recipients=[request.user.email]
                )

            logger.info(
                f"Saved view created: {view.name} by user {request.user.id}",
                extra={'view_id': view.id, 'user_id': request.user.id}
            )

            return JsonResponse({
                'success': True,
                'view_id': view.id,
                'message': 'View saved! You can find it in My Saved Views.'
            })

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error saving view: {e}",
                exc_info=True,
                extra={'user_id': request.user.id}
            )
            return JsonResponse({
                'success': False,
                'error': 'Failed to save view. Please try again.'
            }, status=500)
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class LoadViewAPIView(LoginRequiredMixin, View):
    """Load a saved view configuration"""

    def get(self, request, view_id):
        try:
            view = DashboardSavedView.objects.select_related('cuser').get(id=view_id)

            # Check access permission
            if not view.can_user_access(request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to access this view.'
                }, status=403)

            # Update access tracking
            view.view_count += 1
            view.last_accessed_at = timezone.now()
            view.save(update_fields=['view_count', 'last_accessed_at'])

            return JsonResponse({
                'success': True,
                'view': {
                    'id': view.id,
                    'name': view.name,
                    'description': view.description,
                    'view_type': view.view_type,
                    'scope_config': view.scope_config,
                    'filters': view.filters,
                    'visible_panels': view.visible_panels,
                    'sort_order': view.sort_order,
                    'page_url': view.page_url,
                }
            })

        except DashboardSavedView.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'View not found.'
            }, status=404)


class ExportViewAPIView(LoginRequiredMixin, View):
    """Export a saved view to CSV/Excel/PDF"""

    def get(self, request, view_id):
        try:
            view = DashboardSavedView.objects.get(id=view_id)

            # Check access permission
            if not view.can_user_access(request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to export this view.'
                }, status=403)

            export_format = request.GET.get('format', 'excel').lower()

            # Get export service
            service = ViewExportService()

            # Get data based on view type
            queryset, columns = service.get_view_data(view)

            # Generate export
            filename = f"{view.name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

            if export_format == 'csv':
                response = service.export_to_csv(queryset, columns, filename)
            elif export_format == 'excel':
                response = service.export_to_excel(queryset, columns, filename)
            elif export_format == 'pdf':
                response = service.export_to_pdf(queryset, columns, filename)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid export format. Use csv, excel, or pdf.'
                }, status=400)

            # Update export tracking
            view.last_export_at = timezone.now()
            view.save(update_fields=['last_export_at'])

            logger.info(
                f"View exported: {view.name} by user {request.user.id}",
                extra={'view_id': view.id, 'format': export_format}
            )

            return response

        except DashboardSavedView.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'View not found.'
            }, status=404)


class DeleteViewAPIView(LoginRequiredMixin, View):
    """Delete a saved view"""

    def delete(self, request, view_id):
        try:
            view = DashboardSavedView.objects.get(id=view_id, cuser=request.user)
            view_name = view.name
            view.delete()

            logger.info(
                f"Saved view deleted: {view_name} by user {request.user.id}",
                extra={'view_id': view_id, 'user_id': request.user.id}
            )

            return JsonResponse({
                'success': True,
                'message': f'View "{view_name}" deleted successfully.'
            })

        except DashboardSavedView.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'View not found or you do not have permission to delete it.'
            }, status=404)


__all__ = [
    'SavedViewManagerView',
    'SaveViewAPIView',
    'LoadViewAPIView',
    'ExportViewAPIView',
    'DeleteViewAPIView',
]
