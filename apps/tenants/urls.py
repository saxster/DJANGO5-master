"""
Tenant Management URLs
"""

from django.urls import path
from apps.tenants import views

app_name = 'tenants'

urlpatterns = [
    # Diagnostic endpoints (staff only)
    path(
        'diagnostics/',
        views.TenantDiagnosticsView.as_view(),
        name='diagnostics'
    ),
    path(
        'health/',
        views.TenantHealthCheckView.as_view(),
        name='health_check'
    ),

    # Public endpoint
    path(
        'info/',
        views.TenantInfoView.as_view(),
        name='info'
    ),
]
