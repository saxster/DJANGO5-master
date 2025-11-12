"""
Balanced Performance Index Calculator Service

Calculates the BPI (0-100) based on weighted component scores:
- Attendance: 30%
- Tasks: 25%
- Patrols: 20%
- Work Orders: 15%
- Compliance: 10%

Compliance:
- Rule #6: Service class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import date, timedelta
from typing import Dict, Tuple, Optional
from decimal import Decimal

from django.db.models import Q, Avg
from django.utils import timezone

from apps.peoples.models import People
from apps.performance_analytics.models.worker_metrics import WorkerDailyMetrics
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class BalancedPerformanceIndexCalculator:
    """
    Calculates Balanced Performance Index (BPI) for workers.
    
    BPI is a 0-100 weighted score combining:
    - Attendance reliability
    - Task completion
    - Patrol quality
    - Work order performance
    - Compliance adherence
    """
    
    # Component weights (must sum to 1.0)
    WEIGHTS = {
        'attendance': Decimal('0.30'),
        'tasks': Decimal('0.25'),
        'patrols': Decimal('0.20'),
        'work_orders': Decimal('0.15'),
        'compliance': Decimal('0.10'),
    }
    
    def calculate_bpi(
        self,
        worker: People,
        target_date: date,
        attendance_score: Decimal,
        task_score: Decimal,
        patrol_score: Decimal,
        work_order_score: Decimal,
        compliance_score: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate BPI from component scores.
        
        Args:
            worker: Worker being measured
            target_date: Date for calculation
            attendance_score: Attendance score (0-100)
            task_score: Task performance score (0-100)
            patrol_score: Patrol quality score (0-100)
            work_order_score: Work order score (0-100)
            compliance_score: Compliance score (0-100)
            
        Returns:
            Dict with 'bpi' and component scores
            
        Raises:
            ValueError: If any score is invalid
        """
        scores = {
            'attendance': attendance_score,
            'tasks': task_score,
            'patrols': patrol_score,
            'work_orders': work_order_score,
            'compliance': compliance_score,
        }
        
        for component, score in scores.items():
            if not (0 <= score <= 100):
                raise ValueError(
                    f"Invalid {component} score: {score}. Must be 0-100."
                )
        
        bpi = sum(
            scores[component] * self.WEIGHTS[component]
            for component in scores
        )
        
        return {
            'bpi': round(bpi, 2),
            'attendance_score': attendance_score,
            'task_score': task_score,
            'patrol_score': patrol_score,
            'work_order_score': work_order_score,
            'compliance_score': compliance_score,
        }
    
    def _build_cohort_key(
        self,
        worker: People,
        target_date: date
    ) -> str:
        """
        Build cohort identifier for worker.
        
        Format: site_id|role|shift_type|tenure_band|month
        
        Args:
            worker: Worker to classify
            target_date: Date for cohort assignment
            
        Returns:
            Cohort key string
        """
        try:
            site_id = worker.peopleorganizational.site_id if hasattr(
                worker, 'peopleorganizational'
            ) else 'unknown'
            
            role = worker.peopleorganizational.role if hasattr(
                worker, 'peopleorganizational'
            ) and worker.peopleorganizational.role else 'general'
            
            shift_type = self._get_primary_shift_type(worker, target_date)
            tenure_band = self._get_tenure_band(worker, target_date)
            month = target_date.strftime('%Y-%m')
            
            return f"{site_id}|{role}|{shift_type}|{tenure_band}|{month}"
            
        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                f"Error building cohort key for worker {worker.id}: {e}",
                exc_info=True
            )
            return f"unknown|general|day|new|{target_date.strftime('%Y-%m')}"
    
    def _get_primary_shift_type(
        self,
        worker: People,
        target_date: date
    ) -> str:
        """
        Determine worker's primary shift type.
        
        Args:
            worker: Worker to analyze
            target_date: Date for shift lookup
            
        Returns:
            Shift type: 'day', 'night', 'evening', 'weekend'
        """
        try:
            recent_metrics = WorkerDailyMetrics.objects.filter(
                worker=worker,
                date__gte=target_date - timedelta(days=30),
                date__lte=target_date
            ).values('shift_type').annotate(
                count=Avg('id')
            ).order_by('-count').first()
            
            if recent_metrics and recent_metrics.get('shift_type'):
                return recent_metrics['shift_type']
            
            return 'day'
            
        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                f"Error determining shift type for worker {worker.id}: {e}",
                exc_info=True
            )
            return 'day'
    
    def _get_tenure_band(
        self,
        worker: People,
        target_date: date
    ) -> str:
        """
        Determine worker's tenure band.
        
        Args:
            worker: Worker to analyze
            target_date: Date for tenure calculation
            
        Returns:
            Tenure band: 'new' (0-3 months), 'junior' (3-12 months),
                        'intermediate' (1-3 years), 'senior' (3+ years)
        """
        if not worker.date_joined:
            return 'new'
        
        tenure_days = (target_date - worker.date_joined.date()).days
        
        if tenure_days < 90:
            return 'new'
        elif tenure_days < 365:
            return 'junior'
        elif tenure_days < 1095:
            return 'intermediate'
        else:
            return 'senior'
