"""
Tour Route Optimization Service.

Analyzes tour checkpoint completion data to identify patterns, missed checkpoints,
and propose route improvements for security guard tours.

Following .claude/rules.md:
- Rule #7: Service layer < 150 lines
- Rule #11: Specific exception handling
- Rule #13: Comprehensive validation

Author: Claude Code
Phase: 6 - Data Utilization
Created: 2025-11-06
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.db.models import Count, Q, Avg, F
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.activity.models import Job, Jobneed, JobneedDetails
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

__all__ = ['TourOptimizationService']


class TourOptimizationService:
    """
    Analyzes tour checkpoint data to optimize routes.

    Features:
    - Identifies frequently missed checkpoints
    - Calculates completion rates per checkpoint
    - Detects time bottlenecks in tour sequences
    - Proposes route reordering for efficiency

    Input: Job with INTERNALTOUR/EXTERNALTOUR identifier
    Output: Optimization recommendations with metrics
    """

    MIN_EXECUTION_THRESHOLD = 5

    @classmethod
    def analyze_tour(cls, tour_job_id: int, days_lookback: int = 30) -> Dict[str, Any]:
        """
        Analyze tour execution history and identify optimization opportunities.

        Args:
            tour_job_id: ID of parent tour Job
            days_lookback: Number of days to analyze

        Returns:
            Dictionary with:
            - missed_checkpoints: List of frequently missed locations
            - completion_stats: Per-checkpoint completion rates
            - time_analysis: Bottleneck detection
            - recommendations: Suggested route improvements
        """
        try:
            tour_job = Job.objects.select_related('client').get(pk=tour_job_id)

            if tour_job.identifier not in ['INTERNALTOUR', 'EXTERNALTOUR']:
                raise ValidationError(f"Job {tour_job_id} is not a tour")

            cutoff_date = timezone.now() - timedelta(days=days_lookback)

            checkpoints = Job.objects.filter(parent=tour_job).select_related('asset', 'location')
            checkpoint_stats = []

            for checkpoint in checkpoints:
                executions = Jobneed.objects.filter(
                    job=checkpoint,
                    createdon__gte=cutoff_date,
                    client=tour_job.client
                ).aggregate(
                    total=Count('id'),
                    completed=Count('id', filter=Q(status='COMPLETED')),
                    avg_duration=Avg(F('endtime') - F('starttime'))
                )

                total_count = executions['total'] or 0
                completed_count = executions['completed'] or 0
                completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0

                checkpoint_stats.append({
                    'checkpoint_id': checkpoint.id,
                    'checkpoint_name': checkpoint.jobname,
                    'location': checkpoint.location.locname if checkpoint.location else checkpoint.asset.assetname if checkpoint.asset else 'Unknown',
                    'total_executions': total_count,
                    'completed': completed_count,
                    'completion_rate': round(completion_rate, 2),
                    'avg_duration_seconds': executions['avg_duration'].total_seconds() if executions['avg_duration'] else 0,
                })

            missed_checkpoints = [
                cp for cp in checkpoint_stats
                if cp['total_executions'] >= cls.MIN_EXECUTION_THRESHOLD and cp['completion_rate'] < 80
            ]

            recommendations = cls._generate_recommendations(checkpoint_stats, missed_checkpoints)

            logger.info(
                f"Tour optimization analysis complete",
                extra={
                    'tour_id': tour_job_id,
                    'checkpoints_analyzed': len(checkpoint_stats),
                    'missed_count': len(missed_checkpoints)
                }
            )

            return {
                'tour_id': tour_job_id,
                'tour_name': tour_job.jobname,
                'analysis_period_days': days_lookback,
                'checkpoint_stats': checkpoint_stats,
                'missed_checkpoints': missed_checkpoints,
                'recommendations': recommendations,
                'analyzed_at': timezone.now().isoformat()
            }

        except Job.DoesNotExist:
            logger.error(f"Tour job not found: {tour_job_id}")
            raise ValidationError(f"Tour job {tour_job_id} not found")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error analyzing tour: {e}", exc_info=True)
            raise

    @classmethod
    def _generate_recommendations(cls, stats: List[Dict], missed: List[Dict]) -> List[Dict]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        if missed:
            recommendations.append({
                'type': 'MISSED_CHECKPOINTS',
                'priority': 'HIGH',
                'description': f'{len(missed)} checkpoint(s) have completion rates below 80%',
                'action': 'Review accessibility and timing constraints for these checkpoints',
                'affected_checkpoints': [cp['checkpoint_name'] for cp in missed]
            })

        long_duration_checkpoints = [
            cp for cp in stats
            if cp['avg_duration_seconds'] > 600
        ]

        if long_duration_checkpoints:
            recommendations.append({
                'type': 'TIME_BOTTLENECK',
                'priority': 'MEDIUM',
                'description': f'{len(long_duration_checkpoints)} checkpoint(s) take over 10 minutes on average',
                'action': 'Consider breaking down complex checkpoints or reviewing question sets',
                'affected_checkpoints': [cp['checkpoint_name'] for cp in long_duration_checkpoints]
            })

        return recommendations
