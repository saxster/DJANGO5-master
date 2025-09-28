"""
Transaction Monitoring Dashboard Views

Provides real-time visibility into transaction health and performance.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from apps.core.services.transaction_monitoring_service import (
    TransactionMonitoringService,
    TransactionAuditService
)

logger = logging.getLogger(__name__)


class TransactionHealthDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Dashboard view for transaction health monitoring.
    """

    template_name = 'core/transaction_health_dashboard.html'

    def test_func(self):
        return self.request.user.is_staff or self.request.user.isadmin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        health_summary = TransactionMonitoringService.get_transaction_health_summary(hours=24)
        top_failing = TransactionMonitoringService.get_top_failing_operations(limit=10, hours=24)
        recent_failures = TransactionMonitoringService.get_recent_failures(limit=20)
        slow_transactions = TransactionAuditService.get_slow_transactions(threshold_ms=500, limit=10)

        context.update({
            'health_summary': health_summary,
            'top_failing_operations': top_failing,
            'recent_failures': recent_failures,
            'slow_transactions': slow_transactions,
        })

        return context


class TransactionHealthAPI(LoginRequiredMixin, View):
    """
    API endpoints for transaction health data.
    """

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')

        if action == 'health_summary':
            hours = int(request.GET.get('hours', 24))
            data = TransactionMonitoringService.get_transaction_health_summary(hours=hours)
            return JsonResponse(data)

        elif action == 'top_failing':
            limit = int(request.GET.get('limit', 10))
            hours = int(request.GET.get('hours', 24))
            data = TransactionMonitoringService.get_top_failing_operations(limit=limit, hours=hours)
            return JsonResponse({'operations': data})

        elif action == 'recent_failures':
            limit = int(request.GET.get('limit', 50))
            data = TransactionMonitoringService.get_recent_failures(limit=limit)
            return JsonResponse({'failures': data})

        elif action == 'performance_by_hour':
            from datetime import datetime
            date_str = request.GET.get('date')
            date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
            data = TransactionMonitoringService.get_transaction_performance_by_hour(date=date)
            return JsonResponse({'hourly_metrics': data})

        elif action == 'slow_transactions':
            threshold_ms = float(request.GET.get('threshold_ms', 1000))
            limit = int(request.GET.get('limit', 20))
            data = TransactionAuditService.get_slow_transactions(
                threshold_ms=threshold_ms,
                limit=limit
            )
            return JsonResponse({'slow_transactions': data})

        elif action == 'coverage_audit':
            data = TransactionAuditService.audit_transaction_coverage()
            return JsonResponse(data)

        elif action == 'perform_health_check':
            data = TransactionMonitoringService.perform_health_check()
            return JsonResponse(data)

        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)


class TransactionFailureDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    View for transaction failure details and resolution.
    """

    def test_func(self):
        return self.request.user.is_staff or self.request.user.isadmin

    def get(self, request, *args, **kwargs):
        from apps.core.models.transaction_monitoring import TransactionFailureLog

        failure_id = request.GET.get('id')

        try:
            failure = TransactionFailureLog.objects.get(id=failure_id)
            data = {
                'id': failure.id,
                'operation_name': failure.operation_name,
                'view_name': failure.view_name,
                'error_type': failure.error_type,
                'error_message': failure.error_message,
                'error_traceback': failure.error_traceback,
                'correlation_id': failure.correlation_id,
                'occurred_at': failure.occurred_at.isoformat(),
                'is_resolved': failure.is_resolved,
                'resolution_notes': failure.resolution_notes,
                'additional_context': failure.additional_context
            }
            return JsonResponse(data)
        except TransactionFailureLog.DoesNotExist:
            return JsonResponse({'error': 'Failure not found'}, status=404)

    def post(self, request, *args, **kwargs):
        from apps.core.models.transaction_monitoring import TransactionFailureLog

        failure_id = request.POST.get('id')
        action = request.POST.get('action')

        try:
            failure = TransactionFailureLog.objects.get(id=failure_id)

            if action == 'mark_resolved':
                notes = request.POST.get('notes', '')
                failure.mark_resolved(notes=notes)
                return JsonResponse({'success': True, 'message': 'Failure marked as resolved'})

            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)

        except TransactionFailureLog.DoesNotExist:
            return JsonResponse({'error': 'Failure not found'}, status=404)