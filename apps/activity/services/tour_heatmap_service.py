"""
Tour Heatmap Service.

Generates geographic coverage heatmaps for tour routes to visualize
patrol coverage and identify gaps in security monitoring.

Following .claude/rules.md:
- Rule #7: Service layer < 150 lines
- Rule #11: Specific exception handling
- Rule #16: Network timeouts

Author: Claude Code
Phase: 6 - Data Utilization
Created: 2025-11-06
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any
from django.db.models import Count, Q
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.activity.models import Job, Jobneed, Location
from apps.attendance.models import Tracking
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

__all__ = ['TourHeatmapService']


class TourHeatmapService:
    """
    Generates geographic heatmap data for tour coverage analysis.

    Features:
    - Aggregates GPS tracking data from tour executions
    - Identifies coverage gaps in patrol routes
    - Generates coordinate clusters for visualization
    - Calculates visit frequency per location

    Output format compatible with Leaflet.js heat layer plugin
    """

    @classmethod
    def generate_heatmap_data(cls, tour_job_id: int, days_lookback: int = 30) -> Dict[str, Any]:
        """
        Generate heatmap data from tour execution history.

        Args:
            tour_job_id: Parent tour Job ID
            days_lookback: Number of days to include

        Returns:
            Dictionary with:
            - heatmap_points: List of [lat, lng, intensity] for heatmap
            - checkpoint_coverage: Visit counts per checkpoint
            - coverage_gaps: Locations with low visit frequency
        """
        try:
            tour_job = Job.objects.select_related('client').get(pk=tour_job_id)

            if tour_job.identifier not in ['INTERNALTOUR', 'EXTERNALTOUR']:
                raise ValidationError(f"Job {tour_job_id} is not a tour")

            cutoff_date = timezone.now() - timedelta(days=days_lookback)

            checkpoints = Job.objects.filter(parent=tour_job).select_related('location')

            checkpoint_visits = []
            for checkpoint in checkpoints:
                visit_count = Jobneed.objects.filter(
                    job=checkpoint,
                    createdon__gte=cutoff_date,
                    status='COMPLETED',
                    client=tour_job.client
                ).count()

                if checkpoint.location and checkpoint.location.gpslocation:
                    checkpoint_visits.append({
                        'checkpoint_id': checkpoint.id,
                        'checkpoint_name': checkpoint.jobname,
                        'latitude': checkpoint.location.gpslocation.y,
                        'longitude': checkpoint.location.gpslocation.x,
                        'visit_count': visit_count
                    })

            max_visits = max([cv['visit_count'] for cv in checkpoint_visits], default=1)
            heatmap_points = [
                [cv['latitude'], cv['longitude'], cv['visit_count'] / max_visits]
                for cv in checkpoint_visits
            ]

            tracking_points = cls._get_tracking_heatmap(tour_job, cutoff_date)

            coverage_gaps = [
                cv for cv in checkpoint_visits
                if cv['visit_count'] < (max_visits * 0.3)
            ]

            logger.info(
                f"Heatmap data generated",
                extra={
                    'tour_id': tour_job_id,
                    'checkpoint_count': len(checkpoint_visits),
                    'gap_count': len(coverage_gaps)
                }
            )

            return {
                'tour_id': tour_job_id,
                'tour_name': tour_job.jobname,
                'analysis_period_days': days_lookback,
                'heatmap_points': heatmap_points,
                'tracking_points': tracking_points,
                'checkpoint_coverage': checkpoint_visits,
                'coverage_gaps': coverage_gaps,
                'generated_at': timezone.now().isoformat()
            }

        except Job.DoesNotExist:
            logger.error(f"Tour job not found: {tour_job_id}")
            raise ValidationError(f"Tour job {tour_job_id} not found")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error generating heatmap: {e}", exc_info=True)
            raise

    @classmethod
    def _get_tracking_heatmap(cls, tour_job: Job, cutoff_date) -> List[List[float]]:
        """Extract GPS tracking points from tour executions."""
        tracking_data = Tracking.objects.filter(
            identifier__in=['INTERNALTOUR', 'EXTERNALTOUR'],
            receiveddate__gte=cutoff_date,
            gpslocation__isnull=False
        ).values_list('gpslocation', flat=True)[:1000]

        tracking_points = []
        for point in tracking_data:
            if point:
                tracking_points.append([point.y, point.x, 0.5])

        return tracking_points
