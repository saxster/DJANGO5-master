"""
Multi-Modal Decision Fusion Module for AI-Enhanced Face Recognition (Sprint 1.4)

This module provides intelligent decision fusion across multiple biometric modalities:
- Face recognition
- Voice recognition
- Behavioral biometrics

Aggregates results from multiple verification methods with weighted scoring,
security analysis, and quality adjustments for robust authentication.

Author: Development Team
Date: October 2025
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class MultiModalFusionService:
    """
    Service for intelligent multi-modal biometric decision fusion.

    Combines results from multiple biometric modalities (face, voice, behavioral)
    with security analysis and quality metrics to make robust authentication decisions.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize multi-modal fusion service.

        Args:
            config: Configuration dictionary with fusion parameters
        """
        self.config = config or {}

        # Default modality weights (can be overridden via config)
        self.modality_weights = self.config.get('modality_weights', {
            'face_recognition': 0.6,
            'voice_recognition': 0.25,
            'behavioral_biometrics': 0.15
        })

        # Decision thresholds
        self.required_confidence = self.config.get('required_confidence', 0.75)
        self.min_modalities = self.config.get('min_modalities', 1)
        self.max_fraud_risk = self.config.get('max_fraud_risk', 0.6)
        self.min_quality_score = self.config.get('min_quality_score', 0.3)

    def fuse_decisions(
        self,
        modality_results: Dict[str, Dict],
        security_analysis: Dict[str, Any],
        quality_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform intelligent multi-modal decision fusion.

        Args:
            modality_results: Dictionary of results from each modality
                {
                    'face_recognition': {'verified': True, 'confidence': 0.9, ...},
                    'voice_recognition': {'verified': True, 'confidence': 0.85, ...},
                    'behavioral_biometrics': {'verified': False, 'confidence': 0.6, ...}
                }
            security_analysis: Security analysis results
                {
                    'deepfake_detected': False,
                    '3d_liveness_detected': True,
                    'advanced_liveness_score': 0.85
                }
            quality_metrics: Quality assessment metrics
                {
                    'overall_quality': 0.8,
                    'sharpness': 0.85,
                    'brightness': 0.75
                }

        Returns:
            Dictionary containing:
                - verified: Final verification decision (boolean)
                - confidence: Final confidence score (0.0-1.0)
                - fraud_risk_score: Fraud risk score (0.0-1.0)
                - verified_modalities: List of successfully verified modalities
                - quality_score: Overall quality score
                - security_penalty: Applied security penalty
                - recommendations: List of recommendation strings
                - detailed_scores: Detailed scoring breakdown
        """
        try:
            # Extract verification results and confidence scores
            verified_modalities = []
            confidence_scores = []

            for modality, result in modality_results.items():
                if result.get('verified', False):
                    verified_modalities.append(modality)

                confidence = result.get('confidence', 0.0)
                weight = self.modality_weights.get(modality, 0.1)
                confidence_scores.append(confidence * weight)

            # Calculate weighted confidence
            total_weight = sum(
                self.modality_weights.get(mod, 0.1)
                for mod in modality_results.keys()
            )
            weighted_confidence = sum(confidence_scores) / total_weight if total_weight > 0 else 0.0

            # Security penalties
            security_penalty = 0.0
            fraud_risk_score = 0.0

            if security_analysis.get('deepfake_detected', False):
                security_penalty += 0.5
                fraud_risk_score += 0.4

            if not security_analysis.get('3d_liveness_detected', True):
                security_penalty += 0.3
                fraud_risk_score += 0.3

            if security_analysis.get('advanced_liveness_score', 1.0) < 0.5:
                security_penalty += 0.2
                fraud_risk_score += 0.2

            # Quality adjustments
            quality_score = quality_metrics.get('overall_quality', 0.0)
            if quality_score < 0.5:
                security_penalty += 0.1
                fraud_risk_score += 0.1

            # Apply penalties
            final_confidence = max(0.0, weighted_confidence - security_penalty)
            final_fraud_risk = min(1.0, fraud_risk_score)

            # Decision logic
            verified = (
                len(verified_modalities) >= self.min_modalities and
                final_confidence >= self.required_confidence and
                final_fraud_risk < self.max_fraud_risk and
                quality_score >= self.min_quality_score
            )

            # Generate recommendations
            recommendations = []
            if not verified:
                if len(verified_modalities) == 0:
                    recommendations.append("No biometric modalities successfully verified")
                if final_confidence < self.required_confidence:
                    recommendations.append(
                        f"Confidence too low: {final_confidence:.2f} < {self.required_confidence}"
                    )
                if final_fraud_risk >= self.max_fraud_risk:
                    recommendations.append(f"High fraud risk detected: {final_fraud_risk:.2f}")
                if quality_score < self.min_quality_score:
                    recommendations.append(f"Image quality too low: {quality_score:.2f}")

            return {
                'verified': verified,
                'confidence': float(final_confidence),
                'fraud_risk_score': float(final_fraud_risk),
                'verified_modalities': verified_modalities,
                'quality_score': float(quality_score),
                'security_penalty': float(security_penalty),
                'recommendations': recommendations,
                'detailed_scores': {
                    'weighted_confidence': float(weighted_confidence),
                    'security_penalty': float(security_penalty),
                    'quality_score': float(quality_score),
                    'fraud_risk': float(final_fraud_risk)
                }
            }

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error in multi-modal decision fusion: {str(e)}")
            return {
                'verified': False,
                'confidence': 0.0,
                'fraud_risk_score': 1.0,
                'error': str(e),
                'recommendations': ['Error in decision fusion process'],
                'verified_modalities': [],
                'quality_score': 0.0,
                'security_penalty': 0.0
            }

    def update_weights(self, new_weights: Dict[str, float]):
        """
        Update modality weights for fusion.

        Args:
            new_weights: New weights for each modality
        """
        self.modality_weights.update(new_weights)
        logger.info(f"Updated modality weights: {self.modality_weights}")

    def update_thresholds(
        self,
        required_confidence: float = None,
        min_modalities: int = None,
        max_fraud_risk: float = None,
        min_quality_score: float = None
    ):
        """
        Update decision thresholds.

        Args:
            required_confidence: Minimum confidence required for verification
            min_modalities: Minimum number of modalities required
            max_fraud_risk: Maximum acceptable fraud risk score
            min_quality_score: Minimum quality score required
        """
        if required_confidence is not None:
            self.required_confidence = required_confidence
        if min_modalities is not None:
            self.min_modalities = min_modalities
        if max_fraud_risk is not None:
            self.max_fraud_risk = max_fraud_risk
        if min_quality_score is not None:
            self.min_quality_score = min_quality_score

        logger.info(
            f"Updated thresholds: confidence={self.required_confidence}, "
            f"modalities={self.min_modalities}, fraud_risk={self.max_fraud_risk}, "
            f"quality={self.min_quality_score}"
        )
