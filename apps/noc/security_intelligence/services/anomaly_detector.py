"""
Anomaly Detector Service.

Detects anomalies by comparing observed values against baselines.
Uses statistical deviation (z-scores) with configurable sensitivity.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.utils import timezone

from apps.noc.security_intelligence.models import BaselineProfile, AuditFinding
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector

logger = logging.getLogger('noc.anomaly_detector')


class AnomalyDetector:
    """
    Detects anomalies in site activity using baseline profiles.

    Detection method:
    - Compares current values to hour-of-week baselines
    - Uses robust z-score with configurable thresholds
    - Only alerts when baseline is stable (30+ samples)
    """

    @classmethod
    def detect_anomalies_for_site(cls, site):
        """
        Detect all anomalies for a site at current time.

        Args:
            site: Bt instance

        Returns:
            list: AuditFinding instances for detected anomalies
        """
        try:
            now = timezone.now()
            hour_of_week = now.weekday() * 24 + now.hour

            metric_types = [
                'phone_events',
                'location_updates',
                'movement_distance',
                'tasks_completed',
                'tour_checkpoints',
            ]

            findings = []

            for metric_type in metric_types:
                finding = cls._detect_metric_anomaly(site, metric_type, hour_of_week)
                if finding:
                    findings.append(finding)

            logger.info(f"Detected {len(findings)} anomalies for {site.buname}")
            return findings

        except (ValueError, AttributeError) as e:
            logger.error(f"Anomaly detection error: {e}", exc_info=True)
            return []

    @classmethod
    def _detect_metric_anomaly(cls, site, metric_type, hour_of_week):
        """
        Detect anomaly for single metric type.

        Args:
            site: Bt instance
            metric_type: String metric type
            hour_of_week: Integer 0-167

        Returns:
            AuditFinding or None
        """
        try:
            # Get baseline
            baseline = BaselineProfile.objects.filter(
                site=site,
                metric_type=metric_type,
                hour_of_week=hour_of_week,
                is_stable=True
            ).first()

            if not baseline:
                logger.debug(f"No stable baseline for {site.buname} {metric_type} hour {hour_of_week}")
                return None

            # Get current observed value
            observed_value = cls._get_current_metric_value(site, metric_type)
            if observed_value is None:
                return None

            # Check if anomalous
            is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

            if is_anomalous:
                return cls._create_anomaly_finding(
                    site=site,
                    metric_type=metric_type,
                    observed_value=observed_value,
                    baseline=baseline,
                    z_score=z_score,
                    threshold=threshold
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Metric anomaly detection error: {e}", exc_info=True)
            return None

    @classmethod
    def _get_current_metric_value(cls, site, metric_type):
        """Get current observed value for metric."""
        try:
            # Get active person for this site (simplified)
            from apps.peoples.models import People
            person = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not person:
                return None

            # Collect signals for last hour
            signals = ActivitySignalCollector.collect_all_signals(
                person=person,
                site=site,
                window_minutes=60
            )

            # Map metric type to signal key
            metric_map = {
                'phone_events': 'phone_events_count',
                'location_updates': 'location_updates_count',
                'movement_distance': 'movement_distance_meters',
                'tasks_completed': 'tasks_completed_count',
                'tour_checkpoints': 'tour_checkpoints_scanned',
            }

            return float(signals.get(metric_map.get(metric_type, metric_type), 0))

        except (ValueError, AttributeError) as e:
            logger.error(f"Current metric value error: {e}", exc_info=True)
            return None

    @classmethod
    def _create_anomaly_finding(cls, site, metric_type, observed_value, baseline, z_score, threshold):
        """Create finding for detected anomaly."""
        try:
            # Determine severity based on z-score magnitude
            if abs(z_score) >= 3.0:
                severity = 'CRITICAL'
            elif abs(z_score) >= 2.5:
                severity = 'HIGH'
            elif abs(z_score) >= 2.0:
                severity = 'MEDIUM'
            else:
                severity = 'LOW'

            # Determine direction
            direction = 'ABOVE' if z_score > 0 else 'BELOW'

            # Determine category based on metric type
            category_map = {
                'phone_events': 'DEVICE_HEALTH',
                'location_updates': 'DEVICE_HEALTH',
                'movement_distance': 'OPERATIONAL',
                'tasks_completed': 'OPERATIONAL',
                'tour_checkpoints': 'SECURITY',
            }
            category = category_map.get(metric_type, 'OPERATIONAL')

            finding = AuditFinding.objects.create(
                tenant=site.tenant,
                site=site,
                finding_type=f'ANOMALY_{metric_type.upper()}_{direction}',
                category=category,
                severity=severity,
                title=f'Anomalous {metric_type.replace("_", " ")} detected',
                description=(
                    f'Observed {metric_type}: {observed_value:.1f} is {direction} baseline '
                    f'(expected: {baseline.mean:.1f} ± {baseline.std_dev:.1f}). '
                    f'Z-score: {z_score:.2f} (threshold: {threshold:.1f})'
                ),
                evidence={
                    'metric_type': metric_type,
                    'observed_value': observed_value,
                    'baseline_mean': baseline.mean,
                    'baseline_std_dev': baseline.std_dev,
                    'z_score': z_score,
                    'threshold': threshold,
                    'hour_of_week': baseline.hour_of_week,
                    'sensitivity': baseline.sensitivity,
                    'sample_count': baseline.sample_count,
                },
                recommended_actions=[
                    f'Verify {metric_type.replace("_", " ")} data accuracy',
                    'Check for environmental changes (shifts, events)',
                    'Review guard activity patterns',
                    'Investigate if persistent across multiple hours',
                ]
            )

            logger.info(
                f"Created anomaly finding for {site.buname}: {metric_type} "
                f"observed={observed_value:.1f} baseline={baseline.mean:.1f} z={z_score:.2f}"
            )

            return finding

        except (ValueError, AttributeError) as e:
            logger.error(f"Anomaly finding creation error: {e}", exc_info=True)
            return None
