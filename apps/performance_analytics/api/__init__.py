"""
Performance Analytics API

REST API endpoints for worker and team performance analytics.
"""

from .views import (
    WorkerPerformanceView,
    WorkerTrendsView,
    WorkerAchievementsView,
    TeamPerformanceView,
    CoachingQueueView,
    TopPerformersView,
    KudosCreateView,
)
from .permissions import IsSupervisorOrAdmin
from .serializers import (
    WorkerMetricsSerializer,
    TeamMetricsSerializer,
    KudosSerializer,
    AchievementSerializer,
    CoachingSessionSerializer,
)

__all__ = [
    'WorkerPerformanceView',
    'WorkerTrendsView',
    'WorkerAchievementsView',
    'TeamPerformanceView',
    'CoachingQueueView',
    'TopPerformersView',
    'KudosCreateView',
    'IsSupervisorOrAdmin',
    'WorkerMetricsSerializer',
    'TeamMetricsSerializer',
    'KudosSerializer',
    'AchievementSerializer',
    'CoachingSessionSerializer',
]
