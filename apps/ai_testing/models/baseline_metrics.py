"""
ML-Enhanced Baselines - Metrics and Analysis.

Helper methods for baseline analysis and drift detection.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
"""

from datetime import timedelta
from django.db.models import Count
from django.utils import timezone


class BaselineMetrics:
    """
    Helper class for baseline analysis and metrics.
    Provides analysis methods for MLBaseline model.
    """

    @staticmethod
    def analyze_baseline_drift(baseline_model, days=30):
        """
        Analyze how baselines are changing over time.

        Args:
            baseline_model: The MLBaseline model class
            days: Number of days to analyze

        Returns:
            dict: Analysis results with drift metrics
        """
        since_date = timezone.now() - timedelta(days=days)

        # New baselines created
        new_baselines = baseline_model.objects.filter(
            created_at__gte=since_date
        ).count()

        # Baselines superseded
        superseded = baseline_model.objects.filter(
            superseded_by__isnull=False,
            updated_at__gte=since_date
        ).count()

        # Approval status distribution
        status_distribution = dict(
            baseline_model.objects.filter(created_at__gte=since_date)
            .values('approval_status')
            .annotate(count=Count('id'))
            .values_list('approval_status', 'count')
        )

        # Confidence trends
        high_confidence = baseline_model.objects.filter(
            created_at__gte=since_date,
            semantic_confidence__in=['high', 'very_high']
        ).count()

        total_recent = baseline_model.objects.filter(
            created_at__gte=since_date
        ).count()

        high_confidence_rate = (
            (high_confidence / total_recent * 100)
            if total_recent > 0
            else 0
        )

        return {
            'new_baselines': new_baselines,
            'superseded_baselines': superseded,
            'approval_status_distribution': status_distribution,
            'high_confidence_rate': round(high_confidence_rate, 1),
            'baseline_turnover_rate': round(
                (superseded / max(1, new_baselines)) * 100, 1
            ),
            'analysis_period_days': days
        }

    @staticmethod
    def analyze_visual_difference(baseline, new_visual_data):
        """
        Analyze visual differences using ML semantic understanding.

        Args:
            baseline: MLBaseline instance
            new_visual_data: New visual data to compare

        Returns:
            dict: Visual difference analysis results
        """
        if baseline.baseline_type != 'visual':
            return None

        # This would call the ML visual processor service
        try:
            from apps.ai_testing.services.ml_visual_processor import MLVisualProcessor

            processor = MLVisualProcessor()
            diff_analysis = processor.analyze_semantic_difference(
                baseline=baseline,
                new_data=new_visual_data
            )

            return diff_analysis
        except ImportError:
            # Service not yet implemented
            return None

    @staticmethod
    def detect_functional_changes(baseline, new_functional_data):
        """
        Detect functional changes in API or component behavior.

        Args:
            baseline: MLBaseline instance
            new_functional_data: New functional data to compare

        Returns:
            list: List of detected changes
        """
        if baseline.baseline_type not in ['functional', 'api']:
            return None

        # Compare response structures, timing patterns, etc.
        changes = []

        # This would implement functional change detection logic
        # For now, returning placeholder
        return changes


__all__ = ['BaselineMetrics']
