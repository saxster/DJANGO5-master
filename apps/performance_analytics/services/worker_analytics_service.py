"""
Worker Analytics Service

Prepares dashboard and analytics data for individual workers.

Compliance:
- Rule #7: Service method < 30 lines
- Rule #11: Specific exception handling
- Rule #14: Type hints and docstrings
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

from django.db.models import Avg, Q, Count
from django.utils import timezone

from apps.performance_analytics.models import (
    WorkerDailyMetrics,
    PerformanceStreak,
    WorkerAchievement,
    Achievement
)
from apps.peoples.models import People
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS


class WorkerAnalyticsService:
    """
    Service for worker-specific performance analytics.
    
    Provides dashboard data, trends, achievements, and improvement suggestions.
    """
    
    @staticmethod
    def get_worker_dashboard(worker: People, period_days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for a worker.
        
        Args:
            worker: Worker/People instance
            period_days: Number of days to analyze (default 30)
            
        Returns:
            Dictionary with:
            - current_bpi: Current BPI score
            - percentile: Performance percentile
            - band: Performance band
            - component_scores: Breakdown of score components
            - trends: Time series data
            - streaks: Active streaks
            - achievements: Achievements earned this period
            - focus_areas: Improvement suggestions
            - team_comparison: vs team averages
            
        Raises:
            ValueError: If worker is None or period_days invalid
            DatabaseException: On database errors
        """
        if not worker:
            raise ValueError("Worker cannot be None")
        if period_days < 1 or period_days > 365:
            raise ValueError("period_days must be between 1 and 365")
        
        try:
            start_date = timezone.now().date() - timedelta(days=period_days)
            
            # Get latest metrics
            latest_metrics = WorkerDailyMetrics.objects.filter(
                worker=worker,
                tenant=worker.tenant
            ).select_related('site').order_by('-date').first()
            
            if not latest_metrics:
                return WorkerAnalyticsService._get_empty_dashboard()
            
            # Component scores
            component_scores = {
                'attendance': float(latest_metrics.attendance_score),
                'task_performance': float(latest_metrics.task_score),
                'patrol_quality': float(latest_metrics.patrol_score),
                'work_orders': float(latest_metrics.work_order_score),
                'compliance': float(latest_metrics.compliance_score)
            }
            
            # Get trends
            trends = WorkerAnalyticsService.get_worker_trends(worker, period_days)
            
            # Get streaks
            streaks = WorkerAnalyticsService._get_active_streaks(worker)
            
            # Get achievements earned this period
            achievements = WorkerAnalyticsService._get_recent_achievements(
                worker, start_date
            )
            
            # Get focus areas
            focus_areas = WorkerAnalyticsService.get_focus_areas(worker)
            
            # Team comparison
            team_comparison = WorkerAnalyticsService._get_team_comparison(
                worker, latest_metrics
            )
            
            return {
                'current_bpi': float(latest_metrics.balanced_performance_index),
                'percentile': latest_metrics.bpi_percentile,
                'band': latest_metrics.performance_band,
                'component_scores': component_scores,
                'trends': trends,
                'streaks': streaks,
                'achievements': achievements,
                'focus_areas': focus_areas,
                'team_comparison': team_comparison,
                'last_updated': latest_metrics.date.isoformat()
            }
        
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_worker_dashboard: {e}")
    
    @staticmethod
    def get_worker_trends(worker: People, period_days: int = 90) -> Dict[str, Any]:
        """
        Get time series performance data for a worker.
        
        Args:
            worker: Worker/People instance
            period_days: Number of days to retrieve (default 90)
            
        Returns:
            Dictionary with time series arrays for:
            - dates: List of dates
            - bpi: BPI scores
            - attendance: Attendance scores
            - task: Task scores
            - patrol: Patrol scores
            - compliance: Compliance scores
            
        Raises:
            ValueError: If worker is None
            DatabaseException: On database errors
        """
        if not worker:
            raise ValueError("Worker cannot be None")
        
        try:
            start_date = timezone.now().date() - timedelta(days=period_days)
            
            metrics = WorkerDailyMetrics.objects.filter(
                worker=worker,
                tenant=worker.tenant,
                date__gte=start_date
            ).order_by('date').values(
                'date',
                'balanced_performance_index',
                'attendance_score',
                'task_score',
                'patrol_score',
                'compliance_score'
            )
            
            return {
                'dates': [m['date'].isoformat() for m in metrics],
                'bpi': [float(m['balanced_performance_index']) for m in metrics],
                'attendance': [float(m['attendance_score']) for m in metrics],
                'task': [float(m['task_score']) for m in metrics],
                'patrol': [float(m['patrol_score']) for m in metrics],
                'compliance': [float(m['compliance_score']) for m in metrics]
            }
        
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_worker_trends: {e}")
    
    @staticmethod
    def get_worker_achievements(worker: People) -> List[Dict[str, Any]]:
        """
        Get all achievements earned by a worker.
        
        Args:
            worker: Worker/People instance
            
        Returns:
            List of achievement dictionaries with:
            - code: Achievement code
            - name: Achievement name
            - description: Description
            - icon: Icon/emoji
            - earned_date: When earned
            - count: Times earned
            - rarity: Rarity level
            
        Raises:
            ValueError: If worker is None
            DatabaseException: On database errors
        """
        if not worker:
            raise ValueError("Worker cannot be None")
        
        try:
            worker_achievements = WorkerAchievement.objects.filter(
                worker=worker,
                tenant=worker.tenant
            ).select_related('achievement').order_by('-earned_date')
            
            return [
                {
                    'code': wa.achievement.code,
                    'name': wa.achievement.name,
                    'description': wa.achievement.description,
                    'icon': wa.achievement.icon,
                    'earned_date': wa.earned_date.isoformat(),
                    'count': wa.count,
                    'rarity': wa.achievement.rarity,
                    'category': wa.achievement.category,
                    'points': wa.achievement.points
                }
                for wa in worker_achievements
            ]
        
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_worker_achievements: {e}")
    
    @staticmethod
    def get_focus_areas(worker: People) -> List[Dict[str, Any]]:
        """
        Get specific improvement suggestions for a worker.
        
        Analyzes last 30 days of metrics to identify areas below targets.
        
        Args:
            worker: Worker/People instance
            
        Returns:
            List of focus area dictionaries with:
            - area: Performance area name
            - current_score: Current average score
            - target_score: Target to reach
            - priority: high/medium/low
            - suggestion: Specific improvement action
            
        Raises:
            ValueError: If worker is None
            DatabaseException: On database errors
        """
        if not worker:
            raise ValueError("Worker cannot be None")
        
        try:
            start_date = timezone.now().date() - timedelta(days=30)
            
            avg_scores = WorkerDailyMetrics.objects.filter(
                worker=worker,
                tenant=worker.tenant,
                date__gte=start_date
            ).aggregate(
                avg_attendance=Avg('attendance_score'),
                avg_task=Avg('task_score'),
                avg_patrol=Avg('patrol_score'),
                avg_work_order=Avg('work_order_score'),
                avg_compliance=Avg('compliance_score')
            )
            
            focus_areas = []
            targets = {
                'attendance': (avg_scores['avg_attendance'], 90, 'Attendance & Punctuality'),
                'task': (avg_scores['avg_task'], 85, 'Task Performance'),
                'patrol': (avg_scores['avg_patrol'], 85, 'Patrol Quality'),
                'work_order': (avg_scores['avg_work_order'], 80, 'Work Order Quality'),
                'compliance': (avg_scores['avg_compliance'], 95, 'Compliance & Safety')
            }
            
            for area_key, (current, target, display_name) in targets.items():
                if current is None:
                    continue
                
                current = float(current)
                if current < target:
                    gap = target - current
                    priority = 'high' if gap > 15 else 'medium' if gap > 8 else 'low'
                    
                    focus_areas.append({
                        'area': display_name,
                        'current_score': round(current, 1),
                        'target_score': target,
                        'gap': round(gap, 1),
                        'priority': priority,
                        'suggestion': WorkerAnalyticsService._get_suggestion(
                            area_key, current, target
                        )
                    })
            
            # Sort by priority and gap
            priority_order = {'high': 3, 'medium': 2, 'low': 1}
            focus_areas.sort(
                key=lambda x: (priority_order[x['priority']], x['gap']),
                reverse=True
            )
            
            return focus_areas
        
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_focus_areas: {e}")
    
    # Private helper methods
    
    @staticmethod
    def _get_empty_dashboard() -> Dict[str, Any]:
        """Return empty dashboard structure when no data available."""
        return {
            'current_bpi': 0,
            'percentile': 50,
            'band': 'developing',
            'component_scores': {
                'attendance': 0,
                'task_performance': 0,
                'patrol_quality': 0,
                'work_orders': 0,
                'compliance': 0
            },
            'trends': {'dates': [], 'bpi': [], 'attendance': [], 'task': [], 'patrol': [], 'compliance': []},
            'streaks': [],
            'achievements': [],
            'focus_areas': [],
            'team_comparison': {},
            'last_updated': None
        }
    
    @staticmethod
    def _get_active_streaks(worker: People) -> List[Dict[str, Any]]:
        """Get all active streaks for a worker."""
        try:
            streaks = PerformanceStreak.objects.filter(
                worker=worker,
                tenant=worker.tenant,
                current_count__gt=0
            ).order_by('-current_count')
            
            return [
                {
                    'type': s.get_streak_type_display(),
                    'current': s.current_count,
                    'best': s.best_count,
                    'started': s.started_date.isoformat()
                }
                for s in streaks
            ]
        except DATABASE_EXCEPTIONS:
            return []
    
    @staticmethod
    def _get_recent_achievements(worker: People, since_date) -> List[Dict[str, Any]]:
        """Get achievements earned since a specific date."""
        try:
            recent = WorkerAchievement.objects.filter(
                worker=worker,
                tenant=worker.tenant,
                earned_date__gte=since_date
            ).select_related('achievement').order_by('-earned_date')
            
            return [
                {
                    'name': wa.achievement.name,
                    'icon': wa.achievement.icon,
                    'earned_date': wa.earned_date.isoformat(),
                    'rarity': wa.achievement.rarity
                }
                for wa in recent
            ]
        except DATABASE_EXCEPTIONS:
            return []
    
    @staticmethod
    def _get_team_comparison(worker: People, latest_metrics: WorkerDailyMetrics) -> Dict[str, Any]:
        """Compare worker performance to team averages."""
        try:
            team_avg = WorkerDailyMetrics.objects.filter(
                tenant=worker.tenant,
                site=latest_metrics.site,
                date=latest_metrics.date
            ).aggregate(
                avg_bpi=Avg('balanced_performance_index'),
                avg_attendance=Avg('attendance_score'),
                avg_task=Avg('task_score'),
                avg_patrol=Avg('patrol_score')
            )
            
            return {
                'bpi_vs_team': round(
                    float(latest_metrics.balanced_performance_index) - float(team_avg['avg_bpi'] or 0),
                    1
                ),
                'attendance_vs_team': round(
                    float(latest_metrics.attendance_score) - float(team_avg['avg_attendance'] or 0),
                    1
                ),
                'task_vs_team': round(
                    float(latest_metrics.task_score) - float(team_avg['avg_task'] or 0),
                    1
                ),
                'patrol_vs_team': round(
                    float(latest_metrics.patrol_score) - float(team_avg['avg_patrol'] or 0),
                    1
                )
            }
        except DATABASE_EXCEPTIONS:
            return {}
    
    @staticmethod
    def _get_suggestion(area: str, current: float, target: float) -> str:
        """Get specific improvement suggestion for an area."""
        suggestions = {
            'attendance': "Focus on consistent on-time arrivals and proper punch procedures",
            'task': "Prioritize completing tasks within SLA and improving quality ratings",
            'patrol': "Ensure all checkpoints are scanned on time during patrols",
            'work_order': "Complete work orders within SLA and request quality feedback",
            'compliance': "Submit all required reports and maintain current certifications"
        }
        return suggestions.get(area, "Review performance metrics and consult supervisor")
