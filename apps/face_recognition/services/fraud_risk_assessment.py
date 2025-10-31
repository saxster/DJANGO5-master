"""
Fraud Risk Assessment Service for Face Recognition (Sprint 1.5)

This service provides comprehensive fraud risk assessment by analyzing:
- Verification confidence scores
- Image quality metrics
- Anti-spoofing detection results
- Model consistency (ensemble)
- Historical fraud patterns

Author: Development Team
Date: October 2025
"""

import logging
import numpy as np
from typing import Dict, Any, List
from datetime import timedelta
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.face_recognition.models import FaceVerificationLog

logger = logging.getLogger(__name__)


class FraudRiskAssessmentService:
    """
    Service for assessing fraud risk in biometric verifications.

    Analyzes multiple fraud indicators and provides risk scoring with
    detailed fraud indicator tracking.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize fraud risk assessment service.

        Args:
            config: Configuration dictionary with assessment parameters
        """
        self.config = config or {}

        # Risk thresholds
        self.low_confidence_threshold = self.config.get('low_confidence_threshold', 0.5)
        self.poor_quality_threshold = self.config.get('poor_quality_threshold', 0.4)
        self.high_fraud_threshold = self.config.get('high_fraud_threshold', 0.7)
        self.model_variance_threshold = self.config.get('model_variance_threshold', 0.2)
        self.recent_fraud_lookback_days = self.config.get('recent_fraud_lookback_days', 7)
        self.recent_fraud_count_threshold = self.config.get('recent_fraud_count_threshold', 2)

    def assess_fraud_risk(self, result: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """
        Assess fraud risk based on verification results and historical patterns.

        Args:
            result: Verification result dictionary containing:
                - confidence: Verification confidence score
                - quality_metrics: Image quality assessment
                - anti_spoofing_result: Anti-spoofing detection results
                - model_results: Individual model results (for ensemble)
                - fraud_indicators: Existing fraud indicators
            user_id: User identifier for historical analysis

        Returns:
            Dictionary containing:
                - fraud_risk_score: Overall fraud risk score (0.0-1.0)
                - fraud_indicators: List of specific fraud indicators found
                - risk_level: Categorical risk level (LOW/MEDIUM/HIGH)
        """
        try:
            fraud_indicators = result.get('fraud_indicators', []).copy()
            fraud_score = 0.0

            # 1. Low confidence indicates potential fraud
            confidence = result.get('confidence', 0)
            if confidence < self.low_confidence_threshold:
                fraud_score += 0.3
                fraud_indicators.append('LOW_VERIFICATION_CONFIDENCE')

            # 2. Poor image quality can indicate spoofing
            quality = result.get('quality_metrics', {}).get('overall_quality', 1.0)
            if quality < self.poor_quality_threshold:
                fraud_score += 0.2
                fraud_indicators.append('POOR_IMAGE_QUALITY')

            # 3. Anti-spoofing detection
            if result.get('anti_spoofing_result', {}).get('spoof_detected', False):
                fraud_score += 0.5
                fraud_indicators.extend(
                    result['anti_spoofing_result'].get('fraud_indicators', [])
                )

            # 4. Model inconsistency (ensemble only)
            model_results = result.get('model_results', {})
            if len(model_results) > 1:
                similarities = [r.get('similarity', 0) for r in model_results.values()]
                if len(similarities) > 1 and np.std(similarities) > self.model_variance_threshold:
                    fraud_score += 0.2
                    fraud_indicators.append('MODEL_INCONSISTENCY')

            # 5. Historical fraud patterns (check recent verifications)
            recent_fraud_count = self._check_recent_fraud_history(user_id)
            if recent_fraud_count > self.recent_fraud_count_threshold:
                fraud_score += 0.3
                fraud_indicators.append('RECENT_FRAUD_HISTORY')

            # Calculate final fraud risk score
            final_fraud_risk = float(min(1.0, fraud_score))

            return {
                'fraud_risk_score': final_fraud_risk,
                'fraud_indicators': fraud_indicators,
                'risk_level': self.calculate_risk_level(final_fraud_risk)
            }

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error assessing fraud risk: {str(e)}")
            return {
                'fraud_risk_score': 0.0,
                'fraud_indicators': [],
                'risk_level': 'LOW'
            }

    def _check_recent_fraud_history(self, user_id: int) -> int:
        """
        Check recent fraud history for a user.

        Args:
            user_id: User identifier

        Returns:
            Count of recent fraudulent verifications
        """
        try:
            recent_fraudulent = FaceVerificationLog.objects.filter(
                user_id=user_id,
                verification_timestamp__gte=timezone.now() - timedelta(
                    days=self.recent_fraud_lookback_days
                ),
                fraud_risk_score__gt=self.high_fraud_threshold
            ).count()

            return recent_fraudulent

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.warning(f"Error checking fraud history: {str(e)}")
            return 0

    def make_verification_decision(self, result: Dict[str, Any]) -> bool:
        """
        Make final verification decision based on all factors.

        Args:
            result: Complete verification result containing:
                - threshold_met: Whether similarity threshold was met
                - confidence_met: Whether confidence threshold was met
                - fraud_risk_score: Calculated fraud risk score
                - anti_spoofing_result: Anti-spoofing analysis
                - quality_metrics: Image quality metrics

        Returns:
            Boolean indicating if verification passed
        """
        try:
            # Basic threshold check
            threshold_met = result.get('threshold_met', False)
            confidence_met = result.get('confidence_met', False)

            # Fraud risk check
            fraud_risk = result.get('fraud_risk_score', 0)
            high_fraud_risk = fraud_risk > self.high_fraud_threshold

            # Anti-spoofing check
            spoof_detected = result.get('anti_spoofing_result', {}).get('spoof_detected', False)

            # Quality check
            quality = result.get('quality_metrics', {}).get('overall_quality', 1.0)
            quality_acceptable = quality >= self.poor_quality_threshold

            # Final decision: all checks must pass
            decision = (
                threshold_met and
                confidence_met and
                not high_fraud_risk and
                not spoof_detected and
                quality_acceptable
            )

            return decision

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error making verification decision: {str(e)}")
            return False

    def calculate_risk_level(self, fraud_risk_score: float) -> str:
        """
        Calculate risk level category from fraud risk score.

        Args:
            fraud_risk_score: Fraud risk score (0.0-1.0)

        Returns:
            Risk level string: 'LOW', 'MEDIUM', or 'HIGH'
        """
        if fraud_risk_score < 0.3:
            return 'LOW'
        elif fraud_risk_score < self.high_fraud_threshold:
            return 'MEDIUM'
        else:
            return 'HIGH'
