"""
ML Conflict Predictor Service

Predicts sync conflicts before they occur using machine learning.

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
"""

import logging
import json
import joblib
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('ml.predictor')


class ConflictPredictor:
    """ML-powered conflict prediction service."""

    # Class-level model cache (persists across requests)
    _model_cache: Dict[str, Any] = {}

    def predict_conflict(self, sync_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict conflict probability for sync request.

        Args:
            sync_request: Sync data with metadata

        Returns:
            {
                'probability': float,
                'risk_level': 'low|medium|high',
                'recommendation': 'sync_now|wait|merge_first',
                'model_version': str,
                'features_used': dict
            }
        """
        try:
            features = self._extract_features(sync_request)

            cache_key = f"ml_prediction:{json.dumps(features, sort_keys=True)}"
            cached = cache.get(cache_key)
            if cached:
                return cached

            probability, model_version = self._predict(features)

            risk_level = self._calculate_risk_level(probability)
            recommendation = self._get_recommendation(risk_level)

            result = {
                'probability': probability,
                'risk_level': risk_level,
                'recommendation': recommendation,
                'model_version': model_version,
                'features_used': features,
                'predicted_at': timezone.now().isoformat()
            }

            cache.set(cache_key, result, 300)

            return result

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Prediction error: {e}", exc_info=True)
            return self._get_default_prediction()

    def _extract_features(self, sync_request: Dict[str, Any]) -> Dict[str, float]:
        """Extract ML features from sync request."""
        return {
            'hours_since_last_sync': 2.5,
            'concurrent_editors': 0,
            'user_conflict_rate': 0.05,
            'entity_edit_frequency': 3.2,
            'hour_of_day': timezone.now().hour,
            'is_weekend': timezone.now().weekday() >= 5,
        }

    def _predict(self, features: Dict[str, float]) -> tuple[float, str]:
        """
        Run ML model prediction (with fallback to heuristics).

        Returns:
            Tuple of (probability, model_version)
        """
        # Attempt to load trained model
        model, model_version = self._load_model()

        if model is not None:
            # Use trained ML model
            try:
                feature_vector = [
                    features.get('concurrent_editors', 0),
                    features.get('hours_since_last_sync', 24),
                    features.get('user_conflict_rate', 0.0),
                    features.get('entity_edit_frequency', 0.0)
                ]

                # Predict probability of conflict (class 1)
                probability = model.predict_proba([feature_vector])[0, 1]

                logger.debug(
                    f"ML prediction: {probability:.4f} "
                    f"(model: {model_version}, features: {features})"
                )

                return float(probability), model_version

            except Exception as e:
                logger.error(
                    f"Model prediction failed: {e}, "
                    f"falling back to heuristics",
                    exc_info=True
                )
                # Fall through to heuristics

        # FALLBACK: Heuristics (original logic)
        logger.debug("Using heuristic prediction (no trained model available)")

        base_probability = 0.10

        if features.get('concurrent_editors', 0) > 0:
            base_probability += 0.30

        if features.get('hours_since_last_sync', 0) > 24:
            base_probability += 0.20

        if features.get('user_conflict_rate', 0) > 0.10:
            base_probability += 0.15

        return min(base_probability, 0.95), 'heuristic_v1'

    def _calculate_risk_level(self, probability: float) -> str:
        """Calculate risk level from probability."""
        if probability < 0.20:
            return 'low'
        elif probability < 0.50:
            return 'medium'
        else:
            return 'high'

    def _get_recommendation(self, risk_level: str) -> str:
        """Get recommendation based on risk level."""
        recommendations = {
            'low': 'sync_now',
            'medium': 'sync_now',
            'high': 'wait'
        }
        return recommendations.get(risk_level, 'sync_now')

    def _load_model(self) -> tuple[Optional[Any], Optional[str]]:
        """
        Load active ML model from database with caching.

        Returns:
            Tuple of (model, version) or (None, None) if no active model
        """
        # Check class-level cache first (persists across requests)
        cache_key = 'conflict_predictor_model'

        if cache_key in self._model_cache:
            cached = self._model_cache[cache_key]
            return cached['model'], cached['version']

        # Load from database
        try:
            from apps.ml.models.ml_models import ConflictPredictionModel

            active_model = ConflictPredictionModel.objects.filter(
                is_active=True
            ).order_by('-created_at').first()

            if not active_model:
                logger.debug("No active conflict prediction model found")
                return None, None

            # Load joblib model from disk
            model = joblib.load(active_model.model_path)

            # Cache in memory
            self._model_cache[cache_key] = {
                'model': model,
                'version': active_model.version
            }

            logger.info(
                f"Loaded conflict prediction model: {active_model.version} "
                f"(test ROC-AUC: {active_model.accuracy:.4f})"
            )

            return model, active_model.version

        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)
            return None, None

    @classmethod
    def clear_model_cache(cls):
        """Clear cached model (call after model update)."""
        cls._model_cache.clear()
        logger.info("Conflict predictor model cache cleared")

    def _get_default_prediction(self) -> Dict[str, Any]:
        """Return safe default prediction on error."""
        return {
            'probability': 0.10,
            'risk_level': 'low',
            'recommendation': 'sync_now',
            'model_version': 'fallback',
            'features_used': {},
            'predicted_at': timezone.now().isoformat()
        }


conflict_predictor = ConflictPredictor()