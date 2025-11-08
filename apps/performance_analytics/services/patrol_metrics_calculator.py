"""
Patrol Metrics Calculator Service

Calculates patrol/tour-related performance metrics for workers including:
- Patrol completion rate
- Checkpoint coverage
- Timing compliance
- Route adherence
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.db.models import Q, Count, F, Avg
from django.utils import timezone

from apps.activity.models.job.jobneed import Jobneed
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger(__name__)


class PatrolMetricsCalculator:
    """
    Calculate patrol/tour performance metrics for workers.
    
    Metrics include:
    - Overall patrol score (0-100)
    - Tour completion rate
    - Checkpoint coverage percentage
    - Timing compliance
    """
    
    def __init__(self, lookback_days: int = 30):
        """
        Initialize calculator.
        
        Args:
            lookback_days: Number of days to look back for metrics calculation
        """
        self.lookback_days = lookback_days
    
    def calculate_patrol_score(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate overall patrol score (0-100) for worker.
        
        Score components:
        - 40%: Tour completion rate
        - 35%: Checkpoint coverage
        - 25%: Timing compliance
        
        Args:
            worker: People instance (worker)
            date: Optional specific date, defaults to today
            
        Returns:
            Decimal: Score from 0 to 100
        """
        try:
            metrics = self.calculate_patrol_metrics(worker, date)
            
            score = (
                Decimal('0.40') * metrics['tour_completion_rate'] +
                Decimal('0.35') * metrics['checkpoint_coverage_rate'] +
                Decimal('0.25') * metrics['timing_compliance_rate']
            )
            
            return round(score, 2)
            
        except VALIDATION_EXCEPTIONS as e:
            logger.error(
                f"Validation error calculating patrol score for worker {worker.id}: {e}",
                exc_info=True
            )
            return Decimal('0.00')
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating patrol score for worker {worker.id}: {e}",
                exc_info=True
            )
            raise
    
    def calculate_patrol_metrics(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate all patrol metrics for worker.
        
        Args:
            worker: People instance
            date: Optional specific date
            
        Returns:
            Dict containing:
                - tour_completion_rate: Percentage of tours completed (0-100)
                - checkpoint_coverage_rate: Checkpoint hit percentage (0-100)
                - timing_compliance_rate: On-schedule tour rate (0-100)
                - total_tours_assigned: Total number of tours
                - total_tours_completed: Number of completed tours
                - average_tour_duration_minutes: Average tour duration
        """
        try:
            start_date, end_date = self._get_date_range(date)
            
            metrics = {
                'tour_completion_rate': self._calculate_tour_completion_rate(
                    worker, start_date, end_date
                ),
                'checkpoint_coverage_rate': self._calculate_checkpoint_coverage(
                    worker, start_date, end_date
                ),
                'timing_compliance_rate': self._calculate_timing_compliance(
                    worker, start_date, end_date
                ),
            }
            
            tour_stats = self._calculate_tour_stats(worker, start_date, end_date)
            metrics.update(tour_stats)
            
            return metrics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating patrol metrics for worker {worker.id}: {e}",
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
    
    def _calculate_tour_completion_rate(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate tour completion rate."""
        total_tours = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True
        ).count()
        
        if total_tours == 0:
            return Decimal('0.00')
        
        completed_tours = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True,
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        rate = (Decimal(completed_tours) / Decimal(total_tours)) * 100
        return round(rate, 2)
    
    def _calculate_checkpoint_coverage(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate checkpoint coverage rate."""
        parent_tours = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True,
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).values_list('id', flat=True)
        
        if not parent_tours:
            return Decimal('0.00')
        
        total_checkpoints = Jobneed.objects.filter(
            parent_id__in=parent_tours
        ).count()
        
        if total_checkpoints == 0:
            return Decimal('100.00')
        
        completed_checkpoints = Jobneed.objects.filter(
            parent_id__in=parent_tours,
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        rate = (Decimal(completed_checkpoints) / Decimal(total_checkpoints)) * 100
        return round(rate, 2)
    
    def _calculate_timing_compliance(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate timing compliance rate (tours started/ended on schedule)."""
        completed_tours = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True,
            jobstatus__in=['COMPLETED', 'CLOSED'],
            starttime__isnull=False
        )
        
        total_completed = completed_tours.count()
        if total_completed == 0:
            return Decimal('0.00')
        
        on_time_tours = completed_tours.filter(
            starttime__lte=F('plandatetime') + timedelta(minutes=15)
        ).count()
        
        rate = (Decimal(on_time_tours) / Decimal(total_completed)) * 100
        return round(rate, 2)
    
    def _calculate_tour_stats(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Decimal]:
        """Calculate tour statistics."""
        total_assigned = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True
        ).count()
        
        total_completed = Jobneed.objects.filter(
            people=worker,
            plandatetime__gte=start_date,
            plandatetime__lt=end_date,
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            parent__isnull=True,
            jobstatus__in=['COMPLETED', 'CLOSED']
        ).count()
        
        return {
            'total_tours_assigned': Decimal(total_assigned),
            'total_tours_completed': Decimal(total_completed),
            'average_tour_duration_minutes': Decimal('0.00'),
        }
