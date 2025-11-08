"""
Fraud Detection Orchestrator

Coordinates all fraud detection modules for comprehensive analysis.

Features:
- Real-time fraud scoring
- Multi-detector aggregation
- Risk level determination
- Auto-blocking for high-risk activity
- Manager alert generation

Detectors:
- BehavioralAnomalyDetector: Pattern-based detection
- TemporalAnomalyDetector: Time-based detection
- LocationAnomalyDetector: GPS-based detection
- DeviceFingerprintingDetector: Device-based detection
"""

from typing import Dict, Any, List, Optional
from django.utils import timezone
from apps.attendance.models import PeopleEventlog
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
from apps.attendance.ml_models import (
    BehavioralAnomalyDetector,
    TemporalAnomalyDetector,
    LocationAnomalyDetector,
    DeviceFingerprintingDetector,
)
import logging
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS


logger = logging.getLogger(__name__)


class FraudDetectionOrchestrator:
    """
    Orchestrates all fraud detection modules.

    Provides unified interface for fraud detection across all attendance operations.
    """

    # Risk level thresholds
    RISK_CRITICAL = 0.8  # Auto-block
    RISK_HIGH = 0.6  # Manager review required
    RISK_MEDIUM = 0.4  # Flag for monitoring
    RISK_LOW = 0.2  # Normal

    def __init__(self, employee):
        """
        Initialize orchestrator for an employee.

        Args:
            employee: User object
        """
        self.employee = employee

        # Initialize all detectors
        self.behavioral_detector = BehavioralAnomalyDetector(employee)
        self.temporal_detector = TemporalAnomalyDetector(employee)
        self.location_detector = LocationAnomalyDetector(employee)
        self.device_detector = DeviceFingerprintingDetector(employee)

    def analyze_attendance(self, attendance_record) -> Dict[str, Any]:
        """
        Comprehensive fraud analysis of attendance record.

        Args:
            attendance_record: PeopleEventlog instance to analyze

        Returns:
            Complete fraud analysis with risk score and recommendations
        """
        try:
            # Run all detectors
            behavioral_result = self.behavioral_detector.detect_anomalies(attendance_record)
            temporal_result = self.temporal_detector.detect_anomalies(attendance_record)
            location_result = self.location_detector.detect_anomalies(attendance_record)
            device_result = self.device_detector.detect_anomalies(attendance_record)

            # Aggregate anomalies
            all_anomalies = []
            all_anomalies.extend(behavioral_result.get('anomalies_detected', []))
            all_anomalies.extend(temporal_result.get('anomalies', []))
            all_anomalies.extend(location_result.get('anomalies', []))
            all_anomalies.extend(device_result.get('anomalies', []))

            # Calculate weighted composite score
            composite_score = self._calculate_composite_score(
                behavioral_score=behavioral_result.get('anomaly_score', 0.0),
                temporal_score=temporal_result.get('temporal_score', 0.0),
                location_score=location_result.get('location_score', 0.0),
                device_score=device_result.get('device_score', 0.0),
            )

            # Determine risk level
            risk_level = self._determine_risk_level(composite_score)

            # Determine if should block
            should_block = composite_score >= self.RISK_CRITICAL

            # Generate recommendations
            recommendations = self._generate_recommendations(
                all_anomalies,
                composite_score,
                risk_level
            )

            # Compile comprehensive result
            result = {
                'timestamp': timezone.now().isoformat(),
                'employee_id': self.employee.id,
                'employee_username': self.employee.username,
                'attendance_record_id': attendance_record.id,
                'analysis': {
                    'composite_score': round(composite_score, 3),
                    'risk_level': risk_level,
                    'should_block': should_block,
                    'anomaly_count': len(all_anomalies),
                },
                'detector_scores': {
                    'behavioral': round(behavioral_result.get('anomaly_score', 0.0), 3),
                    'temporal': round(temporal_result.get('temporal_score', 0.0), 3),
                    'location': round(location_result.get('location_score', 0.0), 3),
                    'device': round(device_result.get('device_score', 0.0), 3),
                },
                'anomalies': all_anomalies,
                'recommendations': recommendations,
                'detector_details': {
                    'behavioral': behavioral_result,
                    'temporal': temporal_result,
                    'location': location_result,
                    'device': device_result,
                },
            }

            # Log if anomalous
            if composite_score >= self.RISK_MEDIUM:
                logger.warning(
                    f"Fraud detected for {self.employee.username}: "
                    f"score={composite_score:.3f}, level={risk_level}, anomalies={len(all_anomalies)}"
                )

            return result

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Fraud detection failed for {self.employee.username}: {e}", exc_info=True)
            return {
                'error': str(e),
                'composite_score': 0.0,
                'risk_level': 'UNKNOWN',
                'should_block': False,
            }

    def _calculate_composite_score(
        self,
        behavioral_score: float,
        temporal_score: float,
        location_score: float,
        device_score: float
    ) -> float:
        """
        Calculate weighted composite fraud score.

        Weights:
        - Behavioral: 30%
        - Temporal: 20%
        - Location: 30%
        - Device: 20%

        Args:
            behavioral_score: Score from behavioral detector
            temporal_score: Score from temporal detector
            location_score: Score from location detector
            device_score: Score from device detector

        Returns:
            Composite score (0-1)
        """
        composite = (
            behavioral_score * 0.30 +
            temporal_score * 0.20 +
            location_score * 0.30 +
            device_score * 0.20
        )

        return min(composite, 1.0)

    def _determine_risk_level(self, composite_score: float) -> str:
        """
        Determine risk level from composite score.

        Args:
            composite_score: Fraud score (0-1)

        Returns:
            Risk level string
        """
        if composite_score >= self.RISK_CRITICAL:
            return 'CRITICAL'
        elif composite_score >= self.RISK_HIGH:
            return 'HIGH'
        elif composite_score >= self.RISK_MEDIUM:
            return 'MEDIUM'
        elif composite_score >= self.RISK_LOW:
            return 'LOW'
        else:
            return 'MINIMAL'

    def _generate_recommendations(
        self,
        anomalies: List[Dict[str, Any]],
        composite_score: float,
        risk_level: str
    ) -> List[str]:
        """
        Generate recommendations based on detected anomalies.

        Args:
            anomalies: List of detected anomalies
            composite_score: Overall fraud score
            risk_level: Determined risk level

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if risk_level == 'CRITICAL':
            recommendations.append("BLOCK: Auto-block this attendance entry pending investigation")
            recommendations.append("Notify manager immediately for verification")
            recommendations.append("Require in-person verification before approval")

        elif risk_level == 'HIGH':
            recommendations.append("REVIEW: Manager review required before approval")
            recommendations.append("Request additional verification from employee")

        elif risk_level == 'MEDIUM':
            recommendations.append("MONITOR: Flag for manager awareness")
            recommendations.append("Increase monitoring frequency for this employee")

        # Specific recommendations based on anomaly types
        anomaly_types = [a['type'] for a in anomalies]

        if 'device_sharing' in anomaly_types:
            recommendations.append("Investigate possible buddy punching")

        if 'impossible_travel' in anomaly_types:
            recommendations.append("Verify GPS coordinates are not spoofed")

        if 'null_island_spoofing' in anomaly_types:
            recommendations.append("GPS spoofing detected - reject attendance entry")

        if 'insufficient_rest' in anomaly_types:
            recommendations.append("Verify employee is complying with rest period requirements")

        return recommendations

    def train_employee_baseline(self, force_retrain: bool = False) -> bool:
        """
        Train baseline for employee.

        Args:
            force_retrain: Force retraining even if baseline exists

        Returns:
            True if training successful
        """
        return self.behavioral_detector.train_baseline(force_retrain=force_retrain)

    @classmethod
    def train_all_baselines(cls, force_retrain: bool = False) -> Dict[str, int]:
        """
        Train baselines for all employees.

        Args:
            force_retrain: Force retraining for all

        Returns:
            Dict with training statistics
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get all active employees with attendance records
        employees_with_attendance = PeopleEventlog.objects.filter(
            punchintime__isnull=False
        ).values('people').distinct()

        employee_ids = [e['people'] for e in employees_with_attendance if e['people']]
        # Optimize: select_related to avoid N+1 when accessing employee properties in loop
        employees = User.objects.filter(id__in=employee_ids).select_related('profile', 'organizational')

        trained = 0
        failed = 0
        insufficient_data = 0

        for employee in employees:
            try:
                orchestrator = cls(employee)
                success = orchestrator.train_employee_baseline(force_retrain=force_retrain)

                if success:
                    trained += 1
                else:
                    insufficient_data += 1

            except BUSINESS_LOGIC_EXCEPTIONS as e:
                logger.error(f"Failed to train baseline for {employee.username}: {e}", exc_info=True)
                failed += 1

        logger.info(
            f"Baseline training complete: "
            f"trained={trained}, insufficient_data={insufficient_data}, failed={failed}"
        )

        return {
            'trained': trained,
            'insufficient_data': insufficient_data,
            'failed': failed,
            'total': trained + insufficient_data + failed,
        }

    @classmethod
    def analyze_batch(cls, attendance_records: List) -> List[Dict[str, Any]]:
        """
        Analyze multiple attendance records efficiently.

        Args:
            attendance_records: List of PeopleEventlog instances

        Returns:
            List of analysis results
        """
        results = []

        # Group by employee for efficiency
        from collections import defaultdict
        by_employee = defaultdict(list)

        for record in attendance_records:
            if record.people:
                by_employee[record.people.id].append(record)

        # Analyze each employee's records
        for employee_id, records in by_employee.items():
            try:
                employee = records[0].people  # Get employee from first record
                orchestrator = cls(employee)

                for record in records:
                    analysis = orchestrator.analyze_attendance(record)
                    results.append(analysis)

            except BUSINESS_LOGIC_EXCEPTIONS as e:
                logger.error(f"Batch analysis failed for employee {employee_id}: {e}", exc_info=True)

        return results
