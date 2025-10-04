"""
State Transition Monitoring Dashboard URLs

URL routing for state transition monitoring and analysis views.
"""

from django.urls import path
from apps.core.views import state_transition_dashboard

urlpatterns = [
    # Main dashboard
    path(
        'dashboard/',
        state_transition_dashboard.state_transition_dashboard,
        name='state_transition_dashboard'
    ),

    # Entity-specific history
    path(
        'history/<str:entity_type>/<str:entity_id>/',
        state_transition_dashboard.entity_transition_history,
        name='entity_transition_history'
    ),

    # Failure analysis
    path(
        'failures/',
        state_transition_dashboard.transition_failure_analysis,
        name='transition_failure_analysis'
    ),

    # Performance trends
    path(
        'trends/',
        state_transition_dashboard.performance_trends,
        name='performance_trends'
    ),

    # API endpoint for real-time metrics
    path(
        'api/metrics/',
        state_transition_dashboard.transition_metrics_api,
        name='transition_metrics_api'
    ),
]
