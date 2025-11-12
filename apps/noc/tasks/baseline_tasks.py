"""
Baseline Threshold Update Task.

Celery task that dynamically adjusts baseline anomaly detection thresholds
based on 30-day false positive rates.

Gap #6 Implementation - Addresses:
- High false positive rates in baseline anomaly detection
- Static thresholds that don't adapt to site-specific patterns
- Need for dynamic sensitivity adjustment

@ontology(
    domain="noc",
    purpose="Dynamic baseline threshold tuning based on false positive feedback",
    task="UpdateBaselineThresholdsTask",
    schedule="Daily at 02:00 UTC",
    criticality="medium",
    integration_points=["BaselineProfile", "NOCAlertEvent", "NOC_CONFIG"],
    tags=["celery", "anomaly-detection", "ml-tuning", "false-positives"]
)

Follows:
- .claude/rules.md Rule #13: IdempotentTask with explicit TTL
- .claude/rules.md Rule #22: Specific exceptions only
- CELERY_CONFIGURATION_GUIDE.md: Task naming, organization, decorators
"""

from apps.core.tasks.base import IdempotentTask
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import logging

logger = logging.getLogger('noc.baseline_tasks')


@shared_task(base=IdempotentTask, bind=True)
class UpdateBaselineThresholdsTask(IdempotentTask):
    """
    Update dynamic thresholds for baseline profiles based on false positive rates.

    Queries all stable BaselineProfile records and calculates rolling 30-day
    false positive rates from NOCAlertEvent resolutions. Adjusts dynamic_threshold
    based on FP rate and sample count.

    Configuration (from settings.NOC_CONFIG):
    - BASELINE_FP_THRESHOLD: High FP rate threshold (0.3 = 30%)
    - BASELINE_STABLE_SAMPLE_COUNT: Sample count for "stable" baseline (100)
    - BASELINE_DEFAULT_THRESHOLD: Default z-score threshold (3.0)
    - BASELINE_SENSITIVE_THRESHOLD: Threshold for stable baselines (2.5)
    - BASELINE_CONSERVATIVE_THRESHOLD: Threshold for high FP rate (4.0)

    Idempotency: 1 hour TTL (prevents duplicate runs)
    """

    name = 'noc.baseline.update_thresholds'
    idempotency_ttl = 3600  # 1 hour

    def run(self):
        """
        Update dynamic thresholds based on 30-day false positive rate.

        Returns:
            dict: Statistics about updates performed
                - updated: Number of baselines updated
                - skipped: Number of baselines skipped (no alerts)
                - total_checked: Total baselines checked
        """
        from apps.noc.security_intelligence.models import BaselineProfile
        from apps.noc.models import NOCAlertEvent
        from django.conf import settings

        logger.info("Starting baseline threshold update task")

        # Get NOC configuration
        config = settings.NOC_CONFIG
        fp_threshold = config['BASELINE_FP_THRESHOLD']
        stable_sample_count = config['BASELINE_STABLE_SAMPLE_COUNT']
        default_threshold = config['BASELINE_DEFAULT_THRESHOLD']
        sensitive_threshold = config['BASELINE_SENSITIVE_THRESHOLD']
        conservative_threshold = config['BASELINE_CONSERVATIVE_THRESHOLD']

        # Get all stable baselines
        baselines = BaselineProfile.objects.filter(is_stable=True)
        total_checked = baselines.count()
        updated_count = 0
        skipped_count = 0

        logger.info(f"Processing {total_checked} stable baselines")

        # 30-day cutoff
        cutoff = timezone.now() - timedelta(days=30)

        for baseline in baselines:
            # Get alerts linked to this baseline via metadata
            # Note: Alerts store baseline_id in metadata when created from baseline anomalies
            alerts = NOCAlertEvent.objects.filter(
                created_at__gte=cutoff,
                bu=baseline.site,  # Match site (NOCAlertEvent uses 'bu' field)
                metadata__baseline_id=baseline.id
            )

            total_alerts = alerts.count()
            if total_alerts == 0:
                skipped_count += 1
                continue

            # Count false positives
            # False positives are marked via metadata['false_positive'] = True
            # when alerts are resolved as false positives
            false_positives = alerts.filter(
                Q(metadata__false_positive=True) | Q(metadata__resolution='FALSE_POSITIVE')
            ).count()

            # Calculate FP rate
            fp_rate = false_positives / total_alerts

            # Update false positive rate
            baseline.false_positive_rate = fp_rate

            # Adjust threshold based on configuration and FP rate
            if fp_rate > fp_threshold:
                # High false positive rate - use conservative threshold (less sensitive)
                new_threshold = conservative_threshold
                reason = f"high FP rate ({fp_rate:.2%})"
            elif baseline.sample_count > stable_sample_count:
                # Stable baseline with good data - use sensitive threshold (more sensitive)
                new_threshold = sensitive_threshold
                reason = f"stable baseline ({baseline.sample_count} samples)"
            else:
                # Default threshold
                new_threshold = default_threshold
                reason = "default"

            baseline.dynamic_threshold = new_threshold
            baseline.last_threshold_update = timezone.now()

            baseline.save(update_fields=[
                'false_positive_rate',
                'dynamic_threshold',
                'last_threshold_update'
            ])

            updated_count += 1

            logger.debug(
                f"Updated baseline {baseline.id} ({baseline.site.buname} - {baseline.metric_type}): "
                f"FP rate={fp_rate:.2%}, threshold={new_threshold} ({reason}), "
                f"alerts={total_alerts}, FPs={false_positives}"
            )

        logger.info(
            f"Baseline threshold update complete: {updated_count} updated, "
            f"{skipped_count} skipped (no alerts), {total_checked} total"
        )

        return {
            'updated': updated_count,
            'skipped': skipped_count,
            'total_checked': total_checked
        }
