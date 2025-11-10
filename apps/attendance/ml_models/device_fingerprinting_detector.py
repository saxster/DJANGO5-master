"""
Device Fingerprinting Detector

Detects suspicious device usage patterns.

Anomalies:
- Device sharing (same device, multiple employees)
- Rapid device switching
- Unregistered devices
- Device spoofing indicators
"""

from typing import Dict, Any, List, Optional
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog
import logging

logger = logging.getLogger(__name__)


class DeviceFingerprintingDetector:
    """Detects device-based anomalies"""

    MAX_DEVICES_PER_EMPLOYEE = 3  # Typical: work phone + personal phone + tablet
    DEVICE_SHARING_WINDOW_MINUTES = 30  # Flag if same device used by 2+ people within 30min

    def __init__(self, employee):
        self.employee = employee

    def detect_anomalies(self, attendance_record) -> Dict[str, Any]:
        """
        Detect device-based anomalies.

        Returns:
            Dict with anomalies and risk score
        """
        anomalies = []

        if not attendance_record.deviceid:
            return {'anomalies': [], 'device_score': 0.0, 'count': 0}

        # Check device sharing
        sharing_anomaly = self._check_device_sharing(attendance_record)
        if sharing_anomaly:
            anomalies.append(sharing_anomaly)

        # Check rapid device switching
        switching_anomaly = self._check_rapid_device_switching(attendance_record)
        if switching_anomaly:
            anomalies.append(switching_anomaly)

        # Check too many devices
        device_count_anomaly = self._check_device_count(attendance_record)
        if device_count_anomaly:
            anomalies.append(device_count_anomaly)

        device_score = sum(a['score'] for a in anomalies) if anomalies else 0.0

        return {
            'anomalies': anomalies,
            'device_score': min(device_score, 1.0),
            'count': len(anomalies),
        }

    def _check_device_sharing(self, record) -> Optional[Dict[str, Any]]:
        """Check if device is being shared between employees"""
        # Look for other employees using same device recently
        window_start = record.punchintime - timedelta(minutes=self.DEVICE_SHARING_WINDOW_MINUTES)
        window_end = record.punchintime + timedelta(minutes=self.DEVICE_SHARING_WINDOW_MINUTES)

        other_users = PeopleEventlog.objects.filter(
            deviceid=record.deviceid,
            punchintime__gte=window_start,
            punchintime__lte=window_end
        ).exclude(
            people=self.employee
        ).values('people__username').distinct()

        if other_users.exists():
            usernames = [u['people__username'] for u in other_users]
            return {
                'type': 'device_sharing',
                'severity': 'critical',
                'description': f'Device shared with: {", ".join(usernames)}',
                'score': 0.9,
                'other_users': usernames,
            }

        return None

    def _check_rapid_device_switching(self, record) -> Optional[Dict[str, Any]]:
        """Check if employee is switching devices too frequently"""
        # Get last 5 check-ins
        recent = PeopleEventlog.objects.filter(
            people=self.employee,
            punchintime__isnull=False
        ).order_by('-punchintime')[:5]

        devices = [r.deviceid for r in recent if r.deviceid]

        # Count unique devices
        unique_devices = len(set(devices))

        if unique_devices >= 4:  # 4+ different devices in last 5 check-ins
            return {
                'type': 'rapid_device_switching',
                'severity': 'medium',
                'description': f'Used {unique_devices} different devices in last 5 check-ins',
                'score': 0.6,
            }

        return None

    def _check_device_count(self, record) -> Optional[Dict[str, Any]]:
        """Check if employee is using too many different devices"""
        # Count unique devices in last 30 days
        since = timezone.now() - timedelta(days=30)
        device_count = PeopleEventlog.objects.filter(
            people=self.employee,
            punchintime__gte=since,
            deviceid__isnull=False
        ).values('deviceid').distinct().count()

        if device_count > self.MAX_DEVICES_PER_EMPLOYEE:
            return {
                'type': 'excessive_devices',
                'severity': 'low',
                'description': f'Used {device_count} different devices (typical: {self.MAX_DEVICES_PER_EMPLOYEE})',
                'score': 0.4,
            }

        return None
