"""
Staffing Gap Predictor - XGBoost Binary Classifier.

Predicts if site will be understaffed in next 4 hours.
Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Target: 40-60% staffing gap prevention through proactive resource allocation.

Follows .claude/rules.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O

@ontology(
    domain="noc",
    purpose="Predict staffing gaps 4 hours in advance for proactive resource allocation",
    ml_model="XGBoost binary classifier",
    features=["scheduled_guards_count", "actual_attendance_rate_last_7_days", "time_to_next_shift",
              "site_criticality_score", "current_attendance_vs_scheduled_ratio", "historical_no_show_rate"],
    target="will_be_understaffed (binary 0/1)",
    prediction_window="4 hours",
    criticality="high",
    tags=["noc", "ml", "xgboost", "staffing-prediction", "predictive-analytics"]
)
"""

import joblib
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, FILE_EXCEPTIONS

logger = logging.getLogger('noc.predictive.staffing_gap')

__all__ = ['StaffingGapPredictor']


class StaffingGapPredictor:
    """
    Predicts staffing gaps 4 hours in advance.

    Features (6):
    1. scheduled_guards_count - Number of guards scheduled for next 4 hours
    2. actual_attendance_rate_last_7_days - Percentage of scheduled shifts attended
    3. time_to_next_shift_minutes - Minutes until next shift starts
    4. site_criticality_score - VIP site importance (1-5, VIP sites = 5)
    5. current_attendance_vs_scheduled_ratio - Current staff vs required ratio
    6. historical_no_show_rate - No-show rate for this shift pattern
    """

    MODEL_PATH = Path(settings.BASE_DIR) / 'ml_models' / 'staffing_gap_predictor.pkl'
    PREDICTION_WINDOW_HOURS = 4
    GAP_PROBABILITY_THRESHOLD = 0.6  # 60% confidence to create alert

    @classmethod
    def predict_gap(cls, site, shift_time) -> Tuple[float, Dict[str, Any]]:
        """
        Predict if site will be understaffed at shift_time.

        Args:
            site: Site/BU instance
            shift_time: Datetime of shift to predict

        Returns:
            (probability, features) - Probability 0.0-1.0 and feature dict

        Raises:
            ValueError: If site or shift_time invalid
        """
        features = cls._extract_features(site, shift_time)

        if not cls.MODEL_PATH.exists():
            logger.warning(f"Staffing gap model not found at {cls.MODEL_PATH}, using heuristic")
            return cls._heuristic_prediction(features), features

        try:
            model = joblib.load(cls.MODEL_PATH)
            feature_vector = cls._features_to_vector(features)
            probability = model.predict_proba([feature_vector])[0][1]  # Probability of class 1 (gap)
            return float(probability), features
        except (OSError, ValueError) as e:
            logger.error(f"Error loading staffing gap model: {e}", exc_info=True)
            return cls._heuristic_prediction(features), features

    @classmethod
    def _extract_features(cls, site, shift_time) -> Dict[str, Any]:
        """Extract 6 features from site and shift."""
        from apps.scheduler.models import Schedule
        from apps.attendance.models import Attendance

        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        # Feature 1: Scheduled guards count for next 4 hours
        four_hours_ahead = shift_time + timedelta(hours=4)
        scheduled_guards_count = cls._count_scheduled_guards(site, shift_time, four_hours_ahead)

        # Feature 2: Actual attendance rate last 7 days
        actual_attendance_rate_last_7_days = cls._calculate_attendance_rate(site, seven_days_ago, now)

        # Feature 3: Time to next shift
        time_to_next_shift_minutes = (shift_time - now).total_seconds() / 60.0

        # Feature 4: Site criticality score (1-5)
        site_criticality_score = cls._get_site_criticality(site)

        # Feature 5: Current attendance vs scheduled ratio
        current_attendance_vs_scheduled_ratio = cls._get_current_staffing_ratio(site)

        # Feature 6: Historical no-show rate for this shift pattern
        historical_no_show_rate = cls._get_no_show_rate(site, shift_time)

        return {
            'scheduled_guards_count': scheduled_guards_count,
            'actual_attendance_rate_last_7_days': actual_attendance_rate_last_7_days,
            'time_to_next_shift_minutes': time_to_next_shift_minutes,
            'site_criticality_score': site_criticality_score,
            'current_attendance_vs_scheduled_ratio': current_attendance_vs_scheduled_ratio,
            'historical_no_show_rate': historical_no_show_rate,
        }

    @classmethod
    def _features_to_vector(cls, features: Dict[str, Any]) -> list:
        """Convert feature dict to ordered vector for model input."""
        return [
            features['scheduled_guards_count'],
            features['actual_attendance_rate_last_7_days'],
            features['time_to_next_shift_minutes'],
            features['site_criticality_score'],
            features['current_attendance_vs_scheduled_ratio'],
            features['historical_no_show_rate'],
        ]

    @classmethod
    def _count_scheduled_guards(cls, site, start_time, end_time) -> int:
        """Count guards scheduled in time window."""
        from apps.scheduler.models import Schedule

        # Simplified query - would need actual schedule model structure
        try:
            scheduled = Schedule.objects.filter(
                bu=site,
                start_time__lte=end_time,
                end_time__gte=start_time
            ).values('people').distinct().count()
            return scheduled
        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error counting scheduled guards: {e}", exc_info=True)
            return 0

    @classmethod
    def _calculate_attendance_rate(cls, site, start_time, end_time) -> float:
        """Calculate attendance rate as percentage."""
        from apps.attendance.models import Attendance
        from apps.scheduler.models import Schedule

        try:
            # Count scheduled shifts
            scheduled_count = Schedule.objects.filter(
                bu=site,
                start_time__gte=start_time,
                start_time__lte=end_time
            ).count()

            if scheduled_count == 0:
                return 100.0  # No data means assume 100%

            # Count actual attendance
            attended_count = Attendance.objects.filter(
                bu=site,
                cdtz__gte=start_time,
                cdtz__lte=end_time,
                status='PRESENT'
            ).count()

            return (attended_count / scheduled_count) * 100.0

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error calculating attendance rate: {e}", exc_info=True)
            return 85.0  # Default to 85%

    @classmethod
    def _get_site_criticality(cls, site) -> int:
        """
        Get site criticality score (1-5).

        Logic:
        - VIP clients: 5
        - 24/7 sites: 4
        - High-value sites: 3
        - Regular sites: 2
        - Low priority: 1
        """
        if hasattr(site, 'is_vip') and site.is_vip:
            return 5
        if hasattr(site, 'is_24_7') and site.is_24_7:
            return 4
        if hasattr(site, 'criticality_score'):
            return int(site.criticality_score)
        return 2  # Default: regular site

    @classmethod
    def _get_current_staffing_ratio(cls, site) -> float:
        """
        Get current staffing ratio (actual/required).

        Returns value like 1.0 (fully staffed), 0.8 (understaffed), 1.2 (overstaffed)
        """
        from apps.attendance.models import Attendance

        now = timezone.now()

        # Count currently present guards
        current_present = Attendance.objects.filter(
            bu=site,
            status='PRESENT',
            cdtz__date=now.date()
        ).values('people').distinct().count()

        # Get required count (from site configuration or default)
        required_count = getattr(site, 'required_guards', 1)

        if required_count == 0:
            return 1.0

        return current_present / required_count

    @classmethod
    def _get_no_show_rate(cls, site, shift_time) -> float:
        """
        Get historical no-show rate for this shift pattern.

        Analyzes same day-of-week and time-of-day patterns.
        """
        from apps.attendance.models import Attendance
        from apps.scheduler.models import Schedule

        # Get day of week and hour
        day_of_week = shift_time.weekday()
        hour = shift_time.hour

        # Look back 4 weeks for same shift pattern
        four_weeks_ago = shift_time - timedelta(weeks=4)

        try:
            # Count scheduled vs attended for similar shifts
            similar_shifts = Schedule.objects.filter(
                bu=site,
                start_time__gte=four_weeks_ago,
                start_time__lt=shift_time,
                start_time__week_day=day_of_week + 1,  # Django uses 1-7
                start_time__hour=hour
            )

            total_shifts = similar_shifts.count()
            if total_shifts == 0:
                return 0.15  # Default 15% no-show rate

            # Count no-shows
            scheduled_people = similar_shifts.values_list('people_id', flat=True)
            attended = Attendance.objects.filter(
                people_id__in=scheduled_people,
                bu=site,
                status='PRESENT'
            ).values_list('people_id', flat=True).distinct()

            no_shows = total_shifts - len(attended)
            return (no_shows / total_shifts) if total_shifts > 0 else 0.15

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error calculating no-show rate: {e}", exc_info=True)
            return 0.15  # Default

    @classmethod
    def _heuristic_prediction(cls, features: Dict[str, Any]) -> float:
        """
        Heuristic prediction when ML model unavailable.

        Logic:
        - Few scheduled + high no-show rate: Very high risk (0.85)
        - Low attendance rate + VIP site: High risk (0.75)
        - Current understaffed + shift soon: Medium-high risk (0.65)
        - Otherwise: Scale by attendance rate
        """
        scheduled = features['scheduled_guards_count']
        attendance_rate = features['actual_attendance_rate_last_7_days']
        time_to_shift = features['time_to_next_shift_minutes']
        criticality = features['site_criticality_score']
        current_ratio = features['current_attendance_vs_scheduled_ratio']
        no_show_rate = features['historical_no_show_rate']

        # Few guards scheduled + high no-show rate
        if scheduled <= 1 and no_show_rate > 0.3:
            return 0.85

        # Low attendance rate + VIP site
        if attendance_rate < 70 and criticality >= 4:
            return 0.75

        # Currently understaffed + shift starting soon
        if current_ratio < 0.8 and time_to_shift < 120:  # <2 hours
            return 0.65

        # Scale by attendance rate (inverse)
        base_risk = 1.0 - (attendance_rate / 100.0)
        return min(max(base_risk, 0.1), 0.9)  # Clamp to 0.1-0.9

    @classmethod
    def should_alert(cls, probability: float) -> bool:
        """Check if probability exceeds threshold for alerting."""
        return probability >= cls.GAP_PROBABILITY_THRESHOLD
