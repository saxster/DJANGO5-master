"""
Predictive Fraud Detector Service.

Proactive fraud prediction before attendance occurs.
Uses ML models and behavioral profiles for early warning.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence.ml')


class PredictiveFraudDetector:
    """Predicts fraud probability before it occurs."""

    @classmethod
    def predict_attendance_fraud(cls, person, site, scheduled_time):
        """
        Predict fraud probability for upcoming attendance.

        Args:
            person: People instance
            site: Bt instance
            scheduled_time: datetime of scheduled attendance

        Returns:
            dict: Prediction result
        """
        from apps.noc.security_intelligence.models import BehavioralProfile
        from apps.noc.security_intelligence.ml import GoogleMLIntegrator

        try:
            profile = BehavioralProfile.objects.filter(person=person).first()

            if not profile or not profile.is_sufficient_data:
                return cls._get_default_prediction()

            features = cls._extract_prediction_features(person, site, scheduled_time, profile)

            ml_prediction = GoogleMLIntegrator.predict_fraud_probability(features)

            behavioral_risk = cls._calculate_behavioral_risk(features, profile)

            combined_probability = (
                ml_prediction['fraud_probability'] * 0.7 +
                behavioral_risk * 0.3
            )

            risk_level = cls._determine_risk_level(combined_probability)

            return {
                'fraud_probability': round(combined_probability, 2),
                'risk_level': risk_level,
                'model_confidence': ml_prediction['model_confidence'],
                'behavioral_risk': behavioral_risk,
                'features': features,
                'model_version': ml_prediction['model_version'],
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud prediction error: {e}", exc_info=True)
            return cls._get_default_prediction()

    @classmethod
    def _extract_prediction_features(cls, person, site, scheduled_time, profile):
        """Extract features for ML prediction."""
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        try:
            history = FraudScoreCalculator.calculate_person_fraud_history_score(person, days=30)

            return {
                'person_id': person.id,
                'site_id': site.id,
                'hour': scheduled_time.hour,
                'day_of_week': scheduled_time.weekday(),
                'baseline_fraud_score': profile.baseline_fraud_score,
                'consistency_score': profile.consistency_score,
                'avg_biometric_confidence': profile.avg_biometric_confidence,
                'site_variety_score': profile.site_variety_score,
                'history_fraud_score': history['history_score'],
                'total_flags_30d': history['total_flags'],
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Feature extraction error: {e}", exc_info=True)
            return {}

    @staticmethod
    def _calculate_behavioral_risk(features, profile):
        """Calculate risk from behavioral deviation."""
        try:
            risk = 0.0

            if features.get('hour') not in profile.typical_punch_in_hours:
                risk += 0.2

            if features.get('day_of_week') not in profile.typical_work_days:
                risk += 0.15

            if features.get('history_fraud_score', 0) > 0.3:
                risk += 0.3

            if profile.consistency_score < 0.5:
                risk += 0.2

            return min(risk, 1.0)

        except (ValueError, AttributeError):
            return 0.0

    @staticmethod
    def _determine_risk_level(probability):
        """Determine risk level from probability."""
        if probability >= 0.8:
            return 'CRITICAL'
        elif probability >= 0.6:
            return 'HIGH'
        elif probability >= 0.4:
            return 'MEDIUM'
        elif probability >= 0.2:
            return 'LOW'
        else:
            return 'MINIMAL'

    @staticmethod
    def _get_default_prediction():
        """Get default prediction when profiling insufficient."""
        return {
            'fraud_probability': 0.0,
            'risk_level': 'MINIMAL',
            'model_confidence': 0.0,
            'behavioral_risk': 0.0,
            'features': {},
            'model_version': 'none',
        }

    @classmethod
    @transaction.atomic
    def log_prediction(cls, person, site, scheduled_time, prediction_result):
        """
        Log fraud prediction.

        Args:
            person: People instance
            site: Bt instance
            scheduled_time: datetime
            prediction_result: dict from predict_attendance_fraud

        Returns:
            FraudPredictionLog instance
        """
        from apps.noc.security_intelligence.models import FraudPredictionLog

        try:
            log = FraudPredictionLog.objects.create(
                tenant=person.tenant,
                person=person,
                site=site,
                predicted_at=timezone.now(),
                prediction_type='ATTENDANCE',
                fraud_probability=prediction_result['fraud_probability'],
                risk_level=prediction_result['risk_level'],
                model_confidence=prediction_result['model_confidence'],
                features_used=prediction_result['features'],
                baseline_deviation=prediction_result['behavioral_risk'],
                model_version=prediction_result['model_version'],
            )

            return log

        except (ValueError, AttributeError) as e:
            logger.error(f"Prediction logging error: {e}", exc_info=True)
            return None