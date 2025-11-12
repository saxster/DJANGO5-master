"""
Explainability Service

Generates instance-level ML explanations using SHAP (SHapley Additive exPlanations).

Provides:
- Feature contribution analysis (why THIS prediction was high/low)
- Human-readable explanations for tickets/alerts
- Model-agnostic explanations (works with any tree-based model)
- Compliance-ready audit trail

Phase 4, Feature 1: Closes explainability gap in Recommendation #7

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

from typing import Dict, Any, List, Tuple, Optional
from django.core.cache import cache
import numpy as np
import logging

logger = logging.getLogger('ml.explainability')


class ExplainabilityService:
    """
    Generate SHAP-based explanations for ML predictions.

    SHAP (SHapley Additive exPlanations) provides theoretically-grounded
    feature importance that shows exactly how each feature contributed
    to a specific prediction.
    """

    # Cache SHAP explainers (expensive to create, reuse for same model)
    _explainer_cache = {}

    @classmethod
    def generate_shap_explanation(
        cls,
        model,
        features: np.ndarray,
        feature_names: List[str],
        model_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate SHAP explanation for single prediction.

        Args:
            model: Trained model (XGBoost, RandomForest, etc.)
            features: Feature array (1D numpy array)
            feature_names: List of feature names (same order as features)
            model_version: Model version for caching

        Returns:
            {
                'base_value': float,  # Expected value (average prediction)
                'shap_values': dict,  # {feature_name: contribution}
                'prediction': float,  # Actual prediction
                'top_contributors': list,  # Top 5 features
                'human_readable': str,  # Formatted explanation
            }
        """
        try:
            import shap

            # Get or create explainer (cached)
            explainer = cls._get_cached_explainer(model, model_version)

            if not explainer:
                return None

            # Calculate SHAP values
            shap_values_array = explainer.shap_values(features.reshape(1, -1))

            # Handle different SHAP output formats
            if isinstance(shap_values_array, list):
                # Multi-class output, use positive class (index 1)
                shap_values_array = shap_values_array[1]

            shap_values_flat = shap_values_array[0] if len(shap_values_array.shape) > 1 else shap_values_array

            # Create feature contribution dict
            shap_dict = {
                feature_names[i]: float(shap_values_flat[i])
                for i in range(len(feature_names))
            }

            # Get base value (expected value)
            base_value = explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(base_value[1] if len(base_value) > 1 else base_value[0])
            else:
                base_value = float(base_value)

            # Calculate prediction
            prediction = base_value + sum(shap_values_flat)

            # Get top contributors (absolute values, sorted descending)
            contributions = [
                (name, value, abs(value))
                for name, value in shap_dict.items()
            ]
            top_contributors = sorted(
                contributions,
                key=lambda x: x[2],
                reverse=True
            )[:5]  # Top 5

            # Format human-readable explanation
            human_readable = cls._format_human_readable(
                top_contributors,
                prediction,
                base_value
            )

            return {
                'base_value': base_value,
                'shap_values': shap_dict,
                'prediction': float(prediction),
                'top_contributors': [
                    {
                        'feature': name,
                        'contribution': value,
                        'abs_contribution': abs_val,
                        'percentage': abs_val / sum(abs(v) for v in shap_values_flat) * 100
                    }
                    for name, value, abs_val in top_contributors
                ],
                'human_readable': human_readable
            }

        except (ImportError, ValueError, AttributeError) as e:
            logger.error(f"SHAP explanation generation failed: {e}", exc_info=True)
            return None

    @classmethod
    def _get_cached_explainer(cls, model, model_version: str):
        """
        Get or create SHAP explainer (cached for performance).

        Creating explainers is expensive, so cache for 1 hour.
        """
        cache_key = f"shap_explainer_{model_version}"

        # Check memory cache first (fastest)
        if cache_key in cls._explainer_cache:
            return cls._explainer_cache[cache_key]

        # Check Redis cache
        explainer = cache.get(cache_key)

        if explainer:
            cls._explainer_cache[cache_key] = explainer
            return explainer

        # Create new explainer
        try:
            import shap

            # Use TreeExplainer for XGBoost/tree-based models
            explainer = shap.TreeExplainer(model)

            # Cache for 1 hour
            cache.set(cache_key, explainer, timeout=3600)
            cls._explainer_cache[cache_key] = explainer

            logger.info(f"Created SHAP explainer for model {model_version}")

            return explainer

        except (ImportError, ValueError, AttributeError) as e:
            logger.error(f"Failed to create SHAP explainer: {e}", exc_info=True)
            return None

    @staticmethod
    def _format_human_readable(
        top_contributors: List[Tuple[str, float, float]],
        prediction: float,
        base_value: float
    ) -> str:
        """
        Format SHAP explanation in human-readable text.

        Args:
            top_contributors: List of (feature_name, contribution, abs_contribution)
            prediction: Final prediction value
            base_value: Base prediction (average)

        Returns:
            Human-readable explanation string
        """
        # Map feature names to human-friendly descriptions
        feature_descriptions = {
            'gps_drift_meters': 'GPS drift from site location',
            'hour_of_day': 'Unusual punch-in time',
            'is_weekend': 'Weekend work pattern',
            'is_holiday': 'Holiday work',
            'location_consistency_score': 'Location pattern consistency',
            'face_recognition_confidence': 'Biometric verification confidence',
            'check_in_frequency_zscore': 'Check-in frequency deviation',
            'late_arrival_rate': 'Late arrival pattern',
            'weekend_work_frequency': 'Weekend work history',
            'biometric_mismatch_count_30d': 'Recent biometric mismatches',
            'time_since_last_event': 'Time since last check-in',
            'day_of_week': 'Day of week pattern',
        }

        explanation_parts = []

        for feature_name, contribution, abs_contribution in top_contributors[:5]:
            # Get human-friendly name
            friendly_name = feature_descriptions.get(feature_name, feature_name.replace('_', ' '))

            # Determine direction
            if contribution > 0:
                direction = "increased risk"
            else:
                direction = "decreased risk"

            # Calculate percentage contribution
            total_abs_contributions = sum(abs_val for _, _, abs_val in top_contributors)
            percentage = (abs_contribution / total_abs_contributions * 100) if total_abs_contributions > 0 else 0

            explanation_parts.append(
                f"{friendly_name} ({direction}: {percentage:.0f}%)"
            )

        if prediction > base_value:
            result_desc = f"High prediction ({prediction:.2f} vs average {base_value:.2f})"
        else:
            result_desc = f"Low prediction ({prediction:.2f} vs average {base_value:.2f})"

        return f"{result_desc} because: {', '.join(explanation_parts)}"
