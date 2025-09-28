"""
Dashboard Views for YOUTILITY5
Modern dashboard implementation with HTMLStream design and intelligent caching
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Count
from django.utils.decorators import method_decorator
from datetime import date, timedelta
import logging

from apps.peoples.models import People
from apps.activity.models.asset_model import Asset
from apps.attendance.models import PeopleEventlog
from apps.core.caching.decorators import cache_dashboard_metrics, smart_cache_view

logger = logging.getLogger(__name__)


class ModernDashboardView(LoginRequiredMixin, TemplateView):
    """
    Modern dashboard view using HTMLStream-inspired design
    """
    template_name = 'dashboard/dashboard_modern.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add dashboard-specific context
        context.update({
            'page_title': 'Dashboard',
            'page_subtitle': 'Operations overview and key metrics',
        })
        
        return context


class DashboardDataView(LoginRequiredMixin, TemplateView):
    """
    API endpoint for dashboard data (metrics, charts, etc.)
    Implements intelligent caching with tenant isolation
    """

    @method_decorator(cache_dashboard_metrics(timeout=15*60))  # 15-minute cache
    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"Generating dashboard data for user {request.user.id}")

            # Extract tenant context for optimized queries
            bu_id = request.session.get('bu_id')
            client_id = request.session.get('client_id')

            if not bu_id or not client_id:
                logger.warning("Missing tenant context in dashboard request")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing tenant context'
                }, status=400)

            # Get basic metrics with optimized queries
            metrics = self._get_basic_metrics(bu_id, client_id)
            asset_status_data = self._get_asset_status_breakdown(bu_id, client_id)
            monthly_data = self._get_monthly_attendance_trend(bu_id, client_id)

            data = {
                'metrics': metrics,
                'asset_status': asset_status_data,
                'monthly_attendance': monthly_data,
                'status': 'success',
                'cache_info': {
                    'generated_at': date.today().isoformat(),
                    'tenant_context': f"bu:{bu_id}, client:{client_id}"
                }
            }

            logger.info(f"Dashboard data generated successfully for tenant bu:{bu_id}, client:{client_id}")
            return JsonResponse(data)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error generating dashboard data: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error',
                'error_id': str(hash(str(e)))  # Obfuscated error ID for support
            }, status=500)

    def _get_basic_metrics(self, bu_id: int, client_id: int) -> dict:
        """
        Get basic dashboard metrics with single queries
        Optimized to reduce database calls
        """
        # Single query for people count
        total_people = People.objects.filter(
            bu_id=bu_id,
            client_id=client_id
        ).count()

        # Single query for active assets
        active_assets = Asset.objects.filter(
            bu_id=bu_id,
            client_id=client_id,
            enable=True,
            runningstatus='WORKING'
        ).count()

        # Single query for today's attendance
        today_attendance = PeopleEventlog.objects.filter(
            bu_id=bu_id,
            client_id=client_id,
            datefor=date.today()
        ).values('people').distinct().count()

        # TODO: Implement pending tasks when task model is available
        pending_tasks = 0

        return {
            'total_people': total_people,
            'active_assets': active_assets,
            'today_attendance': today_attendance,
            'pending_tasks': pending_tasks
        }

    @method_decorator(smart_cache_view(timeout=30*60, key_prefix='dashboard:asset_status'))
    def _get_asset_status_breakdown(self, bu_id: int, client_id: int) -> dict:
        """
        Get asset status breakdown with caching
        Cached for 30 minutes since asset status changes less frequently
        """
        asset_status = Asset.objects.filter(
            bu_id=bu_id,
            client_id=client_id
        ).values('runningstatus').annotate(count=Count('id'))

        return {item['runningstatus']: item['count'] for item in asset_status}

    @method_decorator(smart_cache_view(timeout=2*60*60, key_prefix='dashboard:monthly_trends'))
    def _get_monthly_attendance_trend(self, bu_id: int, client_id: int) -> list:
        """
        Get monthly attendance trend with extended caching
        Cached for 2 hours since historical data changes infrequently
        """
        monthly_data = []

        # Generate monthly data for last 12 months
        for i in range(12):
            try:
                month_date = date.today().replace(day=1) - timedelta(days=30*i)

                # Optimized query with single database call per month
                month_attendance = PeopleEventlog.objects.filter(
                    bu_id=bu_id,
                    client_id=client_id,
                    datefor__year=month_date.year,
                    datefor__month=month_date.month
                ).values('people').distinct().count()

                monthly_data.append({
                    'month': month_date.strftime('%b %Y'),
                    'attendance': month_attendance,
                    'year': month_date.year,
                    'month_num': month_date.month
                })

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error calculating attendance for month {month_date}: {e}")
                # Add placeholder data to maintain chart structure
                monthly_data.append({
                    'month': month_date.strftime('%b %Y'),
                    'attendance': 0,
                    'year': month_date.year,
                    'month_num': month_date.month,
                    'error': True
                })

        monthly_data.reverse()  # Show chronological order
        return monthly_data


# Legacy view for backward compatibility
class LegacyDashboardView(LoginRequiredMixin, TemplateView):
    """
    Legacy dashboard view that redirects to modern template
    """
    template_name = 'dashboard/dashboard_modern.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Dashboard',
            'page_subtitle': 'Welcome to your operations dashboard',
        })
        return context