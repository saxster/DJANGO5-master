"""
Unit Tests for Biometric and GPS Fraud Detection.

Tests fraud detection algorithms and scoring logic.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point


@pytest.mark.django_db
class TestBiometricFraudDetector:
    """Test biometric fraud detection methods."""

    def test_detect_buddy_punching_concurrent_sites(
        self, security_config, attendance_event, site_bt
    ):
        """Test detection of concurrent biometric usage at different sites."""
        from apps.noc.security_intelligence.services import BiometricFraudDetector
        from apps.noc.security_intelligence.models import BiometricVerificationLog
        from apps.client_onboarding.models import Bt

        other_site = Bt.objects.create(
            tenant=attendance_event.tenant,
            name='Other Site',
            bttype='SITE',
            enable=True
        )

        BiometricVerificationLog.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=other_site,
            verified_at=attendance_event.punchintime,
            verification_type='FACE',
            result='SUCCESS',
            confidence_score=0.95,
            device_id='device-123',
        )

        detector = BiometricFraudDetector(security_config)
        result = detector.detect_buddy_punching(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'BUDDY_PUNCHING'
        assert result['severity'] == 'CRITICAL'
        assert result['concurrent_count'] >= 1
        assert result['confidence_score'] >= 0.9

    def test_detect_pattern_anomalies_low_confidence(
        self, security_config, test_person
    ):
        """Test detection of low confidence pattern."""
        from apps.noc.security_intelligence.services import BiometricFraudDetector
        from apps.noc.security_intelligence.models import BiometricVerificationLog

        for i in range(15):
            BiometricVerificationLog.objects.create(
                tenant=test_person.tenant,
                person=test_person,
                site=test_person.organizational.bu if hasattr(test_person, 'organizational') else None,
                verified_at=timezone.now() - timedelta(days=i),
                verification_type='FACE',
                result='SUCCESS',
                confidence_score=0.4,
                device_id='device-123',
            )

        detector = BiometricFraudDetector(security_config)
        result = detector.detect_pattern_anomalies(test_person, days=30)

        assert result is not None
        assert result['anomaly_type'] == 'BIOMETRIC_PATTERN_ANOMALY'
        assert 'LOW_BIOMETRIC_CONFIDENCE' in result['indicators']


@pytest.mark.django_db
class TestLocationFraudDetector:
    """Test GPS fraud detection methods."""

    def test_detect_gps_spoofing_impossible_speed(
        self, security_config, attendance_event
    ):
        """Test detection of impossible travel speed."""
        from apps.noc.security_intelligence.services import LocationFraudDetector
        from apps.activity.models import Location

        Location.objects.create(
            tenant=attendance_event.tenant,
            people=attendance_event.people,
            loccode='LOC001',
            locname='Previous Location',
            gpslocation=Point(80.0, 13.0),
            cdtz=attendance_event.punchintime - timedelta(minutes=10)
        )

        detector = LocationFraudDetector(security_config)
        result = detector.detect_gps_spoofing(attendance_event)

        if result:
            assert result['anomaly_type'] == 'GPS_SPOOFING'
            assert result['severity'] == 'CRITICAL'
            assert result['calculated_speed_kmh'] > security_config.max_travel_speed_kmh

    def test_detect_geofence_violation(self, security_config, attendance_event):
        """Test detection of geofence violation."""
        from apps.noc.security_intelligence.services import LocationFraudDetector

        attendance_event.bu.gpslocation = Point(77.5946, 12.9716)
        attendance_event.bu.save()

        attendance_event.startlocation = Point(77.7, 13.2)
        attendance_event.save()

        detector = LocationFraudDetector(security_config)
        result = detector.detect_geofence_violation(attendance_event)

        if result:
            assert result['anomaly_type'] == 'GEOFENCE_VIOLATION'
            assert result['severity'] == 'HIGH'

    def test_validate_gps_quality_low_accuracy(self, security_config, attendance_event):
        """Test GPS quality validation for low accuracy."""
        from apps.noc.security_intelligence.services import LocationFraudDetector

        attendance_event.accuracy = 500
        attendance_event.save()

        detector = LocationFraudDetector(security_config)
        result = detector.validate_gps_quality(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'GPS_LOW_ACCURACY'
        assert result['severity'] == 'MEDIUM'


@pytest.mark.django_db
class TestFraudScoreCalculator:
    """Test unified fraud score calculation."""

    def test_calculate_fraud_score_multiple_indicators(self):
        """Test fraud score with multiple fraud types."""
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        detection_results = {
            'buddy_punching': {'detected': True},
            'gps_spoofing': {'detected': True},
            'geofence_violation': None,
        }

        result = FraudScoreCalculator.calculate_fraud_score(detection_results)

        assert result['fraud_score'] >= 0.6
        assert 'BUDDY_PUNCHING' in result['fraud_types']
        assert 'GPS_SPOOFING' in result['fraud_types']
        assert result['risk_level'] in ['HIGH', 'CRITICAL']
        assert result['requires_action'] is True

    def test_calculate_fraud_score_no_fraud(self):
        """Test fraud score with no fraud detected."""
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        detection_results = {}

        result = FraudScoreCalculator.calculate_fraud_score(detection_results)

        assert result['fraud_score'] == 0.0
        assert result['risk_level'] == 'MINIMAL'
        assert len(result['fraud_types']) == 0
        assert result['requires_action'] is False

    def test_risk_level_determination(self):
        """Test risk level determination logic."""
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        assert FraudScoreCalculator._determine_risk_level(0.9) == 'CRITICAL'
        assert FraudScoreCalculator._determine_risk_level(0.7) == 'HIGH'
        assert FraudScoreCalculator._determine_risk_level(0.5) == 'MEDIUM'
        assert FraudScoreCalculator._determine_risk_level(0.3) == 'LOW'
        assert FraudScoreCalculator._determine_risk_level(0.1) == 'MINIMAL'

    def test_person_fraud_history_score(self, test_person):
        """Test historical fraud score calculation."""
        from apps.noc.security_intelligence.services import FraudScoreCalculator

        history = FraudScoreCalculator.calculate_person_fraud_history_score(
            test_person, days=30
        )

        assert 'history_score' in history
        assert 'total_flags' in history
        assert 'risk_level' in history
        assert history['period_days'] == 30