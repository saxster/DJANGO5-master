"""
Dashboard URL Configuration
"""
from django.urls import path
from apps.core.views.dashboard_views import ModernDashboardView, DashboardDataView

app_name = 'dashboard'

urlpatterns = [
    path('', ModernDashboardView.as_view(), name='main'),
    path('data/', DashboardDataView.as_view(), name='data'),
]