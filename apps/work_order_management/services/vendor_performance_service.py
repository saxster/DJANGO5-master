"""
Vendor Performance and Sentiment Scoring Service

Combines ticket sentiment analysis with vendor performance metrics
to provide comprehensive vendor quality ratings.

Features:
- SLA compliance tracking
- Completion time vs estimate analysis
- Quality ratings aggregation
- Rework rate calculation
- Sentiment-based scoring adjustment
- Trend analysis and ranking

Integrates with:
- Ticket sentiment scores (from y_helpdesk)
- Work order completion data
- Vendor assignment history

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField

from apps.work_order_management.models import WorkOrder
from apps.y_helpdesk.models import Ticket
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger(__name__)


class VendorPerformanceService:
    """
    Service for tracking and scoring vendor performance.
    """

    SENTIMENT_WEIGHT = 0.3
    SLA_WEIGHT = 0.3
    QUALITY_WEIGHT = 0.2
    TIMELINESS_WEIGHT = 0.2

    @classmethod
    def calculate_vendor_score(
        cls,
        vendor_id: int,
        tenant_id: int,
        lookback_days: int = 90
    ) -> Optional[Dict]:
        """
        Calculate comprehensive vendor performance score.

        Args:
            vendor_id: Vendor identifier
            tenant_id: Tenant identifier
            lookback_days: Days to analyze

        Returns:
            Performance score breakdown or None
        """
        cutoff = get_current_utc() - timedelta(days=lookback_days)

        try:
            metrics = {
                'sentiment_score': cls._calculate_sentiment_score(
                    vendor_id, tenant_id, cutoff
                ),
                'sla_compliance': cls._calculate_sla_compliance(
                    vendor_id, tenant_id, cutoff
                ),
                'quality_rating': cls._calculate_quality_rating(
                    vendor_id, tenant_id, cutoff
                ),
                'timeliness_score': cls._calculate_timeliness_score(
                    vendor_id, tenant_id, cutoff
                ),
                'rework_rate': cls._calculate_rework_rate(
                    vendor_id, tenant_id, cutoff
                ),
            }

            if all(v is None for v in metrics.values()):
                logger.warning(f"No performance data for vendor {vendor_id}")
                return None

            overall_score = cls._compute_weighted_score(metrics)

            return {
                'vendor_id': vendor_id,
                'overall_score': overall_score,
                'metrics': metrics,
                'period_days': lookback_days,
                'calculated_at': get_current_utc().isoformat(),
                'grade': cls._score_to_grade(overall_score),
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating vendor score: {e}", exc_info=True)
            return None

    @classmethod
    def rank_vendors(cls, tenant_id: int, lookback_days: int = 90) -> List[Dict]:
        """
        Rank all vendors by performance score.

        Args:
            tenant_id: Tenant identifier
            lookback_days: Days to analyze

        Returns:
            Sorted list of vendor scores
        """
        try:
            vendor_ids = cls._get_active_vendors(tenant_id, lookback_days)

            scores = []
            for vendor_id in vendor_ids:
                score = cls.calculate_vendor_score(vendor_id, tenant_id, lookback_days)
                if score:
                    scores.append(score)

            scores.sort(key=lambda x: x['overall_score'], reverse=True)

            logger.info(
                f"Ranked {len(scores)} vendors for tenant {tenant_id} "
                f"over {lookback_days} days"
            )
            return scores

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error ranking vendors: {e}", exc_info=True)
            return []

    @classmethod
    def get_performance_trend(
        cls,
        vendor_id: int,
        tenant_id: int,
        months: int = 6
    ) -> List[Dict]:
        """
        Get month-over-month performance trend.

        Args:
            vendor_id: Vendor identifier
            tenant_id: Tenant identifier
            months: Number of months to analyze

        Returns:
            Monthly performance scores
        """
        trends = []
        current_date = get_current_utc()

        for i in range(months):
            month_start = current_date - timedelta(days=30 * (i + 1))
            month_end = current_date - timedelta(days=30 * i)

            score = cls._calculate_period_score(
                vendor_id, tenant_id, month_start, month_end
            )

            if score:
                trends.append({
                    'month': month_start.strftime('%Y-%m'),
                    'score': score,
                })

        return list(reversed(trends))

    @classmethod
    def _calculate_sentiment_score(
        cls,
        vendor_id: int,
        tenant_id: int,
        cutoff: datetime
    ) -> Optional[float]:
        """Calculate average sentiment score from tickets."""
        try:
            tickets = Ticket.objects.filter(
                tenant_id=tenant_id,
                assigned_vendor_id=vendor_id,
                created_at__gte=cutoff,
                sentiment_score__isnull=False
            )

            avg = tickets.aggregate(avg=Avg('sentiment_score'))
            return avg['avg']

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating sentiment score: {e}")
            return None

    @classmethod
    def _calculate_sla_compliance(
        cls,
        vendor_id: int,
        tenant_id: int,
        cutoff: datetime
    ) -> Optional[float]:
        """Calculate SLA compliance percentage."""
        try:
            tickets = Ticket.objects.filter(
                tenant_id=tenant_id,
                assigned_vendor_id=vendor_id,
                created_at__gte=cutoff,
                status='CLOSED'
            )

            total = tickets.count()
            if total == 0:
                return None

            met_sla = tickets.filter(sla_met=True).count()
            return (met_sla / total) * 100.0

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating SLA compliance: {e}")
            return None

    @classmethod
    def _calculate_quality_rating(
        cls,
        vendor_id: int,
        tenant_id: int,
        cutoff: datetime
    ) -> Optional[float]:
        """Calculate average quality rating from work orders."""
        try:
            work_orders = WorkOrder.objects.filter(
                tenant_id=tenant_id,
                vendor_id=vendor_id,
                created_at__gte=cutoff,
                quality_rating__isnull=False
            )

            avg = work_orders.aggregate(avg=Avg('quality_rating'))
            return avg['avg']

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating quality rating: {e}")
            return None

    @classmethod
    def _calculate_timeliness_score(
        cls,
        vendor_id: int,
        tenant_id: int,
        cutoff: datetime
    ) -> Optional[float]:
        """Calculate timeliness score (completion vs estimate)."""
        try:
            work_orders = WorkOrder.objects.filter(
                tenant_id=tenant_id,
                vendor_id=vendor_id,
                created_at__gte=cutoff,
                status='COMPLETED',
                estimated_hours__isnull=False,
                actual_hours__isnull=False
            )

            if not work_orders.exists():
                return None

            on_time = work_orders.filter(
                actual_hours__lte=F('estimated_hours')
            ).count()

            total = work_orders.count()
            return (on_time / total) * 100.0

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating timeliness: {e}")
            return None

    @classmethod
    def _calculate_rework_rate(
        cls,
        vendor_id: int,
        tenant_id: int,
        cutoff: datetime
    ) -> Optional[float]:
        """Calculate percentage of work requiring rework."""
        try:
            work_orders = WorkOrder.objects.filter(
                tenant_id=tenant_id,
                vendor_id=vendor_id,
                created_at__gte=cutoff
            )

            total = work_orders.count()
            if total == 0:
                return None

            rework = work_orders.filter(requires_rework=True).count()
            return (rework / total) * 100.0

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating rework rate: {e}")
            return None

    @classmethod
    def _compute_weighted_score(cls, metrics: Dict) -> float:
        """Compute weighted overall score from metrics."""
        score = 0.0
        total_weight = 0.0

        components = [
            (metrics.get('sentiment_score'), cls.SENTIMENT_WEIGHT),
            (metrics.get('sla_compliance'), cls.SLA_WEIGHT),
            (metrics.get('quality_rating'), cls.QUALITY_WEIGHT),
            (metrics.get('timeliness_score'), cls.TIMELINESS_WEIGHT),
        ]

        for value, weight in components:
            if value is not None:
                score += value * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return score / total_weight

    @classmethod
    def _score_to_grade(cls, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'

    @classmethod
    def _get_active_vendors(cls, tenant_id: int, lookback_days: int) -> List[int]:
        """Get list of vendors with activity in period."""
        cutoff = get_current_utc() - timedelta(days=lookback_days)

        try:
            vendor_ids = set()

            work_orders = WorkOrder.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff,
                vendor_id__isnull=False
            ).values_list('vendor_id', flat=True).distinct()

            vendor_ids.update(work_orders)

            return list(vendor_ids)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error fetching active vendors: {e}")
            return []

    @classmethod
    def _calculate_period_score(
        cls,
        vendor_id: int,
        tenant_id: int,
        start: datetime,
        end: datetime
    ) -> Optional[float]:
        """Calculate score for specific time period."""
        days = (end - start).days

        score_data = cls.calculate_vendor_score(vendor_id, tenant_id, days)
        return score_data['overall_score'] if score_data else None
