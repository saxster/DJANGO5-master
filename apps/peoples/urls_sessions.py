"""
Session Management URL Configuration
"""

from django.urls import path
from apps.peoples.api import session_views

app_name = 'sessions'

urlpatterns = [
    # API endpoints
    path(
        'api/sessions/',
        session_views.SessionListView.as_view(),
        name='session_list'
    ),
    path(
        'api/sessions/<int:session_id>/',
        session_views.SessionRevokeView.as_view(),
        name='session_revoke'
    ),
    path(
        'api/sessions/revoke-all/',
        session_views.SessionRevokeAllView.as_view(),
        name='session_revoke_all'
    ),
    path(
        'api/sessions/statistics/',
        session_views.SessionStatisticsView.as_view(),
        name='session_statistics'
    ),
]
