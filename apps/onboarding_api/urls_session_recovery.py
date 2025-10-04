"""
Session Recovery URL Configuration

URL patterns for session checkpoint and recovery endpoints.

Author: Claude Code
Date: 2025-10-01
"""

from django.urls import path
from apps.onboarding_api.views.session_recovery_views import (
    SessionCheckpointView,
    SessionResumeView,
    SessionCheckpointHistoryView,
    AbandonmentRiskView,
    AtRiskSessionsView,
)

app_name = 'session_recovery'

urlpatterns = [
    # Session-specific endpoints
    path(
        'sessions/<uuid:session_id>/checkpoint/',
        SessionCheckpointView.as_view(),
        name='session-checkpoint'
    ),
    path(
        'sessions/<uuid:session_id>/resume/',
        SessionResumeView.as_view(),
        name='session-resume'
    ),
    path(
        'sessions/<uuid:session_id>/checkpoints/',
        SessionCheckpointHistoryView.as_view(),
        name='session-checkpoint-history'
    ),
    path(
        'sessions/<uuid:session_id>/risk/',
        AbandonmentRiskView.as_view(),
        name='session-abandonment-risk'
    ),

    # Admin endpoints
    path(
        'admin/at-risk-sessions/',
        AtRiskSessionsView.as_view(),
        name='at-risk-sessions'
    ),
]

# API Endpoint Documentation
"""
Session Recovery API Endpoints:

1. POST /api/v1/onboarding/sessions/{session_id}/checkpoint/
   - Create checkpoint for current session state
   - Body: {state, data, history, ui_state, version, force}
   - Permissions: IsAuthenticated (session owner)

2. POST /api/v1/onboarding/sessions/{session_id}/resume/
   - Resume session from latest checkpoint
   - Restores state and returns next action
   - Permissions: IsAuthenticated (session owner)

3. GET /api/v1/onboarding/sessions/{session_id}/checkpoints/
   - List historical checkpoints
   - Query params: limit (default: 10, max: 50)
   - Permissions: IsAuthenticated (session owner)

4. GET /api/v1/onboarding/sessions/{session_id}/risk/
   - Get abandonment risk assessment
   - ML-based risk scoring (0-100)
   - Permissions: IsAuthenticated (owner) or IsAdminUser

5. GET /api/v1/onboarding/admin/at-risk-sessions/
   - List all at-risk sessions (admin dashboard)
   - Query params: risk_level, limit
   - Permissions: IsAdminUser

Example Usage:
--------------

# Create checkpoint
POST /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/checkpoint/
{
    "state": "IN_PROGRESS",
    "data": {"answers": [...]},
    "history": ["q1", "q2"],
    "ui_state": {"current_step": 2},
    "version": 1
}

# Resume session
POST /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/resume/

# Check abandonment risk
GET /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/risk/

# List checkpoint history
GET /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/checkpoints/?limit=5

# Admin: Get at-risk sessions
GET /api/v1/onboarding/admin/at-risk-sessions/?risk_level=high&limit=50
"""
