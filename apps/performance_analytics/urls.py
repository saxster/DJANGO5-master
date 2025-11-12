"""
Performance Analytics URL Configuration
"""

from django.urls import path
from apps.performance_analytics.api import views

app_name = 'performance_analytics'

urlpatterns = [
    # Worker Endpoints
    path('me/', views.WorkerPerformanceView.as_view(), name='worker-performance'),
    path('me/trends/', views.WorkerTrendsView.as_view(), name='worker-trends'),
    path('me/achievements/', views.WorkerAchievementsView.as_view(), name='worker-achievements'),
    
    # Team Endpoints
    path('team/<int:site_id>/', views.TeamPerformanceView.as_view(), name='team-performance'),
    path('coaching-queue/<int:site_id>/', views.CoachingQueueView.as_view(), name='coaching-queue'),
    path('top-performers/<int:site_id>/', views.TopPerformersView.as_view(), name='top-performers'),
    
    # Social/Recognition
    path('kudos/', views.KudosCreateView.as_view(), name='kudos-create'),
]
