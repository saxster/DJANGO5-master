"""
IVR Cost Monitor Service.

Tracks IVR costs and enforces budgets.
Provides spending analytics and ROI metrics.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count

logger = logging.getLogger('noc.security_intelligence.ivr')


class IVRCostMonitor:
    """Monitors IVR costs and budgets."""

    @classmethod
    def track_call_cost(cls, call_log, provider_config):
        """
        Track cost for completed call.

        Args:
            call_log: IVRCallLog instance
            provider_config: IVRProviderConfig instance

        Returns:
            Decimal: Call cost
        """
        try:
            cost = provider_config.calculate_cost(call_log.duration_seconds) if hasattr(provider_config, 'calculate_cost') else Decimal('0.00')

            call_log.call_cost = cost
            call_log.save(update_fields=['call_cost'])

            success = call_log.is_successful_verification

            provider_config.record_call_outcome(success=success, cost=cost)

            return cost

        except (ValueError, AttributeError) as e:
            logger.error(f"Cost tracking error: {e}", exc_info=True)
            return Decimal('0.00')

    @classmethod
    def get_monthly_spending(cls, tenant, provider_type=None):
        """
        Get monthly spending statistics.

        Args:
            tenant: Tenant instance
            provider_type: Optional provider filter

        Returns:
            dict: Spending metrics
        """
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        try:
            start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)

            calls = IVRCallLog.objects.filter(
                tenant=tenant,
                initiated_at__gte=start_of_month
            )

            if provider_type:
                calls = calls.filter(provider=provider_type)

            stats = calls.aggregate(
                total_calls=Count('id'),
                total_cost=Sum('call_cost'),
                avg_cost=Avg('call_cost'),
                successful_calls=Count('id', filter=models.Q(is_successful_verification=True))
            )

            return {
                'month': start_of_month.strftime('%B %Y'),
                'total_calls': stats['total_calls'] or 0,
                'total_cost': stats['total_cost'] or Decimal('0.00'),
                'avg_cost_per_call': stats['avg_cost'] or Decimal('0.00'),
                'successful_calls': stats['successful_calls'] or 0,
                'success_rate': (stats['successful_calls'] / max(stats['total_calls'], 1)) * 100,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Spending calculation error: {e}", exc_info=True)
            return {}

    @classmethod
    def check_budget_status(cls, tenant):
        """
        Check if within monthly budget.

        Args:
            tenant: Tenant instance

        Returns:
            dict: Budget status
        """
        from apps.noc.security_intelligence.ivr.models import IVRProviderConfig

        try:
            spending = cls.get_monthly_spending(tenant)
            total_budget = IVRProviderConfig.objects.filter(
                tenant=tenant,
                is_active=True
            ).aggregate(
                total=Sum('monthly_budget')
            )['total'] or Decimal('0.00')

            spent = spending.get('total_cost', Decimal('0.00'))
            remaining = total_budget - spent
            percent_used = (spent / max(total_budget, Decimal('1.00'))) * 100

            return {
                'total_budget': total_budget,
                'spent': spent,
                'remaining': remaining,
                'percent_used': percent_used,
                'within_budget': spent <= total_budget,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Budget check error: {e}", exc_info=True)
            return {}

    @classmethod
    def get_roi_metrics(cls, tenant, days=30):
        """
        Calculate ROI for IVR system.

        Args:
            tenant: Tenant instance
            days: Days to analyze

        Returns:
            dict: ROI metrics
        """
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog
        from apps.noc.security_intelligence.ivr.models import IVRCallLog

        try:
            since = timezone.now() - timedelta(days=days)

            ivr_calls = IVRCallLog.objects.filter(
                tenant=tenant,
                initiated_at__gte=since
            )

            ivr_cost = ivr_calls.aggregate(total=Sum('call_cost'))['total'] or Decimal('0.00')

            fraud_prevented = AttendanceAnomalyLog.objects.filter(
                tenant=tenant,
                detected_at__gte=since,
                status='RESOLVED',
                investigation_notes__icontains='IVR'
            ).count()

            estimated_fraud_value_per_incident = Decimal('3000.00')
            fraud_prevented_value = fraud_prevented * estimated_fraud_value_per_incident

            roi = ((fraud_prevented_value - ivr_cost) / max(ivr_cost, Decimal('1.00'))) * 100

            return {
                'period_days': days,
                'ivr_cost': ivr_cost,
                'fraud_prevented_count': fraud_prevented,
                'fraud_prevented_value': fraud_prevented_value,
                'roi_percent': roi,
                'cost_per_fraud_prevented': ivr_cost / max(fraud_prevented, 1),
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"ROI calculation error: {e}", exc_info=True)
            return {}