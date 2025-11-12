"""
Conformal Prediction Service

Implements uncertainty quantification for ML models using conformal prediction.
Provides prediction intervals with guaranteed coverage (90%, 95%, 99%).

Based on 2025 best practices:
- Distribution-free (no assumptions about data distribution)
- Model-agnostic (works with any point predictor)
- Guaranteed coverage (statistical validity)
- No additional training required

Follows .claude/rules.md:
- Rule #7: Classes < 150 lines
- Specific exception handling
- Type hints throughout
"""

from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CalibrationDataManager:
    """
    Manages calibration dataset for conformal prediction.

    Calibration set is 20% of training data used to calculate
    nonconformity scores without refitting the model.
    """

    @staticmethod
    def store_calibration_set(
        model_type: str,
        model_version: str,
        calibration_predictions: List[float],
        calibration_actuals: List[float]
    ) -> bool:
        """
        Store calibration dataset in cache (1-hour TTL).

        Args:
            model_type: Type of model (fraud_detector, conflict_predictor)
            model_version: Model version identifier
            calibration_predictions: Predicted probabilities on calibration set
            calibration_actuals: Actual outcomes on calibration set

        Returns:
            bool: True if stored successfully
        """
        if len(calibration_predictions) != len(calibration_actuals):
            logger.error("Calibration set size mismatch")
            return False

        if len(calibration_predictions) < 30:
            logger.warning(
                f"Calibration set too small ({len(calibration_predictions)}), "
                "need >= 30 for reliable intervals"
            )
            return False

        cache_key = f"conformal_calib_{model_type}_{model_version}"
        cache_data = {
            'predictions': calibration_predictions,
            'actuals': calibration_actuals,
            'created_at': timezone.now().isoformat()
        }

        # Cache for 1 hour (3600 seconds)
        cache.set(cache_key, cache_data, timeout=3600)
        logger.info(
            f"Stored calibration set for {model_type} v{model_version}: "
            f"{len(calibration_predictions)} samples"
        )
        return True

    @staticmethod
    def get_calibration_set(
        model_type: str,
        model_version: str
    ) -> Optional[Tuple[List[float], List[float]]]:
        """
        Retrieve calibration dataset from cache.

        Args:
            model_type: Type of model
            model_version: Model version identifier

        Returns:
            Tuple of (predictions, actuals) or None if not found
        """
        cache_key = f"conformal_calib_{model_type}_{model_version}"
        cache_data = cache.get(cache_key)

        if cache_data is None:
            logger.warning(
                f"Calibration set not found for {model_type} v{model_version}"
            )
            return None

        return (cache_data['predictions'], cache_data['actuals'])


class NonconformityScorer:
    """
    Calculate nonconformity scores for conformal prediction.

    Nonconformity measures how unusual a prediction is compared to
    calibration set. Higher score = more unusual.
    """

    @staticmethod
    def calculate_scores(
        calibration_predictions: List[float],
        calibration_actuals: List[float]
    ) -> np.ndarray:
        """
        Calculate nonconformity scores using absolute residuals.

        Nonconformity score = |predicted_probability - actual_outcome|

        Args:
            calibration_predictions: Predicted probabilities (0-1)
            calibration_actuals: Actual binary outcomes (0 or 1)

        Returns:
            numpy array of nonconformity scores
        """
        predictions = np.array(calibration_predictions)
        actuals = np.array(calibration_actuals)

        # Absolute residual as nonconformity measure
        scores = np.abs(predictions - actuals)

        logger.debug(
            f"Calculated {len(scores)} nonconformity scores: "
            f"mean={scores.mean():.3f}, median={np.median(scores):.3f}"
        )

        return scores


class ConformalIntervalCalculator:
    """
    Generate prediction intervals with guaranteed coverage.

    Uses conformal prediction to provide statistically valid intervals
    without assumptions about data distribution.
    """

    # Coverage levels and corresponding significance values
    COVERAGE_LEVELS = {
        90: 0.10,  # 90% coverage, 10% error rate
        95: 0.05,  # 95% coverage, 5% error rate
        99: 0.01,  # 99% coverage, 1% error rate
    }

    @classmethod
    def calculate_interval(
        cls,
        point_prediction: float,
        nonconformity_scores: np.ndarray,
        coverage_level: int = 90
    ) -> Dict[str, float]:
        """
        Calculate prediction interval for a single prediction.

        Args:
            point_prediction: Model's point prediction (0-1)
            nonconformity_scores: Calibration set nonconformity scores
            coverage_level: Desired coverage (90, 95, or 99)

        Returns:
            Dict with lower_bound, upper_bound, width, calibration_score
        """
        if coverage_level not in cls.COVERAGE_LEVELS:
            logger.warning(
                f"Invalid coverage level {coverage_level}, defaulting to 90"
            )
            coverage_level = 90

        alpha = cls.COVERAGE_LEVELS[coverage_level]

        # Calculate quantile of nonconformity scores
        # Adjusted quantile for finite sample guarantee
        n = len(nonconformity_scores)
        adjusted_quantile = np.ceil((n + 1) * (1 - alpha)) / n

        # Get the quantile value
        quantile_value = np.quantile(nonconformity_scores, adjusted_quantile)

        # Prediction interval: [prediction - quantile, prediction + quantile]
        lower_bound = max(0.0, point_prediction - quantile_value)
        upper_bound = min(1.0, point_prediction + quantile_value)
        width = upper_bound - lower_bound

        # Calibration score: how well-calibrated is this interval
        # (based on quantile position - lower quantile = better calibration)
        calibration_score = 1.0 - (quantile_value / 1.0)  # Normalize to 0-1

        result = {
            'lower_bound': float(lower_bound),
            'upper_bound': float(upper_bound),
            'width': float(width),
            'calibration_score': float(calibration_score),
            'coverage_level': coverage_level,
            'quantile_value': float(quantile_value)
        }

        logger.debug(
            f"Interval: [{lower_bound:.3f}, {upper_bound:.3f}], "
            f"width={width:.3f}, calibration={calibration_score:.3f}"
        )

        return result


class ConformalPredictorService:
    """
    Main service for conformal prediction integration.

    Coordinates calibration management, nonconformity scoring,
    and interval calculation.
    """

    @classmethod
    def predict_with_intervals(
        cls,
        point_prediction: float,
        model_type: str,
        model_version: str,
        coverage_level: int = 90
    ) -> Optional[Dict[str, float]]:
        """
        Generate prediction with confidence intervals.

        Args:
            point_prediction: Model's point prediction (0-1)
            model_type: Type of model (fraud_detector, etc.)
            model_version: Model version identifier
            coverage_level: Desired coverage (90, 95, 99)

        Returns:
            Dict with interval bounds and metadata, or None if calibration unavailable
        """
        # Retrieve calibration set
        calibration_data = CalibrationDataManager.get_calibration_set(
            model_type, model_version
        )

        if calibration_data is None:
            logger.warning(
                f"No calibration data for {model_type} v{model_version}, "
                "returning point prediction only"
            )
            return None

        predictions, actuals = calibration_data

        # Calculate nonconformity scores
        scores = NonconformityScorer.calculate_scores(predictions, actuals)

        # Generate interval
        interval_result = ConformalIntervalCalculator.calculate_interval(
            point_prediction, scores, coverage_level
        )

        logger.info(
            f"Generated {coverage_level}% interval for {model_type}: "
            f"[{interval_result['lower_bound']:.3f}, "
            f"{interval_result['upper_bound']:.3f}]"
        )

        return interval_result

    @classmethod
    def is_narrow_interval(cls, interval_width: float, threshold: float = 0.2) -> bool:
        """
        Check if interval is narrow (high confidence).

        Narrow intervals indicate high model certainty and enable
        human-out-of-loop automation.

        Args:
            interval_width: Width of confidence interval
            threshold: Width threshold for "narrow" classification (default 0.2)

        Returns:
            bool: True if interval width < threshold
        """
        return interval_width < threshold
