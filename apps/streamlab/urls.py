"""
Stream Testbench URL Configuration
"""

from django.urls import path
from . import views

app_name = 'streamlab'

urlpatterns = [
    # Dashboard views
    path('', views.dashboard_home, name='dashboard'),
    path('metrics/live/', views.live_metrics, name='live_metrics'),
    path('metrics/api/', views.metrics_api, name='metrics_api'),
    path('ai-insights/', views.ai_insights_partial, name='ai_insights_partial'),

    # Scenario management
    path('scenarios/<uuid:scenario_id>/', views.scenario_detail, name='scenario_detail'),
    path('scenarios/<uuid:scenario_id>/start/', views.start_scenario, name='start_scenario'),

    # Test run management
    path('runs/<uuid:run_id>/', views.run_detail, name='run_detail'),
    path('runs/<uuid:run_id>/stop/', views.stop_scenario, name='stop_scenario'),

    # Anomaly tracking
    path('anomalies/', views.anomalies_dashboard, name='anomalies'),
]