"""
Reports API URLs (v1)

Domain: /api/v1/reports/

Handles report generation, scheduling, templates, and export formats.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import viewsets when they're created
# from apps.reports.api import views

app_name = 'reports'

router = DefaultRouter()
# router.register(r'schedules', views.ScheduledReportViewSet, basename='schedules')
# router.register(r'templates', views.ReportTemplateViewSet, basename='templates')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('generate/', views.GenerateReportView.as_view(), name='generate'),
    # path('<str:report_id>/download/', views.DownloadReportView.as_view(), name='download'),
    # path('<str:report_id>/status/', views.ReportStatusView.as_view(), name='status'),
    # path('templates/<int:pk>/preview/', views.TemplatePreviewView.as_view(), name='template-preview'),
]
