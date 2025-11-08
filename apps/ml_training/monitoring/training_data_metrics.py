"""
ML Training Data Capture Metrics - Production Monitoring.

Provides real-time metrics for training data ingestion health,
active learning effectiveness, and labeling task management.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from django.core.cache import cache

from apps.ml_training.models import TrainingExample, TrainingDataset, LabelingTask
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class TrainingDataMetrics:
    """
    Monitor training data capture and quality metrics.

    Provides dashboards and alerts for ML training pipeline health.
    """

    # Cache duration for expensive metrics (5 minutes)
    CACHE_DURATION = 300

    @classmethod
    def get_capture_rate_metrics(cls, days_back: int = 7) -> Dict[str, Any]:
        """
        Get training data capture rate metrics.

        Args:
            days_back: Number of days to analyze

        Returns:
            {
                'total_examples': int,
                'examples_per_day': float,
                'by_source_system': [{system: str, count: int}],
                'low_confidence_rate': float,
                'user_corrections': int,
                'alert_status': 'ok' | 'warning' | 'critical'
            }
        """
        cache_key = f'ml_training_capture_rate_{days_back}d'
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            # Total examples captured
            examples = TrainingExample.objects.filter(
                created_at__gte=cutoff_date
            )

            total_examples = examples.count()
            examples_per_day = total_examples / days_back if days_back > 0 else 0

            # Breakdown by source system
            by_source = list(examples.values('source_system').annotate(
                count=Count('id')
            ).order_by('-count'))

            # Low confidence rate (uncertainty > 0.7)
            low_confidence_count = examples.filter(
                uncertainty_score__gte=0.7
            ).count()
            low_confidence_rate = (
                low_confidence_count / total_examples
                if total_examples > 0 else 0.0
            )

            # User corrections (uncertainty_score = 1.0)
            user_corrections = examples.filter(
                uncertainty_score=1.0
            ).count()

            # Check last 24h capture
            last_24h = timezone.now() - timedelta(hours=24)
            recent_count = TrainingExample.objects.filter(
                created_at__gte=last_24h
            ).count()

            # Determine alert status
            if recent_count == 0:
                alert_status = 'critical'  # No data in 24h
                alert_message = 'CRITICAL: Zero training examples captured in past 24 hours'
            elif examples_per_day < 5:
                alert_status = 'warning'  # Low capture rate
                alert_message = f'WARNING: Low capture rate ({examples_per_day:.1f}/day, target: 10-20/day)'
            else:
                alert_status = 'ok'
                alert_message = f'Capture rate healthy ({examples_per_day:.1f}/day)'

            result = {
                'total_examples': total_examples,
                'examples_per_day': round(examples_per_day, 2),
                'by_source_system': by_source,
                'low_confidence_rate': round(low_confidence_rate, 3),
                'user_corrections': user_corrections,
                'last_24h_count': recent_count,
                'alert_status': alert_status,
                'alert_message': alert_message,
                'period_days': days_back
            }

            # Cache for 5 minutes
            cache.set(cache_key, result, cls.CACHE_DURATION)

            return result

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error calculating capture rate metrics: {e}", exc_info=True)
            return {
                'error': str(e),
                'alert_status': 'error'
            }

    @classmethod
    def get_labeling_backlog_metrics(cls) -> Dict[str, Any]:
        """
        Get labeling task backlog and completion metrics.

        Returns:
            {
                'pending_tasks': int,
                'in_progress_tasks': int,
                'overdue_tasks': int,
                'avg_completion_time_hours': float,
                'total_examples_pending_labeling': int
            }
        """
        cache_key = 'ml_training_labeling_backlog'
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            now = timezone.now()

            # Task counts by status
            pending = LabelingTask.objects.filter(
                task_status=LabelingTask.TaskStatus.ASSIGNED.value
            ).count()

            in_progress = LabelingTask.objects.filter(
                task_status=LabelingTask.TaskStatus.IN_PROGRESS.value
            ).count()

            # Overdue tasks (past due_date and not completed)
            overdue = LabelingTask.objects.filter(
                due_date__lt=now,
                task_status__in=[
                    LabelingTask.TaskStatus.ASSIGNED.value,
                    LabelingTask.TaskStatus.IN_PROGRESS.value
                ]
            ).count()

            # Average completion time (completed tasks in past 30 days)
            cutoff_30d = now - timedelta(days=30)
            completed_tasks = LabelingTask.objects.filter(
                task_status=LabelingTask.TaskStatus.COMPLETED.value,
                completed_at__gte=cutoff_30d,
                started_at__isnull=False
            )

            completion_times = []
            for task in completed_tasks:
                if task.started_at and task.completed_at:
                    delta = task.completed_at - task.started_at
                    completion_times.append(delta.total_seconds() / 3600)  # hours

            avg_completion_hours = (
                sum(completion_times) / len(completion_times)
                if completion_times else 0.0
            )

            # Total examples selected for labeling but not yet labeled
            pending_examples = TrainingExample.objects.filter(
                selected_for_labeling=True,
                is_labeled=False
            ).count()

            result = {
                'pending_tasks': pending,
                'in_progress_tasks': in_progress,
                'overdue_tasks': overdue,
                'avg_completion_time_hours': round(avg_completion_hours, 2),
                'total_examples_pending_labeling': pending_examples,
                'backlog_health': 'ok' if overdue == 0 else 'warning'
            }

            cache.set(cache_key, result, cls.CACHE_DURATION)

            return result

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error calculating labeling backlog: {e}", exc_info=True)
            return {
                'error': str(e)
            }

    @classmethod
    def get_quality_metrics(cls, days_back: int = 30) -> Dict[str, Any]:
        """
        Get training data quality metrics.

        Args:
            days_back: Number of days to analyze

        Returns:
            {
                'avg_quality_score': float,
                'high_quality_count': int,
                'low_quality_count': int,
                'reviewed_percentage': float
            }
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            labeled_examples = TrainingExample.objects.filter(
                is_labeled=True,
                created_at__gte=cutoff_date
            )

            total_labeled = labeled_examples.count()

            if total_labeled == 0:
                return {
                    'avg_quality_score': 0.0,
                    'high_quality_count': 0,
                    'low_quality_count': 0,
                    'reviewed_percentage': 0.0,
                    'total_labeled': 0
                }

            # Average quality score
            avg_quality = labeled_examples.aggregate(
                Avg('quality_score')
            )['quality_score__avg'] or 0.0

            # High quality (score >= 0.8)
            high_quality = labeled_examples.filter(
                quality_score__gte=0.8
            ).count()

            # Low quality (score < 0.5)
            low_quality = labeled_examples.filter(
                quality_score__lt=0.5
            ).count()

            # Reviewed examples (status = REVIEWED)
            reviewed = labeled_examples.filter(
                labeling_status=TrainingExample.LabelingStatus.REVIEWED.value
            ).count()

            reviewed_percentage = (reviewed / total_labeled * 100) if total_labeled > 0 else 0.0

            return {
                'avg_quality_score': round(avg_quality, 3),
                'high_quality_count': high_quality,
                'low_quality_count': low_quality,
                'reviewed_percentage': round(reviewed_percentage, 2),
                'total_labeled': total_labeled,
                'period_days': days_back
            }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error calculating quality metrics: {e}", exc_info=True)
            return {
                'error': str(e)
            }

    @classmethod
    def get_active_learning_metrics(cls) -> Dict[str, Any]:
        """
        Get active learning effectiveness metrics.

        Returns:
            {
                'selected_for_labeling': int,
                'labeled_from_selection': int,
                'selection_to_label_rate': float,
                'high_value_examples': int  # uncertainty or difficulty > 0.7
            }
        """
        try:
            # Selected for labeling
            selected = TrainingExample.objects.filter(
                selected_for_labeling=True
            )

            selected_count = selected.count()

            # How many were actually labeled
            labeled_count = selected.filter(is_labeled=True).count()

            selection_to_label_rate = (
                labeled_count / selected_count * 100
                if selected_count > 0 else 0.0
            )

            # High-value examples (uncertain or difficult)
            high_value = TrainingExample.objects.filter(
                Q(uncertainty_score__gte=0.7) | Q(difficulty_score__gte=0.7)
            ).count()

            return {
                'selected_for_labeling': selected_count,
                'labeled_from_selection': labeled_count,
                'selection_to_label_rate': round(selection_to_label_rate, 2),
                'high_value_examples': high_value
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating active learning metrics: {e}", exc_info=True)
            return {
                'error': str(e)
            }

    @classmethod
    def get_comprehensive_dashboard(cls) -> Dict[str, Any]:
        """
        Get all metrics for comprehensive monitoring dashboard.

        Returns:
            Dictionary with all metric categories
        """
        return {
            'capture_rate': cls.get_capture_rate_metrics(days_back=7),
            'labeling_backlog': cls.get_labeling_backlog_metrics(),
            'quality': cls.get_quality_metrics(days_back=30),
            'active_learning': cls.get_active_learning_metrics(),
            'generated_at': timezone.now().isoformat()
        }
