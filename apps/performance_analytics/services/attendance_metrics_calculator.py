"""
Attendance Metrics Calculator Service

Calculates attendance-related performance metrics for workers including:
- Attendance score (0-100)
- On-time arrival rate
- Check-in/check-out completion rate
- GPS compliance metrics
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.conf import settings
from django.db.models import Q, Count, Avg
from django.utils import timezone

from apps.attendance.models.people_eventlog import PeopleEventlog
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger(__name__)


class AttendanceMetricsCalculator:
    """
    Calculate attendance metrics for worker performance analytics.
    
    Metrics include:
    - Overall attendance score (0-100)
    - On-time arrival rate
    - Check-in/check-out completion rate
    - GPS compliance
    """
    
    def __init__(self, lookback_days: int = 30):
        """
        Initialize calculator.
        
        Args:
            lookback_days: Number of days to look back for metrics calculation
        """
        self.lookback_days = lookback_days
    
    def calculate_attendance_score(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate overall attendance score (0-100) for worker.
        
        Score components:
        - 40%: On-time rate
        - 30%: Check-in/out completion
        - 20%: GPS compliance
        - 10%: Consistency (no gaps)
        
        Args:
            worker: People instance (worker)
            date: Optional specific date, defaults to today
            
        Returns:
            Decimal: Score from 0 to 100
        """
        try:
            metrics = self.calculate_attendance_metrics(worker, date)
            
            score = (
                Decimal('0.40') * metrics['on_time_rate'] +
                Decimal('0.30') * metrics['completion_rate'] +
                Decimal('0.20') * metrics['gps_compliance_rate'] +
                Decimal('0.10') * metrics['consistency_score']
            )
            
            return round(score, 2)
            
        except VALIDATION_EXCEPTIONS as e:
            logger.error(
                f"Validation error calculating attendance score for worker {worker.id}: {e}",
                exc_info=True
            )
            return Decimal('0.00')
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating attendance score for worker {worker.id}: {e}",
                exc_info=True
            )
            raise
    
    def calculate_on_time_rate(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate on-time arrival rate (0-100).
        
        Args:
            worker: People instance
            date: Optional specific date
            
        Returns:
            Decimal: Percentage of on-time arrivals (0-100)
        """
        try:
            start_date, end_date = self._get_date_range(date)
            
            events = PeopleEventlog.objects.filter(
                people=worker,
                logtime__gte=start_date,
                logtime__lt=end_date,
                logtype='IN'
            )
            
            total_checkins = events.count()
            if total_checkins == 0:
                return Decimal('0.00')
            
            on_time_count = events.filter(
                Q(shift__isnull=False),
                Q(logtime__time__lte=models.F('shift__starttime'))
            ).count()
            
            rate = (Decimal(on_time_count) / Decimal(total_checkins)) * 100
            return round(rate, 2)
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating on-time rate for worker {worker.id}: {e}",
                exc_info=True
            )
            raise
    
    def calculate_attendance_metrics(
        self, 
        worker, 
        date: Optional[datetime] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate all attendance metrics for worker.
        
        Args:
            worker: People instance
            date: Optional specific date
            
        Returns:
            Dict containing:
                - on_time_rate: Percentage on-time (0-100)
                - completion_rate: Check-in/out pairs completion (0-100)
                - gps_compliance_rate: GPS verification rate (0-100)
                - consistency_score: Attendance consistency (0-100)
                - total_days_worked: Number of days with attendance
                - average_hours_per_day: Average work hours
        """
        try:
            start_date, end_date = self._get_date_range(date)
            
            metrics = {
                'on_time_rate': self._calculate_on_time_rate_internal(
                    worker, start_date, end_date
                ),
                'completion_rate': self._calculate_completion_rate(
                    worker, start_date, end_date
                ),
                'gps_compliance_rate': self._calculate_gps_compliance(
                    worker, start_date, end_date
                ),
                'consistency_score': self._calculate_consistency(
                    worker, start_date, end_date
                ),
            }
            
            work_stats = self._calculate_work_stats(worker, start_date, end_date)
            metrics.update(work_stats)
            
            return metrics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating attendance metrics for worker {worker.id}: {e}",
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
    
    def _calculate_on_time_rate_internal(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Internal method to calculate on-time rate."""
        from django.db import models
        
        events = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            logtype='IN'
        )
        
        total_checkins = events.count()
        if total_checkins == 0:
            return Decimal('0.00')
        
        on_time_count = events.filter(
            Q(shift__isnull=False),
            Q(logtime__time__lte=models.F('shift__starttime'))
        ).count()
        
        rate = (Decimal(on_time_count) / Decimal(total_checkins)) * 100
        return round(rate, 2)
    
    def _calculate_completion_rate(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate check-in/out completion rate."""
        checkins = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            logtype='IN'
        ).count()
        
        checkouts = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            logtype='OUT'
        ).count()
        
        if checkins == 0:
            return Decimal('0.00')
        
        completion = min(checkouts, checkins)
        rate = (Decimal(completion) / Decimal(checkins)) * 100
        return round(rate, 2)
    
    def _calculate_gps_compliance(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate GPS compliance rate."""
        total_events = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date
        ).count()
        
        if total_events == 0:
            return Decimal('0.00')
        
        gps_events = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            gpslocation__isnull=False
        ).count()
        
        rate = (Decimal(gps_events) / Decimal(total_events)) * 100
        return round(rate, 2)
    
    def _calculate_consistency(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Decimal:
        """Calculate attendance consistency score."""
        expected_days = (end_date - start_date).days
        
        actual_days = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            logtype='IN'
        ).dates('logtime', 'day').count()
        
        if expected_days == 0:
            return Decimal('0.00')
        
        rate = (Decimal(actual_days) / Decimal(expected_days)) * 100
        return round(min(rate, Decimal('100.00')), 2)
    
    def _calculate_work_stats(
        self, 
        worker, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Decimal]:
        """Calculate work statistics."""
        days_worked = PeopleEventlog.objects.filter(
            people=worker,
            logtime__gte=start_date,
            logtime__lt=end_date,
            logtype='IN'
        ).dates('logtime', 'day').count()
        
        return {
            'total_days_worked': Decimal(days_worked),
            'average_hours_per_day': Decimal('0.00'),
        }
