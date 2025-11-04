"""
Location Anomaly Detector

Detects GPS-based anomalies and impossible travel scenarios.

Anomalies:
- Impossible travel (teleportation)
- GPS spoofing indicators
- Outside authorized geofences
- Suspicious location patterns
"""

from typing import Dict, Any, List, Optional
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog
from apps.attendance.services.geospatial_service import GeospatialService
import logging

logger = logging.getLogger(__name__)


class LocationAnomalyDetector:
    """Detects location-based attendance anomalies"""

    # Physics constants
    MAX_WALKING_SPEED_KMH = 6  # km/h
    MAX_DRIVING_SPEED_KMH = 130  # km/h
    MAX_FLYING_SPEED_KMH = 900  # km/h

    # Anomaly thresholds
    NULL_ISLAND_COORDS = (0.0, 0.0)  # Suspicious GPS spoofing
    MIN_GPS_ACCURACY_METERS = 100  # Accuracy worse than 100m is suspicious
    MAX_ACCURACY_JUMP = 50  # Sudden accuracy change >50m is suspicious

    def __init__(self, employee):
        self.employee = employee

    def detect_anomalies(self, attendance_record) -> Dict[str, Any]:
        """
        Detect location-based anomalies.

        Returns:
            Dict with detected anomalies and risk score
        """
        anomalies = []

        # Check for Null Island (GPS spoofing)
        if self._is_null_island(attendance_record):
            anomalies.append({
                'type': 'null_island_spoofing',
                'severity': 'critical',
                'description': 'GPS coordinates at (0, 0) - likely spoofing',
                'score': 1.0,
            })

        # Check GPS accuracy
        accuracy_anomaly = self._check_gps_accuracy(attendance_record)
        if accuracy_anomaly:
            anomalies.append(accuracy_anomaly)

        # Check impossible travel
        travel_anomaly = self._check_impossible_travel(attendance_record)
        if travel_anomaly:
            anomalies.append(travel_anomaly)

        # Check geofence violations
        geofence_anomaly = self._check_geofence_violation(attendance_record)
        if geofence_anomaly:
            anomalies.append(geofence_anomaly)

        # Calculate location score
        location_score = sum(a['score'] for a in anomalies) if anomalies else 0.0

        return {
            'anomalies': anomalies,
            'location_score': min(location_score, 1.0),
            'count': len(anomalies),
        }

    def _is_null_island(self, record) -> bool:
        """Check if coordinates are (0, 0) - GPS spoofing indicator"""
        if not record.startlocation:
            return False

        try:
            lon, lat = GeospatialService.extract_coordinates(record.startlocation)
            return (abs(lat) < 0.001 and abs(lon) < 0.001)
        except Exception:
            return False

    def _check_gps_accuracy(self, record) -> Optional[Dict[str, Any]]:
        """Check if GPS accuracy is suspicious"""
        if not record.accuracy:
            return None

        if record.accuracy > self.MIN_GPS_ACCURACY_METERS:
            return {
                'type': 'poor_gps_accuracy',
                'severity': 'medium',
                'description': f'GPS accuracy poor: {record.accuracy}m (max: {self.MIN_GPS_ACCURACY_METERS}m)',
                'score': 0.5,
            }

        # Check for sudden accuracy jumps (spoofing indicator)
        previous = PeopleEventlog.objects.filter(
            people=self.employee,
            punchintime__isnull=False,
            punchintime__lt=record.punchintime
        ).order_by('-punchintime').first()

        if previous and previous.accuracy:
            accuracy_change = abs(record.accuracy - previous.accuracy)
            if accuracy_change > self.MAX_ACCURACY_JUMP:
                return {
                    'type': 'accuracy_manipulation',
                    'severity': 'high',
                    'description': f'GPS accuracy jumped {accuracy_change}m (previous: {previous.accuracy}m)',
                    'score': 0.7,
                }

        return None

    def _check_impossible_travel(self, record) -> Optional[Dict[str, Any]]:
        """Check if travel from previous location is physically impossible"""
        if not record.startlocation or not record.punchintime:
            return None

        # Get previous attendance
        previous = PeopleEventlog.objects.filter(
            people=self.employee,
            endlocation__isnull=False,
            punchouttime__isnull=False,
            punchouttime__lt=record.punchintime
        ).order_by('-punchouttime').first()

        if not previous:
            return None  # No previous location to compare

        try:
            # Calculate distance between locations
            prev_lon, prev_lat = GeospatialService.extract_coordinates(previous.endlocation)
            curr_lon, curr_lat = GeospatialService.extract_coordinates(record.startlocation)

            distance_km = GeospatialService.haversine_distance(
                (prev_lon, prev_lat),
                (curr_lon, curr_lat)
            )

            # Calculate time elapsed
            time_elapsed = record.punchintime - previous.punchouttime
            hours_elapsed = time_elapsed.total_seconds() / 3600

            if hours_elapsed <= 0:
                return None  # Time anomaly handled by temporal detector

            # Calculate required speed
            required_speed_kmh = distance_km / hours_elapsed

            # Check against physical limits
            severity = None
            description = None

            if required_speed_kmh > self.MAX_FLYING_SPEED_KMH:
                severity = 'critical'
                description = f'Impossible travel: {distance_km:.1f}km in {hours_elapsed:.1f}h ({required_speed_kmh:.0f} km/h)'
            elif required_speed_kmh > self.MAX_DRIVING_SPEED_KMH:
                severity = 'high'
                description = f'Unlikely travel speed: {required_speed_kmh:.0f} km/h (driving: {self.MAX_DRIVING_SPEED_KMH} km/h max)'
            elif required_speed_kmh > self.MAX_WALKING_SPEED_KMH and distance_km < 2:
                # Only flag if short distance but high speed (likely spoofing)
                severity = 'medium'
                description = f'GPS jump detected: {distance_km:.1f}km in {hours_elapsed:.1f}h'

            if severity:
                return {
                    'type': 'impossible_travel',
                    'severity': severity,
                    'description': description,
                    'score': min(required_speed_kmh / self.MAX_DRIVING_SPEED_KMH, 1.0),
                    'distance_km': round(distance_km, 2),
                    'time_hours': round(hours_elapsed, 2),
                    'speed_kmh': round(required_speed_kmh, 1),
                }

        except Exception as e:
            logger.error(f"Error checking impossible travel: {e}")

        return None

    def _check_geofence_violation(self, record) -> Optional[Dict[str, Any]]:
        """Check if location is outside authorized geofences"""
        if not record.startlocation:
            return None

        # Check if location is in an authorized geofence
        extras = record.peventlogextras or {}
        is_in_geofence = extras.get('isStartLocationInGeofence', True)

        if not is_in_geofence:
            return {
                'type': 'geofence_violation',
                'severity': 'high',
                'description': 'Check-in location outside authorized geofence',
                'score': 0.8,
            }

        return None
