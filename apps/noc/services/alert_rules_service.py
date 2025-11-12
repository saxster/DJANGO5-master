"""
Alert Rules Service - Alert suppression, deduplication, and maintenance windows.

Responsibilities:
- Suppress flapping alerts (rapid state changes)
- Deduplicate burst alerts (same type within time window)
- Honor maintenance windows (suppress during planned maintenance)
- Alert noise reduction (40-60% reduction target)

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #11: Specific exception handling
- Rule #15: Network calls with timeouts
- Rule #18: Use constants for magic numbers
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

# Alert suppression constants
FLAP_DETECTION_WINDOW = 5 * SECONDS_IN_MINUTE  # 5 minutes
FLAP_THRESHOLD_COUNT = 3  # 3 state changes = flapping
DEDUPE_WINDOW = 10 * SECONDS_IN_MINUTE  # 10 minutes
BURST_THRESHOLD = 5  # 5 similar alerts = burst
MAINTENANCE_WINDOW_PREFIX = "maint_window"
ALERT_DEDUPE_PREFIX = "alert_dedupe"
FLAP_DETECTION_PREFIX = "alert_flap"


class AlertRulesService:
    """Service for alert suppression, deduplication, and noise reduction."""

    @classmethod
    def should_suppress_alert(cls, alert_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Determine if alert should be suppressed based on rules.

        Args:
            alert_data: Dictionary with alert attributes
                - device_id: Device identifier
                - alert_type: Type of alert
                - severity: Alert severity
                - site_id: Site identifier
                - tenant_id: Tenant identifier

        Returns:
            Tuple of (should_suppress: bool, reason: str)

        Examples:
            >>> AlertRulesService.should_suppress_alert({
            ...     'device_id': 'CAM-001',
            ...     'alert_type': 'OFFLINE',
            ...     'severity': 'HIGH',
            ...     'site_id': 1,
            ...     'tenant_id': 1
            ... })
            (False, None)  # Normal alert
        """
        device_id = alert_data.get('device_id')
        alert_type = alert_data.get('alert_type')
        site_id = alert_data.get('site_id')
        tenant_id = alert_data.get('tenant_id')

        # Check maintenance window
        if cls._is_in_maintenance_window(site_id, device_id):
            logger.info(
                "alert_suppressed_maintenance",
                extra={
                    'device_id': device_id,
                    'alert_type': alert_type,
                    'reason': 'maintenance_window'
                }
            )
            return True, "Device in maintenance window"

        # Check flapping
        if cls._is_flapping(device_id, alert_type):
            logger.info(
                "alert_suppressed_flapping",
                extra={
                    'device_id': device_id,
                    'alert_type': alert_type,
                    'reason': 'flapping_detected'
                }
            )
            return True, "Flapping detected (rapid state changes)"

        # Check deduplication
        if cls._is_duplicate(device_id, alert_type, tenant_id):
            logger.info(
                "alert_suppressed_duplicate",
                extra={
                    'device_id': device_id,
                    'alert_type': alert_type,
                    'reason': 'duplicate_within_window'
                }
            )
            return True, "Duplicate alert within deduplication window"

        # Check burst detection
        if cls._is_burst(alert_type, site_id, tenant_id):
            logger.info(
                "alert_suppressed_burst",
                extra={
                    'alert_type': alert_type,
                    'site_id': site_id,
                    'reason': 'burst_detected'
                }
            )
            return True, "Burst of similar alerts detected"

        return False, None

    @classmethod
    def _is_in_maintenance_window(cls, site_id: int, device_id: str) -> bool:
        """
        Check if device or site is in maintenance window.

        Maintenance windows stored in TypeAssist or Redis cache.
        Format: {site_id}:{device_id}:{start_time}:{end_time}

        Args:
            site_id: Site identifier
            device_id: Device identifier

        Returns:
            True if in maintenance window
        """
        if not site_id or not device_id:
            return False

        # Check device-specific maintenance
        device_key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:{device_id}"
        device_window = cache.get(device_key)
        if device_window:
            start_time, end_time = device_window
            now = timezone.now()
            if start_time <= now <= end_time:
                return True

        # Check site-wide maintenance
        site_key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:all"
        site_window = cache.get(site_key)
        if site_window:
            start_time, end_time = site_window
            now = timezone.now()
            if start_time <= now <= end_time:
                return True

        return False

    @classmethod
    def _is_flapping(cls, device_id: str, alert_type: str) -> bool:
        """
        Detect flapping (rapid state changes).

        Flapping = 3+ state changes within 5 minutes.
        Uses Redis sorted set to track state changes.

        Args:
            device_id: Device identifier
            alert_type: Type of alert

        Returns:
            True if flapping detected
        """
        if not device_id or not alert_type:
            return False

        flap_key = f"{FLAP_DETECTION_PREFIX}:{device_id}:{alert_type}"
        now = timezone.now().timestamp()

        # Get recent state changes
        recent_changes = cache.get(flap_key, [])

        # Filter to only include changes within window
        cutoff = now - FLAP_DETECTION_WINDOW
        recent_changes = [ts for ts in recent_changes if ts > cutoff]

        # Add current change
        recent_changes.append(now)

        # Store updated list
        cache.set(flap_key, recent_changes, FLAP_DETECTION_WINDOW)

        # Check if flapping
        if len(recent_changes) >= FLAP_THRESHOLD_COUNT:
            logger.warning(
                "flapping_detected",
                extra={
                    'device_id': device_id,
                    'alert_type': alert_type,
                    'change_count': len(recent_changes),
                    'window_seconds': FLAP_DETECTION_WINDOW
                }
            )
            return True

        return False

    @classmethod
    def _is_duplicate(cls, device_id: str, alert_type: str, tenant_id: int) -> bool:
        """
        Check if alert is duplicate within deduplication window.

        Args:
            device_id: Device identifier
            alert_type: Type of alert
            tenant_id: Tenant identifier

        Returns:
            True if duplicate found
        """
        if not device_id or not alert_type:
            return False

        dedupe_key = f"{ALERT_DEDUPE_PREFIX}:{tenant_id}:{device_id}:{alert_type}"

        # Check if alert already exists in window
        if cache.get(dedupe_key):
            return True

        # Set dedupe marker
        cache.set(dedupe_key, True, DEDUPE_WINDOW)
        return False

    @classmethod
    def _is_burst(cls, alert_type: str, site_id: int, tenant_id: int) -> bool:
        """
        Detect alert bursts (many similar alerts in short time).

        Burst = 5+ similar alerts within 10 minutes across site.

        Args:
            alert_type: Type of alert
            site_id: Site identifier
            tenant_id: Tenant identifier

        Returns:
            True if burst detected
        """
        if not alert_type or not site_id:
            return False

        burst_key = f"alert_burst:{tenant_id}:{site_id}:{alert_type}"

        # Increment counter
        count = cache.get(burst_key, 0)
        count += 1

        # Set with expiry
        cache.set(burst_key, count, DEDUPE_WINDOW)

        # Check threshold
        if count >= BURST_THRESHOLD:
            logger.warning(
                "burst_detected",
                extra={
                    'alert_type': alert_type,
                    'site_id': site_id,
                    'count': count,
                    'threshold': BURST_THRESHOLD
                }
            )
            return True

        return False

    @classmethod
    def set_maintenance_window(
        cls,
        site_id: int,
        start_time: timezone.datetime,
        end_time: timezone.datetime,
        device_id: Optional[str] = None
    ) -> None:
        """
        Set maintenance window for site or device.

        Args:
            site_id: Site identifier
            start_time: Window start time
            end_time: Window end time
            device_id: Optional device identifier (None = site-wide)

        Raises:
            ValueError: If end_time <= start_time
        """
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")

        duration = int((end_time - start_time).total_seconds())

        if device_id:
            key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:{device_id}"
        else:
            key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:all"

        cache.set(key, (start_time, end_time), duration)

        logger.info(
            "maintenance_window_set",
            extra={
                'site_id': site_id,
                'device_id': device_id or 'all',
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': duration
            }
        )

    @classmethod
    def clear_maintenance_window(cls, site_id: int, device_id: Optional[str] = None) -> None:
        """
        Clear maintenance window.

        Args:
            site_id: Site identifier
            device_id: Optional device identifier (None = site-wide)
        """
        if device_id:
            key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:{device_id}"
        else:
            key = f"{MAINTENANCE_WINDOW_PREFIX}:{site_id}:all"

        cache.delete(key)

        logger.info(
            "maintenance_window_cleared",
            extra={
                'site_id': site_id,
                'device_id': device_id or 'all'
            }
        )

    @classmethod
    def get_suppression_stats(cls, tenant_id: int, hours: int = 24) -> Dict:
        """
        Get alert suppression statistics.

        Args:
            tenant_id: Tenant identifier
            hours: Number of hours to analyze

        Returns:
            Dictionary with suppression metrics:
                - total_alerts_evaluated: int
                - suppressed_maintenance: int
                - suppressed_flapping: int
                - suppressed_duplicate: int
                - suppressed_burst: int
                - suppression_rate: float (0-1)
        """
        # This would typically query a metrics store or logs
        # For now, return structure for implementation
        return {
            'total_alerts_evaluated': 0,
            'suppressed_maintenance': 0,
            'suppressed_flapping': 0,
            'suppressed_duplicate': 0,
            'suppressed_burst': 0,
            'suppression_rate': 0.0,
            'time_period_hours': hours
        }

    @classmethod
    def reset_flap_detection(cls, device_id: str, alert_type: str) -> None:
        """
        Reset flap detection for device/alert type.

        Useful when issue is confirmed resolved.

        Args:
            device_id: Device identifier
            alert_type: Type of alert
        """
        flap_key = f"{FLAP_DETECTION_PREFIX}:{device_id}:{alert_type}"
        cache.delete(flap_key)

        logger.info(
            "flap_detection_reset",
            extra={
                'device_id': device_id,
                'alert_type': alert_type
            }
        )
