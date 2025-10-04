"""
Security Monitoring Engine

Monitors biometric authentication, fraud detection, and security anomalies.
Provides advanced security alerting and threat detection.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.utils import timezone
from django.db.models import Q, Count

from apps.face_recognition.models import FaceVerificationLog
from apps.voice_recognition.models import VoiceVerificationLog
from apps.noc.security_intelligence.models import (
    BiometricVerificationLog, BehavioralProfile
)
from apps.monitoring.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """
    Advanced security monitoring for biometric and behavioral anomalies.

    Features:
    - Biometric authentication failure tracking
    - Concurrent device usage detection
    - Behavioral anomaly detection
    - Fraud risk assessment
    - Security pattern analysis
    """

    def __init__(self):
        self.alert_service = AlertService()

        # Security thresholds
        self.MAX_FAILED_ATTEMPTS = 3         # Max failed attempts before alert
        self.CONCURRENT_DETECTION_MINUTES = 5  # Detect concurrent usage within 5 minutes
        self.FRAUD_RISK_THRESHOLD = 0.7      # Fraud risk threshold
        self.LOW_CONFIDENCE_THRESHOLD = 0.6  # Low biometric confidence threshold

    def monitor_security_status(self, user_id: int, device_id: str) -> Dict:
        """Monitor security status for a user/device"""
        try:
            # Get recent biometric attempts
            biometric_data = self._get_recent_biometric_data(user_id, hours=1)

            # Check for concurrent device usage
            concurrent_usage = self._check_concurrent_usage(user_id, device_id)

            # Analyze behavioral patterns
            behavioral_analysis = self._analyze_behavioral_patterns(user_id)

            # Calculate security metrics
            metrics = self._calculate_security_metrics(biometric_data, concurrent_usage, behavioral_analysis)

            # Evaluate security alerts
            alerts = self._evaluate_security_alerts(
                user_id, device_id, biometric_data, metrics, concurrent_usage, behavioral_analysis
            )

            return {
                'status': 'success',
                'biometric_data': biometric_data,
                'concurrent_usage': concurrent_usage,
                'behavioral_analysis': behavioral_analysis,
                'metrics': metrics,
                'alerts': alerts,
                'recommendations': self._generate_security_recommendations(metrics)
            }

        except Exception as e:
            logger.error(f"Error monitoring security for user {user_id}: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e), 'alerts': []}

    def _get_recent_biometric_data(self, user_id: int, hours: int = 1) -> Dict:
        """Get recent biometric verification data"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            # Get face verification attempts
            face_attempts = FaceVerificationLog.objects.filter(
                user_id=user_id,
                timestamp__gte=cutoff_time
            ).order_by('-timestamp')

            # Get voice verification attempts
            voice_attempts = VoiceVerificationLog.objects.filter(
                user_id=user_id,
                created_at__gte=cutoff_time
            ).order_by('-created_at')

            return {
                'face_verifications': [{
                    'timestamp': attempt.timestamp.isoformat(),
                    'verified': attempt.verified,
                    'confidence': attempt.confidence_score,
                    'quality': attempt.quality_score
                } for attempt in face_attempts],

                'voice_verifications': [{
                    'timestamp': attempt.created_at.isoformat(),
                    'verified': attempt.verified,
                    'confidence': attempt.confidence_score,
                    'quality': attempt.quality_score
                } for attempt in voice_attempts],

                'total_attempts': face_attempts.count() + voice_attempts.count(),
                'failed_attempts': (
                    face_attempts.filter(verified=False).count() +
                    voice_attempts.filter(verified=False).count()
                )
            }

        except Exception as e:
            logger.error(f"Error getting biometric data: {str(e)}")
            return {'total_attempts': 0, 'failed_attempts': 0}

    def _check_concurrent_usage(self, user_id: int, device_id: str) -> Dict:
        """Check for concurrent device usage by the same user"""
        try:
            cutoff_time = timezone.now() - timedelta(minutes=self.CONCURRENT_DETECTION_MINUTES)

            # Check for recent activity from different devices
            recent_devices = DeviceEventlog.objects.filter(
                people_id=user_id,
                receivedon__gte=cutoff_time
            ).exclude(
                deviceid=device_id
            ).values('deviceid').distinct()

            concurrent_devices = list(recent_devices)

            return {
                'has_concurrent_usage': len(concurrent_devices) > 0,
                'concurrent_devices': [d['deviceid'] for d in concurrent_devices],
                'concurrent_count': len(concurrent_devices),
                'detection_window_minutes': self.CONCURRENT_DETECTION_MINUTES
            }

        except Exception as e:
            logger.error(f"Error checking concurrent usage: {str(e)}")
            return {'has_concurrent_usage': False, 'concurrent_devices': []}

    def _analyze_behavioral_patterns(self, user_id: int) -> Dict:
        """Analyze behavioral patterns for anomaly detection"""
        try:
            # Get behavioral profile if available
            try:
                behavioral_profile = BehavioralProfile.objects.get(person_id=user_id)

                return {
                    'has_profile': True,
                    'fraud_baseline': behavioral_profile.baseline_fraud_score,
                    'pattern_confidence': behavioral_profile.pattern_confidence,
                    'total_observations': behavioral_profile.total_observations,
                    'anomaly_threshold': behavioral_profile.anomaly_detection_threshold,
                    'is_sufficient_data': behavioral_profile.is_sufficient_data
                }

            except BehavioralProfile.DoesNotExist:
                return {
                    'has_profile': False,
                    'fraud_baseline': 0,
                    'pattern_confidence': 0,
                    'needs_profile_creation': True
                }

        except Exception as e:
            logger.error(f"Error analyzing behavioral patterns: {str(e)}")
            return {'has_profile': False, 'error': str(e)}

    def _calculate_security_metrics(self, biometric_data: Dict, concurrent_usage: Dict, behavioral_analysis: Dict) -> Dict:
        """Calculate security metrics"""
        metrics = {
            'authentication_success_rate': 100,
            'average_biometric_confidence': 1.0,
            'fraud_risk_score': 0,
            'security_incident_count': 0,
            'behavioral_anomaly_score': 0,
            'overall_security_score': 100
        }

        try:
            # Calculate authentication success rate
            total_attempts = biometric_data.get('total_attempts', 0)
            failed_attempts = biometric_data.get('failed_attempts', 0)

            if total_attempts > 0:
                success_rate = ((total_attempts - failed_attempts) / total_attempts) * 100
                metrics['authentication_success_rate'] = success_rate

            # Calculate average confidence
            all_confidences = []

            for verification in biometric_data.get('face_verifications', []):
                if verification.get('confidence') is not None:
                    all_confidences.append(verification['confidence'])

            for verification in biometric_data.get('voice_verifications', []):
                if verification.get('confidence') is not None:
                    all_confidences.append(verification['confidence'])

            if all_confidences:
                metrics['average_biometric_confidence'] = np.mean(all_confidences)

            # Calculate fraud risk score
            fraud_indicators = 0

            if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                fraud_indicators += 0.3

            if concurrent_usage.get('has_concurrent_usage', False):
                fraud_indicators += 0.4

            if metrics['average_biometric_confidence'] < self.LOW_CONFIDENCE_THRESHOLD:
                fraud_indicators += 0.2

            metrics['fraud_risk_score'] = min(1.0, fraud_indicators)

            # Count security incidents
            incident_count = 0
            if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                incident_count += 1
            if concurrent_usage.get('has_concurrent_usage', False):
                incident_count += 1

            metrics['security_incident_count'] = incident_count

            # Calculate overall security score
            base_score = 100
            base_score -= (failed_attempts * 10)  # -10 per failed attempt
            base_score -= (concurrent_usage.get('concurrent_count', 0) * 20)  # -20 per concurrent device
            base_score -= (metrics['fraud_risk_score'] * 30)  # -30 for high fraud risk

            metrics['overall_security_score'] = max(0, base_score)

        except Exception as e:
            logger.error(f"Error calculating security metrics: {str(e)}")

        return metrics

    def _evaluate_security_alerts(self, user_id: int, device_id: str, biometric_data: Dict,
                                 metrics: Dict, concurrent_usage: Dict, behavioral_analysis: Dict) -> List[Dict]:
        """Evaluate security conditions and create alerts"""
        alerts = []

        try:
            # Multiple failed authentication attempts
            failed_attempts = biometric_data.get('failed_attempts', 0)
            if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                alert = self._create_security_alert(
                    user_id, device_id, 'BIOMETRIC_FAILURE',
                    f"Multiple authentication failures: {failed_attempts} attempts",
                    'HIGH', biometric_data, metrics
                )
                alerts.append(alert)

            # Concurrent device usage
            if concurrent_usage.get('has_concurrent_usage', False):
                concurrent_devices = concurrent_usage.get('concurrent_devices', [])
                alert = self._create_security_alert(
                    user_id, device_id, 'CONCURRENT_USAGE',
                    f"Concurrent device usage detected: {len(concurrent_devices)} other devices active",
                    'CRITICAL', biometric_data, metrics
                )
                alerts.append(alert)

            # High fraud risk
            fraud_risk = metrics.get('fraud_risk_score', 0)
            if fraud_risk >= self.FRAUD_RISK_THRESHOLD:
                alert = self._create_security_alert(
                    user_id, device_id, 'FRAUD_RISK',
                    f"High fraud risk detected: {fraud_risk:.1%} probability",
                    'CRITICAL', biometric_data, metrics
                )
                alerts.append(alert)

            # Low biometric confidence
            avg_confidence = metrics.get('average_biometric_confidence', 1.0)
            if avg_confidence < self.LOW_CONFIDENCE_THRESHOLD:
                alert = self._create_security_alert(
                    user_id, device_id, 'LOW_BIOMETRIC_CONFIDENCE',
                    f"Low biometric confidence: {avg_confidence:.1%}",
                    'WARNING', biometric_data, metrics
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error evaluating security alerts: {str(e)}")

        return [alert for alert in alerts if alert is not None]

    def _create_security_alert(self, user_id: int, device_id: str, alert_type: str,
                              description: str, severity: str, biometric_data: Dict, metrics: Dict) -> Optional[Dict]:
        """Create a security-related alert"""
        try:
            alert_data = {
                'user_id': user_id,
                'device_id': device_id,
                'alert_type': alert_type,
                'severity': severity,
                'title': f"Security Alert: {alert_type.replace('_', ' ').title()}",
                'description': description,
                'alert_data': {
                    'failed_attempts': biometric_data.get('failed_attempts', 0),
                    'avg_biometric_confidence': metrics.get('average_biometric_confidence', 1.0),
                    'fraud_risk_score': metrics.get('fraud_risk_score', 0),
                    'security_incident_count': metrics.get('security_incident_count', 0),
                    'timestamp': timezone.now().isoformat()
                },
                'context_data': {
                    'security_metrics': metrics,
                    'biometric_summary': biometric_data
                }
            }

            alert = self.alert_service.create_alert(alert_data)

            if alert:
                return {
                    'alert_id': str(alert.alert_id),
                    'type': alert_type,
                    'severity': severity,
                    'description': description,
                    'created_at': alert.triggered_at.isoformat()
                }

        except Exception as e:
            logger.error(f"Error creating security alert: {str(e)}")

        return None

    def _generate_security_recommendations(self, metrics: Dict) -> List[str]:
        """Generate security recommendations"""
        recommendations = []

        try:
            fraud_risk = metrics.get('fraud_risk_score', 0)
            if fraud_risk > 0.5:
                recommendations.append("Verify user identity through additional means")
                recommendations.append("Review recent activity for suspicious patterns")

            auth_success_rate = metrics.get('authentication_success_rate', 100)
            if auth_success_rate < 80:
                recommendations.append("Check biometric sensor quality")
                recommendations.append("Ensure proper lighting for face recognition")

            overall_score = metrics.get('overall_security_score', 100)
            if overall_score < 70:
                recommendations.append("Enhanced security monitoring recommended")

        except Exception as e:
            logger.error(f"Error generating security recommendations: {str(e)}")

        return recommendations