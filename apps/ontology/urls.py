"""
Ontology App URL Configuration

Routes for ontology dashboard and API endpoints.
"""
from django.urls import path

from .dashboard import views

app_name = 'ontology'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # API endpoints
    path('api/metrics/', views.metrics_api_view, name='metrics_api'),
    path('api/coverage/', views.coverage_summary_api_view, name='coverage_api'),
]
