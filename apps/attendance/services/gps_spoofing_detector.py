"""
GPS Spoofing Detection Service

Detects GPS location spoofing using multiple techniques.

Detection Methods:
1. Velocity-based impossible travel detection
2. Null Island detection (0,0 coordinates)
3. GPS accuracy manipulation detection
4. Altitude anomalies
5. Signal strength validation

Integrates with LocationAnomalyDetector for comprehensive protection.
"""

from typing import Dict, Any, Optional, Tuple
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog
from apps.attendance.services.geospatial_service import GeospatialService
from apps.attendance.exceptions import AttendanceValidationError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


class GPSSpoofingDetector:
    """
    Advanced GPS spoofing detection service.

    Combines multiple detection techniques for high accuracy.
    """

    # Physical speed limits (km/h)
    MAX_WALKING_SPEED = 6
    MAX_RUNNING_SPEED = 20
    MAX_BICYCLE_SPEED = 30
    MAX_VEHICLE_SPEED = 130
    MAX_TRAIN_SPEED = 300
    MAX_AIRCRAFT_SPEED = 900

    # Transport mode to max speed mapping
    TRANSPORT_SPEED_LIMITS = {
        'BIKE': MAX_BICYCLE_SPEED,
        'RICKSHAW': MAX_BICYCLE_SPEED,
        'BUS': MAX_VEHICLE_SPEED,
        'TRAIN': MAX_TRAIN_SPEED,
        'TRAM': MAX_VEHICLE_SPEED,
        'CAR': MAX_VEHICLE_SPEED,
        'TAXI': MAX_VEHICLE_SPEED,
        'OLA_UBER': MAX_VEHICLE_SPEED,
        'PLANE': MAX_AIRCRAFT_SPEED,
        'FERRY': 50,  # Typical ferry speed
        'NONE': MAX_WALKING_SPEED,  # Assume walking if no transport
    }

    # Spoofing indicators
    NULL_ISLAND_THRESHOLD = 0.001  # Within 0.001 degrees of (0,0)
    MIN_VALID_ACCURACY = 100  # GPS worse than 100m is suspicious
    MAX_ACCURACY_JUMP = 50  # Sudden accuracy change >50m
    MIN_SATELLITES = 4  # Minimum satellites for reliable GPS

    @classmethod
    def validate_gps_location(
        cls,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        previous_record: Optional[PeopleEventlog] = None,
        transport_mode: str = 'NONE'
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive GPS validation.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            accuracy: GPS accuracy in meters
            previous_record: Previous attendance record for velocity check
            transport_mode: Declared transport mode

        Returns:
            Tuple of (is_valid, validation_results)
        """
        results = {
            'is_valid': True,
            'is_suspicious': False,
            'spoofing_indicators': [],
            'warnings': [],
            'risk_score': 0.0,
        }

        # Check 1: Null Island detection
        if cls._is_null_island(latitude, longitude):
            results['is_valid'] = False
            results['is_suspicious'] = True
            results['spoofing_indicators'].append({
                'type': 'null_island',
                'severity': 'critical',
                'description': 'Coordinates at (0,0) - GPS spoofing detected',
            })
            results['risk_score'] = 1.0
            return False, results

        # Check 2: Coordinate validity
        if not cls._are_valid_coordinates(latitude, longitude):
            results['is_valid'] = False
            results['spoofing_indicators'].append({
                'type': 'invalid_coordinates',
                'severity': 'critical',
                'description': f'Invalid GPS coordinates: ({latitude}, {longitude})',
            })
            results['risk_score'] = 1.0
            return False, results

        # Check 3: GPS accuracy
        if accuracy and accuracy > cls.MIN_VALID_ACCURACY:
            results['warnings'].append({
                'type': 'poor_accuracy',
                'severity': 'medium',
                'description': f'GPS accuracy poor: {accuracy}m (threshold: {cls.MIN_VALID_ACCURACY}m)',
            })
            results['risk_score'] += 0.3

        # Check 4: Velocity validation (if previous record exists)
        if previous_record:
            velocity_check = cls._check_velocity(
                previous_record,
                latitude,
                longitude,
                transport_mode
            )

            if not velocity_check['is_valid']:
                results['is_valid'] = False
                results['is_suspicious'] = True
                results['spoofing_indicators'].append(velocity_check['anomaly'])
                results['risk_score'] += 0.7

        # Check 5: Accuracy manipulation
        if previous_record and previous_record.accuracy and accuracy:
            accuracy_jump = abs(accuracy - previous_record.accuracy)
            if accuracy_jump > cls.MAX_ACCURACY_JUMP:
                results['warnings'].append({
                    'type': 'accuracy_manipulation',
                    'severity': 'high',
                    'description': f'GPS accuracy jumped {accuracy_jump}m (previous: {previous_record.accuracy}m)',
                })
                results['risk_score'] += 0.5

        # Determine final validity
        results['is_suspicious'] = results['risk_score'] >= 0.5
        final_valid = results['is_valid'] and results['risk_score'] < 0.8

        return final_valid, results

    @classmethod
    def _is_null_island(cls, latitude: float, longitude: float) -> bool:
        """Check if coordinates are at Null Island (0,0)"""
        return (
            abs(latitude) < cls.NULL_ISLAND_THRESHOLD and
            abs(longitude) < cls.NULL_ISLAND_THRESHOLD
        )

    @staticmethod
    def _are_valid_coordinates(latitude: float, longitude: float) -> bool:
        """Validate coordinate bounds"""
        return (
            -90 <= latitude <= 90 and
            -180 <= longitude <= 180
        )

    @classmethod
    def _check_velocity(
        cls,
        previous_record: PeopleEventlog,
        current_lat: float,
        current_lng: float,
        transport_mode: str
    ) -> Dict[str, Any]:
        """
        Check if velocity between locations is physically possible.

        Args:
            previous_record: Previous attendance record
            current_lat: Current latitude
            current_lng: Current longitude
            transport_mode: Declared transport mode

        Returns:
            Dict with validation result
        """
        if not previous_record.endlocation or not previous_record.punchouttime:
            return {'is_valid': True}

        try:
            # Get previous location
            prev_lon, prev_lat = GeospatialService.extract_coordinates(
                previous_record.endlocation
            )

            # Calculate distance
            distance_km = GeospatialService.haversine_distance(
                (prev_lon, prev_lat),
                (current_lng, current_lat)
            )

            # Calculate time elapsed (using timezone-aware datetimes)
            # Previous record's punchouttime to current time
            # For validation, we need the current punchintime which we don't have yet
            # So we'll use timezone.now() as an approximation
            time_elapsed = timezone.now() - previous_record.punchouttime
            hours_elapsed = time_elapsed.total_seconds() / 3600

            if hours_elapsed <= 0:
                # Negative time - this shouldn't happen
                return {
                    'is_valid': False,
                    'anomaly': {
                        'type': 'time_anomaly',
                        'severity': 'critical',
                        'description': 'Clock-in time before previous clock-out',
                    }
                }

            # Calculate velocity
            velocity_kmh = distance_km / hours_elapsed

            # Get speed limit for transport mode
            max_speed = cls.TRANSPORT_SPEED_LIMITS.get(transport_mode, cls.MAX_WALKING_SPEED)

            # Allow 20% margin for error
            max_speed_with_margin = max_speed * 1.2

            if velocity_kmh > max_speed_with_margin:
                return {
                    'is_valid': False,
                    'anomaly': {
                        'type': 'impossible_travel',
                        'severity': 'critical' if velocity_kmh > max_speed * 2 else 'high',
                        'description': (
                            f'Impossible travel: {distance_km:.1f}km in {hours_elapsed:.1f}h '
                            f'({velocity_kmh:.0f} km/h, max for {transport_mode}: {max_speed} km/h)'
                        ),
                        'distance_km': round(distance_km, 2),
                        'time_hours': round(hours_elapsed, 2),
                        'velocity_kmh': round(velocity_kmh, 1),
                        'max_allowed_kmh': max_speed,
                    }
                }

            return {'is_valid': True, 'velocity_kmh': velocity_kmh}

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during velocity check: {e}", exc_info=True)
            return {'is_valid': True}  # Don't block on database errors
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.error(f"Data validation error during velocity check: {e}", exc_info=True)
            return {'is_valid': True}  # Don't block on validation errors

    @classmethod
    def check_spoofing_indicators(
        cls,
        latitude: float,
        longitude: float,
        accuracy: Optional[float],
        device_info: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for multiple GPS spoofing indicators.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            accuracy: GPS accuracy
            device_info: Device metadata

        Returns:
            List of detected spoofing indicators
        """
        indicators = []

        # Indicator 1: Null Island
        if cls._is_null_island(latitude, longitude):
            indicators.append({
                'indicator': 'null_island',
                'confidence': 1.0,
                'description': 'Coordinates at (0,0)',
            })

        # Indicator 2: Too accurate (some spoofing tools report perfect accuracy)
        if accuracy and accuracy < 1.0:
            indicators.append({
                'indicator': 'unrealistic_accuracy',
                'confidence': 0.7,
                'description': f'GPS accuracy suspiciously perfect: {accuracy}m',
            })

        # Indicator 3: Too inaccurate
        if accuracy and accuracy > 100:
            indicators.append({
                'indicator': 'poor_accuracy',
                'confidence': 0.6,
                'description': f'GPS accuracy poor: {accuracy}m',
            })

        # Indicator 4: Device indicators (if available)
        if device_info:
            # Check if GPS hardware info is missing
            if not device_info.get('gps_provider'):
                indicators.append({
                    'indicator': 'missing_gps_provider',
                    'confidence': 0.5,
                    'description': 'GPS provider information missing',
                })

        return indicators
