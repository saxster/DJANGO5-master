"""
Activity Monitoring Engine

Advanced movement and activity monitoring with anomaly detection.
Detects stationary periods, location violations, and unusual activity patterns.

Follows .claude/rules.md:
- Rule #13: Use constants instead of magic numbers
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db.models import Q, Avg, Count
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance

from apps.activity.models import DeviceEventlog
from apps.attendance.models import PeopleEventlog
from apps.monitoring.models import (
    Alert, MonitoringMetric, UserActivityPattern
)
from apps.monitoring.services.alert_service import AlertService
from apps.core.constants.spatial_constants import EARTH_RADIUS_M, METERS_PER_DEGREE_LAT

logger = logging.getLogger(__name__)


class ActivityMonitor:
    """
    Intelligent activity and movement monitoring system.

    Features:
    - Movement pattern analysis
    - Stationary period detection
    - Location violation monitoring
    - Step count anomaly detection
    - Geofence compliance checking
    - Activity trend analysis
    """

    def __init__(self):
        self.alert_service = AlertService()

        # Movement thresholds
        self.MIN_STEPS_PER_HOUR = 100        # Minimum expected steps per hour
        self.STATIONARY_THRESHOLD_MINUTES = 30  # Alert if no movement for 30+ minutes
        self.EXCESSIVE_MOVEMENT_KM = 5       # Alert if >5km movement in stationary shift

        # Location thresholds
        self.GEOFENCE_BUFFER_METERS = 100    # Buffer zone around assigned areas
        self.LOCATION_ACCURACY_THRESHOLD = 50  # Minimum GPS accuracy in meters

        # Pattern analysis
        self.PATTERN_LEARNING_DAYS = 30      # Days of data for pattern learning
        self.ANOMALY_SENSITIVITY = 0.3       # Sensitivity for anomaly detection

    def monitor_activity_status(self, user_id: int, device_id: str) -> Dict:
        """
        Comprehensive activity monitoring for a specific user/device.

        Returns activity analysis and any triggered alerts.
        """
        try:
            logger.info(f"Monitoring activity for user {user_id}, device {device_id}")

            # Get current activity data
            current_data = self._get_current_activity_data(user_id, device_id)
            if not current_data:
                logger.warning(f"No activity data found for user {user_id}, device {device_id}")
                return {'status': 'no_data', 'alerts': []}

            # Get historical activity data
            historical_data = self._get_historical_activity_data(user_id, device_id, hours=8)

            # Get user context for intelligent monitoring
            user_context = self._get_user_activity_context(user_id)

            # Calculate activity metrics
            metrics = self._calculate_activity_metrics(current_data, historical_data, user_context)

            # Detect movement patterns and anomalies
            patterns = self._analyze_movement_patterns(historical_data, user_context)

            # Check location compliance
            location_status = self._check_location_compliance(user_id, current_data, user_context)

            # Evaluate activity alerts
            alerts = self._evaluate_activity_alerts(
                user_id, device_id, current_data, metrics, patterns, location_status, user_context
            )

            # Update activity monitoring metrics
            self._update_activity_metrics(user_id, device_id, metrics, patterns)

            # Update user activity patterns
            self._update_user_patterns(user_id, current_data, metrics)

            return {
                'status': 'success',
                'current_activity': current_data,
                'metrics': metrics,
                'patterns': patterns,
                'location_status': location_status,
                'alerts': alerts,
                'recommendations': self._generate_activity_recommendations(metrics, patterns, user_context)
            }

        except Exception as e:
            logger.error(f"Error monitoring activity for user {user_id}: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e), 'alerts': []}

    def _get_current_activity_data(self, user_id: int, device_id: str) -> Optional[Dict]:
        """Get the most recent activity data"""
        try:
            # Get latest device event log
            latest_device_event = DeviceEventlog.objects.filter(
                deviceid=device_id
            ).order_by('-receivedon').first()

            # Get latest attendance event
            latest_attendance = PeopleEventlog.objects.filter(
                people_id=user_id
            ).order_by('-createdon').first()

            if not latest_device_event:
                return None

            # Extract step count
            step_count = self._safe_int(latest_device_event.stepcount) if latest_device_event.stepcount != 'No Steps' else 0

            # Extract location data
            location_data = None
            if latest_device_event.gpslocation:
                location_data = {
                    'lat': latest_device_event.gpslocation.y,
                    'lon': latest_device_event.gpslocation.x,
                    'accuracy': self._safe_float(latest_device_event.accuracy),
                    'timestamp': latest_device_event.receivedon
                }

            return {
                'user_id': user_id,
                'device_id': device_id,
                'step_count': step_count,
                'location': location_data,
                'timestamp': latest_device_event.receivedon,
                'location_enabled': latest_device_event.locationserviceenabled,
                'location_mocked': latest_device_event.islocationmocked,
                'attendance_data': {
                    'last_event': latest_attendance.createdon if latest_attendance else None,
                    'event_type': getattr(latest_attendance, 'eventtype', None),
                    'site': getattr(latest_attendance, 'bu', None)
                }
            }

        except Exception as e:
            logger.error(f"Error getting current activity data: {str(e)}")
            return None

    def _get_historical_activity_data(self, user_id: int, device_id: str, hours: int = 8) -> List[Dict]:
        """Get historical activity data for analysis"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            # Get device events with location and step data
            device_events = DeviceEventlog.objects.filter(
                deviceid=device_id,
                receivedon__gte=cutoff_time
            ).exclude(
                Q(stepcount='No Steps') | Q(gpslocation__isnull=True)
            ).order_by('receivedon')

            historical_data = []
            for event in device_events:
                step_count = self._safe_int(event.stepcount)
                if event.gpslocation and step_count >= 0:
                    historical_data.append({
                        'timestamp': event.receivedon,
                        'step_count': step_count,
                        'location': {
                            'lat': event.gpslocation.y,
                            'lon': event.gpslocation.x,
                            'accuracy': self._safe_float(event.accuracy)
                        },
                        'location_mocked': event.islocationmocked,
                        'device_info': {
                            'battery': self._safe_int(event.batterylevel),
                            'signal': event.signalstrength
                        }
                    })

            return historical_data

        except Exception as e:
            logger.error(f"Error getting historical activity data: {str(e)}")
            return []

    def _get_user_activity_context(self, user_id: int) -> Dict:
        """Get user context for activity monitoring"""
        try:
            from apps.peoples.models import People

            user = People.objects.get(id=user_id)

            # Get user's activity pattern if available
            activity_pattern = getattr(user, 'activity_pattern', None)

            # Get current shift information
            current_time = timezone.now()
            shift_info = self._get_shift_information(user, current_time)

            # Get assigned work areas/sites
            work_sites = self._get_user_work_sites(user)

            return {
                'user_id': user_id,
                'user_name': user.peoplename,
                'activity_pattern': activity_pattern,
                'shift_info': shift_info,
                'work_sites': work_sites,
                'current_time': current_time,
                'work_schedule': {
                    'start_hour': 9,
                    'end_hour': 17,
                    'break_hours': [12, 13, 15]  # Lunch and tea breaks
                }
            }

        except Exception as e:
            logger.error(f"Error getting user activity context: {str(e)}")
            return {'user_id': user_id}

    def _calculate_activity_metrics(self, current_data: Dict, historical_data: List[Dict], user_context: Dict) -> Dict:
        """Calculate comprehensive activity metrics"""
        metrics = {
            'current_step_count': current_data.get('step_count', 0),
            'steps_last_hour': 0,
            'movement_distance_km': 0,
            'time_since_last_movement': None,
            'stationary_duration_minutes': 0,
            'average_steps_per_hour': 0,
            'location_changes_count': 0,
            'activity_level_score': 0,
            'movement_consistency_score': 0
        }

        if not historical_data:
            return metrics

        try:
            current_time = timezone.now()

            # Calculate steps in last hour
            hour_ago = current_time - timedelta(hours=1)
            recent_data = [d for d in historical_data if d['timestamp'] >= hour_ago]

            if recent_data:
                step_counts = [d['step_count'] for d in recent_data]
                metrics['steps_last_hour'] = max(step_counts) - min(step_counts) if len(step_counts) > 1 else step_counts[0]

            # Calculate movement distance
            if len(historical_data) >= 2:
                total_distance = 0
                for i in range(1, len(historical_data)):
                    distance = self._calculate_distance(
                        historical_data[i-1]['location'],
                        historical_data[i]['location']
                    )
                    total_distance += distance

                metrics['movement_distance_km'] = total_distance / 1000  # Convert to km

            # Detect stationary periods
            stationary_info = self._detect_stationary_periods(historical_data)
            metrics['stationary_duration_minutes'] = stationary_info['current_stationary_minutes']
            metrics['time_since_last_movement'] = stationary_info['time_since_movement']

            # Calculate activity level
            metrics['activity_level_score'] = self._calculate_activity_level(historical_data, user_context)

            # Calculate movement consistency
            metrics['movement_consistency_score'] = self._calculate_movement_consistency(historical_data)

            # Calculate average steps per hour
            if len(historical_data) >= 2:
                time_span_hours = (historical_data[-1]['timestamp'] - historical_data[0]['timestamp']).total_seconds() / 3600
                if time_span_hours > 0:
                    total_steps = max([d['step_count'] for d in historical_data]) - min([d['step_count'] for d in historical_data])
                    metrics['average_steps_per_hour'] = total_steps / time_span_hours

            # Count location changes
            metrics['location_changes_count'] = self._count_location_changes(historical_data)

        except Exception as e:
            logger.error(f"Error calculating activity metrics: {str(e)}")

        return metrics

    def _analyze_movement_patterns(self, historical_data: List[Dict], user_context: Dict) -> Dict:
        """Analyze movement patterns and detect anomalies"""
        patterns = {
            'pattern_type': 'unknown',
            'is_normal_pattern': True,
            'anomalies_detected': [],
            'pattern_confidence': 0,
            'movement_zones': [],
            'typical_routes': []
        }

        if len(historical_data) < 10:
            return patterns

        try:
            # Analyze movement zones
            movement_zones = self._identify_movement_zones(historical_data)
            patterns['movement_zones'] = movement_zones

            # Detect pattern type
            pattern_type = self._classify_movement_pattern(historical_data, user_context)
            patterns['pattern_type'] = pattern_type

            # Detect anomalies
            anomalies = self._detect_movement_anomalies(historical_data, user_context)
            patterns['anomalies_detected'] = anomalies
            patterns['is_normal_pattern'] = len(anomalies) == 0

            # Calculate pattern confidence
            patterns['pattern_confidence'] = self._calculate_pattern_confidence(historical_data, user_context)

        except Exception as e:
            logger.error(f"Error analyzing movement patterns: {str(e)}")

        return patterns

    def _check_location_compliance(self, user_id: int, current_data: Dict, user_context: Dict) -> Dict:
        """Check location compliance with assigned work areas"""
        compliance = {
            'is_compliant': True,
            'violations': [],
            'distance_from_nearest_site': None,
            'assigned_sites': [],
            'current_location_valid': False
        }

        try:
            current_location = current_data.get('location')
            if not current_location:
                compliance['violations'].append('no_location_data')
                return compliance

            # Check location accuracy
            accuracy = current_location.get('accuracy', 999)
            if accuracy > self.LOCATION_ACCURACY_THRESHOLD:
                compliance['violations'].append('poor_gps_accuracy')

            # Check for location spoofing
            if current_data.get('location_mocked', False):
                compliance['violations'].append('location_spoofing_detected')
                compliance['is_compliant'] = False

            # Get assigned work sites
            work_sites = user_context.get('work_sites', [])
            compliance['assigned_sites'] = work_sites

            if work_sites:
                # Check proximity to assigned sites
                min_distance = float('inf')
                current_point = Point(current_location['lon'], current_location['lat'])

                for site in work_sites:
                    site_location = site.get('location')
                    if site_location:
                        site_point = Point(site_location['lon'], site_location['lat'])
                        distance = current_point.distance(site_point) * METERS_PER_DEGREE_LAT  # Convert degrees to meters

                        min_distance = min(min_distance, distance)

                compliance['distance_from_nearest_site'] = min_distance

                # Check if within acceptable range
                if min_distance > self.GEOFENCE_BUFFER_METERS:
                    compliance['violations'].append('outside_assigned_area')
                    compliance['is_compliant'] = False
                else:
                    compliance['current_location_valid'] = True

        except Exception as e:
            logger.error(f"Error checking location compliance: {str(e)}")
            compliance['violations'].append('location_check_error')

        return compliance

    def _evaluate_activity_alerts(self, user_id: int, device_id: str, current_data: Dict,
                                 metrics: Dict, patterns: Dict, location_status: Dict, user_context: Dict) -> List[Dict]:
        """Evaluate activity conditions and trigger appropriate alerts"""
        alerts = []

        try:
            # No movement alert
            stationary_minutes = metrics.get('stationary_duration_minutes', 0)
            if stationary_minutes >= self.STATIONARY_THRESHOLD_MINUTES:
                # Check if it's during work hours and not a break time
                if self._is_work_time(user_context) and not self._is_break_time(user_context):
                    alert = self._create_activity_alert(
                        user_id, device_id, 'NO_MOVEMENT',
                        f"No movement detected for {stationary_minutes} minutes",
                        'HIGH', current_data, metrics, patterns
                    )
                    alerts.append(alert)

            # Low activity alert
            steps_last_hour = metrics.get('steps_last_hour', 0)
            if steps_last_hour < self.MIN_STEPS_PER_HOUR and self._is_work_time(user_context):
                alert = self._create_activity_alert(
                    user_id, device_id, 'LOW_ACTIVITY',
                    f"Low activity: only {steps_last_hour} steps in last hour",
                    'WARNING', current_data, metrics, patterns
                )
                alerts.append(alert)

            # Excessive movement alert (for stationary roles)
            movement_distance = metrics.get('movement_distance_km', 0)
            if movement_distance > self.EXCESSIVE_MOVEMENT_KM:
                alert = self._create_activity_alert(
                    user_id, device_id, 'EXCESSIVE_MOVEMENT',
                    f"Excessive movement: {movement_distance:.1f}km during shift",
                    'WARNING', current_data, metrics, patterns
                )
                alerts.append(alert)

            # Location violation alerts
            if not location_status['is_compliant']:
                for violation in location_status['violations']:
                    if violation == 'outside_assigned_area':
                        alert = self._create_activity_alert(
                            user_id, device_id, 'LOCATION_VIOLATION',
                            f"Outside assigned work area by {location_status['distance_from_nearest_site']:.0f}m",
                            'HIGH', current_data, metrics, patterns
                        )
                        alerts.append(alert)
                    elif violation == 'location_spoofing_detected':
                        alert = self._create_activity_alert(
                            user_id, device_id, 'LOCATION_SPOOFING',
                            "GPS spoofing detected - location may be falsified",
                            'CRITICAL', current_data, metrics, patterns
                        )
                        alerts.append(alert)

            # Pattern anomaly alerts
            if not patterns['is_normal_pattern']:
                for anomaly in patterns['anomalies_detected']:
                    alert = self._create_activity_alert(
                        user_id, device_id, 'ACTIVITY_ANOMALY',
                        f"Unusual activity pattern detected: {anomaly}",
                        'WARNING', current_data, metrics, patterns
                    )
                    alerts.append(alert)

        except Exception as e:
            logger.error(f"Error evaluating activity alerts: {str(e)}")

        return [alert for alert in alerts if alert is not None]

    def _create_activity_alert(self, user_id: int, device_id: str, alert_type: str,
                              description: str, severity: str, current_data: Dict,
                              metrics: Dict, patterns: Dict) -> Optional[Dict]:
        """Create an activity-related alert"""
        try:
            alert_data = {
                'user_id': user_id,
                'device_id': device_id,
                'alert_type': alert_type,
                'severity': severity,
                'title': f"Activity Alert: {alert_type.replace('_', ' ').title()}",
                'description': description,
                'alert_data': {
                    'current_step_count': current_data.get('step_count', 0),
                    'stationary_minutes': metrics.get('stationary_duration_minutes', 0),
                    'movement_distance_km': metrics.get('movement_distance_km', 0),
                    'activity_level_score': metrics.get('activity_level_score', 0),
                    'location': current_data.get('location'),
                    'timestamp': timezone.now().isoformat()
                },
                'context_data': {
                    'activity_metrics': metrics,
                    'movement_patterns': patterns,
                    'is_work_time': self._is_work_time({'current_time': timezone.now()})
                }
            }

            # Create alert through alert service
            alert = self.alert_service.create_alert(alert_data)

            if alert:
                return {
                    'alert_id': str(alert.alert_id),
                    'type': alert_type,
                    'severity': severity,
                    'description': description,
                    'created_at': alert.triggered_at.isoformat()
                }

        except Exception as e:
            logger.error(f"Error creating activity alert: {str(e)}")

        return None

    # Helper methods for activity analysis

    def _safe_int(self, value, default=0):
        """Safely convert value to integer"""
        if value == 'NA' or value is None or value == 'No Steps':
            return default
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default

    def _safe_float(self, value, default=0.0):
        """Safely convert value to float"""
        if value == 'NA' or value is None or value == '-':
            return default
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return default

    def _calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """
        Calculate distance between two locations in meters.

        Note: Consider using apps.core.utils_new.spatial_math.haversine_distance()
        for better performance (LRU cached) and consistency.
        """
        try:
            from math import radians, cos, sin, asin, sqrt

            # Haversine formula
            lat1, lon1 = radians(loc1['lat']), radians(loc1['lon'])
            lat2, lon2 = radians(loc2['lat']), radians(loc2['lon'])

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            return 2 * asin(sqrt(a)) * EARTH_RADIUS_M  # Use constant instead of magic number

        except Exception as e:
            logger.error(f"Error calculating distance: {str(e)}")
            return 0

    def _detect_stationary_periods(self, historical_data: List[Dict]) -> Dict:
        """Detect stationary periods in movement data"""
        try:
            if len(historical_data) < 2:
                return {'current_stationary_minutes': 0, 'time_since_movement': None}

            current_time = timezone.now()
            last_movement_time = None
            movement_threshold = 10  # meters

            # Look for last significant movement
            for i in range(len(historical_data) - 1, 0, -1):
                distance = self._calculate_distance(
                    historical_data[i]['location'],
                    historical_data[i-1]['location']
                )

                if distance > movement_threshold:
                    last_movement_time = historical_data[i]['timestamp']
                    break

            if last_movement_time:
                stationary_minutes = (current_time - last_movement_time).total_seconds() / 60
                return {
                    'current_stationary_minutes': int(stationary_minutes),
                    'time_since_movement': last_movement_time
                }

            # If no movement detected in available data
            data_span_minutes = (historical_data[-1]['timestamp'] - historical_data[0]['timestamp']).total_seconds() / 60
            return {
                'current_stationary_minutes': int(data_span_minutes),
                'time_since_movement': historical_data[0]['timestamp']
            }

        except Exception as e:
            logger.error(f"Error detecting stationary periods: {str(e)}")
            return {'current_stationary_minutes': 0, 'time_since_movement': None}

    def _calculate_activity_level(self, historical_data: List[Dict], user_context: Dict) -> int:
        """Calculate activity level score (0-100)"""
        try:
            if not historical_data:
                return 0

            # Calculate metrics
            step_counts = [d['step_count'] for d in historical_data]
            total_steps = max(step_counts) - min(step_counts) if len(step_counts) > 1 else step_counts[0]

            # Calculate time span
            time_span_hours = (historical_data[-1]['timestamp'] - historical_data[0]['timestamp']).total_seconds() / 3600

            if time_span_hours <= 0:
                return 0

            # Steps per hour
            steps_per_hour = total_steps / time_span_hours

            # Movement distance
            total_distance = 0
            for i in range(1, len(historical_data)):
                distance = self._calculate_distance(
                    historical_data[i-1]['location'],
                    historical_data[i]['location']
                )
                total_distance += distance

            distance_per_hour = total_distance / time_span_hours / 1000  # km per hour

            # Calculate score (normalize to 0-100)
            step_score = min(100, (steps_per_hour / 500) * 100)  # 500 steps/hour = 100%
            distance_score = min(100, (distance_per_hour / 2) * 100)  # 2km/hour = 100%

            # Weighted average
            activity_score = (step_score * 0.7) + (distance_score * 0.3)

            return int(activity_score)

        except Exception as e:
            logger.error(f"Error calculating activity level: {str(e)}")
            return 0

    def _calculate_movement_consistency(self, historical_data: List[Dict]) -> int:
        """Calculate movement consistency score"""
        try:
            if len(historical_data) < 5:
                return 50

            # Calculate step intervals
            step_intervals = []
            for i in range(1, len(historical_data)):
                time_diff = (historical_data[i]['timestamp'] - historical_data[i-1]['timestamp']).total_seconds() / 60
                step_diff = historical_data[i]['step_count'] - historical_data[i-1]['step_count']

                if time_diff > 0:
                    step_intervals.append(step_diff / time_diff)  # steps per minute

            if not step_intervals:
                return 50

            # Calculate consistency (lower standard deviation = higher consistency)
            std_dev = np.std(step_intervals)
            mean_rate = np.mean(step_intervals)

            if mean_rate > 0:
                consistency_score = max(0, min(100, 100 - (std_dev / mean_rate * 100)))
            else:
                consistency_score = 50

            return int(consistency_score)

        except Exception as e:
            logger.error(f"Error calculating movement consistency: {str(e)}")
            return 50

    def _count_location_changes(self, historical_data: List[Dict]) -> int:
        """Count significant location changes"""
        try:
            if len(historical_data) < 2:
                return 0

            change_count = 0
            change_threshold = 50  # meters

            for i in range(1, len(historical_data)):
                distance = self._calculate_distance(
                    historical_data[i-1]['location'],
                    historical_data[i]['location']
                )

                if distance > change_threshold:
                    change_count += 1

            return change_count

        except Exception as e:
            logger.error(f"Error counting location changes: {str(e)}")
            return 0

    def _identify_movement_zones(self, historical_data: List[Dict]) -> List[Dict]:
        """Identify zones where user spends time"""
        # Implementation would cluster locations to identify zones
        # Placeholder for now
        return []

    def _classify_movement_pattern(self, historical_data: List[Dict], user_context: Dict) -> str:
        """Classify the type of movement pattern"""
        try:
            total_distance = sum(
                self._calculate_distance(historical_data[i-1]['location'], historical_data[i]['location'])
                for i in range(1, len(historical_data))
            ) / 1000  # Convert to km

            location_changes = self._count_location_changes(historical_data)

            if total_distance < 0.1 and location_changes < 3:
                return 'stationary'
            elif total_distance < 1 and location_changes < 10:
                return 'limited_movement'
            elif total_distance < 5:
                return 'moderate_movement'
            else:
                return 'high_movement'

        except Exception as e:
            logger.error(f"Error classifying movement pattern: {str(e)}")
            return 'unknown'

    def _detect_movement_anomalies(self, historical_data: List[Dict], user_context: Dict) -> List[str]:
        """Detect anomalies in movement patterns"""
        anomalies = []

        try:
            # Get user's typical patterns
            activity_pattern = user_context.get('activity_pattern')
            if not activity_pattern:
                return anomalies

            # Check step count anomaly
            current_steps_per_hour = self._calculate_current_steps_per_hour(historical_data)
            typical_steps = getattr(activity_pattern, 'avg_steps_per_hour', 200)

            if abs(current_steps_per_hour - typical_steps) > (typical_steps * 0.5):
                anomalies.append('unusual_step_count')

            # Check movement distance anomaly
            current_distance = sum(
                self._calculate_distance(historical_data[i-1]['location'], historical_data[i]['location'])
                for i in range(1, len(historical_data))
            ) / 1000

            # If significantly more movement than usual
            if current_distance > 3:  # More than 3km in a few hours
                anomalies.append('excessive_movement')

        except Exception as e:
            logger.error(f"Error detecting movement anomalies: {str(e)}")

        return anomalies

    def _calculate_current_steps_per_hour(self, historical_data: List[Dict]) -> float:
        """Calculate current steps per hour from historical data"""
        try:
            if len(historical_data) < 2:
                return 0

            time_span_hours = (historical_data[-1]['timestamp'] - historical_data[0]['timestamp']).total_seconds() / 3600
            if time_span_hours <= 0:
                return 0

            step_counts = [d['step_count'] for d in historical_data]
            total_steps = max(step_counts) - min(step_counts)

            return total_steps / time_span_hours

        except Exception as e:
            logger.error(f"Error calculating current steps per hour: {str(e)}")
            return 0

    def _calculate_pattern_confidence(self, historical_data: List[Dict], user_context: Dict) -> float:
        """Calculate confidence in pattern analysis"""
        try:
            # Base confidence on amount of data
            data_confidence = min(1.0, len(historical_data) / 20)

            # Adjust based on data quality
            locations_with_good_accuracy = sum(
                1 for d in historical_data
                if d['location'].get('accuracy', 999) < self.LOCATION_ACCURACY_THRESHOLD
            )

            accuracy_confidence = locations_with_good_accuracy / len(historical_data) if historical_data else 0

            # Combined confidence
            return (data_confidence + accuracy_confidence) / 2

        except Exception as e:
            logger.error(f"Error calculating pattern confidence: {str(e)}")
            return 0

    def _get_shift_information(self, user, current_time):
        """Get current shift information"""
        # Placeholder implementation
        return {
            'shift_start': current_time.replace(hour=9, minute=0),
            'shift_end': current_time.replace(hour=17, minute=0),
            'is_night_shift': False,
            'break_times': [
                (current_time.replace(hour=12, minute=0), current_time.replace(hour=13, minute=0)),
                (current_time.replace(hour=15, minute=0), current_time.replace(hour=15, minute=15))
            ]
        }

    def _get_user_work_sites(self, user):
        """Get user's assigned work sites"""
        # Placeholder implementation
        return []

    def _is_work_time(self, user_context: Dict) -> bool:
        """Check if current time is within work hours"""
        try:
            current_time = user_context.get('current_time', timezone.now())
            schedule = user_context.get('work_schedule', {})

            start_hour = schedule.get('start_hour', 9)
            end_hour = schedule.get('end_hour', 17)

            return start_hour <= current_time.hour < end_hour

        except Exception as e:
            logger.error(f"Error checking work time: {str(e)}")
            return True  # Default to work time

    def _is_break_time(self, user_context: Dict) -> bool:
        """Check if current time is within break hours"""
        try:
            current_time = user_context.get('current_time', timezone.now())
            schedule = user_context.get('work_schedule', {})
            break_hours = schedule.get('break_hours', [])

            return current_time.hour in break_hours

        except Exception as e:
            logger.error(f"Error checking break time: {str(e)}")
            return False

    def _update_activity_metrics(self, user_id: int, device_id: str, metrics: Dict, patterns: Dict):
        """Update activity monitoring metrics"""
        try:
            metric_data = [
                ('STEP_COUNT', metrics['current_step_count'], 'steps'),
                ('MOVEMENT_DISTANCE', metrics['movement_distance_km'], 'km'),
                ('ACTIVITY_LEVEL_SCORE', metrics['activity_level_score'], 'score'),
                ('STATIONARY_DURATION', metrics['stationary_duration_minutes'], 'minutes'),
            ]

            for metric_type, value, unit in metric_data:
                MonitoringMetric.objects.create(
                    user_id=user_id,
                    device_id=device_id,
                    metric_type=metric_type,
                    value=value,
                    unit=unit,
                    context={
                        'pattern_type': patterns.get('pattern_type', 'unknown'),
                        'pattern_confidence': patterns.get('pattern_confidence', 0)
                    }
                )

        except Exception as e:
            logger.error(f"Error updating activity metrics: {str(e)}")

    def _update_user_patterns(self, user_id: int, current_data: Dict, metrics: Dict):
        """Update user activity patterns for learning"""
        try:
            pattern, created = UserActivityPattern.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'total_observations': 0,
                    'avg_steps_per_hour': 0,
                    'typical_movement_variance': 0
                }
            )

            # Update pattern with new observation
            pattern.total_observations += 1
            current_steps_per_hour = metrics.get('average_steps_per_hour', 0)

            # Running average update
            if pattern.total_observations == 1:
                pattern.avg_steps_per_hour = current_steps_per_hour
            else:
                pattern.avg_steps_per_hour = (
                    (pattern.avg_steps_per_hour * (pattern.total_observations - 1) + current_steps_per_hour)
                    / pattern.total_observations
                )

            # Update confidence
            pattern.pattern_confidence = min(1.0, pattern.total_observations / 100)

            pattern.save()

        except Exception as e:
            logger.error(f"Error updating user patterns: {str(e)}")

    def _generate_activity_recommendations(self, metrics: Dict, patterns: Dict, user_context: Dict) -> List[str]:
        """Generate actionable recommendations based on activity analysis"""
        recommendations = []

        try:
            # Stationary recommendations
            stationary_minutes = metrics.get('stationary_duration_minutes', 0)
            if stationary_minutes > 30:
                recommendations.append("Take a short walk to maintain activity levels")

            # Low activity recommendations
            steps_per_hour = metrics.get('average_steps_per_hour', 0)
            if steps_per_hour < self.MIN_STEPS_PER_HOUR:
                recommendations.append("Increase movement - aim for at least 100 steps per hour")

            # Pattern-based recommendations
            if not patterns.get('is_normal_pattern', True):
                recommendations.append("Activity pattern differs from normal - check if additional tasks assigned")

            # Location-based recommendations
            activity_level = metrics.get('activity_level_score', 0)
            if activity_level < 30:
                recommendations.append("Consider checking assigned patrol routes or tasks")

        except Exception as e:
            logger.error(f"Error generating activity recommendations: {str(e)}")

        return recommendations