"""
LLM Monitoring Dashboard Views

Real-time LLM usage metrics, cost trends, and circuit breaker status.

Following CLAUDE.md:
- Rule #7: <150 lines
- Permission-based access
- JSON API endpoints

Sprint 7-8 Phase 5: Monitoring Dashboard
"""

import logging
from datetime import datetime, timedelta
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from apps.core.models import LLMUsageLog, LLMQuota
from apps.core_onboarding.services.llm.circuit_breaker import CircuitBreaker
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class LLMMonitoringDashboard(PermissionRequiredMixin, TemplateView):
    """LLM usage monitoring dashboard."""

    template_name = 'core/monitoring/llm_dashboard.html'
    permission_required = 'core.view_monitoring'

    def get_context_data(self, **kwargs):
        """Add LLM metrics to context."""
        context = super().get_context_data(**kwargs)

        context['providers'] = ['openai', 'anthropic']
        context['time_ranges'] = ['24h', '7d', '30d']

        return context


class LLMUsageAPIView(PermissionRequiredMixin, View):
    """JSON API for LLM usage data."""

    permission_required = 'core.view_monitoring'

    def get(self, request):
        """Get LLM usage statistics."""
        try:
            # Parse parameters
            time_range = request.GET.get('range', '24h')
            provider = request.GET.get('provider', 'all')

            # Calculate date range
            now = timezone.now()
            range_map = {
                '24h': now - timedelta(hours=24),
                '7d': now - timedelta(days=7),
                '30d': now - timedelta(days=30),
            }
            start_date = range_map.get(time_range, now - timedelta(hours=24))

            # Query logs
            logs = LLMUsageLog.objects.filter(created_at__gte=start_date)

            if provider != 'all':
                logs = logs.filter(provider=provider)

            # Aggregate stats
            stats = logs.aggregate(
                total_requests=Count('id'),
                total_cost=Sum('cost_usd'),
                total_input_tokens=Sum('input_tokens'),
                total_output_tokens=Sum('output_tokens'),
                avg_latency=Avg('latency_ms')
            )

            # Provider breakdown
            by_provider = logs.values('provider').annotate(
                requests=Count('id'),
                cost=Sum('cost_usd'),
                avg_latency=Avg('latency_ms')
            )

            # Top operations
            top_operations = logs.values('operation').annotate(
                count=Count('id'),
                cost=Sum('cost_usd')
            ).order_by('-cost')[:5]

            return JsonResponse({
                'stats': stats,
                'by_provider': list(by_provider),
                'top_operations': list(top_operations),
                'time_range': time_range,
                'generated_at': datetime.now().isoformat()
            })

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error getting LLM usage stats: {e}")
            return JsonResponse({'error': 'Failed to get statistics'}, status=500)


class CircuitBreakerStatusView(PermissionRequiredMixin, View):
    """JSON API for circuit breaker states."""

    permission_required = 'core.view_monitoring'

    def get(self, request):
        """Get circuit breaker status for all providers."""
        try:
            tenant_id = int(request.GET.get('tenant_id', 1))
            providers = request.GET.get('providers', 'openai,anthropic').split(',')

            statuses = []
            for provider in providers:
                circuit = CircuitBreaker(provider.strip(), tenant_id)
                state = circuit.get_state()
                statuses.append(state)

            return JsonResponse({
                'circuit_breakers': statuses,
                'tenant_id': tenant_id,
                'checked_at': datetime.now().isoformat()
            })

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error getting circuit breaker status: {e}")
            return JsonResponse({'error': 'Failed to get status'}, status=500)
