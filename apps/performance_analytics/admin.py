"""
Performance Analytics Admin

Admin interface for performance metrics management.
"""

from django.contrib import admin
from apps.performance_analytics.models import (
    WorkerDailyMetrics,
    TeamDailyMetrics,
    CohortBenchmark,
    PerformanceStreak,
    Kudos,
    Achievement,
    WorkerAchievement,
    CoachingSession,
)


@admin.register(WorkerDailyMetrics)
class WorkerDailyMetricsAdmin(admin.ModelAdmin):
    """Admin for worker daily metrics."""
    
    list_display = [
        'worker', 'date', 'balanced_performance_index',
        'performance_band', 'site', 'shift_type'
    ]
    list_filter = ['date', 'performance_band', 'site', 'shift_type', 'role']
    search_fields = ['worker__loginid', 'worker__first_name', 'worker__last_name']
    readonly_fields = [
        'balanced_performance_index', 'attendance_score', 'task_score',
        'patrol_score', 'work_order_score', 'compliance_score', 'bpi_percentile'
    ]
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Identification', {
            'fields': ('tenant', 'date', 'worker', 'site', 'role', 'shift_type')
        }),
        ('Exposure', {
            'fields': ('scheduled_hours', 'worked_hours', 'scheduled_shifts')
        }),
        ('Scores', {
            'fields': (
                'balanced_performance_index', 'performance_band', 'bpi_percentile',
                'attendance_score', 'task_score', 'patrol_score',
                'work_order_score', 'compliance_score'
            )
        }),
        ('Attendance Metrics', {
            'fields': ('on_time_punches', 'late_punches', 'total_late_minutes', 'geofence_violations'),
            'classes': ('collapse',)
        }),
        ('Task Metrics', {
            'fields': ('tasks_assigned', 'tasks_completed', 'tasks_within_sla', 'task_quality_avg'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TeamDailyMetrics)
class TeamDailyMetricsAdmin(admin.ModelAdmin):
    """Admin for team daily metrics."""
    
    list_display = ['site', 'date', 'shift_type', 'active_workers', 'team_bpi_avg', 'sla_hit_rate_avg']
    list_filter = ['date', 'site', 'shift_type']
    date_hierarchy = 'date'


@admin.register(CohortBenchmark)
class CohortBenchmarkAdmin(admin.ModelAdmin):
    """Admin for cohort benchmarks."""
    
    list_display = ['cohort_key', 'metric_name', 'period_start', 'period_end', 'sample_size', 'median']
    list_filter = ['metric_name', 'period_start']
    search_fields = ['cohort_key']


@admin.register(PerformanceStreak)
class PerformanceStreakAdmin(admin.ModelAdmin):
    """Admin for performance streaks."""
    
    list_display = ['worker', 'streak_type', 'current_count', 'best_count', 'started_date']
    list_filter = ['streak_type', 'worker']
    search_fields = ['worker__loginid']


@admin.register(Kudos)
class KudosAdmin(admin.ModelAdmin):
    """Admin for kudos."""
    
    list_display = ['recipient', 'giver', 'kudos_type', 'created_at', 'visibility']
    list_filter = ['kudos_type', 'visibility', 'created_at']
    search_fields = ['recipient__loginid', 'giver__loginid', 'message']


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Admin for achievement definitions."""
    
    list_display = ['icon', 'name', 'rarity', 'points', 'category']
    list_filter = ['rarity', 'category']
    search_fields = ['name', 'code']


@admin.register(WorkerAchievement)
class WorkerAchievementAdmin(admin.ModelAdmin):
    """Admin for worker achievements."""
    
    list_display = ['worker', 'achievement', 'earned_date', 'count']
    list_filter = ['achievement', 'earned_date']
    search_fields = ['worker__loginid']


@admin.register(CoachingSession)
class CoachingSessionAdmin(admin.ModelAdmin):
    """Admin for coaching sessions."""
    
    list_display = ['worker', 'coach', 'session_date', 'session_type', 'follow_up_completed']
    list_filter = ['session_type', 'session_date', 'follow_up_completed']
    search_fields = ['worker__loginid', 'coach__loginid']
    date_hierarchy = 'session_date'
