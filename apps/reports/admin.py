from django.contrib import admin
from .models import ScheduleReport


@admin.register(ScheduleReport)
class ScheduleReportAdmin(admin.ModelAdmin):
    """
    Admin interface for scheduled reports with N+1 query optimization.
    
    N+1 Prevention: Uses select_related for FK access in list_display.
    """
    fields = ["report_type", "report_name", "filename", "report_sendtime", "cron"]
    list_display = ["report_type", "cron", "report_params"]
    list_display_links = ["report_type"]
    list_per_page = 50
    
    # N+1 query optimization for list view
    list_select_related = ['bu', 'client']

    def get_queryset(self, request):
        """Override to ensure select_related is always applied."""
        return super().get_queryset(request).select_related('bu', 'client')
