"""
Dashboard Views for YOUTILITY5
Modern dashboard implementation with HTMLStream design
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q
from apps.peoples.models import People
from apps.activity.models.asset_model import Asset
from apps.attendance.models import PeopleEventlog
from datetime import date, datetime, timedelta


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
    """
    
    def get(self, request, *args, **kwargs):
        try:
            # Get basic metrics
            total_people = People.objects.filter(
                bu_id=request.session.get('bu_id'),
                client_id=request.session.get('client_id')
            ).count()
            
            active_assets = Asset.objects.filter(
                bu_id=request.session.get('bu_id'),
                client_id=request.session.get('client_id'),
                enable=True,
                runningstatus='WORKING'
            ).count()
            
            today_attendance = PeopleEventlog.objects.filter(
                bu_id=request.session.get('bu_id'),
                client_id=request.session.get('client_id'),
                datefor=date.today()
            ).values('people').distinct().count()
            
            # Asset status breakdown
            asset_status = Asset.objects.filter(
                bu_id=request.session.get('bu_id'),
                client_id=request.session.get('client_id')
            ).values('runningstatus').annotate(count=Count('id'))
            
            asset_status_data = {item['runningstatus']: item['count'] for item in asset_status}
            
            # Monthly attendance trend (last 12 months)
            monthly_data = []
            for i in range(12):
                month_date = date.today().replace(day=1) - timedelta(days=30*i)
                month_attendance = PeopleEventlog.objects.filter(
                    bu_id=request.session.get('bu_id'),
                    client_id=request.session.get('client_id'),
                    datefor__year=month_date.year,
                    datefor__month=month_date.month
                ).values('people').distinct().count()
                monthly_data.append({
                    'month': month_date.strftime('%b %Y'),
                    'attendance': month_attendance
                })
            
            monthly_data.reverse()  # Show chronological order
            
            data = {
                'metrics': {
                    'total_people': total_people,
                    'active_assets': active_assets,
                    'today_attendance': today_attendance,
                    'pending_tasks': 0  # Placeholder - implement based on your task model
                },
                'asset_status': asset_status_data,
                'monthly_attendance': monthly_data,
                'status': 'success'
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


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