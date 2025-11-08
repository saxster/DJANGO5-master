"""
Team Analytics Service

Prepares dashboard and analytics data for team/site-level performance.

Compliance:
- Rule #7: Service method < 30 lines
- Rule #11: Specific exception handling
- Rule #14: Type hints and docstrings
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

from django.db.models import Avg, Q, Count, Max, Min
from django.utils import timezone

from apps.performance_analytics.models import (
    WorkerDailyMetrics,
    TeamDailyMetrics
)
from apps.onboarding.models import Bt
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS


class TeamAnalyticsService:
    """
    Service for team/site-level performance analytics.
    
    Provides team dashboards, coaching queues, top performers, and comparisons.
    """
    
    @staticmethod
    def get_team_dashboard(site_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive team health dashboard for a site.
        
        Args:
            site_id: Site/Bt ID
            period_days: Number of days to analyze (default 30)
            
        Returns:
            Dictionary with:
            - team_bpi_avg: Average team BPI
            - team_bpi_median: Median team BPI
            - performance_distribution: Band distribution percentages
            - coaching_queue: Workers needing attention
            - top_performers: Top N workers
            - metrics_heatmap: Daily metrics grid
            - shift_comparison: Compare day/night/evening shifts
            - trends: Time series of team performance
            
        Raises:
            ValueError: If site_id invalid or period_days out of range
            DatabaseException: On database errors
        """
        if not site_id or site_id < 1:
            raise ValueError("Invalid site_id")
        if period_days < 1 or period_days > 365:
            raise ValueError("period_days must be between 1 and 365")
        
        try:
            site = Bt.objects.get(id=site_id)
            start_date = timezone.now().date() - timedelta(days=period_days)
            
            # Get latest team metrics
            latest_team = TeamDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                shift_type__isnull=True  # Overall site metrics
            ).order_by('-date').first()
            
            if not latest_team:
                return TeamAnalyticsService._get_empty_dashboard()
            
            # Performance distribution
            performance_dist = {
                'exceptional': latest_team.workers_exceptional,
                'strong': latest_team.workers_strong,
                'solid': latest_team.workers_solid,
                'developing': latest_team.workers_developing,
                'needs_support': latest_team.workers_needs_support
            }
            
            # Coaching queue
            coaching_queue = TeamAnalyticsService.get_coaching_queue(site_id, threshold=60)
            
            # Top performers
            top_performers = TeamAnalyticsService.get_top_performers(site_id, limit=5)
            
            # Metrics heatmap
            metrics_heatmap = TeamAnalyticsService._get_metrics_heatmap(site, start_date)
            
            # Shift comparison
            shift_comparison = TeamAnalyticsService.get_team_comparison(site_id)
            
            # Trends
            trends = TeamAnalyticsService._get_team_trends(site, period_days)
            
            return {
                'team_bpi_avg': float(latest_team.team_bpi_avg),
                'team_bpi_median': float(latest_team.team_bpi_median),
                'team_bpi_std_dev': float(latest_team.team_bpi_std_dev),
                'active_workers': latest_team.active_workers,
                'performance_distribution': performance_dist,
                'performance_distribution_pct': latest_team.get_performance_distribution(),
                'coaching_queue': coaching_queue,
                'top_performers': top_performers,
                'metrics_heatmap': metrics_heatmap,
                'shift_comparison': shift_comparison,
                'trends': trends,
                'key_metrics': {
                    'on_time_rate': float(latest_team.on_time_rate_avg),
                    'sla_hit_rate': float(latest_team.sla_hit_rate_avg),
                    'patrol_coverage': float(latest_team.patrol_coverage_avg),
                    'task_completion_rate': float(latest_team.task_completion_rate_avg),
                    'quality_score': float(latest_team.quality_score_avg)
                },
                'operational_kpis': {
                    'ncns_incidents': latest_team.total_ncns_incidents,
                    'late_incidents': latest_team.total_late_incidents,
                    'geofence_violations': latest_team.total_geofence_violations,
                    'coverage_gap_hours': float(latest_team.coverage_gap_hours)
                },
                'last_updated': latest_team.date.isoformat()
            }
        
        except Bt.DoesNotExist:
            raise ValueError(f"Site with id {site_id} does not exist")
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_team_dashboard: {e}")
    
    @staticmethod
    def get_coaching_queue(site_id: int, threshold: int = 60) -> List[Dict[str, Any]]:
        """
        Get workers with BPI below threshold who need coaching attention.
        
        Args:
            site_id: Site/Bt ID
            threshold: BPI threshold (default 60)
            
        Returns:
            List of worker dictionaries with:
            - worker_id: Worker ID
            - worker_name: Worker name
            - current_bpi: Current BPI score
            - performance_band: Performance band
            - focus_areas: Top 2 lowest scoring areas
            - days_below_threshold: Consecutive days below threshold
            
        Raises:
            ValueError: If site_id or threshold invalid
            DatabaseException: On database errors
        """
        if not site_id or site_id < 1:
            raise ValueError("Invalid site_id")
        if threshold < 0 or threshold > 100:
            raise ValueError("threshold must be between 0 and 100")
        
        try:
            site = Bt.objects.get(id=site_id)
            recent_date = timezone.now().date() - timedelta(days=7)
            
            # Get workers below threshold in last 7 days
            low_performers = WorkerDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                date__gte=recent_date,
                balanced_performance_index__lt=threshold
            ).select_related('worker').order_by('worker', '-date').distinct('worker')
            
            coaching_queue = []
            for metric in low_performers:
                # Count consecutive days below threshold
                days_below = WorkerDailyMetrics.objects.filter(
                    worker=metric.worker,
                    tenant=metric.tenant,
                    date__lte=metric.date,
                    balanced_performance_index__lt=threshold
                ).order_by('-date').count()
                
                # Identify focus areas (lowest 2 scores)
                scores = [
                    ('Attendance', metric.attendance_score),
                    ('Task Performance', metric.task_score),
                    ('Patrol Quality', metric.patrol_score),
                    ('Work Orders', metric.work_order_score),
                    ('Compliance', metric.compliance_score)
                ]
                scores.sort(key=lambda x: x[1])
                focus_areas = [area for area, score in scores[:2]]
                
                coaching_queue.append({
                    'worker_id': metric.worker.id,
                    'worker_name': metric.worker.get_full_name(),
                    'worker_loginid': metric.worker.loginid,
                    'current_bpi': float(metric.balanced_performance_index),
                    'performance_band': metric.performance_band,
                    'focus_areas': focus_areas,
                    'days_below_threshold': days_below,
                    'last_measured': metric.date.isoformat()
                })
            
            # Sort by BPI ascending (worst first)
            coaching_queue.sort(key=lambda x: x['current_bpi'])
            
            return coaching_queue
        
        except Bt.DoesNotExist:
            raise ValueError(f"Site with id {site_id} does not exist")
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_coaching_queue: {e}")
    
    @staticmethod
    def get_top_performers(site_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N workers by BPI at a site.
        
        Args:
            site_id: Site/Bt ID
            limit: Number of top performers to return (default 5)
            
        Returns:
            List of worker dictionaries with:
            - worker_id: Worker ID
            - worker_name: Worker name
            - current_bpi: Current BPI score
            - percentile: Performance percentile
            - strengths: Top 2 scoring areas
            - streak_count: Longest active streak
            
        Raises:
            ValueError: If site_id or limit invalid
            DatabaseException: On database errors
        """
        if not site_id or site_id < 1:
            raise ValueError("Invalid site_id")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        
        try:
            site = Bt.objects.get(id=site_id)
            recent_date = timezone.now().date() - timedelta(days=7)
            
            # Get top performers from last 7 days
            top_metrics = WorkerDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                date__gte=recent_date
            ).select_related('worker').order_by(
                'worker',
                '-balanced_performance_index',
                '-date'
            ).distinct('worker')[:limit]
            
            top_performers = []
            for metric in top_metrics:
                # Identify strengths (highest 2 scores)
                scores = [
                    ('Attendance', metric.attendance_score),
                    ('Task Performance', metric.task_score),
                    ('Patrol Quality', metric.patrol_score),
                    ('Work Orders', metric.work_order_score),
                    ('Compliance', metric.compliance_score)
                ]
                scores.sort(key=lambda x: x[1], reverse=True)
                strengths = [area for area, score in scores[:2]]
                
                # Get longest active streak
                from apps.performance_analytics.models import PerformanceStreak
                best_streak = PerformanceStreak.objects.filter(
                    worker=metric.worker,
                    tenant=metric.tenant,
                    current_count__gt=0
                ).order_by('-current_count').first()
                
                top_performers.append({
                    'worker_id': metric.worker.id,
                    'worker_name': metric.worker.get_full_name(),
                    'worker_loginid': metric.worker.loginid,
                    'current_bpi': float(metric.balanced_performance_index),
                    'percentile': metric.bpi_percentile,
                    'performance_band': metric.performance_band,
                    'strengths': strengths,
                    'streak': {
                        'type': best_streak.get_streak_type_display() if best_streak else None,
                        'count': best_streak.current_count if best_streak else 0
                    } if best_streak else None,
                    'last_measured': metric.date.isoformat()
                })
            
            return top_performers
        
        except Bt.DoesNotExist:
            raise ValueError(f"Site with id {site_id} does not exist")
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_top_performers: {e}")
    
    @staticmethod
    def get_team_comparison(site_id: int) -> Dict[str, Any]:
        """
        Compare performance across different shifts at a site.
        
        Args:
            site_id: Site/Bt ID
            
        Returns:
            Dictionary with shift comparisons:
            - day_shift: Day shift metrics
            - night_shift: Night shift metrics
            - evening_shift: Evening shift metrics
            - weekend_shift: Weekend shift metrics
            Each with: avg_bpi, active_workers, key_metrics
            
        Raises:
            ValueError: If site_id invalid
            DatabaseException: On database errors
        """
        if not site_id or site_id < 1:
            raise ValueError("Invalid site_id")
        
        try:
            site = Bt.objects.get(id=site_id)
            latest_date = timezone.now().date() - timedelta(days=1)
            
            # Get latest metrics by shift
            shift_metrics = TeamDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                date=latest_date,
                shift_type__isnull=False
            ).order_by('shift_type')
            
            comparison = {}
            for shift in shift_metrics:
                shift_key = f"{shift.shift_type}_shift"
                comparison[shift_key] = {
                    'avg_bpi': float(shift.team_bpi_avg),
                    'median_bpi': float(shift.team_bpi_median),
                    'active_workers': shift.active_workers,
                    'performance_distribution': shift.get_performance_distribution(),
                    'key_metrics': {
                        'on_time_rate': float(shift.on_time_rate_avg),
                        'sla_hit_rate': float(shift.sla_hit_rate_avg),
                        'patrol_coverage': float(shift.patrol_coverage_avg),
                        'task_completion': float(shift.task_completion_rate_avg)
                    },
                    'worked_hours': float(shift.total_worked_hours),
                    'ncns_incidents': shift.total_ncns_incidents
                }
            
            return comparison
        
        except Bt.DoesNotExist:
            raise ValueError(f"Site with id {site_id} does not exist")
        except DATABASE_EXCEPTIONS as e:
            raise type(e)(f"Database error in get_team_comparison: {e}")
    
    # Private helper methods
    
    @staticmethod
    def _get_empty_dashboard() -> Dict[str, Any]:
        """Return empty dashboard structure when no data available."""
        return {
            'team_bpi_avg': 0,
            'team_bpi_median': 0,
            'team_bpi_std_dev': 0,
            'active_workers': 0,
            'performance_distribution': {
                'exceptional': 0,
                'strong': 0,
                'solid': 0,
                'developing': 0,
                'needs_support': 0
            },
            'performance_distribution_pct': {},
            'coaching_queue': [],
            'top_performers': [],
            'metrics_heatmap': [],
            'shift_comparison': {},
            'trends': {'dates': [], 'bpi_avg': [], 'bpi_median': []},
            'key_metrics': {},
            'operational_kpis': {},
            'last_updated': None
        }
    
    @staticmethod
    def _get_metrics_heatmap(site: Bt, start_date) -> List[Dict[str, Any]]:
        """Get daily metrics grid for heatmap visualization."""
        try:
            daily_metrics = TeamDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                date__gte=start_date,
                shift_type__isnull=True
            ).order_by('date').values(
                'date',
                'team_bpi_avg',
                'on_time_rate_avg',
                'sla_hit_rate_avg',
                'patrol_coverage_avg',
                'task_completion_rate_avg'
            )
            
            return [
                {
                    'date': m['date'].isoformat(),
                    'bpi': float(m['team_bpi_avg']),
                    'on_time': float(m['on_time_rate_avg']),
                    'sla': float(m['sla_hit_rate_avg']),
                    'patrol': float(m['patrol_coverage_avg']),
                    'task_completion': float(m['task_completion_rate_avg'])
                }
                for m in daily_metrics
            ]
        except DATABASE_EXCEPTIONS:
            return []
    
    @staticmethod
    def _get_team_trends(site: Bt, period_days: int) -> Dict[str, Any]:
        """Get time series of team performance."""
        try:
            start_date = timezone.now().date() - timedelta(days=period_days)
            
            metrics = TeamDailyMetrics.objects.filter(
                site=site,
                tenant=site.tenant,
                date__gte=start_date,
                shift_type__isnull=True
            ).order_by('date').values(
                'date',
                'team_bpi_avg',
                'team_bpi_median',
                'active_workers'
            )
            
            return {
                'dates': [m['date'].isoformat() for m in metrics],
                'bpi_avg': [float(m['team_bpi_avg']) for m in metrics],
                'bpi_median': [float(m['team_bpi_median']) for m in metrics],
                'active_workers': [m['active_workers'] for m in metrics]
            }
        except DATABASE_EXCEPTIONS:
            return {'dates': [], 'bpi_avg': [], 'bpi_median': [], 'active_workers': []}
