"""
Behavioral Anomaly Detector

Detects anomalous attendance behavior based on learned patterns.

Features:
- Baseline learning from historical data (30+ days)
- Pattern recognition for typical behavior
- Deviation detection
- Continuous learning and adaptation

Anomalies Detected:
- Unusual check-in/out times
- New or unfamiliar locations
- Device changes
- Atypical work patterns
"""

from typing import Dict, Any, List, Tuple, Optional
from django.db.models import Avg, Count, StdDev, Q
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
import logging
import statistics

logger = logging.getLogger(__name__)


class BehavioralAnomalyDetector:
    """
    Detects behavioral anomalies in attendance patterns.

    Uses statistical analysis and machine learning to identify
    unusual behavior that may indicate fraud.
    """

    MINIMUM_BASELINE_RECORDS = 30  # Need 30+ records for reliable baseline
    BASELINE_WINDOW_DAYS = 90  # Use last 90 days for baseline

    def __init__(self, employee):
        """
        Initialize detector for an employee.

        Args:
            employee: User object
        """
        self.employee = employee
        self.profile = self._get_or_create_profile()

    def _get_or_create_profile(self) -> UserBehaviorProfile:
        """Get or create behavior profile for employee"""
        profile, created = UserBehaviorProfile.objects.get_or_create(
            employee=self.employee,
            defaults={
                'tenant': self.employee.client_id if hasattr(self.employee, 'client_id') else 'default'
            }
        )

        if created:
            logger.info(f"Created new behavior profile for {self.employee.username}")

        return profile

    def train_baseline(self, force_retrain: bool = False) -> bool:
        """
        Train behavioral baseline from historical data.

        Args:
            force_retrain: Force retraining even if baseline exists

        Returns:
            True if baseline trained successfully
        """
        # Check if retraining needed
        if not force_retrain and self.profile.is_baseline_sufficient:
            if not self.profile.needs_retraining(days=30):
                logger.debug(f"Baseline for {self.employee.username} is still fresh")
                return True

        try:
            # Get historical attendance records
            since = timezone.now() - timedelta(days=self.BASELINE_WINDOW_DAYS)
            records = PeopleEventlog.objects.filter(
                people=self.employee,
                punchintime__gte=since,
                punchintime__isnull=False
            ).order_by('punchintime')

            record_count = records.count()

            if record_count < self.MINIMUM_BASELINE_RECORDS:
                logger.warning(
                    f"Insufficient data for {self.employee.username}: "
                    f"{record_count} records (need {self.MINIMUM_BASELINE_RECORDS})"
                )
                self.profile.is_baseline_sufficient = False
                self.profile.training_records_count = record_count
                self.profile.save()
                return False

            # Learn patterns
            self._learn_temporal_patterns(records)
            self._learn_location_patterns(records)
            self._learn_device_patterns(records)
            self._learn_work_day_patterns(records)
            self._learn_transport_patterns(records)

            # Update profile metadata
            self.profile.training_records_count = record_count
            self.profile.is_baseline_sufficient = True
            self.profile.baseline_updated_at = timezone.now()
            self.profile.total_checkins = record_count
            self.profile.save()

            logger.info(
                f"Trained baseline for {self.employee.username} "
                f"using {record_count} records"
            )
            return True

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error training baseline: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to train baseline: {e}", exc_info=True)
            return False

    def _learn_temporal_patterns(self, records) -> None:
        """Learn typical check-in/out times"""
        checkin_hours = []
        checkin_minutes = []
        durations = []

        for record in records:
            if record.punchintime:
                checkin_hours.append(record.punchintime.hour)
                checkin_minutes.append(record.punchintime.minute)

            if record.duration:
                durations.append(record.duration)

        if checkin_hours:
            # Most common check-in hour (mode)
            self.profile.typical_checkin_hour = statistics.mode(checkin_hours)

            # Average check-in minute within that hour
            self.profile.typical_checkin_minute = int(statistics.mean(checkin_minutes))

            # Calculate variance (standard deviation)
            if len(checkin_hours) > 1:
                hour_variance = statistics.stdev(checkin_hours)
                self.profile.checkin_time_variance_minutes = int(hour_variance * 60)

        if durations:
            self.profile.typical_work_duration_minutes = int(statistics.mean(durations))
            if len(durations) > 1:
                self.profile.work_duration_variance_minutes = int(statistics.stdev(durations))

    def _learn_location_patterns(self, records) -> None:
        """Learn typical check-in locations"""
        from collections import Counter

        locations = []
        geofences = []

        for record in records:
            if record.startlocation:
                from apps.attendance.services.geospatial_service import GeospatialService
                try:
                    lon, lat = GeospatialService.extract_coordinates(record.startlocation)
                    locations.append({'lat': lat, 'lng': lon})
                except Exception:
                    pass

            if record.geofence_id:
                geofences.append(record.geofence_id)

        if locations:
            # Cluster nearby locations
            clustered = self._cluster_locations(locations, radius_meters=100)
            self.profile.typical_locations = clustered

        if geofences:
            # Most common geofences
            geofence_counts = Counter(geofences)
            self.profile.typical_geofences = [gf for gf, count in geofence_counts.most_common(5)]

    def _cluster_locations(self, locations: List[Dict], radius_meters: float = 100) -> List[Dict]:
        """Cluster nearby locations into centroids"""
        if not locations:
            return []

        from apps.attendance.services.geospatial_service import GeospatialService

        clusters = []

        for loc in locations:
            # Find existing cluster within radius
            found_cluster = False

            for cluster in clusters:
                distance_meters = GeospatialService.haversine_distance(
                    (cluster['lng'], cluster['lat']),
                    (loc['lng'], loc['lat'])
                ) * 1000

                if distance_meters <= radius_meters:
                    # Add to existing cluster
                    cluster['count'] += 1
                    cluster['frequency'] = cluster['count'] / len(locations)
                    found_cluster = True
                    break

            if not found_cluster:
                # Create new cluster
                clusters.append({
                    'lat': loc['lat'],
                    'lng': loc['lng'],
                    'count': 1,
                    'frequency': 1 / len(locations)
                })

        # Sort by frequency (most common first)
        clusters.sort(key=lambda c: c['frequency'], reverse=True)

        return clusters[:10]  # Keep top 10 locations

    def _learn_device_patterns(self, records) -> None:
        """Learn typical devices"""
        from collections import Counter

        devices = [r.deviceid for r in records if r.deviceid]

        if devices:
            device_counts = Counter(devices)
            # Keep devices used at least 3 times
            self.profile.typical_devices = [
                device for device, count in device_counts.items()
                if count >= 3
            ]

    def _learn_work_day_patterns(self, records) -> None:
        """Learn typical work days of week"""
        from collections import Counter

        work_days = [r.datefor.isoweekday() for r in records if r.datefor]

        if work_days:
            day_counts = Counter(work_days)
            # Keep days worked at least 20% of the time
            total = len(work_days)
            self.profile.typical_work_days = [
                day for day, count in day_counts.items()
                if count / total >= 0.2
            ]

    def _learn_transport_patterns(self, records) -> None:
        """Learn typical transport modes"""
        from collections import Counter

        all_modes = []
        for record in records:
            if record.transportmodes:
                all_modes.extend(record.transportmodes)

        if all_modes:
            mode_counts = Counter(all_modes)
            # Keep modes used at least 10% of the time
            total = len(all_modes)
            self.profile.typical_transport_modes = [
                mode for mode, count in mode_counts.items()
                if count / total >= 0.1 and mode != 'NONE'
            ]

    def detect_anomalies(self, attendance_record) -> Dict[str, Any]:
        """
        Detect anomalies in an attendance record.

        Args:
            attendance_record: PeopleEventlog instance

        Returns:
            Dict with anomaly detection results:
            {
                'is_anomalous': bool,
                'anomaly_score': float,
                'anomalies_detected': list[dict],
                'risk_level': str,
                'should_block': bool,
            }
        """
        if not self.profile.is_baseline_sufficient:
            logger.debug(f"No baseline for {self.employee.username}, skipping anomaly detection")
            return {
                'is_anomalous': False,
                'anomaly_score': 0.0,
                'anomalies_detected': [],
                'risk_level': 'UNKNOWN',
                'should_block': False,
                'reason': 'Insufficient baseline data',
            }

        anomalies = []

        # Check temporal anomalies
        time_anomalies = self._check_temporal_anomalies(attendance_record)
        anomalies.extend(time_anomalies)

        # Check location anomalies
        location_anomalies = self._check_location_anomalies(attendance_record)
        anomalies.extend(location_anomalies)

        # Check device anomalies
        device_anomalies = self._check_device_anomalies(attendance_record)
        anomalies.extend(device_anomalies)

        # Check day of week anomalies
        day_anomalies = self._check_day_anomalies(attendance_record)
        anomalies.extend(day_anomalies)

        # Calculate overall anomaly score using profile's method
        anomaly_score = self.profile.calculate_anomaly_score(attendance_record)

        # Determine risk level
        if anomaly_score >= self.profile.auto_block_threshold:
            risk_level = 'CRITICAL'
            should_block = True
        elif anomaly_score >= self.profile.anomaly_score_threshold:
            risk_level = 'HIGH'
            should_block = False  # Flag for review but don't auto-block
        elif anomaly_score >= 0.5:
            risk_level = 'MEDIUM'
            should_block = False
        else:
            risk_level = 'LOW'
            should_block = False

        is_anomalous = anomaly_score >= self.profile.anomaly_score_threshold

        if is_anomalous:
            self.profile.anomalies_detected += 1
            self.profile.last_anomaly_at = timezone.now()
            self.profile.save()

        return {
            'is_anomalous': is_anomalous,
            'anomaly_score': round(anomaly_score, 3),
            'anomalies_detected': anomalies,
            'risk_level': risk_level,
            'should_block': should_block,
            'baseline_records': self.profile.training_records_count,
        }

    def _check_temporal_anomalies(self, record) -> List[Dict[str, Any]]:
        """Check for unusual times"""
        anomalies = []

        if record.punchintime and self.profile.typical_checkin_hour is not None:
            hour_diff = abs(record.punchintime.hour - self.profile.typical_checkin_hour)

            if hour_diff > 2:
                anomalies.append({
                    'type': 'unusual_checkin_time',
                    'severity': 'high' if hour_diff > 4 else 'medium',
                    'description': f'Check-in at {record.punchintime.hour}:00 (typical: {self.profile.typical_checkin_hour}:00)',
                    'score': min(hour_diff / 12, 1.0),  # Normalize to 0-1
                })

        return anomalies

    def _check_location_anomalies(self, record) -> List[Dict[str, Any]]:
        """Check for unusual locations"""
        anomalies = []

        if record.startlocation:
            from apps.attendance.services.geospatial_service import GeospatialService
            lon, lat = GeospatialService.extract_coordinates(record.startlocation)

            if not self.profile.is_location_typical(lat, lon):
                anomalies.append({
                    'type': 'unfamiliar_location',
                    'severity': 'high',
                    'description': f'Check-in at unfamiliar location: ({lat:.4f}, {lon:.4f})',
                    'score': 0.8,
                })

        return anomalies

    def _check_device_anomalies(self, record) -> List[Dict[str, Any]]:
        """Check for unusual devices"""
        anomalies = []

        if record.deviceid and not self.profile.is_device_typical(record.deviceid):
            anomalies.append({
                'type': 'new_device',
                'severity': 'medium',
                'description': f'Check-in from new device: {record.deviceid}',
                'score': 0.6,
            })

        return anomalies

    def _check_day_anomalies(self, record) -> List[Dict[str, Any]]:
        """Check for unusual work days"""
        anomalies = []

        if record.datefor and self.profile.typical_work_days:
            day_of_week = record.datefor.isoweekday()

            if day_of_week not in self.profile.typical_work_days:
                anomalies.append({
                    'type': 'unusual_work_day',
                    'severity': 'low',
                    'description': f'Working on atypical day: {record.datefor.strftime("%A")}',
                    'score': 0.3,
                })

        return anomalies

    def update_baseline_incremental(self, new_record) -> None:
        """
        Update baseline incrementally with new record.

        Uses exponential moving average to give more weight to recent behavior.

        Args:
            new_record: New PeopleEventlog to incorporate
        """
        if not self.profile.is_baseline_sufficient:
            # Need full training first
            self.train_baseline()
            return

        # Update check-in time (exponential moving average)
        if new_record.punchintime:
            alpha = 0.1  # Weight for new data
            new_hour = new_record.punchintime.hour

            if self.profile.typical_checkin_hour:
                # Weighted average
                self.profile.typical_checkin_hour = int(
                    alpha * new_hour + (1 - alpha) * self.profile.typical_checkin_hour
                )
            else:
                self.profile.typical_checkin_hour = new_hour

        # Add new location if different from existing
        if new_record.startlocation:
            from apps.attendance.services.geospatial_service import GeospatialService
            lon, lat = GeospatialService.extract_coordinates(new_record.startlocation)

            if not self.profile.is_location_typical(lat, lon):
                # Add to typical locations
                locations = self.profile.typical_locations or []
                locations.append({
                    'lat': lat,
                    'lng': lon,
                    'count': 1,
                    'frequency': 0.0  # Will be recalculated
                })
                self.profile.typical_locations = locations[:15]  # Keep max 15

        # Add new device if not seen before
        if new_record.deviceid and new_record.deviceid not in self.profile.typical_devices:
            devices = self.profile.typical_devices or []
            devices.append(new_record.deviceid)
            self.profile.typical_devices = devices[:5]  # Keep max 5

        self.profile.total_checkins += 1
        self.profile.save()

        logger.debug(f"Updated baseline for {self.employee.username} incrementally")
