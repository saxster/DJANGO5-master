"""
Predictive Fraud Detector Service.

Proactive fraud prediction before attendance occurs.
Uses trained XGBoost models and behavioral profiles for early warning.

Architecture:
- Load XGBoost model from FraudDetectionModel registry
- Extract 12 features using FraudFeatureExtractor
- Predict with optimal threshold
- Fallback to behavioral heuristics if model fails

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
import numpy as np
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import joblib

logger = logging.getLogger('noc.security_intelligence.ml')


class PredictiveFraudDetector:
    """Predicts fraud probability using trained XGBoost model."""

    # Class-level model cache
    _model_cache = {}

    @classmethod
    def predict_attendance_fraud(cls, person, site, scheduled_time):
        """
        Predict fraud probability for upcoming attendance.

        Args:
            person: People instance
            site: Bt instance
            scheduled_time: datetime of scheduled attendance

        Returns:
            dict: Prediction result with fraud_probability and risk_level
        """
        from apps.noc.security_intelligence.models import BehavioralProfile

        try:
            # Check if sufficient behavioral data exists
            profile = BehavioralProfile.objects.filter(person=person).first()

            if not profile or not profile.is_sufficient_data:
                return cls._get_default_prediction()

            # Try ML model prediction first
            try:
                ml_prediction = cls._predict_with_model(person, site, scheduled_time, profile)
                if ml_prediction:
                    return ml_prediction
            except (ValueError, AttributeError, OSError) as e:
                logger.warning(f"ML model prediction failed, falling back to heuristics: {e}")

            # Fallback to behavioral heuristics
            return cls._predict_with_heuristics(person, site, scheduled_time, profile)

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud prediction error: {e}", exc_info=True)
            return cls._get_default_prediction()

    @classmethod
    def _predict_with_model(cls, person, site, scheduled_time, profile):
        """
        Predict fraud using trained XGBoost model.

        Args:
            person: People instance
            site: Bt instance
            scheduled_time: datetime
            profile: BehavioralProfile instance

        Returns:
            dict: Prediction result or None if model unavailable
        """
        # Load model
        model, model_record = cls._load_model(person.tenant)
        if not model or not model_record:
            return None

        # Create mock attendance event for feature extraction
        mock_event = type('obj', (object,), {
            'punchintime': scheduled_time,
            'datefor': scheduled_time.date(),
            'scheduled_time': scheduled_time,
            'startlat': None,  # Will be populated from profile if available
            'startlng': None,
            'peventlogextras': {},
            'people': person,
            'bu': site,
        })()

        # Extract features
        from apps.ml.features.fraud_features import FraudFeatureExtractor
        features_dict = FraudFeatureExtractor.extract_all_features(mock_event, person, site)

        # Convert to numpy array (preserve feature order)
        feature_cols = [
            'hour_of_day', 'day_of_week', 'is_weekend', 'is_holiday',
            'gps_drift_meters', 'location_consistency_score',
            'check_in_frequency_zscore', 'late_arrival_rate', 'weekend_work_frequency',
            'face_recognition_confidence', 'biometric_mismatch_count_30d', 'time_since_last_event'
        ]
        X = np.array([[features_dict[col] for col in feature_cols]])

        # Track inference latency (Recommendation #8 - Observability)
        from apps.ml.services.inference_metrics_collector import InferenceMetricsCollector

        with InferenceMetricsCollector.track_inference(
            model_type='fraud_detector',
            model_version=model_record.model_version
        ) as inference_metrics:
            # Predict probability
            fraud_probability = model.predict_proba(X)[0, 1]

        # Log inference latency
        inference_latency_ms = inference_metrics.get('latency_ms', 0)

        # Apply optimal threshold
        optimal_threshold = model_record.optimal_threshold
        is_fraud = fraud_probability >= optimal_threshold

        # Determine risk level
        risk_level = cls._determine_risk_level(fraud_probability)

        # Calculate behavioral risk for context
        behavioral_risk = cls._calculate_behavioral_risk(features_dict, profile)

        # Generate confidence intervals using conformal prediction (Phase 1)
        conformal_interval = cls._get_conformal_interval(
            fraud_probability,
            model_record.model_version
        )

        result = {
            'fraud_probability': round(float(fraud_probability), 3),
            'risk_level': risk_level,
            'model_confidence': model_record.pr_auc,  # Use PR-AUC as confidence
            'behavioral_risk': behavioral_risk,
            'features': features_dict,
            'model_version': model_record.model_version,
            'optimal_threshold': optimal_threshold,
            'prediction_method': 'xgboost',
            'inference_latency_ms': inference_latency_ms,  # Observability
        }

        # Add conformal prediction intervals if available
        if conformal_interval:
            result.update({
                'prediction_lower_bound': conformal_interval['lower_bound'],
                'prediction_upper_bound': conformal_interval['upper_bound'],
                'confidence_interval_width': conformal_interval['width'],
                'calibration_score': conformal_interval['calibration_score'],
                'is_narrow_interval': conformal_interval['width'] < 0.2,
            })

            # Log decision (Recommendation #8 - Observability)
            decision_type = 'ticket' if result.get('is_narrow_interval') and risk_level in ['HIGH', 'CRITICAL'] else 'alert'
            automated = result.get('is_narrow_interval', False) and risk_level in ['HIGH', 'CRITICAL']

            InferenceMetricsCollector.log_decision(
                model_type='fraud_detector',
                decision_type=decision_type,
                confidence=conformal_interval['calibration_score'],
                automated=automated
            )

        return result

    @classmethod
    def _load_model(cls, tenant):
        """
        Load active XGBoost model for tenant.

        Uses cache to avoid repeated disk I/O.

        Args:
            tenant: Tenant instance

        Returns:
            tuple: (model, model_record) or (None, None)
        """
        cache_key = f'fraud_model_{tenant.id}'

        # Check cache first
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Load from database
        from apps.noc.security_intelligence.models import FraudDetectionModel
        model_record = FraudDetectionModel.get_active_model(tenant)

        if not model_record:
            logger.warning(f"No active fraud detection model for tenant {tenant.schema_name}")
            return None, None

        try:
            # Load model from disk
            model = joblib.load(model_record.model_path)

            # Cache for 1 hour
            cache.set(cache_key, (model, model_record), 3600)

            logger.info(f"Loaded fraud detection model {model_record.model_version}")
            return model, model_record

        except (FileNotFoundError, ValueError, OSError) as e:
            logger.error(f"Model loading error: {e}", exc_info=True)
            return None, None

    @classmethod
    def _predict_with_heuristics(cls, person, site, scheduled_time, profile):
        """
        Fallback prediction using behavioral heuristics.

        Used when ML model is unavailable or fails.

        Args:
            person: People instance
            site: Bt instance
            scheduled_time: datetime
            profile: BehavioralProfile instance

        Returns:
            dict: Prediction result
        """
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        try:
            # Create mock event for feature extraction
            mock_event = type('obj', (object,), {
                'scheduled_time': scheduled_time,
                'datefor': scheduled_time.date(),
            })()

            from apps.ml.features.fraud_features import FraudFeatureExtractor
            features = FraudFeatureExtractor.extract_all_features(mock_event, person, site)

            # Calculate fraud history score
            history = FraudScoreCalculator.calculate_person_fraud_history_score(person, days=30)

            # Behavioral risk calculation
            behavioral_risk = cls._calculate_behavioral_risk(features, profile)

            # Simple weighted heuristic
            fraud_probability = (
                behavioral_risk * 0.5 +
                (history['history_score'] * 0.3) +
                (features['late_arrival_rate'] * 0.2)
            )

            risk_level = cls._determine_risk_level(fraud_probability)

            return {
                'fraud_probability': round(fraud_probability, 3),
                'risk_level': risk_level,
                'model_confidence': 0.6,  # Lower confidence for heuristics
                'behavioral_risk': behavioral_risk,
                'features': features,
                'model_version': 'heuristic_fallback',
                'prediction_method': 'heuristic',
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Heuristic prediction error: {e}", exc_info=True)
            return cls._get_default_prediction()

    @staticmethod
    def _calculate_behavioral_risk(features, profile):
        """
        Calculate risk from behavioral deviation.

        Args:
            features: dict of extracted features
            profile: BehavioralProfile instance

        Returns:
            float: Risk score (0-1)
        """
        try:
            risk = 0.0

            # Unusual hour
            if features.get('hour_of_day') not in profile.typical_punch_in_hours:
                risk += 0.2

            # Unusual day
            if features.get('day_of_week') not in profile.typical_work_days:
                risk += 0.15

            # High GPS drift
            if features.get('gps_drift_meters', 0) > 500:
                risk += 0.25

            # Low location consistency
            if features.get('location_consistency_score', 1.0) < 0.5:
                risk += 0.2

            # Weekend work without history
            if features.get('is_weekend') and features.get('weekend_work_frequency', 0) < 0.1:
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
            'prediction_method': 'default',
        }

    @staticmethod
    def _get_conformal_interval(fraud_probability, model_version):
        """
        Generate confidence interval using conformal prediction.

        Phase 1 enhancement: Adds uncertainty quantification to fraud predictions.

        Args:
            fraud_probability: Point prediction (0-1)
            model_version: Model version for calibration lookup

        Returns:
            dict: Interval bounds and metadata, or None if calibration unavailable
        """
        from apps.ml.services.conformal_predictor import ConformalPredictorService

        try:
            interval = ConformalPredictorService.predict_with_intervals(
                point_prediction=fraud_probability,
                model_type='fraud_detector',
                model_version=model_version,
                coverage_level=90  # 90% coverage by default
            )
            return interval
        except (ValueError, AttributeError) as e:
            logger.warning(f"Conformal interval calculation failed: {e}")
            return None

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
            # Base log fields
            log_data = {
                'tenant': person.tenant,
                'person': person,
                'site': site,
                'predicted_at': timezone.now(),
                'prediction_type': 'ATTENDANCE',
                'fraud_probability': prediction_result['fraud_probability'],
                'risk_level': prediction_result['risk_level'],
                'model_confidence': prediction_result['model_confidence'],
                'features_used': prediction_result['features'],
                'baseline_deviation': prediction_result['behavioral_risk'],
                'model_version': prediction_result['model_version'],
            }

            # Add confidence interval fields if available (Phase 1)
            if 'prediction_lower_bound' in prediction_result:
                log_data.update({
                    'prediction_lower_bound': prediction_result['prediction_lower_bound'],
                    'prediction_upper_bound': prediction_result['prediction_upper_bound'],
                    'confidence_interval_width': prediction_result['confidence_interval_width'],
                    'calibration_score': prediction_result['calibration_score'],
                })

            log = FraudPredictionLog.objects.create(**log_data)

            return log

        except (ValueError, AttributeError) as e:
            logger.error(f"Prediction logging error: {e}", exc_info=True)
            return None

    @classmethod
    def clear_model_cache(cls):
        """Clear cached model instances."""
        cls._model_cache = {}
        cache.delete_pattern('fraud_model_*')
        logger.info("Cleared fraud detection model cache")
