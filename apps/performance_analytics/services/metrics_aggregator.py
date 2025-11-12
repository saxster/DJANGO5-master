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
from contextlib import nullcontext
from datetime import date
from typing import Dict, Optional, List, Iterable, Tuple
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, StdDev, Count, Q, Max, Min
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
    WORKER_BATCH_SIZE = getattr(settings, 'PERF_ANALYTICS_WORKER_BATCH_SIZE', 50)
    
    def __init__(self):
        """Initialize all calculator services."""
        self.attendance_calc = AttendanceMetricsCalculator()
        self.task_calc = TaskMetricsCalculator()
        self.patrol_calc = PatrolMetricsCalculator()
        self.work_order_calc = WorkOrderMetricsCalculator()
        self.compliance_calc = ComplianceMetricsCalculator()
        self.bpi_calc = BalancedPerformanceIndexCalculator()
        self.cohort_analyzer = CohortAnalyzer()
    
    @classmethod
    def aggregate_all_metrics(cls, target_date: date) -> Dict:
        """Class-level entry point to aggregate all metrics."""
        return cls()._aggregate_all_metrics(target_date)

    def _aggregate_all_metrics(self, target_date: date) -> Dict:
        """Main orchestrator for daily aggregation."""
        summary = {
            'date': target_date,
            'workers_processed': 0,
            'teams_updated': 0,
            'errors': [],
            'summary_stats': {},
        }
        
        worker_qs = self._get_active_workers_queryset()
        for scope, workers in self._iter_workers_by_scope(worker_qs):
            self._process_worker_scope_batch(scope, workers, target_date, summary)
        
        self._aggregate_active_sites(target_date, summary)
        summary['summary_stats'] = self._get_summary_stats(target_date)
        # Backwards compatibility for older callers still reading teams_processed
        summary['teams_processed'] = summary['teams_updated']
        
        return summary

    def _get_active_workers_queryset(self):
        """
        Return optimized queryset of active workers for batching.

        Note: Filters on People.is_active only. The organizational.employmentstatus
        field does not exist in PeopleOrganizational model (removed during schema cleanup).
        Active status is determined by People.is_active flag.
        """
        return (
            People.objects.filter(
                is_active=True
            )
            .select_related('tenant', 'organizational__site')
            .order_by('tenant_id', 'organizational__site_id', 'id')
        )

    def _iter_workers_by_scope(
        self,
        queryset
    ) -> Iterable[Tuple[Tuple[Optional[int], Optional[int]], List[People]]]:
        """Yield workers grouped by (tenant_id, site_id) scopes in batches."""
        batch: List[People] = []
        current_scope: Optional[Tuple[Optional[int], Optional[int]]] = None
        for worker in queryset.iterator(chunk_size=self.WORKER_BATCH_SIZE):
            site_id = getattr(getattr(worker, 'organizational', None), 'site_id', None)
            scope = (worker.tenant_id, site_id)
            if current_scope is None:
                current_scope = scope
            if scope != current_scope or len(batch) >= self.WORKER_BATCH_SIZE:
                if batch:
                    yield current_scope, batch
                batch = []
                current_scope = scope
            batch.append(worker)
        if batch:
            yield current_scope, batch

    def _process_worker_scope_batch(
        self,
        scope: Tuple[Optional[int], Optional[int]],
        workers: List[People],
        target_date: date,
        summary: Dict
    ) -> None:
        """Process a batch of workers sharing the same tenant/site scope."""
        if not workers:
            return
        tenant_id, site_id = scope
        with transaction.atomic():
            for worker in workers:
                savepoint = transaction.savepoint()
                try:
                    self._aggregate_worker_metrics(
                        worker,
                        target_date,
                        use_transaction=False
                    )
                    transaction.savepoint_commit(savepoint)
                    summary['workers_processed'] += 1
                except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
                    transaction.savepoint_rollback(savepoint)
                    logger.error(
                        "Error aggregating metrics for %s (tenant=%s, site=%s): %s",
                        worker.loginid,
                        tenant_id,
                        site_id,
                        e,
                        exc_info=True
                    )
                    summary['errors'].append(str(e))

    def _aggregate_active_sites(self, target_date: date, summary: Dict) -> None:
        """Aggregate team metrics for all active sites."""
        sites = Bt.objects.filter(is_active=True).select_related('tenant')
        for site in sites.iterator():
            try:
                team_metrics = self._aggregate_team_metrics(site, target_date)
                if team_metrics:
                    summary['teams_updated'] += 1
            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    "Error aggregating team metrics for %s: %s",
                    site.abbr,
                    e,
                    exc_info=True
                )
                summary['errors'].append(str(e))

    def _get_summary_stats(self, target_date: date) -> Dict:
        """Summarize aggregation results using staging tables."""
        worker_metrics = WorkerDailyMetrics.objects.filter(date=target_date)
        team_metrics = TeamDailyMetrics.objects.filter(date=target_date)
        worker_count = worker_metrics.count()
        if worker_count == 0:
            return {
                'workers': 0,
                'avg_bpi': 0,
                'max_bpi': 0,
                'min_bpi': 0,
                'exceptional_workers': 0,
                'needs_support_workers': 0,
                'teams': team_metrics.count(),
                'avg_team_bpi': 0,
            }
        worker_aggregates = worker_metrics.aggregate(
            avg_bpi=Avg('balanced_performance_index'),
            max_bpi=Max('balanced_performance_index'),
            min_bpi=Min('balanced_performance_index')
        )
        team_avg = team_metrics.aggregate(avg=Avg('team_bpi_avg'))['avg'] or 0
        return {
            'workers': worker_count,
            'avg_bpi': worker_aggregates['avg_bpi'] or 0,
            'max_bpi': worker_aggregates['max_bpi'] or 0,
            'min_bpi': worker_aggregates['min_bpi'] or 0,
            'exceptional_workers': worker_metrics.filter(
                performance_band='exceptional'
            ).count(),
            'needs_support_workers': worker_metrics.filter(
                performance_band__in=['developing', 'needs_support']
            ).count(),
            'teams': team_metrics.count(),
            'avg_team_bpi': team_avg,
        }
    
    @classmethod
    def aggregate_worker_metrics(
        cls,
        worker: People,
        target_date: date
    ) -> WorkerDailyMetrics:
        """Class-level helper for aggregating a single worker."""
        return cls()._aggregate_worker_metrics(worker, target_date)

    def _aggregate_worker_metrics(
        self,
        worker: People,
        target_date: date,
        use_transaction: bool = True
    ) -> WorkerDailyMetrics:
        """
        Aggregate all metrics for a single worker on target date.
        
        Args:
            worker: Worker to aggregate metrics for
            target_date: Date to calculate metrics for
            use_transaction: Wrap writes in transaction.atomic when True
        
        Returns:
            Created/updated WorkerDailyMetrics record
        """
        context = transaction.atomic if use_transaction else nullcontext
        with context():
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
    
    @classmethod
    def aggregate_team_metrics(
        cls,
        site: Bt,
        target_date: date,
        shift_type: Optional[str] = None
    ) -> TeamDailyMetrics:
        """Class-level helper for aggregating team metrics."""
        return cls()._aggregate_team_metrics(site, target_date, shift_type)

    def _aggregate_team_metrics(
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
