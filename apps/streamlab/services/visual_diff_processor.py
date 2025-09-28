"""
Visual Diff Pipeline and Baseline Management
Processes visual regression test results from mobile Paparazzi tests.
"""

import hashlib
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.issue_tracker.models import AnomalyOccurrence, AnomalySignature

logger = logging.getLogger(__name__)


class VisualDiffProcessor:
    """
    Visual Diff Pipeline for processing mobile visual regression tests.

    Integrates with existing Stream Testbench anomaly detection for visual regressions.
    Manages baselines and calculates visual difference scores.
    """

    def __init__(self):
        self.baseline_storage_path = getattr(settings, 'VISUAL_BASELINE_STORAGE_PATH', 'visual_baselines/')
        self.diff_threshold = getattr(settings, 'VISUAL_DIFF_THRESHOLD', 0.05)  # 5% change threshold

    def process_visual_event(self, stream_event: StreamEvent) -> Optional[Dict]:
        """
        Process a visual regression test event.

        Args:
            stream_event: StreamEvent with visual regression test data

        Returns:
            Dict with visual diff analysis results or None if processing failed
        """
        try:
            if not self.is_visual_regression_event(stream_event):
                return None

            screen_name = stream_event.payload_sanitized.get('screen_name')
            visual_baseline_hash = stream_event.payload_sanitized.get('visual_baseline_hash')

            if not screen_name or not visual_baseline_hash:
                logger.warning(f"Missing screen_name or visual_baseline_hash in event {stream_event.id}")
                return None

            # Get or create baseline
            baseline_info = self.get_or_create_baseline(screen_name, visual_baseline_hash, stream_event)

            # Calculate visual diff score
            diff_result = self.calculate_visual_diff(baseline_info, stream_event)

            # Update stream event with visual regression data
            self.update_stream_event_visual_data(stream_event, diff_result)

            # Check for visual anomaly
            if diff_result['visual_diff_score'] > self.diff_threshold:
                self.create_visual_anomaly(stream_event, diff_result)

            logger.info(f"Processed visual event for {screen_name}: diff_score={diff_result['visual_diff_score']:.3f}")

            return diff_result

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to process visual event {stream_event.id}: {e}")
            return None

    def is_visual_regression_event(self, stream_event: StreamEvent) -> bool:
        """Check if this is a visual regression test event."""
        payload = stream_event.payload_sanitized or {}
        return (
            payload.get('test_type') == 'visual_regression' or
            stream_event.endpoint.startswith('compose_screen/') and
            'visual_baseline_hash' in payload
        )

    def get_or_create_baseline(self, screen_name: str, visual_hash: str, stream_event: StreamEvent) -> Dict:
        """
        Get existing visual baseline or create a new one.

        Args:
            screen_name: Name of the screen being tested
            visual_hash: Visual baseline hash from Paparazzi
            stream_event: Current stream event

        Returns:
            Dict with baseline information
        """
        baseline_key = f"{screen_name}_{stream_event.client_app_version or 'unknown'}"

        # Check for existing baseline in recent events
        existing_baseline = StreamEvent.objects.filter(
            endpoint=f"compose_screen/{screen_name}",
            visual_baseline_hash=visual_hash,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).first()

        if existing_baseline:
            return {
                'baseline_event_id': str(existing_baseline.id),
                'baseline_hash': visual_hash,
                'baseline_timestamp': existing_baseline.timestamp,
                'is_new_baseline': False,
                'app_version': existing_baseline.client_app_version
            }
        else:
            # Create new baseline
            logger.info(f"Creating new visual baseline for {screen_name} with hash {visual_hash}")
            return {
                'baseline_event_id': str(stream_event.id),
                'baseline_hash': visual_hash,
                'baseline_timestamp': stream_event.timestamp,
                'is_new_baseline': True,
                'app_version': stream_event.client_app_version
            }

    def calculate_visual_diff(self, baseline_info: Dict, current_event: StreamEvent) -> Dict:
        """
        Calculate visual difference between baseline and current event.

        For now, this is a simplified hash-based comparison.
        In production, this would involve actual image comparison.

        Args:
            baseline_info: Baseline information
            current_event: Current visual test event

        Returns:
            Dict with visual diff analysis
        """
        current_hash = current_event.payload_sanitized.get('visual_baseline_hash')
        baseline_hash = baseline_info['baseline_hash']

        # Simple hash comparison (in production, use actual image diff)
        if current_hash == baseline_hash:
            diff_score = 0.0
            diff_regions = []
        else:
            # Simulate visual diff analysis
            diff_score = self.simulate_visual_diff_score(baseline_hash, current_hash)
            diff_regions = self.simulate_diff_regions(diff_score)

        return {
            'visual_diff_score': diff_score,
            'baseline_hash': baseline_hash,
            'current_hash': current_hash,
            'comparison_method': 'hash_based_simulation',
            'diff_regions': diff_regions,
            'analysis_timestamp': timezone.now().isoformat(),
            'is_regression': diff_score > self.diff_threshold,
            'baseline_info': baseline_info
        }

    def simulate_visual_diff_score(self, baseline_hash: str, current_hash: str) -> float:
        """
        Simulate visual diff score based on hash comparison.
        In production, this would use actual image comparison algorithms.
        """
        if baseline_hash == current_hash:
            return 0.0

        # Simple hash-based difference simulation
        baseline_int = int(hashlib.md5(baseline_hash.encode()).hexdigest()[:8], 16)
        current_int = int(hashlib.md5(current_hash.encode()).hexdigest()[:8], 16)

        # Calculate normalized difference (0.0 to 1.0)
        diff = abs(baseline_int - current_int) / (2**32 - 1)

        # Scale to reasonable range for visual diffs (0.0 to 0.3 max)
        return min(diff * 0.3, 0.3)

    def simulate_diff_regions(self, diff_score: float) -> List[Dict]:
        """
        Simulate diff regions based on diff score.
        In production, this would identify actual changed regions.
        """
        if diff_score == 0.0:
            return []

        # Simulate 1-3 changed regions
        num_regions = min(int(diff_score * 10) + 1, 3)
        regions = []

        for i in range(num_regions):
            regions.append({
                'region_id': f"region_{i+1}",
                'x': 50 + (i * 100),
                'y': 100 + (i * 50),
                'width': 100,
                'height': 50,
                'change_type': 'content_change' if diff_score > 0.1 else 'minor_change',
                'severity': 'high' if diff_score > 0.2 else 'medium' if diff_score > 0.1 else 'low'
            })

        return regions

    def update_stream_event_visual_data(self, stream_event: StreamEvent, diff_result: Dict):
        """Update StreamEvent with visual regression analysis data."""
        stream_event.visual_baseline_hash = diff_result['baseline_hash']
        stream_event.visual_diff_score = diff_result['visual_diff_score']
        stream_event.visual_diff_metadata = {
            'diff_regions': diff_result['diff_regions'],
            'comparison_method': diff_result['comparison_method'],
            'analysis_timestamp': diff_result['analysis_timestamp'],
            'baseline_info': diff_result['baseline_info']
        }

        # Mark as anomaly if significant visual change
        if diff_result['is_regression']:
            stream_event.outcome = 'anomaly'

        stream_event.save()

    def create_visual_anomaly(self, stream_event: StreamEvent, diff_result: Dict):
        """
        Create anomaly occurrence for visual regression.
        Integrates with existing issue tracker anomaly detection.
        """
        try:
            screen_name = stream_event.payload_sanitized.get('screen_name', 'unknown_screen')

            # Create anomaly signature for visual regression
            signature_data = {
                'screen_name': screen_name,
                'visual_change_type': 'regression',
                'app_version': stream_event.client_app_version or 'unknown'
            }
            signature_hash = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()

            # Get or create anomaly signature
            signature, created = AnomalySignature.objects.get_or_create(
                signature_hash=signature_hash,
                defaults={
                    'anomaly_type': 'visual_regression',
                    'severity': self.get_visual_severity(diff_result['visual_diff_score']),
                    'pattern': signature_data,
                    'endpoint_pattern': f"compose_screen/{screen_name}",
                    'schema_signature': f"visual_regression_{screen_name}"
                }
            )

            if not created:
                signature.update_occurrence()

            # Create anomaly occurrence
            occurrence = AnomalyOccurrence.objects.create(
                signature=signature,
                test_run_id=stream_event.run.id if stream_event.run else None,
                event_ref=stream_event.id,
                endpoint=stream_event.endpoint,
                error_message=f"Visual regression detected: {diff_result['visual_diff_score']:.1%} change",
                payload_sanitized={
                    'visual_diff_score': diff_result['visual_diff_score'],
                    'screen_name': screen_name,
                    'diff_regions': diff_result['diff_regions'],
                    'baseline_hash': diff_result['baseline_hash']
                },
                client_app_version=stream_event.client_app_version,
                client_os_version=stream_event.client_os_version,
                client_device_model=stream_event.client_device_model,
                correlation_id=stream_event.correlation_id
            )

            logger.info(f"Created visual anomaly occurrence: {occurrence.id} for screen {screen_name}")

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create visual anomaly for event {stream_event.id}: {e}")

    def get_visual_severity(self, diff_score: float) -> str:
        """Determine severity level based on visual diff score."""
        if diff_score > 0.3:
            return 'critical'
        elif diff_score > 0.15:
            return 'error'
        elif diff_score > 0.05:
            return 'warning'
        else:
            return 'info'

    def get_visual_baselines_for_screen(self, screen_name: str, app_version: str = None) -> List[Dict]:
        """
        Get visual baselines for a specific screen.

        Args:
            screen_name: Name of the screen
            app_version: Optional app version filter

        Returns:
            List of baseline information
        """
        query_filters = {
            'endpoint': f"compose_screen/{screen_name}",
            'visual_baseline_hash__isnull': False,
            'timestamp__gte': timezone.now() - timedelta(days=90)
        }

        if app_version:
            query_filters['client_app_version'] = app_version

        baselines = StreamEvent.objects.filter(**query_filters).values(
            'visual_baseline_hash',
            'client_app_version',
            'timestamp',
            'visual_diff_score'
        ).distinct('visual_baseline_hash').order_by('visual_baseline_hash', '-timestamp')[:10]

        return list(baselines)

    def cleanup_old_baselines(self, days_to_keep: int = 90):
        """Clean up old visual baselines to manage storage."""
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        old_events = StreamEvent.objects.filter(
            visual_baseline_hash__isnull=False,
            timestamp__lt=cutoff_date
        )

        count = old_events.count()
        if count > 0:
            # Clear visual data from old events but keep the events
            old_events.update(
                visual_baseline_hash='',
                visual_diff_score=None,
                visual_diff_metadata=None
            )

            logger.info(f"Cleaned up visual data from {count} old events (older than {days_to_keep} days)")

        return count