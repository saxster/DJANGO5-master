"""
Work Order Metrics Calculator Service

Calculates work order performance scores based on:
- Completion rate
- SLA compliance
- Quality ratings
- Efficiency

Compliance:
- Rule #6: Service class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import date, timedelta
from typing import Dict
from decimal import Decimal

from django.db.models import Q, Count, Avg
from django.utils import timezone

from apps.peoples.models import People
from apps.work_order_management.models.work_order import Wom
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class WorkOrderMetricsCalculator:
    """
    Calculates work order performance score (0-100).
    
    Components:
    - Completion rate: 40%
    - SLA compliance: 30%
    - Quality ratings: 20%
    - Efficiency: 10%
    """
    
    WEIGHTS = {
        'completion': Decimal('0.40'),
        'sla': Decimal('0.30'),
        'quality': Decimal('0.20'),
        'efficiency': Decimal('0.10'),
    }
    
    def calculate_wo_score(
        self,
        worker: People,
        target_date: date,
        work_orders_assigned: int = 0,
        work_orders_completed: int = 0,
        work_orders_within_sla: int = 0,
        work_order_quality_avg: Decimal = Decimal('0')
    ) -> Dict[str, Decimal]:
        """
        Calculate work order performance score.
        
        Args:
            worker: Worker being evaluated
            target_date: Date for calculation
            work_orders_assigned: Total work orders assigned
            work_orders_completed: Work orders completed
            work_orders_within_sla: Work orders completed within SLA
            work_order_quality_avg: Average quality rating (0-5)
            
        Returns:
            Dict with 'work_order_score' and component scores
        """
        try:
            completion_score = self._calculate_completion_score(
                work_orders_assigned,
                work_orders_completed
            )
            
            sla_score = self._calculate_sla_score(
                work_orders_completed,
                work_orders_within_sla
            )
            
            quality_score = self._calculate_quality_score(
                work_order_quality_avg
            )
            
            efficiency_score = self._calculate_efficiency_score(
                worker,
                target_date
            )
            
            wo_score = (
                completion_score * self.WEIGHTS['completion'] +
                sla_score * self.WEIGHTS['sla'] +
                quality_score * self.WEIGHTS['quality'] +
                efficiency_score * self.WEIGHTS['efficiency']
            )
            
            return {
                'work_order_score': round(wo_score, 2),
                'completion_score': completion_score,
                'sla_score': sla_score,
                'quality_score': quality_score,
                'efficiency_score': efficiency_score,
            }
            
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(
                f"Error calculating work order score for worker {worker.id}: {e}",
                exc_info=True
            )
            return {
                'work_order_score': Decimal('0'),
                'completion_score': Decimal('0'),
                'sla_score': Decimal('0'),
                'quality_score': Decimal('0'),
                'efficiency_score': Decimal('0'),
            }
    
    def _calculate_completion_score(
        self,
        assigned: int,
        completed: int
    ) -> Decimal:
        """Calculate work order completion score."""
        if assigned == 0:
            return Decimal('100')
        
        rate = (completed / assigned) * 100
        return Decimal(str(min(rate, 100)))
    
    def _calculate_sla_score(
        self,
        completed: int,
        within_sla: int
    ) -> Decimal:
        """Calculate SLA compliance score."""
        if completed == 0:
            return Decimal('100')
        
        rate = (within_sla / completed) * 100
        return Decimal(str(min(rate, 100)))
    
    def _calculate_quality_score(
        self,
        quality_avg: Decimal
    ) -> Decimal:
        """
        Calculate quality score from average rating.
        
        Converts 0-5 scale to 0-100 scale.
        """
        if quality_avg == 0:
            return Decimal('0')
        
        score = (quality_avg / 5) * 100
        return Decimal(str(min(score, 100)))
    
    def _calculate_efficiency_score(
        self,
        worker: People,
        target_date: date
    ) -> Decimal:
        """
        Calculate efficiency score based on work order completion patterns.
        
        Looks at recent work order completion velocity.
        """
        try:
            period_start = target_date - timedelta(days=7)
            
            recent_wos = Wom.objects.filter(
                assigned_to=worker,
                created_at__date__gte=period_start,
                created_at__date__lte=target_date,
                tenant=worker.tenant
            )
            
            total_count = recent_wos.count()
            
            if total_count == 0:
                return Decimal('80')
            
            completed_count = recent_wos.filter(
                status__in=['completed', 'closed']
            ).count()
            
            if completed_count >= total_count:
                return Decimal('100')
            elif completed_count >= total_count * 0.8:
                return Decimal('90')
            elif completed_count >= total_count * 0.6:
                return Decimal('75')
            elif completed_count >= total_count * 0.4:
                return Decimal('60')
            else:
                return Decimal('40')
                
        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                f"Error calculating efficiency for worker {worker.id}: {e}",
                exc_info=True
            )
            return Decimal('80')
