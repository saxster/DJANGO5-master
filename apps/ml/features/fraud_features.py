"""
Fraud Detection Feature Engineering Module.

This module extracts 12 features from attendance records for fraud prediction.
Features are designed for imbalanced classification with XGBoost.

Architecture:
- Temporal features (4): Time-based patterns
- Location features (2): GPS and geofence analysis
- Behavioral features (3): Peer comparison and consistency
- Biometric features (3): Face recognition and verification

Follows .claude/rules.md:
- Rule #7: Utility < 50 lines per function
- Rule #11: Specific exception handling
- Rule #13: Network timeouts where applicable
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from math import radians, cos, sin, asin, sqrt
from django.utils import timezone
from django.db.models import Avg, StdDev, Count, Q

logger = logging.getLogger('noc.ml.features')


class FraudFeatureExtractor:
    """
    Extract 12 fraud detection features from attendance records.

    Design Principles:
    - Each feature has clear business logic
    - All computations are deterministic
    - Features normalized to [0, 1] where possible
    - Missing values handled with safe defaults
    """

    @classmethod
    def extract_all_features(cls, attendance_event, person, site) -> Dict[str, float]:
        """
        Extract all 12 features for fraud prediction.

        Args:
            attendance_event: PeopleEventlog instance (or scheduled event data)
            person: People instance
            site: Bt instance

        Returns:
            Dict with 12 feature values

        Raises:
            ValueError: If required fields are missing
        """
        try:
            features = {}

            # Temporal features (4)
            features['hour_of_day'] = cls.extract_hour_of_day(attendance_event)
            features['day_of_week'] = cls.extract_day_of_week(attendance_event)
            features['is_weekend'] = cls.extract_is_weekend(attendance_event)
            features['is_holiday'] = cls.extract_is_holiday(attendance_event)

            # Location features (2)
            features['gps_drift_meters'] = cls.extract_gps_drift(attendance_event, site)
            features['location_consistency_score'] = cls.extract_location_consistency(person, site)

            # Behavioral features (3)
            features['check_in_frequency_zscore'] = cls.extract_check_in_frequency_zscore(person, site)
            features['late_arrival_rate'] = cls.extract_late_arrival_rate(person, site)
            features['weekend_work_frequency'] = cls.extract_weekend_work_frequency(person)

            # Biometric features (3)
            features['face_recognition_confidence'] = cls.extract_face_confidence(attendance_event)
            features['biometric_mismatch_count_30d'] = cls.extract_biometric_mismatch_count(person)
            features['time_since_last_event'] = cls.extract_time_since_last_event(person)

            return features

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Feature extraction error: {e}", exc_info=True)
            return cls._get_default_features()

    # ========== TEMPORAL FEATURES (4) ==========

    @staticmethod
    def extract_hour_of_day(attendance_event) -> int:
        """
        Extract hour of day (0-23).

        Business Logic:
        - Fraud peaks at unusual hours (2-5 AM, late night)
        - Normal work hours: 6 AM - 10 PM
        - Used to detect off-hours check-ins

        Computation:
        - Extract hour from punchintime
        - Range: 0 (midnight) to 23 (11 PM)

        Expected Range:
        - Normal: 6-22 (work hours)
        - Suspicious: 0-5, 23 (off hours)
        """
        try:
            if hasattr(attendance_event, 'punchintime') and attendance_event.punchintime:
                return attendance_event.punchintime.hour
            elif hasattr(attendance_event, 'scheduled_time'):
                return attendance_event.scheduled_time.hour
            return 8  # Default to 8 AM
        except (AttributeError, TypeError):
            return 8

    @staticmethod
    def extract_day_of_week(attendance_event) -> int:
        """
        Extract day of week (0-6, Monday=0).

        Business Logic:
        - Weekend work less common in security roles
        - Pattern breaks indicate potential fraud
        - Combined with work schedule validation

        Computation:
        - Extract weekday from datefor or scheduled_time
        - Range: 0 (Monday) to 6 (Sunday)

        Expected Range:
        - Normal: 0-4 (weekdays)
        - Suspicious: 5-6 (weekends) unless scheduled
        """
        try:
            if hasattr(attendance_event, 'datefor') and attendance_event.datefor:
                return attendance_event.datefor.weekday()
            elif hasattr(attendance_event, 'scheduled_time'):
                return attendance_event.scheduled_time.weekday()
            return 0  # Default to Monday
        except (AttributeError, TypeError):
            return 0

    @staticmethod
    def extract_is_weekend(attendance_event) -> float:
        """
        Binary flag for weekend work (0 or 1).

        Business Logic:
        - Unauthorized weekend work is fraud indicator
        - Cross-validated with shift schedule
        - Higher weight if no weekend shifts assigned

        Computation:
        - 1.0 if day_of_week in [5, 6]
        - 0.0 otherwise

        Expected Range:
        - Normal: 0.0 (weekday work)
        - Suspicious: 1.0 (weekend work without schedule)
        """
        day = FraudFeatureExtractor.extract_day_of_week(attendance_event)
        return 1.0 if day in [5, 6] else 0.0

    @staticmethod
    def extract_is_holiday(attendance_event) -> float:
        """
        Binary flag for holiday work (0 or 1).

        Business Logic:
        - Holiday attendance is red flag
        - Most facilities closed on holidays
        - Fake attendance often created on holidays

        Computation:
        - Check datefor against holiday calendar
        - Placeholder: always returns 0.0 (MVP)
        - TODO: Integrate with tenant holiday calendar

        Expected Range:
        - Normal: 0.0 (non-holiday)
        - Suspicious: 1.0 (holiday without authorization)
        """
        # TODO: Integrate with tenant-specific holiday calendar
        # For MVP, return 0.0 (not a holiday)
        return 0.0

    # ========== LOCATION FEATURES (2) ==========

    @staticmethod
    def extract_gps_drift(attendance_event, site) -> float:
        """
        GPS drift from geofence center (meters).

        Business Logic:
        - Measures distance from expected location
        - GPS spoofing shows abnormal distances
        - Combined with geofence radius for validation

        Computation:
        - Haversine formula between punch location and site center
        - Returns meters (0 = perfect match)
        - Capped at 10,000m for outliers

        Expected Range:
        - Normal: 0-500m (within geofence)
        - Suspicious: 500-5000m (outside geofence)
        - Critical: >5000m (GPS spoofing likely)
        """
        try:
            if not site or not hasattr(site, 'geofence'):
                return 0.0

            # Get punch location
            if hasattr(attendance_event, 'startlat') and attendance_event.startlat:
                punch_lat = float(attendance_event.startlat)
                punch_lng = float(attendance_event.startlng)
            else:
                return 0.0

            # Get site center from geofence
            geofence = site.geofence
            if not geofence or not hasattr(geofence, 'latitude'):
                return 0.0

            site_lat = float(geofence.latitude)
            site_lng = float(geofence.longitude)

            # Haversine distance
            distance = FraudFeatureExtractor._haversine_distance(
                punch_lat, punch_lng, site_lat, site_lng
            )

            # Cap at 10km
            return min(distance, 10000.0)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"GPS drift calculation error: {e}")
            return 0.0

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate Haversine distance between two GPS coordinates.

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            Distance in meters
        """
        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        return R * c

    @staticmethod
    def extract_location_consistency(person, site, days=30) -> float:
        """
        Location consistency score (0-1, 1=consistent).

        Business Logic:
        - Measures GPS location variance over time
        - Consistent employees check-in from similar locations
        - High variance indicates potential GPS manipulation

        Computation:
        - Calculate StdDev of GPS coordinates (last 30 days)
        - Normalize to [0, 1]: 1 - (stddev / max_expected_stddev)
        - High score = consistent, Low score = erratic

        Expected Range:
        - Normal: 0.7-1.0 (consistent location)
        - Suspicious: 0.3-0.7 (moderate variance)
        - Critical: 0.0-0.3 (high variance, GPS spoofing)
        """
        try:
            from apps.attendance.models import PeopleEventlog

            since = timezone.now() - timedelta(days=days)

            # Get recent check-ins at this site
            recent_events = PeopleEventlog.objects.filter(
                people=person,
                bu=site,
                datefor__gte=since.date(),
                startlat__isnull=False,
                startlng__isnull=False
            ).values_list('startlat', 'startlng')

            if len(recent_events) < 5:
                return 0.5  # Insufficient data

            # Calculate coordinate variance
            lats = [float(lat) for lat, _ in recent_events]
            lngs = [float(lng) for _, lng in recent_events]

            lat_stddev = _calculate_stddev(lats)
            lng_stddev = _calculate_stddev(lngs)

            # Average stddev (in degrees)
            avg_stddev = (lat_stddev + lng_stddev) / 2

            # Normalize (0.01 degree ≈ 1km, expect <0.005 for consistent)
            max_expected_stddev = 0.01
            consistency = 1.0 - min(avg_stddev / max_expected_stddev, 1.0)

            return round(consistency, 2)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Location consistency calculation error: {e}")
            return 0.5

    # ========== BEHAVIORAL FEATURES (3) ==========

    @staticmethod
    def extract_check_in_frequency_zscore(person, site, days=30) -> float:
        """
        Z-score of check-in frequency vs peer group.

        Business Logic:
        - Abnormal check-in frequency is fraud indicator
        - Compare person to peers at same site/role
        - High Z-score = more frequent than normal

        Computation:
        - Count person's check-ins (last 30 days)
        - Calculate mean/stddev for peer group (same site)
        - Z-score = (person_count - mean) / stddev

        Expected Range:
        - Normal: -1.0 to +1.0 (within 1 stddev)
        - Suspicious: +1.0 to +2.0 (more frequent)
        - Critical: >+2.0 (abnormally high frequency)
        """
        try:
            from apps.attendance.models import PeopleEventlog

            since = timezone.now() - timedelta(days=days)

            # Person's check-in count
            person_count = PeopleEventlog.objects.filter(
                people=person,
                bu=site,
                datefor__gte=since.date()
            ).count()

            # Peer group statistics (same site)
            peer_stats = PeopleEventlog.objects.filter(
                bu=site,
                datefor__gte=since.date()
            ).values('people').annotate(
                count=Count('id')
            ).aggregate(
                avg_count=Avg('count'),
                stddev_count=StdDev('count')
            )

            mean = peer_stats['avg_count'] or person_count
            stddev = peer_stats['stddev_count'] or 1.0

            if stddev == 0:
                return 0.0

            zscore = (person_count - mean) / stddev

            # Cap at ±3.0 for outliers
            return max(-3.0, min(zscore, 3.0))

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Check-in frequency Z-score error: {e}")
            return 0.0

    @staticmethod
    def extract_late_arrival_rate(person, site, days=30) -> float:
        """
        Late arrival rate (0-1, % of late check-ins).

        Business Logic:
        - Consistent lateness indicates disengagement
        - Fake attendance often created before shift
        - Combined with shift schedule validation

        Computation:
        - Compare punchintime to scheduled shift start
        - Late = check-in >15 minutes after shift start
        - Rate = late_count / total_count

        Expected Range:
        - Normal: 0.0-0.1 (0-10% late)
        - Suspicious: 0.1-0.3 (10-30% late)
        - Critical: >0.3 (>30% late)
        """
        try:
            from apps.attendance.models import PeopleEventlog
            from apps.scheduler.models import Schedule

            since = timezone.now() - timedelta(days=days)

            # Get person's check-ins with shift info
            events = PeopleEventlog.objects.filter(
                people=person,
                bu=site,
                datefor__gte=since.date(),
                punchintime__isnull=False
            ).select_related('people')

            if events.count() == 0:
                return 0.0

            late_count = 0
            total_count = events.count()

            for event in events:
                # Get scheduled shift for this date
                scheduled_shift = Schedule.objects.filter(
                    people=person,
                    bu=site,
                    datef=event.datefor
                ).first()

                if not scheduled_shift or not scheduled_shift.fromt:
                    continue

                # Combine date + time for comparison
                scheduled_start = datetime.combine(
                    event.datefor,
                    scheduled_shift.fromt
                )
                scheduled_start = timezone.make_aware(scheduled_start)

                # Check if late (>15 minutes)
                time_diff = (event.punchintime - scheduled_start).total_seconds() / 60
                if time_diff > 15:
                    late_count += 1

            return round(late_count / total_count, 2)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Late arrival rate calculation error: {e}")
            return 0.0

    @staticmethod
    def extract_weekend_work_frequency(person, days=90) -> float:
        """
        Weekend work frequency (0-1, % of weekend check-ins).

        Business Logic:
        - Weekend work is less common
        - Unauthorized weekend attendance is fraud indicator
        - Must be cross-validated with shift schedule

        Computation:
        - Count weekend check-ins (last 90 days)
        - Frequency = weekend_count / total_count
        - Higher = more weekend work

        Expected Range:
        - Normal: 0.0-0.2 (0-20% weekend work)
        - Suspicious: 0.2-0.5 (20-50% weekend work)
        - Critical: >0.5 (>50% weekend work)
        """
        try:
            from apps.attendance.models import PeopleEventlog

            since = timezone.now() - timedelta(days=days)

            # Total check-ins
            total_events = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date()
            )

            total_count = total_events.count()
            if total_count == 0:
                return 0.0

            # Weekend check-ins (Saturday=5, Sunday=6)
            weekend_count = sum(
                1 for event in total_events
                if event.datefor.weekday() in [5, 6]
            )

            return round(weekend_count / total_count, 2)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Weekend work frequency error: {e}")
            return 0.0

    # ========== BIOMETRIC FEATURES (3) ==========

    @staticmethod
    def extract_face_confidence(attendance_event) -> float:
        """
        Face recognition confidence (0-1).

        Business Logic:
        - Low confidence indicates biometric fraud
        - Fake faces score lower in face recognition
        - Distance metric from face embedding comparison

        Computation:
        - Extract from peventlogextras['distance_in']
        - Convert distance to confidence: 1 - distance
        - Range: 0 (no match) to 1 (perfect match)

        Expected Range:
        - Normal: 0.7-1.0 (high confidence)
        - Suspicious: 0.3-0.7 (low confidence)
        - Critical: 0.0-0.3 (biometric fraud likely)
        """
        try:
            if not hasattr(attendance_event, 'peventlogextras'):
                return 0.5

            extras = attendance_event.peventlogextras or {}

            # Get face distance (lower = better match)
            distance = extras.get('distance_in')
            if distance is None:
                return 0.5

            # Convert distance to confidence (assuming threshold ~0.4)
            # distance 0.0 = confidence 1.0, distance 0.4+ = confidence 0.0
            confidence = max(0.0, 1.0 - (float(distance) / 0.4))

            return round(confidence, 2)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Face confidence extraction error: {e}")
            return 0.5

    @staticmethod
    def extract_biometric_mismatch_count(person, days=30) -> int:
        """
        Count of biometric mismatches (last 30 days).

        Business Logic:
        - Repeated biometric failures indicate fraud attempts
        - Normal employees have <2 mismatches per month
        - High count = potential buddy punching or fake attendance

        Computation:
        - Count events with peventlogextras['verified_in'] = False
        - Or distance_in > 0.4 (failed verification)
        - Raw count (not normalized)

        Expected Range:
        - Normal: 0-2 (occasional failures)
        - Suspicious: 3-5 (multiple failures)
        - Critical: >5 (systematic fraud)
        """
        try:
            from apps.attendance.models import PeopleEventlog

            since = timezone.now() - timedelta(days=days)

            # Count failed verifications
            mismatch_count = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date(),
                peventlogextras__verified_in=False
            ).count()

            return mismatch_count

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Biometric mismatch count error: {e}")
            return 0

    @staticmethod
    def extract_time_since_last_event(person) -> float:
        """
        Time since last check-in (seconds).

        Business Logic:
        - Rapid consecutive check-ins are suspicious
        - Normal: >8 hours between check-ins (shift length)
        - Rapid check-ins may indicate system gaming

        Computation:
        - Get most recent PeopleEventlog for person
        - Calculate seconds since punchintime
        - Normalized: capped at 86400 (24 hours)

        Expected Range:
        - Normal: >28800 (>8 hours)
        - Suspicious: 3600-28800 (1-8 hours)
        - Critical: <3600 (<1 hour, rapid check-ins)
        """
        try:
            from apps.attendance.models import PeopleEventlog

            last_event = PeopleEventlog.objects.filter(
                people=person,
                punchintime__isnull=False
            ).order_by('-punchintime').first()

            if not last_event:
                return 86400.0  # No history = 24 hours

            time_diff = (timezone.now() - last_event.punchintime).total_seconds()

            # Cap at 24 hours
            return min(time_diff, 86400.0)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning(f"Time since last event error: {e}")
            return 86400.0

    # ========== HELPER METHODS ==========

    @staticmethod
    def _get_default_features() -> Dict[str, float]:
        """Return default feature values when extraction fails."""
        return {
            'hour_of_day': 8,
            'day_of_week': 0,
            'is_weekend': 0.0,
            'is_holiday': 0.0,
            'gps_drift_meters': 0.0,
            'location_consistency_score': 0.5,
            'check_in_frequency_zscore': 0.0,
            'late_arrival_rate': 0.0,
            'weekend_work_frequency': 0.0,
            'face_recognition_confidence': 0.5,
            'biometric_mismatch_count_30d': 0,
            'time_since_last_event': 86400.0,
        }


def _calculate_stddev(values: List[float]) -> float:
    """Calculate standard deviation of a list of values."""
    if not values or len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return sqrt(variance)
