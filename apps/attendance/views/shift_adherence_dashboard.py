"""
Shift Adherence Dashboard View - Real-time attendance tracking.

Shows who's on time, late, or missing from scheduled shifts.
"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import datetime
from apps.attendance.services.shift_adherence_service import ShiftAdherenceService
from apps.client_onboarding.models import Bt
import logging

logger = logging.getLogger(__name__)


class ShiftAdherenceDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard showing shift attendance vs schedule compliance"""
    
    template_name = 'admin/attendance/shift_adherence_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date from URL or default to today
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = timezone.now().date()
        else:
            selected_date = timezone.now().date()
        
        # Get site filter
        site_id = self.request.GET.get('site')
        site = None
        if site_id:
            try:
                site = Bt.objects.get(id=site_id)
            except Bt.DoesNotExist:
                logger.warning(f"Site {site_id} not found")
        
        # Calculate adherence
        service = ShiftAdherenceService()
        adherence = service.calculate_adherence(selected_date, site)
        stats = service.get_coverage_stats(adherence)
        
        # Group by status
        by_status = {
            'on_time': [r for r in adherence if r['status'] == 'ON_TIME'],
            'late': [r for r in adherence if r['status'] == 'LATE'],
            'no_show': [r for r in adherence if r['status'] == 'NO_SHOW'],
            'early_exit': [r for r in adherence if r['status'] == 'EARLY_EXIT']
        }
        
        context.update({
            'date': selected_date,
            'site': site,
            'adherence_data': adherence,
            'stats': stats,
            'by_status': by_status,
            'sites': Bt.objects.filter(is_client=False).order_by('name')
        })
        
        return context
