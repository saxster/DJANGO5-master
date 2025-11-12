"""
URL Configuration for Report Generation

API endpoints for intelligent report generation with AI guidance.

ARCHITECTURE:
- /api/v1/reports/sync/ - Mobile sync (Kotlin Android app)
- /api/v2/report-generation/ - Admin/supervisor API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.report_generation import views
from apps.report_generation import views_sync

app_name = 'report_generation'

# API v2 Router (Admin/Supervisor/Web interface)
router = DefaultRouter()
router.register(r'templates', views.ReportTemplateViewSet, basename='template')
router.register(r'reports', views.GeneratedReportViewSet, basename='report')
router.register(r'exemplars', views.ReportExemplarViewSet, basename='exemplar')
router.register(r'trends', views.ReportIncidentTrendViewSet, basename='trend')
router.register(r'analytics', views.ReportAnalyticsViewSet, basename='analytics')

urlpatterns = [
    # API v2: Admin/Supervisor interface
    path('api/v2/report-generation/', include(router.urls)),
    
    # API v1: Mobile sync (Kotlin Android app) - Follows existing pattern
    path('api/v1/reports/sync/', views_sync.ReportSyncView.as_view(), name='reports-sync'),
    path('api/v1/reports/changes/', views_sync.ReportChangesView.as_view(), name='reports-changes'),
]
