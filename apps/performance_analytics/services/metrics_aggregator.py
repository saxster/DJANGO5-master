"""
Metrics Aggregator Service

Orchestrates all metric calculations for workers and teams.
Main entry point for daily performance metric aggregation.

Compliance:
- Rule #6: Service class < 150 lines
- Rule #11: Specific exception handling
- Methods < 50 lines each
"""

import logging
from datetime import date
from typing import Dict, Optional, List
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, StdDev, Count, Q
from django.utils import timezone

from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.performance_analytics.models import (
    WorkerDailyMetrics,
    TeamDailyMetrics,
    PerformanceStreak,
    WorkerAchievement,
    Achievement,
)
from apps.performance_analytics.services.attendance_metrics_calculator import (
    AttendanceMetricsCalculator
)
from apps.performance_analytics.services.task_metrics_calculator import (
    TaskMetricsCalculator
)
from apps.performance_analytics.services.patrol_metrics_calculator import (
    PatrolMetricsCalculator
)
from apps.performance_analytics.services.work_order_metrics_calculator import (
    WorkOrderMetricsCalculator
)
from apps.performance_analytics.services.compliance_metrics_calculator import (
    ComplianceMetricsCalculator
)
from apps.performance_analytics.services.bpi_calculator import (
    BalancedPerformanceIndexCalculator
)
from apps.performance_analytics.services.cohort_analyzer import CohortAnalyzer
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """
    Orchestrates all metric calculations for workers and teams.
    
    Main entry point for daily/nightly performance aggregation.
    Coordinates individual calculators and updates all metric records.
    """
    
    def __init__(self):
        """Initialize all calculator services."""
        self.attendance_calc = AttendanceMetricsCalculator()
        self.task_calc = TaskMetricsCalculator()
        self.patrol_calc = PatrolMetricsCalculator()
        self.work_order_calc = WorkOrderMetricsCalculator()
        self.compliance_calc = ComplianceMetricsCalculator()
        self.bpi_calc = BalancedPerformanceIndexCalculator()
        self.cohort_analyzer = CohortAnalyzer()
    
    def aggregate_all_metrics(self, target_date: date) -> Dict:
        """
        Main orchestrator for daily aggregation.
        
        Args:
            target_date: Date to aggregate metrics for
        
        Returns:
            Summary dict with counts and errors
        """
        summary = {
            'date': target_date,
            'workers_processed': 0,
            'teams_processed': 0,
            'errors': [],
        }
        
        active_workers = People.objects.filter(
            is_active=True,
            organizational__employmentstatus='Active'
        )
        
        for worker in active_workers:
            try:
                self.aggregate_worker_metrics(worker, target_date)
                summary['workers_processed'] += 1
            except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
                logger.error(
                    f"Error aggregating metrics for {worker.loginid}: {e}",
                    exc_info=True
                )
                summary['errors'].append(str(e))
        
        sites = Bt.objects.filter(is_active=True)
        for site in sites:
            try:
                self.aggregate_team_metrics(site, target_date)
                summary['teams_processed'] += 1
            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    f"Error aggregating team metrics for {site.abbr}: {e}",
                    exc_info=True
                )
                summary['errors'].append(str(e))
        
        return summary
    
    def aggregate_worker_metrics(
        self,
        worker: People,
        target_date: date
    ) -> WorkerDailyMetrics:
        """
        Aggregate all metrics for a single worker on target date.
        
        Args:
            worker: Worker to aggregate metrics for
            target_date: Date to calculate metrics for
        
        Returns:
            Created/updated WorkerDailyMetrics record
        """
        with transaction.atomic():
            attendance_data = self.attendance_calc.calculate_metrics(
                worker, target_date
            )
            task_data = self.task_calc.calculate_metrics(worker, target_date)
            patrol_data = self.patrol_calc.calculate_metrics(worker, target_date)
            work_order_data = self.work_order_calc.calculate_metrics(
                worker, target_date
            )
            compliance_data = self.compliance_calc.calculate_metrics(
                worker, target_date
            )
            
            component_scores = {
                'attendance': attendance_data.get('score', 0),
                'tasks': task_data.get('score', 0),
                'patrols': patrol_data.get('score', 0),
                'work_orders': work_order_data.get('score', 0),
                'compliance': compliance_data.get('score', 0),
            }
            
            bpi = self.bpi_calc.calculate_bpi(component_scores)
            cohort_key = self._build_cohort_key(worker, target_date)
            
            metrics, created = WorkerDailyMetrics.objects.update_or_create(
                tenant=worker.tenant,
                worker=worker,
                date=target_date,
                defaults={
                    **attendance_data,
                    **task_data,
                    **patrol_data,
                    **work_order_data,
                    **compliance_data,
                    'balanced_performance_index': bpi,
                    'cohort_key': cohort_key,
                    'performance_band': self._get_performance_band(bpi),
                }
            )
            
            self.update_streaks(worker, metrics, target_date)
            self.check_and_award_achievements(worker, metrics, target_date)
            
            return metrics
    
    def aggregate_team_metrics(
        self,
        site: Bt,
        target_date: date,
        shift_type: Optional[str] = None
    ) -> TeamDailyMetrics:
        """
        Aggregate team-level metrics from worker metrics.
        
        Args:
            site: Site to aggregate for
            target_date: Date to aggregate
            shift_type: Optional shift type filter
        
        Returns:
            Created/updated TeamDailyMetrics record
        """
        filters = Q(site=site, date=target_date)
        if shift_type:
            filters &= Q(shift_type=shift_type)
        
        worker_metrics = WorkerDailyMetrics.objects.filter(filters)
        
        if not worker_metrics.exists():
            logger.warning(f"No worker metrics for {site.abbr} on {target_date}")
            return None
        
        aggregates = worker_metrics.aggregate(
            bpi_avg=Avg('balanced_performance_index'),
            bpi_std=StdDev('balanced_performance_index'),
            total_workers=Count('id'),
        )
        
        team_metrics, created = TeamDailyMetrics.objects.update_or_create(
            tenant=site.tenant,
            site=site,
            date=target_date,
            shift_type=shift_type,
            defaults={
                'active_workers': aggregates['total_workers'],
                'team_bpi_avg': aggregates['bpi_avg'] or 0,
                'team_bpi_std_dev': aggregates['bpi_std'] or 0,
                'workers_exceptional': worker_metrics.filter(
                    performance_band='exceptional'
                ).count(),
                'workers_strong': worker_metrics.filter(
                    performance_band='strong'
                ).count(),
                'workers_solid': worker_metrics.filter(
                    performance_band='solid'
                ).count(),
                'workers_developing': worker_metrics.filter(
                    performance_band='developing'
                ).count(),
                'workers_needs_support': worker_metrics.filter(
                    performance_band='needs_support'
                ).count(),
            }
        )
        
        return team_metrics
    
    def update_streaks(
        self,
        worker: People,
        metrics: WorkerDailyMetrics,
        date: date
    ) -> None:
        """
        Update performance streak records.
        
        Args:
            worker: Worker to update streaks for
            metrics: Daily metrics to check
            date: Current date
        """
        streak_checks = {
            'on_time': metrics.late_punches == 0 and metrics.ncns_incidents == 0,
            'perfect_patrol': (
                metrics.checkpoints_expected > 0 and
                metrics.checkpoints_missed == 0
            ),
            'sla_hit': (
                metrics.tasks_assigned > 0 and
                metrics.tasks_within_sla == metrics.tasks_assigned
            ),
            'zero_ncns': metrics.ncns_incidents == 0,
        }
        
        for streak_type, continues in streak_checks.items():
            streak, created = PerformanceStreak.objects.get_or_create(
                tenant=worker.tenant,
                worker=worker,
                streak_type=streak_type,
                defaults={'started_date': date, 'last_updated': date}
            )
            
            if continues:
                streak.increment()
                streak.last_updated = date
            else:
                streak.break_streak(date)
                streak.started_date = date
            
            streak.save()
    
    def check_and_award_achievements(
        self,
        worker: People,
        metrics: WorkerDailyMetrics,
        date: date
    ) -> None:
        """
        Check achievement criteria and award if met.
        
        Args:
            worker: Worker to check achievements for
            metrics: Daily metrics to evaluate
            date: Achievement earned date
        """
        achievements = Achievement.objects.all()
        
        for achievement in achievements:
            if self._meets_criteria(worker, metrics, achievement):
                WorkerAchievement.objects.update_or_create(
                    tenant=worker.tenant,
                    worker=worker,
                    achievement=achievement,
                    defaults={
                        'earned_date': date,
                        'count': 1,
                    }
                )
    
    def _build_cohort_key(self, worker: People, target_date: date) -> str:
        """Build cohort key for worker."""
        return f"{worker.organizational.site_id}|{worker.role}|{worker.shift}|{target_date.month}"
    
    def _get_performance_band(self, bpi: Decimal) -> str:
        """Determine performance band from BPI score."""
        if bpi >= 90:
            return 'exceptional'
        elif bpi >= 75:
            return 'strong'
        elif bpi >= 60:
            return 'solid'
        elif bpi >= 40:
            return 'developing'
        else:
            return 'needs_support'
    
    def _meets_criteria(
        self,
        worker: People,
        metrics: WorkerDailyMetrics,
        achievement: Achievement
    ) -> bool:
        """Check if worker meets achievement criteria."""
        criteria = achievement.criteria
        
        if 'bpi_threshold' in criteria:
            if metrics.balanced_performance_index < criteria['bpi_threshold']:
                return False
        
        if 'on_time_rate' in criteria:
            total_punches = metrics.on_time_punches + metrics.late_punches
            if total_punches > 0:
                rate = (metrics.on_time_punches / total_punches) * 100
                if rate < criteria['on_time_rate']:
                    return False
        
        return True
