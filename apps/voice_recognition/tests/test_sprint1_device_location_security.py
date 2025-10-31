"""
Integration Tests for Sprint 1: Device Trust & Location Security

Tests the complete flow of device trust registry and location security
integration with voice enrollment service.

Following CLAUDE.md testing standards:
- Unit tests for each service
- Integration tests for full enrollment flow
- Security-focused edge cases
- Performance benchmarks

Created: 2025-10-11
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from apps.peoples.models import People, DeviceRegistration, DeviceRiskEvent
from apps.onboarding.models import ApprovedLocation, Bt
from apps.peoples.services.device_trust_service import DeviceTrustService
from apps.core.services.location_security_service import LocationSecurityService
from apps.voice_recognition.services.enrollment_service import VoiceEnrollmentService


@pytest.mark.django_db
class TestDeviceTrustRegistry(TestCase):
    """Test Device Trust Registry models and service."""

    def setUp(self):
        """Set up test data."""
        self.user = People.objects.create(
            peoplecode='TEST001',
            peoplename='Test User',
            loginid='testuser',
            mobno='+919876543210',
            email='test@example.com',
            is_active=True,
            enable=True
        )

        self.device_service = DeviceTrustService()

    def test_device_registration_creation(self):
        """Test device registration model creation."""
        device = DeviceRegistration.objects.create(
            device_id='test_device_123',
            user=self.user,
            device_fingerprint={'canvas': 'abc123'},
            user_agent='Mozilla/5.0',
            ip_address='192.168.1.100',
            trust_score=50,
            trust_factors={'known_device': 50},
            is_trusted=False
        )

        assert device.device_id == 'test_device_123'
        assert device.user == self.user
        assert device.trust_score == 50
        assert not device.is_trusted

    def test_device_trust_scoring_known_device(self):
        """Test trust scoring for known device."""
        # Create existing device
        DeviceRegistration.objects.create(
            device_id='known_device',
            user=self.user,
            device_fingerprint={'canvas': 'def456'},
            user_agent='Mozilla/5.0',
            ip_address='192.168.1.100',
            trust_score=50,
            is_trusted=True,
            biometric_enrolled=True
        )

        # Validate same device
        result = self.device_service.validate_device(
            user=self.user,
            user_agent='Mozilla/5.0',
            ip_address='192.168.1.100',
            fingerprint_data={'canvas': 'def456'}
        )

        # Known device (50) + Biometric enrolled (20) = 70 (threshold)
        assert result['passed']
        assert result['trust_score'] >= 70
        assert result['trust_factors']['known_device'] > 0

    def test_device_trust_scoring_corporate_network(self):
        """Test trust scoring for corporate network."""
        result = self.device_service.validate_device(
            user=self.user,
            user_agent='Mozilla/5.0',
            ip_address='10.0.0.50',  # Corporate IP
            fingerprint_data={'canvas': 'new123'}
        )

        # Corporate network gives +30 points
        assert result['trust_factors']['corporate_network'] > 0

    def test_device_risk_event_creation(self):
        """Test risk event recording."""
        device = DeviceRegistration.objects.create(
            device_id='risky_device',
            user=self.user,
            device_fingerprint={},
            user_agent='Mozilla/5.0',
            ip_address='1.2.3.4',
            trust_score=10
        )

        risk_event = DeviceRiskEvent.objects.create(
            device=device,
            event_type='SPOOFING_DETECTED',
            risk_score=80,
            event_data={'details': 'Suspicious audio patterns'},
            ip_address='1.2.3.4'
        )

        assert risk_event.event_type == 'SPOOFING_DETECTED'
        assert risk_event.risk_score == 80
        assert not risk_event.resolved


@pytest.mark.django_db
class TestLocationSecurity(TestCase):
    """Test Location Security service and models."""

    def setUp(self):
        """Set up test data."""
        self.user = People.objects.create(
            peoplecode='TEST002',
            peoplename='Location Test User',
            loginid='loctest',
            mobno='+919876543211',
            email='loctest@example.com',
            is_active=True,
            enable=True
        )

        self.tenant = None  # Would create tenant in full setup

        self.location_service = LocationSecurityService()

        # Create approved location
        self.approved_location = ApprovedLocation.objects.create(
            location_name='Mumbai Corporate Office',
            location_type='CORPORATE_OFFICE',
            address='123 Tech Park, Mumbai',
            city='Mumbai',
            country='India',
            ip_ranges=['192.168.1.0/24'],
            trust_level='HIGH',
            latitude=19.0760,
            longitude=72.8777,
            radius_meters=500,
            is_active=True,
            approved_by=self.user
        )

    def test_approved_location_creation(self):
        """Test approved location model creation."""
        assert self.approved_location.location_name == 'Mumbai Corporate Office'
        assert self.approved_location.trust_level == 'HIGH'
        assert self.approved_location.is_active

    def test_ip_range_validation(self):
        """Test IP range matching."""
        # IP within range
        assert self.approved_location.is_ip_approved('192.168.1.100')

        # IP outside range
        assert not self.approved_location.is_ip_approved('10.0.0.1')

    def test_geofence_validation(self):
        """Test geofence radius validation."""
        # Coordinates within 500m of office
        assert self.approved_location.is_within_geofence(19.0765, 72.8780)

        # Coordinates far away (>500m)
        assert not self.approved_location.is_within_geofence(19.1000, 72.9000)

    def test_location_security_approved_location(self):
        """Test location validation for approved location."""
        result = self.location_service.validate_location(
            user=self.user,
            ip_address='192.168.1.100',
            latitude=19.0765,
            longitude=72.8780
        )

        assert result['passed']
        assert result['location_secure']
        assert result['trust_level'] == 'HIGH'

    def test_location_security_unapproved_location(self):
        """Test location validation for unapproved location."""
        result = self.location_service.validate_location(
            user=self.user,
            ip_address='1.2.3.4',  # Unknown IP
            latitude=20.0000,
            longitude=73.0000
        )

        assert not result['passed']

    def test_location_security_corporate_network_fallback(self):
        """Test corporate network fallback when no approved location."""
        result = self.location_service.validate_location(
            user=self.user,
            ip_address='10.0.0.50'  # Corporate IP
        )

        # Should pass on corporate network even without approved location
        assert result['passed']
        assert result['location_type'] == 'CORPORATE_NETWORK'


@pytest.mark.django_db
class TestVoiceEnrollmentIntegration(TestCase):
    """Test complete voice enrollment flow with security checks."""

    def setUp(self):
        """Set up test data for enrollment."""
        self.user = People.objects.create(
            peoplecode='ENROLL001',
            peoplename='Enrollment Test User',
            loginid='enrolltest',
            mobno='+919876543212',
            email='enroll@example.com',
            is_active=True,
            enable=True,
            isverified=True
        )

        # Create face embedding (prerequisite)
        from apps.face_recognition.models import FaceEmbedding, ExtractionModel
        model, _ = ExtractionModel.objects.get_or_create(
            model_name='facenet',
            defaults={'model_version': '1.0'}
        )

        FaceEmbedding.objects.create(
            user=self.user,
            embedding_vector=[0.1] * 128,
            extraction_model=model,
            is_validated=True
        )

        self.enrollment_service = VoiceEnrollmentService()

        # Set enrollment context on user (simulates request context)
        self.user._enrollment_context = {
            'user_agent': 'Mozilla/5.0 Chrome/120.0',
            'ip_address': '192.168.1.100',
            'site_id': None,
            'fingerprint_data': {'canvas': 'test123'}
        }

    def test_enrollment_eligibility_with_security_checks(self):
        """Test full enrollment eligibility with all security checks."""
        result = self.enrollment_service.validate_enrollment_eligibility(self.user)

        # Should have all checks
        assert 'face_enrolled' in result['checks']
        assert 'voice_status' in result['checks']
        assert 'account_status' in result['checks']
        assert 'device_trust' in result['checks']
        assert 'location_security' in result['checks']

    def test_enrollment_eligibility_device_not_trusted(self):
        """Test enrollment rejection when device not trusted."""
        # Set risky IP
        self.user._enrollment_context['ip_address'] = '1.2.3.4'

        with pytest.raises(Exception):  # EnrollmentEligibilityError
            self.enrollment_service.validate_enrollment_eligibility(self.user)

    def test_enrollment_eligibility_location_not_secure(self):
        """Test enrollment rejection when location not secure."""
        # Set context without corporate network or approved location
        self.user._enrollment_context['ip_address'] = '203.0.113.0'  # Public IP

        with pytest.raises(Exception):  # EnrollmentEligibilityError
            self.enrollment_service.validate_enrollment_eligibility(self.user)


# Performance benchmarks
@pytest.mark.benchmark
@pytest.mark.django_db
class TestPerformance(TestCase):
    """Performance benchmarks for Sprint 1 features."""

    def test_device_trust_check_performance(self):
        """Verify device trust check completes within 50ms."""
        import time

        user = People.objects.create(
            peoplecode='PERF001',
            peoplename='Perf User',
            loginid='perfuser',
            mobno='+919876543213',
            email='perf@example.com'
        )

        service = DeviceTrustService()

        start = time.time()
        result = service.validate_device(
            user=user,
            user_agent='Mozilla/5.0',
            ip_address='10.0.0.1',
            fingerprint_data={'canvas': 'abc'}
        )
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 50, f"Device trust check took {duration_ms}ms (threshold: 50ms)"
        assert result is not None

    def test_location_security_check_performance(self):
        """Verify location security check completes within 50ms."""
        import time

        user = People.objects.create(
            peoplecode='PERF002',
            peoplename='Perf User 2',
            loginid='perfuser2',
            mobno='+919876543214',
            email='perf2@example.com'
        )

        service = LocationSecurityService()

        start = time.time()
        result = service.validate_location(
            user=user,
            ip_address='10.0.0.1'
        )
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 50, f"Location check took {duration_ms}ms (threshold: 50ms)"
        assert result is not None
