"""
LLM Usage Tracker Service

Tracks API calls, token usage, costs, and enforces quotas.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Cost transparency

Sprint 7-8 Phase 2: Core Services
"""

import logging
from typing import Dict, Any
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction, DatabaseError
from django.db.models import Sum
from django.utils import timezone
from apps.core.models import LLMUsageLog, LLMQuota
from apps.core_onboarding.services.llm.exceptions import QuotaExceededError

logger = logging.getLogger(__name__)


class LLMUsageTracker:
    """Service for tracking LLM usage and enforcing quotas."""

    def __init__(self, tenant_id: int, provider_name: str):
        """
        Initialize usage tracker.

        Args:
            tenant_id: Tenant identifier
            provider_name: LLM provider ('openai', 'anthropic', 'gemini')
        """
        self.tenant_id = tenant_id
        self.provider_name = provider_name

    @transaction.atomic
    def track_usage(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        latency_ms: float,
        metadata: Dict[str, Any] = None
    ) -> LLMUsageLog:
        """
        Log LLM API call and check quotas.

        Args:
            operation: Operation type
            input_tokens: Input token count
            output_tokens: Output token count
            cost_usd: Cost in USD
            latency_ms: Latency in milliseconds
            metadata: Additional context

        Returns:
            LLMUsageLog instance

        Raises:
            QuotaExceededError: If quota limits exceeded
        """
        try:
            # Create usage log
            usage_log = LLMUsageLog.objects.create(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                metadata=metadata or {}
            )

            # Check quotas after logging
            self._check_quotas()

            logger.info(
                f"LLM usage tracked: {self.provider_name}/{operation} - "
                f"{input_tokens}+{output_tokens} tokens, ${cost_usd}, {latency_ms}ms"
            )

            return usage_log

        except DatabaseError as e:
            logger.error(f"Failed to track LLM usage: {e}")
            raise

    def _check_quotas(self):
        """
        Check if tenant is within quota limits.

        Raises:
            QuotaExceededError: If quota exceeded
        """
        try:
            # Get quota for tenant+provider
            quota = LLMQuota.objects.filter(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                enabled=True
            ).first()

            if not quota:
                return  # No quota = unlimited

            # Check daily request limit
            today = timezone.now().date()
            daily_requests = LLMUsageLog.objects.filter(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                created_at__date=today
            ).count()

            if daily_requests > quota.daily_request_limit:
                raise QuotaExceededError(
                    'daily_requests',
                    daily_requests,
                    quota.daily_request_limit
                )

            # Check daily cost limit
            daily_cost = LLMUsageLog.objects.filter(
                tenant_id=self.tenant_id,
                provider=self.provider_name,
                created_at__date=today
            ).aggregate(total=Sum('cost_usd'))['total'] or Decimal('0.00')

            if daily_cost > quota.daily_cost_limit_usd:
                raise QuotaExceededError(
                    'daily_cost_usd',
                    float(daily_cost),
                    float(quota.daily_cost_limit_usd)
                )

        except QuotaExceededError:
            raise
        except DatabaseError as e:
            logger.error(f"Failed to check quotas: {e}")
            # Fail open on database errors (don't block service)

    def get_usage_stats(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get usage statistics for date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with aggregated usage stats
        """
        logs = LLMUsageLog.objects.filter(
            tenant_id=self.tenant_id,
            provider=self.provider_name,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        return {
            'total_requests': logs.count(),
            'total_cost_usd': float(logs.aggregate(total=Sum('cost_usd'))['total'] or 0),
            'total_input_tokens': logs.aggregate(total=Sum('input_tokens'))['total'] or 0,
            'total_output_tokens': logs.aggregate(total=Sum('output_tokens'))['total'] or 0,
            'avg_latency_ms': logs.aggregate(avg=Sum('latency_ms'))['avg'] or 0,
        }
