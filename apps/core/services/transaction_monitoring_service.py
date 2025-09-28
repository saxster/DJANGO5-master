"""
Transaction Monitoring Service

Provides real-time transaction health monitoring and alerting.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, F, Q
from django.db import connection

logger = logging.getLogger(__name__)


class TransactionMonitoringService:
    """
    Service for monitoring transaction health and performance.
    """

    @staticmethod
    def log_transaction_failure(
        operation_name: str,
        error: Exception,
        view_name: str = None,
        request=None,
        correlation_id: str = None,
        additional_context: Dict[str, Any] = None
    ):
        """
        Log a transaction failure for monitoring.

        Args:
            operation_name: Name of the failed operation
            error: The exception that caused the failure
            view_name: Name of the view where failure occurred
            request: Django request object
            correlation_id: Request correlation ID
            additional_context: Additional context data
        """
        from apps.core.models.transaction_monitoring import TransactionFailureLog

        error_type = type(error).__name__
        error_message = str(error)

        import traceback
        error_traceback = traceback.format_exc() if hasattr(error, '__traceback__') else None

        log_data = {
            'operation_name': operation_name,
            'error_type': error_type,
            'error_message': error_message[:1000],
            'error_traceback': error_traceback[:5000] if error_traceback else None,
            'correlation_id': correlation_id,
            'additional_context': additional_context or {}
        }

        if view_name:
            log_data['view_name'] = view_name

        if request:
            log_data.update({
                'request_path': request.path[:500],
                'request_method': request.method,
                'user_id': request.user.id if request.user.is_authenticated else None
            })

        try:
            TransactionFailureLog.objects.create(**log_data)
            logger.debug(f"Logged transaction failure: {operation_name}")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to log transaction failure: {e}")

    @staticmethod
    def record_transaction_metrics(
        operation_name: str,
        duration_ms: float,
        success: bool,
        error_type: str = None
    ):
        """
        Record transaction metrics for an operation.

        Args:
            operation_name: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether transaction succeeded
            error_type: Type of error if failed
        """
        from apps.core.models.transaction_monitoring import TransactionMetrics

        now = timezone.now()
        metric_date = now.date()
        hour_of_day = now.hour

        try:
            metric, created = TransactionMetrics.objects.get_or_create(
                operation_name=operation_name,
                metric_date=metric_date,
                hour_of_day=hour_of_day,
                defaults={
                    'total_attempts': 1,
                    'successful_commits': 1 if success else 0,
                    'failed_commits': 0 if success else 1,
                    'rollbacks': 0 if success else 1,
                    'avg_duration_ms': duration_ms,
                    'max_duration_ms': duration_ms,
                    'min_duration_ms': duration_ms
                }
            )

            if not created:
                metric.total_attempts = F('total_attempts') + 1

                if success:
                    metric.successful_commits = F('successful_commits') + 1
                else:
                    metric.failed_commits = F('failed_commits') + 1
                    metric.rollbacks = F('rollbacks') + 1

                    if error_type == 'IntegrityError':
                        metric.integrity_errors = F('integrity_errors') + 1
                    elif error_type == 'ValidationError':
                        metric.validation_errors = F('validation_errors') + 1

                metric.save()

                metric.refresh_from_db()

                current_avg = metric.avg_duration_ms or 0
                new_avg = (current_avg * (metric.total_attempts - 1) + duration_ms) / metric.total_attempts
                metric.avg_duration_ms = new_avg

                if duration_ms > (metric.max_duration_ms or 0):
                    metric.max_duration_ms = duration_ms

                if duration_ms < (metric.min_duration_ms or float('inf')):
                    metric.min_duration_ms = duration_ms

                metric.save(update_fields=['avg_duration_ms', 'max_duration_ms', 'min_duration_ms'])

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to record transaction metrics: {e}")

    @staticmethod
    def get_transaction_health_summary(hours: int = 24) -> Dict[str, Any]:
        """
        Get transaction health summary for the last N hours.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with health metrics
        """
        from apps.core.models.transaction_monitoring import TransactionFailureLog, TransactionMetrics

        cutoff_time = timezone.now() - timedelta(hours=hours)

        failures = TransactionFailureLog.objects.filter(
            occurred_at__gte=cutoff_time
        ).values('error_type').annotate(count=Count('id'))

        metrics = TransactionMetrics.objects.filter(
            last_updated__gte=cutoff_time
        ).aggregate(
            total_attempts=Count('id'),
            avg_success_rate=Avg(
                F('successful_commits') * 100.0 / F('total_attempts')
            ),
            total_failures=Count('id', filter=Q(failed_commits__gt=0))
        )

        failure_by_type = {f['error_type']: f['count'] for f in failures}

        total_failures = sum(failure_by_type.values())
        total_attempts = metrics['total_attempts'] or 1

        failure_rate = (total_failures / total_attempts) * 100 if total_attempts > 0 else 0

        health_status = 'healthy'
        if failure_rate > 5.0:
            health_status = 'critical'
        elif failure_rate > 1.0:
            health_status = 'degraded'

        return {
            'health_status': health_status,
            'failure_rate': round(failure_rate, 2),
            'success_rate': round(100 - failure_rate, 2),
            'total_failures': total_failures,
            'total_attempts': total_attempts,
            'failure_by_type': failure_by_type,
            'avg_success_rate': round(metrics['avg_success_rate'] or 0, 2),
            'period_hours': hours
        }

    @staticmethod
    def get_top_failing_operations(limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get operations with highest failure rates.

        Args:
            limit: Maximum number of operations to return
            hours: Hours to analyze

        Returns:
            List of operations with failure statistics
        """
        from apps.core.models.transaction_monitoring import TransactionFailureLog

        cutoff_time = timezone.now() - timedelta(hours=hours)

        failures = TransactionFailureLog.objects.filter(
            occurred_at__gte=cutoff_time
        ).values('operation_name', 'view_name').annotate(
            failure_count=Count('id'),
            unresolved_count=Count('id', filter=Q(is_resolved=False))
        ).order_by('-failure_count')[:limit]

        return list(failures)

    @staticmethod
    def get_recent_failures(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get most recent transaction failures.

        Args:
            limit: Maximum number of failures to return

        Returns:
            List of recent failures with details
        """
        from apps.core.models.transaction_monitoring import TransactionFailureLog

        failures = TransactionFailureLog.objects.filter(
            is_resolved=False
        ).values(
            'id', 'operation_name', 'view_name', 'error_type',
            'error_message', 'occurred_at', 'correlation_id', 'user_id'
        ).order_by('-occurred_at')[:limit]

        return list(failures)

    @staticmethod
    def get_transaction_performance_by_hour(date=None) -> List[Dict[str, Any]]:
        """
        Get transaction performance metrics by hour for a specific date.

        Args:
            date: Date to analyze (defaults to today)

        Returns:
            List of hourly metrics
        """
        from apps.core.models.transaction_monitoring import TransactionMetrics

        if date is None:
            date = timezone.now().date()

        hourly_metrics = TransactionMetrics.objects.filter(
            metric_date=date
        ).values('hour_of_day').annotate(
            total=Count('id'),
            avg_duration=Avg('avg_duration_ms'),
            total_attempts=Count('total_attempts'),
            total_failures=Count('failed_commits')
        ).order_by('hour_of_day')

        return list(hourly_metrics)

    @staticmethod
    def perform_health_check() -> Dict[str, Any]:
        """
        Perform comprehensive transaction health check.

        Returns:
            Health check results
        """
        from apps.core.models.transaction_monitoring import TransactionHealthCheck

        summary = TransactionMonitoringService.get_transaction_health_summary(hours=1)

        health_check = TransactionHealthCheck.objects.create(
            total_transactions_last_hour=summary['total_attempts'],
            failed_transactions_last_hour=summary['total_failures'],
            health_status=summary['health_status']
        )

        if summary['health_status'] == 'critical':
            health_check.alerts_triggered.append({
                'type': 'high_failure_rate',
                'message': f"Failure rate at {summary['failure_rate']}%",
                'timestamp': timezone.now().isoformat()
            })

        if summary['failure_rate'] > 0:
            top_failing = TransactionMonitoringService.get_top_failing_operations(limit=5, hours=1)
            if top_failing:
                health_check.recommendations.append({
                    'type': 'investigate_failures',
                    'operations': [op['operation_name'] for op in top_failing[:3]],
                    'message': 'Investigate top failing operations'
                })

        health_check.save()

        return {
            'health_check_id': health_check.id,
            'status': health_check.health_status,
            'summary': summary,
            'alerts': health_check.alerts_triggered,
            'recommendations': health_check.recommendations
        }


class TransactionAuditService:
    """
    Service for auditing transaction patterns and compliance.
    """

    @staticmethod
    def audit_transaction_coverage() -> Dict[str, Any]:
        """
        Audit which operations use transaction.atomic.

        Returns:
            Audit results with coverage statistics
        """
        import os
        import re
        from pathlib import Path

        base_path = Path(__file__).resolve().parent.parent.parent

        results = {
            'total_handle_valid_form_methods': 0,
            'with_transaction': 0,
            'without_transaction': [],
            'coverage_percentage': 0.0
        }

        view_files = []
        for app_dir in (base_path / 'apps').iterdir():
            if app_dir.is_dir():
                views_dir = app_dir / 'views'
                if views_dir.exists():
                    view_files.extend(views_dir.glob('*.py'))

                views_file = app_dir / 'views.py'
                if views_file.exists():
                    view_files.append(views_file)

        handle_valid_form_pattern = re.compile(r'def handle_valid_form\(')
        transaction_atomic_pattern = re.compile(r'with transaction\.atomic|@transaction\.atomic')

        for view_file in view_files:
            try:
                content = view_file.read_text()
                methods = list(handle_valid_form_pattern.finditer(content))

                for method_match in methods:
                    results['total_handle_valid_form_methods'] += 1

                    method_start = method_match.start()
                    next_method = handle_valid_form_pattern.search(content, method_match.end())
                    method_end = next_method.start() if next_method else len(content)

                    method_content = content[method_start:method_end]

                    if transaction_atomic_pattern.search(method_content):
                        results['with_transaction'] += 1
                    else:
                        file_path = str(view_file.relative_to(base_path))
                        line_num = content[:method_start].count('\n') + 1
                        results['without_transaction'].append({
                            'file': file_path,
                            'line': line_num
                        })

            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                logger.warning(f"Error auditing {view_file}: {e}")

        if results['total_handle_valid_form_methods'] > 0:
            results['coverage_percentage'] = (
                results['with_transaction'] / results['total_handle_valid_form_methods']
            ) * 100

        return results

    @staticmethod
    def get_slow_transactions(threshold_ms: float = 1000, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get transactions exceeding performance threshold.

        Args:
            threshold_ms: Threshold in milliseconds
            limit: Maximum results to return

        Returns:
            List of slow transactions
        """
        from apps.core.models.transaction_monitoring import TransactionMetrics

        slow_transactions = TransactionMetrics.objects.filter(
            avg_duration_ms__gte=threshold_ms
        ).values(
            'operation_name', 'avg_duration_ms', 'max_duration_ms',
            'total_attempts', 'metric_date'
        ).order_by('-avg_duration_ms')[:limit]

        return list(slow_transactions)