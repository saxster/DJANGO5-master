"""
Cohort Analyzer Service

Calculates worker percentiles within cohorts and maintains benchmark statistics.
Enables fair peer-to-peer comparisons.

Compliance:
- Rule #6: Service class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import date, timedelta
from typing import Dict, Optional
from decimal import Decimal

from django.db.models import Count, Avg, StdDev, Min, Max
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.peoples.models import People
from apps.performance_analytics.models.benchmarks import CohortBenchmark
from apps.performance_analytics.models.worker_metrics import WorkerDailyMetrics
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class CohortAnalyzer:
    """
    Analyzes worker performance relative to cohort peers.
    
    Cohort = workers with same:
    - Site
    - Role
    - Shift type
    - Tenure band
    - Month
    """
    
    MIN_COHORT_SIZE = 5
    
    def calculate_percentile(
        self,
        worker: People,
        bpi: Decimal,
        cohort_key: str,
        target_date: date
    ) -> int:
        """
        Calculate worker's percentile within cohort.
        
        Args:
            worker: Worker being evaluated
            bpi: Worker's BPI score
            cohort_key: Cohort identifier
            target_date: Date for calculation
            
        Returns:
            Percentile (0-100)
        """
        try:
            period_start = target_date - timedelta(days=30)
            
            cohort_scores = WorkerDailyMetrics.objects.filter(
                cohort_key=cohort_key,
                date__gte=period_start,
                date__lte=target_date,
                tenant=worker.tenant
            ).values_list('balanced_performance_index', flat=True)
            
            if not cohort_scores:
                logger.info(
                    f"No cohort data for {cohort_key}, defaulting to 50th percentile"
                )
                return 50
            
            scores_list = sorted(cohort_scores)
            count = len(scores_list)
            
            below_count = sum(1 for s in scores_list if s < bpi)
            percentile = int((below_count / count) * 100)
            
            return min(max(percentile, 0), 100)
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error calculating percentile for worker {worker.id}: {e}",
                exc_info=True
            )
            return 50
    
    def update_cohort_benchmarks(
        self,
        target_date: date,
        period_days: int = 30
    ) -> int:
        """
        Recalculate benchmark statistics for all cohorts.
        
        Args:
            target_date: End date for benchmark period
            period_days: Number of days to include in benchmark
            
        Returns:
            Number of cohort benchmarks updated
        """
        period_start = target_date - timedelta(days=period_days)
        updated_count = 0
        
        try:
            cohort_keys = WorkerDailyMetrics.objects.filter(
                date__gte=period_start,
                date__lte=target_date
            ).values_list('cohort_key', flat=True).distinct()
            
            for cohort_key in cohort_keys:
                self._update_single_cohort(
                    cohort_key=cohort_key,
                    metric_name='bpi',
                    period_start=period_start,
                    period_end=target_date
                )
                updated_count += 1
                
            logger.info(
                f"Updated {updated_count} cohort benchmarks for {target_date}"
            )
            return updated_count
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error updating cohort benchmarks: {e}",
                exc_info=True
            )
            raise
    
    def _update_single_cohort(
        self,
        cohort_key: str,
        metric_name: str,
        period_start: date,
        period_end: date
    ) -> None:
        """Update benchmark statistics for a single cohort."""
        try:
            metrics = WorkerDailyMetrics.objects.filter(
                cohort_key=cohort_key,
                date__gte=period_start,
                date__lte=period_end
            )
            
            stats = metrics.aggregate(
                sample_size=Count('id'),
                worker_count=Count('worker', distinct=True),
                mean=Avg('balanced_performance_index'),
                std_dev=Coalesce(StdDev('balanced_performance_index'), 0),
                min_value=Min('balanced_performance_index'),
                max_value=Max('balanced_performance_index')
            )
            
            if stats['worker_count'] < self.MIN_COHORT_SIZE:
                logger.info(
                    f"Skipping cohort {cohort_key}: insufficient sample size"
                )
                return
            
            scores = sorted(
                metrics.values_list('balanced_performance_index', flat=True)
            )
            percentiles = self._calculate_percentiles(scores)
            
            tenant = metrics.first().tenant if metrics.exists() else None
            
            CohortBenchmark.objects.update_or_create(
                cohort_key=cohort_key,
                metric_name=metric_name,
                period_start=period_start,
                tenant=tenant,
                defaults={
                    'period_end': period_end,
                    'sample_size': stats['sample_size'],
                    'worker_count': stats['worker_count'],
                    'mean': stats['mean'] or 0,
                    'std_dev': stats['std_dev'] or 0,
                    'min_value': stats['min_value'] or 0,
                    'max_value': stats['max_value'] or 0,
                    'median': percentiles['p50'],
                    'p10': percentiles['p10'],
                    'p25': percentiles['p25'],
                    'p50': percentiles['p50'],
                    'p75': percentiles['p75'],
                    'p90': percentiles['p90'],
                    'lower_control_limit': max(
                        0,
                        (stats['mean'] or 0) - 2 * (stats['std_dev'] or 0)
                    ),
                    'upper_control_limit': min(
                        100,
                        (stats['mean'] or 0) + 2 * (stats['std_dev'] or 0)
                    ),
                }
            )
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error updating cohort {cohort_key}: {e}",
                exc_info=True
            )
            raise
    
    def _calculate_percentiles(self, scores: list) -> Dict[str, Decimal]:
        """Calculate percentile values from sorted scores."""
        if not scores:
            return {
                'p10': Decimal('0'),
                'p25': Decimal('0'),
                'p50': Decimal('0'),
                'p75': Decimal('0'),
                'p90': Decimal('0'),
            }
        
        def percentile(data, p):
            n = len(data)
            index = (p / 100) * (n - 1)
            lower = int(index)
            upper = min(lower + 1, n - 1)
            weight = index - lower
            return Decimal(str(
                data[lower] * (1 - weight) + data[upper] * weight
            ))
        
        return {
            'p10': percentile(scores, 10),
            'p25': percentile(scores, 25),
            'p50': percentile(scores, 50),
            'p75': percentile(scores, 75),
            'p90': percentile(scores, 90),
        }
    
    def get_cohort_stats(
        self,
        cohort_key: str,
        metric_name: str,
        period_days: int = 30
    ) -> Optional[CohortBenchmark]:
        """
        Get latest benchmark statistics for a cohort.
        
        Args:
            cohort_key: Cohort identifier
            metric_name: Metric to retrieve (e.g., 'bpi')
            period_days: Number of days to look back
            
        Returns:
            CohortBenchmark instance or None if not found
        """
        try:
            return CohortBenchmark.objects.filter(
                cohort_key=cohort_key,
                metric_name=metric_name
            ).order_by('-period_end').first()
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Error retrieving cohort stats for {cohort_key}: {e}",
                exc_info=True
            )
            return None
