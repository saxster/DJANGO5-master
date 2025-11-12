"""
Task Metrics Calculator Service

Calculates task-related performance metrics for workers including:
- Task completion rate
- SLA hit rate
- Quality score
- First-time-pass rate
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone

from apps.activity.models.job.jobneed import Jobneed
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger(__name__)


class TaskMetricsCalculator:
    """
    Calculate task performance metrics for workers.
    
    Metrics include:
    - Overall task score (0-100)
    - Task completion rate
    - SLA hit rate
    - Quality score
    - First-time-pass rate
    """
    
    def __init__(self, lookback_days: int = 30):
        """
        Initialize calculator.
        
        Args:
            lookback_days: Number of days to look back for metrics calculation
        """
        self.lookback_days = lookback_days
    
    def calculate_task_score(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate overall task score (0-100) for worker.
        
        Score components:
        - 35%: Completion rate
        - 30%: SLA hit rate
        - 25%: Quality score
        - 10%: First-time-pass rate
        
        Args:
            worker: People instance (worker)
            date: Optional specific date, defaults to today
            
        Returns:
            Decimal: Score from 0 to 100
        """
        try:
            metrics = self.calculate_task_metrics(worker, date)
            
            score = (
                Decimal('0.35') * metrics['completion_rate'] +
                Decimal('0.30') * metrics['sla_hit_rate'] +
                Decimal('0.25') * metrics['quality_score'] +
                Decimal('0.10') * metrics['first_time_pass_rate']
            )
            
            return round(score, 2)
            
        except VALIDATION_EXCEPTIONS as e:
            logger.error(
                f"Validation error calculating task score for worker {worker.id}: {e}",
                exc_info=True
            )
            return Decimal('0.00')
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating task score for worker {worker.id}: {e}",
                exc_info=True
            )
            raise
    
    def calculate_task_metrics(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate all task metrics for worker.
        
        Args:
            worker: People instance
            date: Optional specific date
            
        Returns:
            Dict containing:
                - completion_rate: Task completion percentage (0-100)
                - sla_hit_rate: SLA compliance percentage (0-100)
                - quality_score: Average quality rating (0-100)
                - first_time_pass_rate: First-time completion percentage (0-100)
                - total_tasks_assigned: Total number of tasks
                - total_tasks_completed: Number of completed tasks
                - average_completion_time_minutes: Average time to complete
        """
        try:
            start_date, end_date = self._get_date_range(date)
            
            metrics = {
                'completion_rate': self._calculate_completion_rate(
                    worker, start_date, end_date
                ),
                'sla_hit_rate': self._calculate_sla_hit_rate(
                    worker, start_date, end_date
                ),
                'quality_score': self._calculate_quality_score(
                    worker, start_date, end_date
                ),
                'first_time_pass_rate': self._calculate_first_time_pass_rate(
                    worker, start_date, end_date
                ),
            }
            
            task_stats = self._calculate_task_stats(worker, start_date, end_date)
            metrics.update(task_stats)
            
            return metrics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating task metrics for worker {worker.id}: {e}",
                exc_info=True
            )
            raise
    
    def _get_date_range(self, date: Optional[datetime]) -> Tuple[datetime, datetime]:
        """Get start and end dates for metrics calculation."""
        if date:
            end_date = timezone.make_aware(
                datetime.combine(date.date(), datetime.max.time())
            )
        else:
            end_date = timezone.now()
        
        start_date = end_date - timedelta(days=self.lookback_days)
        return start_date, end_date
    
    def _calculate_completion_rate(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate task completion rate."""
        total_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK']
        ).count()
        
        if total_tasks == 0:
            return Decimal('0.00')
        
        completed_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        rate = (Decimal(completed_tasks) / Decimal(total_tasks)) * 100
        return round(rate, 2)
    
    def _calculate_sla_hit_rate(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate SLA compliance rate."""
        completed_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['COMPLETED', 'CLOSED'],
            endtime__isnull=False,
            expirydatetime__isnull=False
        )
        
        total_completed = completed_tasks.count()
        if total_completed == 0:
            return Decimal('0.00')
        
        sla_met = completed_tasks.filter(
            endtime__lte=F('expirydatetime')
        ).count()
        
        rate = (Decimal(sla_met) / Decimal(total_completed)) * 100
        return round(rate, 2)
    
    def _calculate_quality_score(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """
        Calculate quality score based on task completion quality.
        
        Uses rework rate as proxy (tasks reopened or failed).
        """
        completed_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        if completed_tasks == 0:
            return Decimal('0.00')
        
        rework_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['REWORK', 'REOPENED', 'FAILED']
        ).count()
        
        quality_tasks = completed_tasks - rework_tasks
        quality_rate = (Decimal(max(quality_tasks, 0)) / Decimal(completed_tasks)) * 100
        return round(quality_rate, 2)
    
    def _calculate_first_time_pass_rate(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate first-time-pass rate (no rework needed)."""
        total_tasks = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        if total_tasks == 0:
            return Decimal('0.00')
        
        first_time_pass = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus='COMPLETED',
            raisedtktflag=False
        ).count()
        
        rate = (Decimal(first_time_pass) / Decimal(total_tasks)) * 100
        return round(rate, 2)
    
    def _calculate_task_stats(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Decimal]:
        """Calculate task statistics."""
        total_assigned = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK']
        ).count()
        
        total_completed = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTASK', 'EXTERNALTASK', 'ADHOCTASK'],
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        return {
            'total_tasks_assigned': Decimal(total_assigned),
            'total_tasks_completed': Decimal(total_completed),
            'average_completion_time_minutes': Decimal('0.00'),
        }
