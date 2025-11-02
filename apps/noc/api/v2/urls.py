"""
NOC API v2 URL Configuration.

REST API endpoints for telemetry and operational intelligence.
"""

from django.urls import path
from . import telemetry_views, fraud_views

app_name = 'noc_api_v2'

urlpatterns = [
    # Telemetry endpoints
    path(
        'telemetry/signals/<int:person_id>/',
        telemetry_views.person_signals_view,
        name='person-signals'
    ),
    path(
        'telemetry/signals/site/<int:site_id>/',
        telemetry_views.site_signals_view,
        name='site-signals'
    ),
    path(
        'telemetry/correlations/',
        telemetry_views.correlations_view,
        name='correlations'
    ),

    # Fraud intelligence endpoints
    path(
        'security/fraud-scores/live/',
        fraud_views.fraud_scores_live_view,
        name='fraud-scores-live'
    ),
    path(
        'security/fraud-scores/history/<int:person_id>/',
        fraud_views.fraud_scores_history_view,
        name='fraud-scores-history'
    ),
    path(
        'security/fraud-scores/heatmap/',
        fraud_views.fraud_scores_heatmap_view,
        name='fraud-scores-heatmap'
    ),
    path(
        'security/ml-models/performance/',
        fraud_views.ml_model_performance_view,
        name='ml-model-performance'
    ),
]
