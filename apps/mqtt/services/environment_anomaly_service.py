"""
Environment Anomaly Detection Service

Analyzes temperature, humidity, and environmental sensor readings
to detect zone-level anomalies, HVAC failures, and leak detection.

Features:
- Zone-level aggregation and anomaly detection
- HVAC failure detection (temperature deviation)
- Leak detection (rapid humidity spikes)
- Baseline learning with statistical thresholds
- Multi-tenant isolation

Uses SensorReading model for analysis.

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db.models import Avg, Max, Min, Count, Q

from apps.mqtt.models import SensorReading
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger(__name__)


class EnvironmentAnomalyService:
    """
    Service for detecting environmental anomalies from sensor data.
    """

    TEMPERATURE_THRESHOLD = 5.0
    HUMIDITY_SPIKE_THRESHOLD = 20.0
    BASELINE_WINDOW_HOURS = 24
    ANOMALY_DETECTION_WINDOW = 4

    @classmethod
    def detect_zone_anomalies(
        cls,
        tenant_id: int,
        zone_id: Optional[str] = None,
        lookback_hours: int = 1
    ) -> List[Dict]:
        """
        Detect environmental anomalies across zones.

        Args:
            tenant_id: Tenant identifier
            zone_id: Optional specific zone to check
            lookback_hours: Hours to analyze

        Returns:
            List of detected anomalies with details
        """
        anomalies = []
        cutoff_time = get_current_utc() - timedelta(hours=lookback_hours)

        try:
            query = Q(tenant_id=tenant_id, timestamp__gte=cutoff_time)
            if zone_id:
                query &= Q(zone_id=zone_id)

            sensors = SensorReading.objects.filter(query).order_by('zone_id', 'sensor_id')

            if not sensors.exists():
                logger.info(f"No sensor data for tenant {tenant_id} in last {lookback_hours}h")
                return []

            zone_data = cls._aggregate_by_zone(sensors)

            for zone, readings in zone_data.items():
                temp_anomaly = cls._check_temperature_anomaly(zone, readings, tenant_id)
                if temp_anomaly:
                    anomalies.append(temp_anomaly)

                humidity_anomaly = cls._check_humidity_anomaly(zone, readings, tenant_id)
                if humidity_anomaly:
                    anomalies.append(humidity_anomaly)

            logger.info(
                f"Detected {len(anomalies)} environmental anomalies "
                f"for tenant {tenant_id}"
            )
            return anomalies

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error detecting anomalies: {e}", exc_info=True)
            return []

    @classmethod
    def detect_hvac_failure(cls, tenant_id: int, zone_id: str) -> Optional[Dict]:
        """
        Detect potential HVAC failure in zone.

        Args:
            tenant_id: Tenant identifier
            zone_id: Zone identifier

        Returns:
            Failure details or None
        """
        try:
            baseline = cls._get_temperature_baseline(tenant_id, zone_id)
            if not baseline:
                logger.warning(f"No baseline data for zone {zone_id}")
                return None

            recent_avg = cls._get_recent_temperature(tenant_id, zone_id, hours=1)
            if not recent_avg:
                return None

            deviation = abs(recent_avg - baseline['avg'])

            if deviation > cls.TEMPERATURE_THRESHOLD:
                return {
                    'type': 'HVAC_FAILURE',
                    'zone_id': zone_id,
                    'baseline_temp': baseline['avg'],
                    'current_temp': recent_avg,
                    'deviation': deviation,
                    'severity': 'HIGH' if deviation > 10 else 'MEDIUM',
                    'detected_at': get_current_utc().isoformat(),
                }

            return None

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting HVAC failure: {e}", exc_info=True)
            return None

    @classmethod
    def detect_leak(cls, tenant_id: int, zone_id: str) -> Optional[Dict]:
        """
        Detect potential water leak from humidity spike.

        Args:
            tenant_id: Tenant identifier
            zone_id: Zone identifier

        Returns:
            Leak detection details or None
        """
        try:
            cutoff = get_current_utc() - timedelta(hours=cls.ANOMALY_DETECTION_WINDOW)

            readings = SensorReading.objects.filter(
                tenant_id=tenant_id,
                zone_id=zone_id,
                sensor_type='HUMIDITY',
                timestamp__gte=cutoff
            ).order_by('timestamp')

            if readings.count() < 2:
                return None

            values = list(readings.values_list('value', flat=True))
            max_spike = max([values[i+1] - values[i] for i in range(len(values)-1)])

            if max_spike > cls.HUMIDITY_SPIKE_THRESHOLD:
                return {
                    'type': 'WATER_LEAK',
                    'zone_id': zone_id,
                    'humidity_spike': max_spike,
                    'current_humidity': values[-1],
                    'severity': 'CRITICAL' if max_spike > 40 else 'HIGH',
                    'detected_at': get_current_utc().isoformat(),
                }

            return None

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting leak: {e}", exc_info=True)
            return None

    @classmethod
    def _aggregate_by_zone(cls, sensors) -> Dict[str, List]:
        """Group sensor readings by zone."""
        zone_data = defaultdict(list)

        for reading in sensors:
            zone_data[reading.zone_id or 'UNKNOWN'].append({
                'sensor_id': reading.sensor_id,
                'sensor_type': reading.sensor_type,
                'value': reading.value,
                'timestamp': reading.timestamp,
            })

        return dict(zone_data)

    @classmethod
    def _check_temperature_anomaly(
        cls,
        zone_id: str,
        readings: List[Dict],
        tenant_id: int
    ) -> Optional[Dict]:
        """Check for temperature anomalies in zone."""
        temp_readings = [r for r in readings if r['sensor_type'] == 'TEMPERATURE']

        if not temp_readings:
            return None

        current_avg = sum(r['value'] for r in temp_readings) / len(temp_readings)
        baseline = cls._get_temperature_baseline(tenant_id, zone_id)

        if not baseline:
            return None

        deviation = abs(current_avg - baseline['avg'])

        if deviation > cls.TEMPERATURE_THRESHOLD:
            return {
                'type': 'TEMPERATURE_ANOMALY',
                'zone_id': zone_id,
                'baseline': baseline['avg'],
                'current': current_avg,
                'deviation': deviation,
                'severity': 'HIGH' if deviation > 10 else 'MEDIUM',
                'detected_at': get_current_utc().isoformat(),
            }

        return None

    @classmethod
    def _check_humidity_anomaly(
        cls,
        zone_id: str,
        readings: List[Dict],
        tenant_id: int
    ) -> Optional[Dict]:
        """Check for humidity anomalies in zone."""
        humidity_readings = [r for r in readings if r['sensor_type'] == 'HUMIDITY']

        if len(humidity_readings) < 2:
            return None

        values = [r['value'] for r in humidity_readings]
        max_spike = max([values[i+1] - values[i] for i in range(len(values)-1)])

        if max_spike > cls.HUMIDITY_SPIKE_THRESHOLD:
            return {
                'type': 'HUMIDITY_SPIKE',
                'zone_id': zone_id,
                'spike_value': max_spike,
                'current_humidity': values[-1],
                'severity': 'HIGH',
                'detected_at': get_current_utc().isoformat(),
            }

        return None

    @classmethod
    def _get_temperature_baseline(cls, tenant_id: int, zone_id: str) -> Optional[Dict]:
        """Calculate temperature baseline for zone."""
        try:
            cutoff = get_current_utc() - timedelta(hours=cls.BASELINE_WINDOW_HOURS)

            stats = SensorReading.objects.filter(
                tenant_id=tenant_id,
                zone_id=zone_id,
                sensor_type='TEMPERATURE',
                timestamp__gte=cutoff
            ).aggregate(
                avg=Avg('value'),
                min_val=Min('value'),
                max_val=Max('value'),
                count=Count('id')
            )

            if stats['count'] < 10:
                return None

            return {
                'avg': stats['avg'],
                'min': stats['min_val'],
                'max': stats['max_val'],
                'sample_count': stats['count'],
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating baseline: {e}")
            return None

    @classmethod
    def _get_recent_temperature(
        cls,
        tenant_id: int,
        zone_id: str,
        hours: int = 1
    ) -> Optional[float]:
        """Get recent average temperature for zone."""
        try:
            cutoff = get_current_utc() - timedelta(hours=hours)

            avg = SensorReading.objects.filter(
                tenant_id=tenant_id,
                zone_id=zone_id,
                sensor_type='TEMPERATURE',
                timestamp__gte=cutoff
            ).aggregate(avg=Avg('value'))

            return avg['avg']

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error fetching recent temperature: {e}")
            return None
