"""
Device Failure Predictor - XGBoost Binary Classifier.

Predicts if device will go offline in next 1 hour.
Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Target: 40-60% device failure prevention through proactive maintenance.

Follows .claude/rules.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O

@ontology(
    domain="noc",
    purpose="Predict device failures 1 hour in advance for proactive maintenance",
    ml_model="XGBoost binary classifier",
    features=["offline_duration_last_7_days", "sync_health_score_trend", "time_since_last_event",
              "event_frequency_last_24h", "battery_level", "gps_accuracy_degradation", "device_type_failure_rate"],
    target="will_go_offline (binary 0/1)",
    prediction_window="1 hour",
    criticality="high",
    tags=["noc", "ml", "xgboost", "device-prediction", "predictive-analytics"]
)
"""

import joblib
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Sum

logger = logging.getLogger('noc.predictive.device_failure')

__all__ = ['DeviceFailurePredictor']


class DeviceFailurePredictor:
    """
    Predicts device offline events 1 hour in advance.

    Features (7):
    1. offline_duration_last_7_days - Total minutes offline in last week
    2. sync_health_score_trend - Improving=1, Stable=0, Degrading=-1
    3. time_since_last_event_minutes - Minutes since last attendance event
    4. event_frequency_last_24h - Events per hour in last 24h
    5. battery_level - Battery percentage (0-100, -1 if unknown)
    6. gps_accuracy_degradation - 1 if GPS accuracy worsening
    7. device_type_failure_rate - Historical failure rate for device type
    """

    MODEL_PATH = Path(settings.BASE_DIR) / 'ml_models' / 'device_failure_predictor.pkl'
    PREDICTION_WINDOW_HOURS = 1
    FAILURE_PROBABILITY_THRESHOLD = 0.65  # 65% confidence to create alert

    @classmethod
    def predict_failure(cls, device) -> Tuple[float, Dict[str, Any]]:
        """
        Predict if device will go offline in next 1 hour.

        Args:
            device: Device model instance (from monitoring or attendance)

        Returns:
            (probability, features) - Probability 0.0-1.0 and feature dict

        Raises:
            ValueError: If device data invalid
        """
        features = cls._extract_features(device)

        if not cls.MODEL_PATH.exists():
            logger.warning(f"Device failure model not found at {cls.MODEL_PATH}, using heuristic")
            return cls._heuristic_prediction(features), features

        try:
            model = joblib.load(cls.MODEL_PATH)
            feature_vector = cls._features_to_vector(features)
            probability = model.predict_proba([feature_vector])[0][1]  # Probability of class 1 (failure)
            return float(probability), features
        except (OSError, ValueError) as e:
            logger.error(f"Error loading device failure model: {e}", exc_info=True)
            return cls._heuristic_prediction(features), features

    @classmethod
    def _extract_features(cls, device) -> Dict[str, Any]:
        """Extract 7 features from device."""
        from apps.attendance.models import Attendance
        from apps.monitoring.models import DeviceEvent

        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        twenty_four_hours_ago = now - timedelta(hours=24)

        # Feature 1: Offline duration last 7 days (from device events or attendance gaps)
        offline_duration_last_7_days = cls._calculate_offline_duration(device, seven_days_ago, now)

        # Feature 2: Sync health score trend (from mobile sync data)
        sync_health_score_trend = cls._calculate_sync_trend(device)

        # Feature 3: Time since last event
        last_event_time = cls._get_last_event_time(device)
        time_since_last_event_minutes = (now - last_event_time).total_seconds() / 60.0 if last_event_time else 9999.0

        # Feature 4: Event frequency last 24h
        event_count_24h = cls._count_recent_events(device, twenty_four_hours_ago, now)
        event_frequency_last_24h = event_count_24h / 24.0  # Events per hour

        # Feature 5: Battery level (if available from mobile device)
        battery_level = getattr(device, 'battery_level', -1)

        # Feature 6: GPS accuracy degradation
        gps_accuracy_degradation = cls._is_gps_degrading(device)

        # Feature 7: Device type failure rate (historical)
        device_type_failure_rate = cls._get_device_type_failure_rate(device)

        return {
            'offline_duration_last_7_days': offline_duration_last_7_days,
            'sync_health_score_trend': sync_health_score_trend,
            'time_since_last_event_minutes': time_since_last_event_minutes,
            'event_frequency_last_24h': event_frequency_last_24h,
            'battery_level': battery_level,
            'gps_accuracy_degradation': gps_accuracy_degradation,
            'device_type_failure_rate': device_type_failure_rate,
        }

    @classmethod
    def _features_to_vector(cls, features: Dict[str, Any]) -> list:
        """Convert feature dict to ordered vector for model input."""
        return [
            features['offline_duration_last_7_days'],
            features['sync_health_score_trend'],
            features['time_since_last_event_minutes'],
            features['event_frequency_last_24h'],
            features['battery_level'],
            features['gps_accuracy_degradation'],
            features['device_type_failure_rate'],
        ]

    @classmethod
    def _calculate_offline_duration(cls, device, start_time, end_time) -> float:
        """Calculate total offline minutes in time window."""
        # Simplified: Check if device has offline_duration field or calculate from events
        if hasattr(device, 'offline_duration_minutes'):
            return device.offline_duration_minutes
        # Default: assume 0 if no offline tracking
        return 0.0

    @classmethod
    def _calculate_sync_trend(cls, device) -> int:
        """
        Calculate sync health score trend.

        Returns:
            1 if improving, 0 if stable, -1 if degrading
        """
        if not hasattr(device, 'sync_health_score'):
            return 0

        # Get last 3 sync scores
        recent_scores = getattr(device, 'recent_sync_scores', [])
        if len(recent_scores) < 2:
            return 0

        # Calculate trend
        first_half_avg = sum(recent_scores[:len(recent_scores)//2]) / (len(recent_scores)//2)
        second_half_avg = sum(recent_scores[len(recent_scores)//2:]) / (len(recent_scores) - len(recent_scores)//2)

        if second_half_avg > first_half_avg + 5:
            return 1  # Improving
        elif second_half_avg < first_half_avg - 5:
            return -1  # Degrading
        return 0  # Stable

    @classmethod
    def _get_last_event_time(cls, device):
        """Get timestamp of last event from device."""
        if hasattr(device, 'last_event_time'):
            return device.last_event_time
        if hasattr(device, 'last_sync'):
            return device.last_sync
        return None

    @classmethod
    def _count_recent_events(cls, device, start_time, end_time) -> int:
        """Count events in time window."""
        # Simplified: Check if device has event_count field
        if hasattr(device, 'recent_event_count'):
            return device.recent_event_count
        return 0

    @classmethod
    def _is_gps_degrading(cls, device) -> int:
        """Check if GPS accuracy is worsening. Returns 1 if degrading, 0 otherwise."""
        if not hasattr(device, 'gps_accuracy'):
            return 0

        recent_accuracy = getattr(device, 'recent_gps_accuracy', [])
        if len(recent_accuracy) < 2:
            return 0

        # If recent accuracy is worse than historical average
        avg_accuracy = sum(recent_accuracy) / len(recent_accuracy)
        latest_accuracy = recent_accuracy[-1]

        return 1 if latest_accuracy > avg_accuracy * 1.5 else 0  # Higher accuracy value = worse

    @classmethod
    def _get_device_type_failure_rate(cls, device) -> float:
        """Get historical failure rate for device type."""
        # Simplified: Would query historical data
        # Default failure rates by device type
        device_type = getattr(device, 'device_type', 'unknown')
        failure_rates = {
            'mobile': 0.05,  # 5% failure rate
            'tablet': 0.03,
            'biometric': 0.08,
            'gps_tracker': 0.10,
            'unknown': 0.05,
        }
        return failure_rates.get(device_type.lower(), 0.05)

    @classmethod
    def _heuristic_prediction(cls, features: Dict[str, Any]) -> float:
        """
        Heuristic prediction when ML model unavailable.

        Logic:
        - Long offline duration + degrading trend: High risk (0.8)
        - Low battery + no recent events: Medium-high risk (0.7)
        - GPS degrading + sync degrading: Medium risk (0.6)
        - Otherwise: Low risk (0.2)
        """
        offline_duration = features['offline_duration_last_7_days']
        sync_trend = features['sync_health_score_trend']
        time_since_event = features['time_since_last_event_minutes']
        battery = features['battery_level']
        gps_degrading = features['gps_accuracy_degradation']

        # High offline duration + degrading sync
        if offline_duration > 500 and sync_trend == -1:  # >500 mins offline in 7 days
            return 0.8

        # Low battery + no recent activity
        if battery > 0 and battery < 20 and time_since_event > 120:  # <20% battery, >2h idle
            return 0.7

        # GPS and sync both degrading
        if gps_degrading and sync_trend == -1:
            return 0.6

        # Long time since last event
        if time_since_event > 180:  # >3 hours idle
            return 0.5

        return 0.2  # Low risk

    @classmethod
    def should_alert(cls, probability: float) -> bool:
        """Check if probability exceeds threshold for alerting."""
        return probability >= cls.FAILURE_PROBABILITY_THRESHOLD
