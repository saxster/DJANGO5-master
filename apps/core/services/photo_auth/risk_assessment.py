"""
Photo authenticity risk assessment and decision making.

Handles:
- Comprehensive risk scoring
- Authentication decision logic
- Recommendation generation
- Threshold management

Complies with .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from typing import Dict, Any, List
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class RiskAssessment:
    """Risk assessment and authentication decision engine."""

    # Risk thresholds for different validation scenarios
    RISK_THRESHOLDS = {
        'attendance': {
            'low_risk': 0.8,      # High authenticity required for attendance
            'medium_risk': 0.6,
            'high_risk': 0.4
        },
        'facility_audit': {
            'low_risk': 0.7,      # Moderate authenticity for audits
            'medium_risk': 0.5,
            'high_risk': 0.3
        },
        'incident_report': {
            'low_risk': 0.9,      # Very high authenticity for incidents
            'medium_risk': 0.7,
            'high_risk': 0.5
        },
        'general': {
            'low_risk': 0.6,      # Lower threshold for general photos
            'medium_risk': 0.4,
            'high_risk': 0.2
        }
    }

    @classmethod
    def calculate_comprehensive_risk(
        cls,
        validation_results: List[Dict[str, Any]],
        upload_type: str,
        validation_level: str
    ) -> Dict[str, Any]:
        """Calculate comprehensive risk assessment."""
        try:
            # Collect authenticity scores and fraud indicators
            authenticity_scores = []
            all_fraud_indicators = []
            confidence_factors = []

            for result in validation_results:
                if result.get('status') == 'completed':
                    score = result.get('authenticity_score', 0.5)
                    authenticity_scores.append(score)
                    confidence_factors.append(1.0)
                elif result.get('status') == 'error':
                    authenticity_scores.append(0.3)  # Penalize errors
                    confidence_factors.append(0.5)

                all_fraud_indicators.extend(result.get('fraud_indicators', []))

            # Calculate weighted authenticity score
            if authenticity_scores:
                weighted_authenticity = sum(
                    score * weight for score, weight in zip(authenticity_scores, confidence_factors)
                ) / sum(confidence_factors)
            else:
                weighted_authenticity = 0.5

            # Calculate confidence level
            confidence_level = sum(confidence_factors) / len(validation_results) if validation_results else 0.5

            # Determine risk level based on thresholds
            thresholds = cls.RISK_THRESHOLDS.get(upload_type, cls.RISK_THRESHOLDS['general'])

            if weighted_authenticity >= thresholds['low_risk']:
                risk_level = 'low'
            elif weighted_authenticity >= thresholds['medium_risk']:
                risk_level = 'medium'
            elif weighted_authenticity >= thresholds['high_risk']:
                risk_level = 'high'
            else:
                risk_level = 'critical'

            return {
                'authenticity_score': weighted_authenticity,
                'confidence_level': confidence_level,
                'risk_level': risk_level,
                'fraud_indicators': list(set(all_fraud_indicators)),
                'validation_count': len(validation_results),
                'successful_validations': len([r for r in validation_results if r.get('status') == 'completed']),
                'thresholds_used': thresholds
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Comprehensive risk calculation failed: {e}", exc_info=True)
            return {
                'authenticity_score': 0.1,
                'confidence_level': 0.1,
                'risk_level': 'critical',
                'fraud_indicators': ['RISK_CALCULATION_FAILED'],
                'error': str(e)
            }

    @classmethod
    def make_authentication_decision(
        cls,
        risk_assessment: Dict[str, Any],
        upload_type: str,
        validation_level: str
    ) -> Dict[str, Any]:
        """Make final authentication decision."""
        try:
            authenticity_score = risk_assessment.get('authenticity_score', 0.0)
            risk_level = risk_assessment.get('risk_level', 'critical')
            fraud_indicators = risk_assessment.get('fraud_indicators', [])

            # Determine authentication result
            if risk_level in ['critical', 'high']:
                authenticated = False
                requires_manual_review = True
                compliance_status = 'failed'
            elif risk_level == 'medium':
                authenticated = (validation_level != 'strict')
                requires_manual_review = (validation_level == 'strict')
                compliance_status = 'conditional'
            else:  # low risk
                authenticated = True
                requires_manual_review = False
                compliance_status = 'passed'

            # Override for specific fraud indicators
            critical_indicators = [
                'BLOCKED_DEVICE', 'PHOTO_MANIPULATION_DETECTED',
                'EXIF_GPS_IMPOSSIBLE_DISTANCE', 'HIGH_FRAUD_DEVICE'
            ]

            if any(indicator in fraud_indicators for indicator in critical_indicators):
                authenticated = False
                requires_manual_review = True
                compliance_status = 'failed'

            return {
                'authenticated': authenticated,
                'requires_manual_review': requires_manual_review,
                'compliance_status': compliance_status,
                'decision_factors': {
                    'risk_level': risk_level,
                    'validation_level': validation_level,
                    'critical_indicators_present': any(
                        indicator in fraud_indicators for indicator in critical_indicators
                    )
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Authentication decision failed: {e}", exc_info=True)
            return {
                'authenticated': False,
                'requires_manual_review': True,
                'compliance_status': 'error',
                'decision_factors': {'error': str(e)}
            }

    @classmethod
    def generate_recommendations(
        cls,
        auth_result: Dict[str, Any],
        validation_level: str
    ) -> List[str]:
        """Generate actionable recommendations based on authentication results."""
        recommendations = []

        try:
            risk_level = auth_result.get('risk_assessment', {}).get('risk_level', 'unknown')
            fraud_indicators = auth_result.get('risk_assessment', {}).get('fraud_indicators', [])
            authenticity_score = auth_result.get('authenticity_score', 0.0)

            # General recommendations based on risk level
            if risk_level == 'critical':
                recommendations.append("CRITICAL: Photo rejected - manual investigation required")
                recommendations.append("Do not accept this photo for any official purpose")

            elif risk_level == 'high':
                recommendations.append("HIGH RISK: Require manual verification before acceptance")
                recommendations.append("Consider requesting alternative photo from different angle")

            elif risk_level == 'medium':
                recommendations.append("MEDIUM RISK: Additional verification recommended")
                recommendations.append("Monitor user for pattern analysis")

            # Specific recommendations based on fraud indicators
            if 'PHOTO_MANIPULATION_DETECTED' in fraud_indicators:
                recommendations.append("Photo shows signs of editing - request original unedited photo")

            if 'BLOCKED_DEVICE' in fraud_indicators:
                recommendations.append("Photo taken with blocked device - security review required")

            if 'EXIF_GPS_GEOFENCE_VIOLATION' in fraud_indicators:
                recommendations.append("GPS location outside allowed area - verify user location")

            if 'MISSING_CRITICAL_EXIF_DATA' in fraud_indicators:
                recommendations.append("Photo lacks metadata - request photo with location services enabled")

            # Quality improvement recommendations
            if authenticity_score < 0.6:
                recommendations.append("Consider implementing stricter photo validation policies")
                recommendations.append("Provide user training on proper photo capture techniques")

            # No issues found
            if not recommendations and auth_result.get('authenticated'):
                recommendations.append("Photo meets authenticity standards - approved for use")

            return recommendations

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Recommendation generation failed: {e}", exc_info=True)
            return ["Manual review recommended due to system error"]
