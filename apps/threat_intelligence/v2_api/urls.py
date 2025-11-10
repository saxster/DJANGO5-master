from django.urls import path
from apps.threat_intelligence.v2_api import views

app_name = 'threat_intelligence_v2'

urlpatterns = [
    # Alert endpoints
    path(
        'alerts/',
        views.IntelligenceAlertListView.as_view(),
        name='alert_list'
    ),
    path(
        'alerts/<int:alert_id>/',
        views.IntelligenceAlertDetailView.as_view(),
        name='alert_detail'
    ),
    path(
        'alerts/<int:alert_id>/feedback/',
        views.IntelligenceAlertDetailView.as_view(),
        name='alert_feedback'
    ),
    
    # Profile management
    path(
        'profile/',
        views.TenantIntelligenceProfileView.as_view(),
        name='profile'
    ),
    
    # Learning metrics
    path(
        'metrics/',
        views.LearningMetricsView.as_view(),
        name='metrics'
    ),
    
    # Collective patterns
    path(
        'patterns/',
        views.CollectivePatternsView.as_view(),
        name='patterns'
    ),
]
