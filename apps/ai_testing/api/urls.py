"""
AI Testing API URL Configuration
REST API endpoints for external tool integration
"""

from django.urls import path
from . import views

app_name = 'ai_testing_api'

urlpatterns = [
    # Core AI Insights
    path('insights/', views.ai_insights_api, name='ai_insights'),
    path('health/', views.health_api, name='health'),

    # Coverage Gaps
    path('coverage-gaps/', views.coverage_gaps_api, name='coverage_gaps'),
    path('coverage-gaps/<uuid:gap_id>/', views.coverage_gap_detail_api, name='coverage_gap_detail'),
    path('coverage-gaps/stats/', views.coverage_gaps_stats_api, name='coverage_gaps_stats'),

    # Regression Risk
    path('regression-risk/', views.regression_risk_api, name='regression_risk'),
    path('regression-risk/<str:version>/', views.regression_risk_api, name='regression_risk_version'),

    # Adaptive Thresholds
    path('thresholds/', views.adaptive_thresholds_api, name='thresholds'),

    # Patterns
    path('patterns/', views.patterns_api, name='patterns'),

    # Test Generation
    path('generate-test/', views.generate_test_api, name='generate_test'),

    # Analysis
    path('trigger-analysis/', views.trigger_analysis_api, name='trigger_analysis'),

    # Export Endpoints
    path('export/coverage-gaps.csv', views.export_coverage_gaps_csv, name='export_coverage_gaps_csv'),
    path('export/coverage-gaps.json', views.export_coverage_gaps_json, name='export_coverage_gaps_json'),
    path('export/insights.json', views.export_ai_insights_json, name='export_ai_insights_json'),
]